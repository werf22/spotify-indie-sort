#!/usr/bin/env python3
"""Rank the whole library against one track, by how it actually SOUNDS.

WHAT IT USES: the three audio embeddings the GPU pass produced for ~42,900
tracks — numeric fingerprints of the audio, not tag strings:

    laion/larger_clap_music   512   mood, texture, "vibe"
    mtg-upf/discogs-maest     400   genre and style
    essentia/discogs-effnet  1280   general musical representation

WHY ALL THREE: each model is confidently wrong in its own way — CLAP hears mood
but confuses genres, MAEST knows genre but ignores energy. A track ranking high
on all three is similar in every sense we can measure.

THE ONE SUBTLETY: each model's cosine scores are turned into z-scores ACROSS THE
LIBRARY before averaging. Raw cosines are not comparable between models — one may
spread every track over 0.85-0.99 and another over 0.1-0.6, and a plain average
would silently let the narrow model decide the ranking.

MEMORY: vectors stay float16 (~190 MB for the lot) and the similarity is done in
float32 in chunks, so peak memory stays small instead of materialising a 376 MB
float32 copy of the library.

HOW TO TWEAK: WEIGHTS is the whole opinion — raise `tags` to favour tracks
labelled alike, `audio` to favour tracks that sound alike.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

# EXACT identifiers — matched literally in SQL. An abbreviated one matches
# nothing and every model is silently "skipped", yielding zero results.
MODELS = {
    "laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate": 512,
    "mtg-upf/discogs-maest-10s-dw-75e@d298f3a38365aa566b6a4417560423061ed82380/aggregate-probabilities": 400,
    "essentia/discogs-effnet-bs64-1+19-supervised-heads/aggregate-embedding": 1280,
}
WEIGHTS = {"audio": 1.0, "tags": 0.35, "musical": 0.25}
CHUNK = 8192

_lock = threading.Lock()
_cache: dict = {}


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    db.row_factory = sqlite3.Row
    return db


def _decode(blob: bytes, dim: int):
    try:
        vec = np.frombuffer(zlib.decompress(blob), dtype=np.float16)
    except Exception:
        return None
    return vec if vec.size == dim else None


def status() -> dict:
    return {"ready": bool(_cache.get("ready")),
            "loading": bool(_cache.get("loading")),
            "tracks": _cache.get("track_count", 0),
            "error": _cache.get("error")}


def warm() -> None:
    """Load every embedding once. Safe to call from many threads."""
    with _lock:
        if _cache.get("ready") or _cache.get("loading"):
            return
        _cache["loading"] = True
    try:
        db = connect()
        models = {}
        for model, dim in MODELS.items():
            ids, rows = [], []
            for sid, blob in db.execute(
                    """SELECT spotify_id, vector FROM audio_embeddings
                       WHERE model=? AND (segment_start IS NULL OR segment_start=0.0)""",
                    (model,)):
                vec = _decode(blob, dim)
                if vec is None:
                    continue
                ids.append(sid)
                rows.append(vec)
            if not rows:
                continue
            matrix = np.vstack(rows)
            norms = np.linalg.norm(matrix.astype(np.float32), axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            models[model] = {"ids": ids, "index": {s: i for i, s in enumerate(ids)},
                             "matrix": (matrix / norms).astype(np.float16)}
        tags: dict[str, set] = {}
        for sid, ttype, tag in db.execute(
                "SELECT spotify_id, tag_type, tag FROM tags WHERE tag IS NOT NULL"):
            tags.setdefault(sid, set()).add(f"{ttype}:{tag}".lower())
        mus: dict[str, dict] = {}
        for sid, blob in db.execute(
                "SELECT spotify_id, payload_blob FROM audio_analysis_artifacts WHERE stage='rhythm_full'"):
            try:
                p = json.loads(zlib.decompress(blob))
            except Exception:
                continue
            mus[sid] = {"bpm": p.get("bpm"), "rhythm": p.get("rhythm_pattern")}
        for sid, key in db.execute(
                "SELECT spotify_id, key FROM audio_features WHERE source='freqblog' AND key IS NOT NULL"):
            mus.setdefault(sid, {})["key"] = key
        db.close()
        _cache.update(models=models, tags=tags, musical=mus, ready=True, loading=False,
                      track_count=max((len(m["ids"]) for m in models.values()), default=0))
    except Exception as exc:                    # never fail silently behind a spinner
        _cache.update(loading=False, ready=False, error=f"{type(exc).__name__}: {exc}")


def _cosines(model: dict, ref: str):
    """Cosine of every track against the reference, computed in float32 chunks."""
    matrix, i = model["matrix"], model["index"][ref]
    query = matrix[i].astype(np.float32)
    out = np.empty(matrix.shape[0], dtype=np.float32)
    for start in range(0, matrix.shape[0], CHUNK):
        block = matrix[start:start + CHUNK].astype(np.float32)
        out[start:start + CHUNK] = block @ query
    return out


def song_key(title: str, artist: str) -> str:
    """Identity of a SONG, ignoring which mix it is.

    The library holds the radio edit, extended mix and remix as separate tracks
    and they cluster together in any ranking — "Samsara" alone took three of the
    top fifty slots. Collapsing them keeps a playlist varied.
    """
    base = (title or "").lower()
    for cut in (" - ", " (", " ["):
        if cut in base:
            base = base.split(cut)[0]
    return f"{base.strip()}|{(artist or '').split(',')[0].strip().lower()}"


def similar(ref: str, limit: int = 100, spotify_only: bool = True,
            bpm_window: float = 0.0, same_key: bool = False,
            dedupe: bool = True) -> list[dict]:
    if not _cache.get("ready"):
        warm()
    if _cache.get("error"):
        raise RuntimeError(_cache["error"])
    scores: dict[str, list] = {}
    used = 0
    for model in _cache["models"].values():
        if ref not in model["index"]:
            continue
        cos = _cosines(model, ref)
        z = (cos - cos.mean()) / (cos.std() or 1.0)
        for sid, value in zip(model["ids"], z):
            scores.setdefault(sid, []).append(float(value))
        used += 1
    if not used:
        raise RuntimeError("this track has no audio analysis yet, so nothing can be compared")

    tags, mus = _cache["tags"], _cache["musical"]
    ref_tags, ref_mus = tags.get(ref, set()), mus.get(ref, {})
    rows = []
    for sid, zs in scores.items():
        if sid == ref or len(zs) < 2:
            continue
        # A length check is NOT enough: a local id looks like
        # "local_c1e89649e0ddf452" — exactly 22 characters, same as a real one.
        if spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        audio = sum(zs) / len(zs)
        t = tags.get(sid, set())
        jac = len(ref_tags & t) / len(ref_tags | t) if (ref_tags and t) else 0.0
        m = mus.get(sid, {})
        bpm_pen = bonus = 0.0
        if ref_mus.get("bpm") and m.get("bpm"):
            diff = abs(float(m["bpm"]) - float(ref_mus["bpm"])) / float(ref_mus["bpm"])
            if bpm_window and diff * 100 > bpm_window:
                continue
            bpm_pen = -min(diff * 4, 1.0)
        if ref_mus.get("key") and m.get("key"):
            match = str(m["key"]).strip().lower() == str(ref_mus["key"]).strip().lower()
            if same_key and not match:
                continue
            bonus = 0.5 if match else 0.0
        if ref_mus.get("rhythm") and m.get("rhythm") == ref_mus.get("rhythm"):
            bonus += 0.3
        rows.append({"spotify_id": sid,
                     "score": WEIGHTS["audio"] * audio + WEIGHTS["tags"] * jac * 4
                              + WEIGHTS["musical"] * (bpm_pen + bonus),
                     "audio_z": audio, "tag_overlap": jac,
                     "bpm": m.get("bpm"), "key": m.get("key")})
    rows.sort(key=lambda r: -r["score"])

    db = connect()
    out, seen = [], set()
    for row in rows:
        info = db.execute("""SELECT t.title, t.artist_names,
                                    (SELECT path FROM audio_files f
                                     WHERE f.spotify_id=t.spotify_id AND f.path IS NOT NULL
                                     LIMIT 1) path
                             FROM tracks t WHERE t.spotify_id=?""", (row["spotify_id"],)).fetchone()
        title = info["title"] if info else ""
        artist = info["artist_names"] if info else ""
        if dedupe:
            key = song_key(title, artist)
            if key in seen:
                continue
            seen.add(key)
        row.update(title=title, artist=artist, has_file=bool(info and info["path"]),
                   score=round(row["score"], 3), audio_z=round(row["audio_z"], 2),
                   tag_overlap=round(row["tag_overlap"], 3),
                   bpm=round(float(row["bpm"]), 1) if row["bpm"] else None)
        out.append(row)
        if len(out) >= limit:
            break
    db.close()
    return out


def search(query: str, limit: int = 25) -> list[dict]:
    """Find candidate reference tracks; only ones we can actually compare."""
    if not query.strip():
        return []
    db = connect()
    words = query.split()
    sql = ("SELECT spotify_id, title, artist_names FROM tracks WHERE "
           + " AND ".join(["(title LIKE ? OR artist_names LIKE ?)"] * len(words))
           + " LIMIT 400")
    params = [x for w in words for x in (f"%{w}%", f"%{w}%")]
    rows = db.execute(sql, params).fetchall()
    db.close()
    have = _cache.get("models") or {}
    analysed = set()
    for model in have.values():
        analysed |= model["index"].keys()
    out = [{"spotify_id": r["spotify_id"], "title": r["title"],
            "artist": r["artist_names"],
            "analysed": (r["spotify_id"] in analysed) if analysed else None}
           for r in rows]
    out.sort(key=lambda r: (not r["analysed"], len(r["title"] or "")))
    return out[:limit]

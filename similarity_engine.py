#!/usr/bin/env python3
"""Rank the library against one track using EVERYTHING we know about it.

Six independent opinions, each answering "how close is this?" in its own way:

  audio     3 embedding models — how the track actually sounds        weight 1.00
  tags      weighted overlap of genre/mood/instrument/voice/…          0.60
  rhythm    12 drum-behaviour numbers (four-on-floor, syncopation…)    0.50
  features  energy, danceability, valence, acousticness, …            0.40
  key       harmonic compatibility, not just an exact match            0.30
  bpm       tempo distance                                            0.30

WHY EACH IS Z-SCORED BEFORE ADDING: the six live on different scales — a cosine
sits near 0.9, a tag overlap near 0.05, a bpm penalty is negative. Adding them
raw would let whichever happens to have the widest spread decide the ranking.
Standardising each across the candidates first means the WEIGHTS above are the
only thing that decides importance, which is the point of having them.

MISSING DATA NEVER PUNISHES: a track with no rhythm analysis scores exactly
average on that component, so it competes on the signals it does have instead of
being pushed to the bottom for a gap in our data.

HOW TO TWEAK: WEIGHTS is the whole opinion. Want "same genre" to dominate? Raise
`tags`. Want "sounds the same" regardless of labels? Raise `audio`.
"""
from __future__ import annotations

import sqlite3
import threading

import numpy as np

import similarity_features as feat

WEIGHTS = {"audio": 1.0, "tags": 0.6, "rhythm": 0.5,
           "features": 0.4, "key": 0.3, "bpm": 0.3}
CHUNK = 8192

# Camelot wheel: tracks a DJ can actually mix. Same key, one step around the
# wheel, or the relative major/minor all work; anything else clashes.
_NOTE = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5,
         "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}
_MINOR_TO_CAMELOT = {9: 1, 4: 2, 11: 3, 6: 4, 1: 5, 8: 6, 3: 7, 10: 8, 5: 9, 0: 10, 7: 11, 2: 12}
_MAJOR_TO_CAMELOT = {0: 1, 7: 2, 2: 3, 9: 4, 4: 5, 11: 6, 6: 7, 1: 8, 8: 9, 3: 10, 10: 11, 5: 12}

_lock = threading.Lock()
_state: dict = {"lib": None, "ready": False, "loading": False, "error": None}


def camelot(value) -> tuple[int, str] | None:
    """'E-Minor' -> (9, 'm'). Returns None for anything unparseable."""
    if not value:
        return None
    text = str(value).strip().lower().replace(" ", "-")
    mode = "m" if "min" in text else ("d" if "maj" in text else None)
    if mode is None:
        return None
    note = _NOTE.get(text.split("-")[0].strip())
    if note is None:
        return None
    table = _MINOR_TO_CAMELOT if mode == "m" else _MAJOR_TO_CAMELOT
    return table[note], mode


def key_score(a, b) -> float:
    """1.0 same key · 0.6 mixable · 0.0 clashes."""
    ka, kb = camelot(a), camelot(b)
    if not ka or not kb:
        return np.nan
    if ka == kb:
        return 1.0
    if ka[1] == kb[1] and min(abs(ka[0] - kb[0]), 12 - abs(ka[0] - kb[0])) == 1:
        return 0.6                       # neighbour on the wheel
    if ka[0] == kb[0] and ka[1] != kb[1]:
        return 0.6                       # relative major/minor
    return 0.0


def status() -> dict:
    lib = _state["lib"]
    return {"ready": _state["ready"], "loading": _state["loading"],
            "error": _state["error"], "tracks": len(lib.ids) if lib else 0}


def warm() -> None:
    with _lock:
        if _state["ready"] or _state["loading"]:
            return
        _state["loading"] = True
    try:
        lib = feat.Library()
        lib.load()
        _state.update(lib=lib, ready=True, loading=False, error=None)
    except Exception as exc:              # never hide a failure behind a spinner
        _state.update(loading=False, ready=False, error=f"{type(exc).__name__}: {exc}")


def _z(values: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Standardise, ignoring rows we have no data for (they become 0 = average)."""
    out = np.zeros_like(values, dtype=np.float32)
    use = np.isfinite(values) if mask is None else (mask & np.isfinite(values))
    if use.sum() < 2:
        return out
    mean, std = values[use].mean(), values[use].std() or 1.0
    out[use] = (values[use] - mean) / std
    return out


def _audio_component(lib, ref: str, n: int):
    total = np.zeros(n, dtype=np.float32)
    count = np.zeros(n, dtype=np.float32)
    used = 0
    for model in lib.models.values():
        i = model["index"].get(ref)
        if i is None:
            continue
        matrix, rows = model["matrix"], model["rows"]
        query = matrix[i].astype(np.float32)
        cos = np.empty(matrix.shape[0], dtype=np.float32)
        for start in range(0, matrix.shape[0], CHUNK):
            cos[start:start + CHUNK] = matrix[start:start + CHUNK].astype(np.float32) @ query
        z = (cos - cos.mean()) / (cos.std() or 1.0)
        total[rows] += z
        count[rows] += 1
        used += 1
    if not used:
        return None, None
    seen = count > 0
    out = np.zeros(n, dtype=np.float32)
    out[seen] = total[seen] / count[seen]
    return out, seen


def _tag_component(lib, ref: str, n: int):
    """Weighted Jaccard against the reference, via the inverted index."""
    ref_tags = lib.tag_types.get(ref)
    if not ref_tags:
        return np.zeros(n, dtype=np.float32), np.zeros(n, dtype=bool)
    shared = np.zeros(n, dtype=np.float32)
    for tag in ref_tags:
        entry = lib.tag_index.get(tag)
        if entry is not None:
            shared[entry[0]] += entry[1]
    ref_sum = lib.tag_sum[lib.pos[ref]]
    union = ref_sum + lib.tag_sum - shared
    union[union <= 0] = 1.0
    return (shared / union).astype(np.float32), lib.tag_sum > 0


def _distance_component(matrix, present, row: int, n: int):
    """Negative euclidean distance — closer means bigger."""
    diff = matrix - matrix[row]
    dist = np.sqrt((diff * diff).sum(axis=1))
    return (-dist).astype(np.float32), present.copy()


def similar(ref: str, limit: int = 100, spotify_only: bool = True,
            bpm_window: float = 0.0, same_key: bool = False,
            dedupe: bool = True, weights: dict | None = None) -> list[dict]:
    if not _state["ready"]:
        warm()
    if _state["error"]:
        raise RuntimeError(_state["error"])
    lib = _state["lib"]
    if ref not in lib.pos:
        raise RuntimeError("this track has no audio analysis yet, so nothing can be compared")
    w = {**WEIGHTS, **(weights or {})}
    row, n = lib.pos[ref], len(lib.ids)

    audio, audio_seen = _audio_component(lib, ref, n)
    if audio is None:
        raise RuntimeError("this track has no embeddings yet")
    tags, tags_seen = _tag_component(lib, ref, n)
    rhythm, rhythm_seen = _distance_component(lib.rhythm, lib.has_rhythm, row, n)
    feats, feats_seen = _distance_component(lib.features, lib.has_features, row, n)

    ref_bpm = lib.bpm[row]
    bpm_rel = np.full(n, np.nan, dtype=np.float32)
    if np.isfinite(ref_bpm) and ref_bpm > 0:
        bpm_rel = np.abs(lib.bpm - ref_bpm) / ref_bpm
    keys = np.array([key_score(lib.key[row], k) for k in lib.key], dtype=np.float32)

    score = (w["audio"] * _z(audio, audio_seen)
             + w["tags"] * _z(tags, tags_seen)
             + w["rhythm"] * _z(rhythm, rhythm_seen & lib.has_rhythm[row].reshape(()))
             + w["features"] * _z(feats, feats_seen & lib.has_features[row].reshape(()))
             + w["key"] * _z(keys)
             + w["bpm"] * _z(-np.nan_to_num(bpm_rel, nan=np.nan)))

    order = np.argsort(-score)
    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    out, seen_songs = [], set()
    for idx in order:
        sid = lib.ids[idx]
        if sid == ref or not audio_seen[idx]:
            continue
        # A length check is NOT enough: a local id looks like
        # "local_c1e89649e0ddf452" — exactly 22 characters, same as a real one.
        if spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        if bpm_window and np.isfinite(bpm_rel[idx]) and bpm_rel[idx] * 100 > bpm_window:
            continue
        if same_key and not (keys[idx] >= 1.0):
            continue
        info = db.execute("""SELECT t.title, t.artist_names,
                                    (SELECT path FROM audio_files f WHERE f.spotify_id=t.spotify_id
                                     AND f.path IS NOT NULL LIMIT 1) path
                             FROM tracks t WHERE t.spotify_id=?""", (sid,)).fetchone()
        title = info["title"] if info else ""
        artist = info["artist_names"] if info else ""
        if dedupe:
            key = song_key(title, artist)
            if key in seen_songs:
                continue
            seen_songs.add(key)
        out.append({
            "spotify_id": sid, "title": title, "artist": artist,
            "has_file": bool(info and info["path"]),
            "score": round(float(score[idx]), 3),
            "bpm": round(float(lib.bpm[idx]), 1) if np.isfinite(lib.bpm[idx]) else None,
            "key": lib.key[idx],
            "why": {"audio": round(float(audio[idx]), 2),
                    "tags": round(float(tags[idx]), 3),
                    "rhythm": round(float(rhythm[idx]), 2),
                    "features": round(float(feats[idx]), 2),
                    "key": None if not np.isfinite(keys[idx]) else round(float(keys[idx]), 2),
                    "bpm_diff": None if not np.isfinite(bpm_rel[idx]) else round(float(bpm_rel[idx] * 100), 1)},
        })
        if len(out) >= limit:
            break
    db.close()
    return out


def song_key(title: str, artist: str) -> str:
    """Identity of a SONG, ignoring which mix it is — the radio edit, extended
    mix and remix cluster together and would eat a playlist's variety."""
    base = (title or "").lower()
    for cut in (" - ", " (", " ["):
        if cut in base:
            base = base.split(cut)[0]
    return f"{base.strip()}|{(artist or '').split(',')[0].strip().lower()}"


def search(query: str, limit: int = 25) -> list[dict]:
    if not query.strip():
        return []
    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    words = query.split()
    sql = ("SELECT spotify_id, title, artist_names FROM tracks WHERE "
           + " AND ".join(["(title LIKE ? OR artist_names LIKE ?)"] * len(words)) + " LIMIT 400")
    rows = db.execute(sql, [x for word in words for x in (f"%{word}%", f"%{word}%")]).fetchall()
    db.close()
    lib = _state["lib"]
    out = [{"spotify_id": r["spotify_id"], "title": r["title"], "artist": r["artist_names"],
            "analysed": (r["spotify_id"] in lib.pos) if lib else None} for r in rows]
    out.sort(key=lambda r: (not r["analysed"], len(r["title"] or "")))
    return out[:limit]

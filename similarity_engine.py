#!/usr/bin/env python3
"""Rank the library against one track, using whichever signals you switch on.

EVERY comparable thing in the database is a separate, tickable signal:

  audio      3 embedding models — how the track actually sounds
  tags       all 40 tag types, each compared on its own (genre apart from mood,
             apart from label, apart from instrument …)
  numbers    every musical number — energy, valence, syncopation, loudness,
             tempo stability … — scored by how CLOSE the value is
  musical    bpm distance and Camelot key compatibility

TWO RULES MAKE THE MIX FAIR

1. Each signal is standardised across the candidates before it is weighted. The
   signals live on different scales — a cosine sits near 0.9, a tag overlap near
   0.05, a bpm penalty is negative. Added raw, whichever had the widest spread
   would quietly decide everything and the weights would be decoration.

2. A GROUP's weight is shared among the signals ticked inside it. Ticking all 40
   tag types therefore does not drown the audio; it just makes the tag opinion
   better informed. Without this, "use everything" would always mean "tags win".

MISSING DATA NEVER PUNISHES: a track we lack a number for scores exactly average
on that signal rather than sinking to the bottom for a gap in our data.

HOW TO TWEAK: GROUP_WEIGHTS is the balance between the four families; the app
sends its own per-search, so this is only the default.
"""
from __future__ import annotations

import sqlite3
import threading

import numpy as np

import similarity_features as feat

GROUP_WEIGHTS = {"audio": 1.0, "tags": 0.8, "numbers": 0.6, "musical": 0.6}
CHUNK = 8192

_NOTE = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5,
         "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}
_MIN = {9: 1, 4: 2, 11: 3, 6: 4, 1: 5, 8: 6, 3: 7, 10: 8, 5: 9, 0: 10, 7: 11, 2: 12}
_MAJ = {0: 1, 7: 2, 2: 3, 9: 4, 4: 5, 11: 6, 6: 7, 1: 8, 8: 9, 3: 10, 10: 11, 5: 12}

_lock = threading.Lock()
_state: dict = {"lib": None, "ready": False, "loading": False, "error": None}


def camelot(value):
    if not value:
        return None
    text = str(value).strip().lower().replace(" ", "-")
    mode = "m" if "min" in text else ("d" if "maj" in text else None)
    note = _NOTE.get(text.split("-")[0].strip())
    if mode is None or note is None:
        return None
    return (_MIN if mode == "m" else _MAJ)[note], mode


def key_score(a, b) -> float:
    """1.0 same key · 0.6 mixable (wheel neighbour or relative) · 0.0 clashes."""
    ka, kb = camelot(a), camelot(b)
    if not ka or not kb:
        return np.nan
    if ka == kb:
        return 1.0
    if ka[1] == kb[1] and min(abs(ka[0] - kb[0]), 12 - abs(ka[0] - kb[0])) == 1:
        return 0.6
    if ka[0] == kb[0] and ka[1] != kb[1]:
        return 0.6
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
    except Exception as exc:
        _state.update(loading=False, ready=False, error=f"{type(exc).__name__}: {exc}")


def signals() -> list[dict]:
    """Everything that CAN be compared — the checkbox list the app draws."""
    if not _state["ready"]:
        warm()
    lib = _state["lib"]
    out: list[dict] = []
    for model, (_, label, note) in feat.MODELS.items():
        if model in lib.models:
            out.append({"id": f"emb:{model}", "group": "audio", "label": label,
                        "note": note, "coverage": len(lib.models[model]["index"]),
                        "default": True})
    for ttype, index in sorted(lib.tag_index.items()):
        out.append({"id": f"tag:{ttype}", "group": "tags", "label": ttype,
                    "note": f"{len(index):,} rôznych hodnôt",
                    "coverage": int((lib.tag_sum[ttype] > 0).sum()),
                    "default": ttype in feat.TAG_DEFAULT_ON})
    for name in sorted(lib.numbers):
        out.append({"id": f"num:{name}", "group": "numbers", "label": name,
                    "note": "najbližšia hodnota",
                    "coverage": int(lib.number_present[name].sum()),
                    "default": name in feat.NUMBER_DEFAULT_ON})
    out.append({"id": "bpm", "group": "musical", "label": "BPM",
                "note": "vzdialenosť tempa",
                "coverage": int(np.isfinite(lib.bpm).sum()), "default": True})
    out.append({"id": "key", "group": "musical", "label": "Tónina",
                "note": "Camelot — rovnaká 1.0, mixovateľná 0.6",
                "coverage": int(sum(1 for k in lib.key if k)), "default": True})
    return out


def _z(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values, dtype=np.float32)
    use = mask & np.isfinite(values)
    if use.sum() < 2:
        return out
    mean, std = values[use].mean(), values[use].std() or 1.0
    out[use] = (values[use] - mean) / std
    return out


def _signal_vector(lib, sid: str, ref: str, row: int, n: int):
    """One signal's raw opinion, plus the mask of tracks it can speak about."""
    if sid.startswith("emb:"):
        model = lib.models.get(sid[4:])
        if not model or ref not in model["index"]:
            return None
        matrix, rows = model["matrix"], model["rows"]
        query = matrix[model["index"][ref]].astype(np.float32)
        cos = np.empty(matrix.shape[0], dtype=np.float32)
        for start in range(0, matrix.shape[0], CHUNK):
            cos[start:start + CHUNK] = matrix[start:start + CHUNK].astype(np.float32) @ query
        values = np.full(n, np.nan, dtype=np.float32)
        values[rows] = cos
        mask = np.zeros(n, dtype=bool)
        mask[rows] = True
        return values, mask

    if sid.startswith("tag:"):
        ttype = sid[4:]
        index, sums = lib.tag_index.get(ttype), lib.tag_sum.get(ttype)
        if index is None:
            return None
        mine = lib.tag_of.get(ttype, {}).get(ref)
        if not mine:
            return None                       # reference has no tag of this kind
        shared = np.zeros(n, dtype=np.float32)
        for tag in mine:
            entry = index.get(tag)
            if entry is not None:
                shared[entry[0]] += entry[1]
        union = sums[row] + sums - shared
        union[union <= 0] = 1.0
        return (shared / union).astype(np.float32), sums > 0

    if sid.startswith("num:"):
        name = sid[4:]
        values, present = lib.numbers.get(name), lib.number_present.get(name)
        if values is None or not present[row]:
            return None
        return -np.abs(values - values[row]), present.copy()

    if sid == "bpm":
        ref_bpm = lib.bpm[row]
        if not np.isfinite(ref_bpm) or ref_bpm <= 0:
            return None
        return -np.abs(lib.bpm - ref_bpm) / ref_bpm, np.isfinite(lib.bpm)

    if sid == "key":
        if not lib.key[row]:
            return None
        values = np.array([key_score(lib.key[row], k) for k in lib.key], dtype=np.float32)
        return values, np.isfinite(values)
    return None


def similar(ref: str, limit: int = 100, spotify_only: bool = True,
            bpm_window: float = 0.0, same_key: bool = False, dedupe: bool = True,
            enabled: list[str] | None = None,
            group_weights: dict | None = None) -> dict:
    if not _state["ready"]:
        warm()
    if _state["error"]:
        raise RuntimeError(_state["error"])
    lib = _state["lib"]
    if ref not in lib.pos:
        raise RuntimeError("tento track ešte nemá audio analýzu, nedá sa porovnať")
    row, n = lib.pos[ref], len(lib.ids)
    if enabled is None:
        enabled = [s["id"] for s in signals() if s["default"]]
    weights = {**GROUP_WEIGHTS, **(group_weights or {})}
    catalogue = signals()
    group_of = {s["id"]: s["group"] for s in catalogue}
    labels = {s["id"]: s["label"] for s in catalogue}

    # Collect each signal, then split its GROUP's weight between the ones that
    # actually produced an opinion — so ticking 40 tag types cannot drown audio.
    collected: dict[str, list] = {}
    for sid in enabled:
        result = _signal_vector(lib, sid, ref, row, n)
        if result is not None:
            collected.setdefault(group_of.get(sid, "other"), []).append((sid, result))

    score = np.zeros(n, dtype=np.float32)
    used: dict[str, int] = {}
    contributions: dict[str, np.ndarray] = {}
    for group, items in collected.items():
        share = weights.get(group, 0.5) / len(items)
        used[group] = len(items)
        for sid, (values, mask) in items:
            z = _z(values, mask)
            score += share * z
            contributions[sid] = z

    keys = np.array([key_score(lib.key[row], k) for k in lib.key], dtype=np.float32)
    ref_bpm = lib.bpm[row]
    bpm_rel = (np.abs(lib.bpm - ref_bpm) / ref_bpm) if np.isfinite(ref_bpm) and ref_bpm > 0 \
        else np.full(n, np.nan, dtype=np.float32)

    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    out, seen = [], set()
    for idx in np.argsort(-score):
        sid = lib.ids[idx]
        if sid == ref:
            continue
        # A length check is NOT enough: a local id looks like
        # "local_c1e89649e0ddf452" — exactly 22 characters, same as a real one.
        if spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        if bpm_window and np.isfinite(bpm_rel[idx]) and bpm_rel[idx] * 100 > bpm_window:
            continue
        if same_key and not keys[idx] >= 1.0:
            continue
        info = db.execute("""SELECT t.title, t.artist_names,
                                (SELECT path FROM audio_files f WHERE f.spotify_id=t.spotify_id
                                 AND f.path IS NOT NULL LIMIT 1) path
                             FROM tracks t WHERE t.spotify_id=?""", (sid,)).fetchone()
        title, artist = (info["title"] if info else ""), (info["artist_names"] if info else "")
        if dedupe:
            song = song_key(title, artist)
            if song in seen:
                continue
            seen.add(song)
        # Short names: a signal id like
        # "emb:laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate"
        # is unreadable in a table, and splitting on ":" alone leaves the path.
        top = sorted(((labels.get(s, s), float(v[idx])) for s, v in contributions.items()),
                     key=lambda kv: -kv[1])[:4]
        out.append({"spotify_id": sid, "title": title, "artist": artist,
                    "has_file": bool(info and info["path"]),
                    "score": round(float(score[idx]), 3),
                    "bpm": round(float(lib.bpm[idx]), 1) if np.isfinite(lib.bpm[idx]) else None,
                    "key": lib.key[idx],
                    "bpm_diff": None if not np.isfinite(bpm_rel[idx]) else round(float(bpm_rel[idx] * 100), 1),
                    "key_match": None if not np.isfinite(keys[idx]) else float(keys[idx]),
                    "why": [name for name, v in top if v > 0.5]})
        if len(out) >= limit:
            break
    db.close()
    return {"results": out, "signals_used": used}


def song_key(title: str, artist: str) -> str:
    """Identity of a SONG, ignoring which mix it is — radio edit, extended and
    remix cluster together and would eat a playlist's variety."""
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
    rows = db.execute(sql, [x for w in words for x in (f"%{w}%", f"%{w}%")]).fetchall()
    db.close()
    lib = _state["lib"]
    out = [{"spotify_id": r["spotify_id"], "title": r["title"], "artist": r["artist_names"],
            "analysed": (r["spotify_id"] in lib.pos) if lib else None} for r in rows]
    out.sort(key=lambda r: (not r["analysed"], len(r["title"] or "")))
    return out[:limit]

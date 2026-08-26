#!/usr/bin/env python3
"""Build and score the pool of records a themed set can be made from.

INPUT:  the library database.
OUTPUT: one row per playable track — path, artist, title, length, key, BPM and a
        score for each feeling defined in `ecstatic_signals.py`.

ONLY PLAYABLE RECORDS GET IN. A set you cannot play is not a set, so a track
must have a file that exists on disk, a detected key (there is no harmonic set
without one) and a BPM. Everything else is dropped here, loudly counted, so the
numbers later cannot silently be about tracks that do not exist.

HOW TO TWEAK: BPM_RANGE is the widest tempo considered danceable for this kind
of night; MIN_SECONDS drops interludes and skits.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from ecstatic_signals import (ARTIST_LEVEL_DAMPING, ARTIST_LEVEL_SOURCES, FLAVOUR_TITLE_WORDS,
                              ORIENT_ARTISTS, ORIENT_TITLE_WORDS, SIGNALS)

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

# Anything outside this is not what this night is: too slow to move to, or too
# fast for an ecstatic-dance floor. Widen it for a harder party.
BPM_RANGE = (95.0, 132.0)
MIN_SECONDS = 150          # below this it is an intro, not a record
MAX_SECONDS = 900


def _squash(total: float, half: float) -> float:
    """Sum of evidence -> 0..1, where `half` worth of evidence scores 0.5.

    WHY NOT A PLAIN SUM: one very confident tag would otherwise beat three
    independent ones, and three independent markers are much better evidence
    than one. This keeps adding markers useful but never explosive.
    """
    return total / (total + half) if total > 0 else 0.0


def load(verbose: bool = True) -> dict:
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.execute("PRAGMA temp_store=MEMORY")

    # --- playable files ---------------------------------------------------
    rows = db.execute("""SELECT spotify_id, path, artist_names, title, duration_seconds
                         FROM audio_files
                         WHERE scan_status='matched' AND path IS NOT NULL
                           AND spotify_id IS NOT NULL""").fetchall()
    pool: dict[str, dict] = {}
    for sid, path, artist, title, dur in rows:
        if sid in pool:
            continue
        pool[sid] = {"id": sid, "path": path, "artist": artist or "", "title": title or "",
                     "seconds": float(dur or 0)}
    if verbose:
        print(f"spárovaných súborov: {len(pool):,}")

    # --- key (same precedence as the similarity engine) -------------------
    for source in ("reccobeats", "freqblog"):
        for sid, value in db.execute(
                "SELECT spotify_id, key FROM audio_features WHERE source=? AND key IS NOT NULL",
                (source,)):
            t = pool.get(sid)
            if t is not None and not t.get("key"):
                t["key"] = str(value)

    # --- bpm --------------------------------------------------------------
    for source in ("freqblog", "reccobeats"):
        for sid, value in db.execute(
                "SELECT spotify_id, bpm FROM audio_features WHERE source=? AND bpm IS NOT NULL",
                (source,)):
            t = pool.get(sid)
            if t is not None and not t.get("bpm"):
                t["bpm"] = float(value)

    # --- what the owner typed himself always wins -------------------------
    for sid, field, vtext, vnum in db.execute(
            "SELECT spotify_id, field, value_text, value_num FROM user_overrides"):
        t = pool.get(sid)
        if not t:
            continue
        if field == "key" and vtext:
            t["key"] = vtext
        elif field == "bpm" and vnum:
            t["bpm"] = float(vnum)

    # --- the owner's own energy rating ------------------------------------
    for sid, energy in db.execute(
            "SELECT spotify_id, energy FROM track_comment WHERE energy IS NOT NULL"):
        t = pool.get(sid)
        if t is not None and t.get("energy") is None:
            t["energy"] = int(energy)

    # --- feelings ---------------------------------------------------------
    for name, markers in SIGNALS.items():
        for t in pool.values():
            t.setdefault("raw", {})[name] = 0.0
        for tag_type, tag, weight, src in markers:
            q = "SELECT spotify_id, source, confidence FROM tags WHERE tag_type=? AND tag=?"
            args = [tag_type, tag]
            if src:
                q += " AND source LIKE ?"
                args.append(src + "%")
            for sid, source, conf in db.execute(q, args):
                t = pool.get(sid)
                if t is None:
                    continue
                w = weight * (conf if conf is not None else 0.6)
                if (source or "").startswith(ARTIST_LEVEL_SOURCES):
                    w *= ARTIST_LEVEL_DAMPING
                t["raw"][name] = max(t["raw"][name], 0) + w
    db.close()

    # --- who made it and what it is called --------------------------------
    # The strongest evidence for THIS theme is not a mood model but a name.
    # Applied after the tags so it adds to the same pot.
    for t in pool.values():
        hay = f"{t['artist']} {t['title']}".lower()
        for name, weight in ORIENT_ARTISTS.items():
            if name in hay:
                t["raw"]["orient"] += weight
                break                      # one artist, counted once
        for word, weight in ORIENT_TITLE_WORDS.items():
            if word in hay:
                t["raw"]["orient"] += weight * 0.8
        for word, (signal, weight) in FLAVOUR_TITLE_WORDS.items():
            if word in hay:
                t["raw"][signal] += weight * 0.8

    # --- keep only what can actually be played ----------------------------
    dropped = {"no_key": 0, "no_bpm": 0, "bpm_range": 0, "length": 0, "missing_file": 0}
    out = []
    for t in pool.values():
        if not t.get("key"):
            dropped["no_key"] += 1;  continue
        if not t.get("bpm"):
            dropped["no_bpm"] += 1;  continue
        if not (BPM_RANGE[0] <= t["bpm"] <= BPM_RANGE[1]):
            dropped["bpm_range"] += 1;  continue
        if not (MIN_SECONDS <= t["seconds"] <= MAX_SECONDS):
            dropped["length"] += 1;  continue
        if not Path(t["path"]).exists():
            dropped["missing_file"] += 1;  continue
        # HALF-EVIDENCE POINTS: how much marker weight counts as "clearly yes".
        # Orient is rarest, so it reaches 0.5 on less evidence than driving.
        for name, half in (("orient", 0.8), ("sensual", 0.9), ("playful", 0.9),
                           ("driving", 1.1), ("scene", 1.2), ("wrong", 0.9)):
            t[name] = _squash(t["raw"].get(name, 0.0), half)
        t.pop("raw", None)
        out.append(t)

    if verbose:
        print(f"hrateľných (súbor + tónina + BPM {BPM_RANGE[0]:.0f}-{BPM_RANGE[1]:.0f}): {len(out):,}")
        print("  vypadlo: " + " · ".join(f"{k}={v:,}" for k, v in dropped.items()))
    return {"tracks": out, "dropped": dropped}


if __name__ == "__main__":
    data = load()
    ts = data["tracks"]
    for name in ("orient", "sensual", "playful", "driving", "wrong"):
        strong = sum(1 for t in ts if t[name] >= 0.5)
        print(f"  {name:<9} >=0.5: {strong:>7,}   >=0.7: {sum(1 for t in ts if t[name]>=0.7):>7,}")

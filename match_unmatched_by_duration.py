"""Match leftover audio files to track-less library tracks, verified by duration.

WHAT: after the AppleDouble purge ~1.6k real files still carry no track, and
~17k library tracks carry no file. Their tags are usually unreadable (that is
why they were never matched), so the indexer stored duration 0 and had nothing
to check a name match against.

HOW: ffprobe reads the true duration straight from the stream, and a file is
only attached to a track when BOTH the normalised "artist title" is a unique
match AND the durations agree within DURATION_TOLERANCE_S. A name match alone is
never enough - the owner's requirement is the right file on the right track.

INPUTS : data/music.db (audio_files, tracks); ffprobe on PATH
OUTPUTS: audio_files rows updated with spotify_id + scan_status='matched'

TWEAK: DURATION_TOLERANCE_S widens or tightens how close the lengths must be.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"
DURATION_TOLERANCE_S = 5.0
MATCH_METHOD = "filename_duration_verified"


def connect() -> sqlite3.Connection:
    last = None
    for _ in range(10):
        try:
            db = sqlite3.connect(DB, timeout=60)
            db.execute("PRAGMA busy_timeout=60000")
            db.execute("select 1")
            return db
        except sqlite3.OperationalError as exc:
            last = exc
            time.sleep(10)
    raise SystemExit(f"nepodarilo sa otvoriť databázu: {last}")


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def probe_seconds(path: str) -> float | None:
    """True duration from the audio stream, or None when the file is unreadable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=60)
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = connect()
    tracks = db.execute(
        """select spotify_id, title, artist_names, duration_ms from tracks
           where spotify_id not in (select spotify_id from audio_files
             where spotify_id is not null and spotify_id<>'')""").fetchall()
    index: dict[str, list] = {}
    for sid, title, artist, dur_ms in tracks:
        for key in {norm(f"{artist} {title}"), norm(f"{title} {artist}")}:
            index.setdefault(key, []).append((sid, dur_ms))
    print(f"trackov bez súboru: {len(tracks):,}")

    files = db.execute(
        "select path, title, artist_names from audio_files where scan_status='unmatched'").fetchall()
    print(f"nespárovaných súborov: {len(files):,}\n")

    accepted, rejected_dur, no_probe, no_name = [], 0, 0, 0
    for path, ftitle, fartist in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        cands = None
        for key in {norm(stem), norm(f"{fartist} {ftitle}")}:
            hit = index.get(key)
            if hit and len(hit) == 1:
                cands = hit[0]
                break
        if not cands:
            no_name += 1
            continue
        seconds = probe_seconds(path)
        if seconds is None:
            no_probe += 1
            continue
        sid, dur_ms = cands
        if dur_ms and abs(seconds - dur_ms / 1000) <= DURATION_TOLERANCE_S:
            accepted.append((sid, seconds, path))
        else:
            rejected_dur += 1

    print(f"prijaté (meno aj dĺžka sedí): {len(accepted)}")
    print(f"zamietnuté pre nesúlad dĺžky: {rejected_dur}")
    print(f"nečitateľné pre ffprobe:      {no_probe}")
    print(f"bez jednoznačnej zhody mena:  {no_name}")

    if not args.apply:
        print("\nSKÚŠOBNÝ BEH — nič sa nezapísalo. Spusti s --apply.")
        return

    db.execute("BEGIN IMMEDIATE")
    for sid, seconds, path in accepted:
        db.execute("""update audio_files
                      set spotify_id=?, duration_seconds=?, scan_status='matched',
                          match_method=?, match_confidence=1.0
                      where path=?""", (sid, seconds, MATCH_METHOD, path))
    db.commit()
    print(f"\nspárovaných {len(accepted)} súborov metódou {MATCH_METHOD}")


if __name__ == "__main__":
    main()

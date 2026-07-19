"""Import exact-ID legacy Spotify audio features from a public HF dataset."""
from __future__ import annotations

import csv
import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect, record_source_run

URL = "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv?download=true"
ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "public_datasets" / "spotify_tracks_114k.csv"
SOURCE = "spotify_legacy_dataset"
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def number(value, integer=False):
    try:
        return int(float(value)) if integer else float(value)
    except (TypeError, ValueError):
        return None


def truth(value):
    return 1 if str(value).strip().lower() in {"1", "true", "yes"} else 0


def main() -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": "local-dj-music-db/1.0"})
        temporary = CACHE.with_suffix(".download")
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(CACHE)

    db = connect()
    library = {r[0] for r in db.execute("SELECT spotify_id FROM tracks")}
    matches = {}
    genres: dict[str, set[str]] = defaultdict(set)
    scanned = 0
    with CACHE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            scanned += 1
            sid = row.get("track_id")
            if sid not in library:
                continue
            matches.setdefault(sid, row)
            genre = (row.get("track_genre") or "").strip().lower()
            if genre:
                genres[sid].add(genre)

    now = datetime.now(timezone.utc).isoformat()
    with db:
        for sid, row in matches.items():
            key_num = number(row.get("key"), integer=True)
            mode_num = number(row.get("mode"), integer=True)
            key = KEYS[key_num] + ("-Major" if mode_num == 1 else "-Minor") if key_num is not None and 0 <= key_num < 12 else None
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            db.execute(
                """INSERT INTO audio_features(
                     spotify_id,source,source_id,bpm,key,mode,time_signature,
                     danceability,energy,valence,acousticness,instrumentalness,
                     speechiness,liveness,loudness,confidence,raw_json,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(spotify_id,source) DO UPDATE SET
                     bpm=excluded.bpm,key=excluded.key,mode=excluded.mode,
                     time_signature=excluded.time_signature,danceability=excluded.danceability,
                     energy=excluded.energy,valence=excluded.valence,acousticness=excluded.acousticness,
                     instrumentalness=excluded.instrumentalness,speechiness=excluded.speechiness,
                     liveness=excluded.liveness,loudness=excluded.loudness,
                     confidence=excluded.confidence,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
                (
                    sid, SOURCE, sid, number(row.get("tempo")), key,
                    "major" if mode_num == 1 else "minor" if mode_num == 0 else None,
                    number(row.get("time_signature"), integer=True),
                    number(row.get("danceability")), number(row.get("energy")),
                    number(row.get("valence")), number(row.get("acousticness")),
                    number(row.get("instrumentalness")), number(row.get("speechiness")),
                    number(row.get("liveness")), number(row.get("loudness")),
                    0.97, raw, now,
                ),
            )
            db.execute(
                """UPDATE tracks SET album=COALESCE(album,?),duration_ms=COALESCE(duration_ms,?),
                   popularity=COALESCE(popularity,?),explicit=COALESCE(explicit,?),updated_at=?
                   WHERE spotify_id=?""",
                (row.get("album_name"), number(row.get("duration_ms"), integer=True),
                 number(row.get("popularity"), integer=True), truth(row.get("explicit")), now, sid),
            )
            for genre in genres[sid]:
                db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", (sid, genre, "genre", SOURCE, 0.85))
            db.execute(
                """INSERT OR REPLACE INTO track_attributes
                   (spotify_id,attribute,source,value_json,confidence,updated_at)
                   VALUES(?,? ,?,?,?,?)""",
                (sid, "dataset_row", SOURCE, raw, 0.97, now),
            )
    record_source_run(db, SOURCE, now, len(matches), f"scanned={scanned},license=BSD,source={URL}")
    print(f"HF Spotify legacy dataset: scanned={scanned:,}, exact_matches={len(matches):,}")


if __name__ == "__main__":
    main()

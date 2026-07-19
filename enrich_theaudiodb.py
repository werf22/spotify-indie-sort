"""Resumable TheAudioDB enrichment using the public free API key by default."""
from __future__ import annotations

import argparse
import json
import os
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from musicdb import connect, record_source_run

SOURCE = "theaudiodb"


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(c.lower() for c in value if c.isalnum())


def get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "local-dj-music-db/1.0"})
    return json.loads(urlopen(req, timeout=30).read())


def scalar_attributes(sid: str, data: dict, now: str) -> list[tuple]:
    rows = []
    for key, value in data.items():
        if value in (None, ""):
            continue
        text = num = raw = None
        if isinstance(value, bool):
            text, num = str(value).lower(), float(value)
        elif isinstance(value, (int, float)):
            num = float(value)
        elif isinstance(value, (dict, list)):
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        rows.append((sid, key, SOURCE, text, num, raw, 0.75, now))
    return rows


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay", type=float, default=2.10)
    args = parser.parse_args()
    api_key = (os.getenv("THEAUDIODB_API_KEY") or "123").strip()
    base = f"https://www.theaudiodb.com/api/v1/json/{api_key}"
    db = connect()
    db.execute(
        """CREATE TABLE IF NOT EXISTS theaudiodb_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
             last_error TEXT,updated_at TEXT NOT NULL)"""
    )
    rows = db.execute(
        """SELECT t.spotify_id,t.title,t.artist_names FROM tracks t
           LEFT JOIN theaudiodb_status s USING(spotify_id)
           WHERE COALESCE(s.status,'') NOT IN ('success','not_found')
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (args.limit,),
    ).fetchall()
    success = not_found = errors = 0
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        artist = (row["artist_names"] or "").split(",", 1)[0].strip()
        try:
            url = base + "/searchtrack.php?" + urlencode({"s": artist, "t": row["title"]})
            candidates = get(url).get("track") or []
            hit = next(
                (x for x in candidates if norm(x.get("strTrack")) == norm(row["title"])
                 and norm(x.get("strArtist")) == norm(artist)), None,
            )
            if not hit:
                raise LookupError("no exact match")
            sid = row["spotify_id"]
            attrs = scalar_attributes(sid, hit, now)
            with db:
                db.execute(
                    """UPDATE tracks SET album=COALESCE(album,?),duration_ms=COALESCE(duration_ms,?),
                       musicbrainz_id=COALESCE(musicbrainz_id,?),updated_at=? WHERE spotify_id=?""",
                    (hit.get("strAlbum"), int(hit.get("intDuration") or 0) or None,
                     hit.get("strMusicBrainzID") or None, now, sid),
                )
                for field, tag_type in (("strGenre", "genre"), ("strMood", "mood"),
                                        ("strStyle", "style"), ("strTheme", "theme")):
                    for value in (hit.get(field) or "").replace("/", ",").split(","):
                        value = value.strip().lower()
                        if value:
                            db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                                       (sid, value, tag_type, SOURCE, 0.75))
                if attrs:
                    db.executemany(
                        """INSERT OR REPLACE INTO track_attributes
                           (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
                           VALUES(?,?,?,?,?,?,?,?)""", attrs,
                    )
                db.execute(
                    """INSERT INTO theaudiodb_status VALUES(?,'success',1,NULL,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='success',attempts=attempts+1,
                       last_error=NULL,updated_at=excluded.updated_at""", (sid, now),
                )
            success += 1
        except LookupError as exc:
            with db:
                db.execute("INSERT OR REPLACE INTO theaudiodb_status VALUES(?,'not_found',1,?,?)",
                           (row["spotify_id"], str(exc), now))
            not_found += 1
        except Exception as exc:
            with db:
                db.execute(
                    """INSERT INTO theaudiodb_status VALUES(?,'failed',1,?,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='failed',attempts=attempts+1,
                       last_error=excluded.last_error,updated_at=excluded.updated_at""",
                    (row["spotify_id"], str(exc), now),
                )
            errors += 1
        time.sleep(args.delay)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), success,
                      f"not_found={not_found},errors={errors}")
    print(f"TheAudioDB: enriched={success}, not_found={not_found}, errors={errors}")


if __name__ == "__main__":
    main()

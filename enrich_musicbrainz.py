"""Restart-safe MusicBrainz recording enrichment, exact by ISRC when possible."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from enrich_lastfm_artists import kind
from musicdb import connect, record_source_run

API = "https://musicbrainz.org/ws/2"
SOURCE = "musicbrainz"


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(c.lower() for c in value if c.isalnum())


def get(url: str, user_agent: str) -> dict:
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    return json.loads(urlopen(req, timeout=30).read())


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--delay", type=float, default=1.10)
    args = parser.parse_args()
    user_agent = os.getenv("MUSICBRAINZ_USER_AGENT", "local-dj-music-db/1.0 (contact: jakubcerulik)")
    db = connect()
    db.execute(
        """CREATE TABLE IF NOT EXISTS musicbrainz_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
             last_error TEXT,updated_at TEXT NOT NULL)"""
    )
    rows = db.execute(
        """SELECT t.spotify_id,t.title,t.artist_names,t.isrc,t.musicbrainz_id
           FROM tracks t LEFT JOIN musicbrainz_status s USING(spotify_id)
           WHERE COALESCE(s.status,'') NOT IN ('success','not_found')
           ORDER BY (t.isrc IS NULL),COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (args.limit,),
    ).fetchall()
    success = not_found = errors = 0
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        artist = (row["artist_names"] or "").split(",", 1)[0].strip()
        try:
            if row["musicbrainz_id"]:
                url = (f"{API}/recording/{quote(row['musicbrainz_id'])}?"
                       "inc=artist-credits%2Btags%2Bgenres%2Bisrcs&fmt=json")
                hits = [get(url, user_agent)]
            elif row["isrc"]:
                clean_isrc = re.sub(r"[^A-Z0-9]", "", row["isrc"].upper())
                url = (f"{API}/isrc/{quote(clean_isrc)}?"
                       "inc=artist-credits%2Btags&fmt=json")
                hits = get(url, user_agent).get("recordings") or []
            else:
                query = f'recording:"{row["title"]}" AND artist:"{artist}"'
                url = f"{API}/recording/?" + urlencode({"query": query, "fmt": "json", "limit": 5})
                hits = get(url, user_agent).get("recordings") or []
            hit = next(
                (x for x in hits if norm(x.get("title")) == norm(row["title"])
                 and (not artist or any(norm(c.get("name")) == norm(artist)
                     for c in (x.get("artist-credit") or [])))), None,
            )
            if not hit and len(hits) == 1 and row["isrc"]:
                hit = hits[0]
            if not hit:
                raise LookupError("no exact recording match")
            tags = (hit.get("tags") or []) + (hit.get("genres") or [])
            maximum = max([abs(int(x.get("count") or 0)) for x in tags] or [1])
            with db:
                db.execute(
                    """UPDATE tracks SET musicbrainz_id=?,isrc=COALESCE(isrc,?),
                       duration_ms=COALESCE(duration_ms,?),release_date=COALESCE(release_date,?),
                       updated_at=? WHERE spotify_id=?""",
                    (hit.get("id"), (hit.get("isrcs") or [None])[0], hit.get("length"),
                     hit.get("first-release-date"), now, row["spotify_id"]),
                )
                for tag in tags:
                    name = (tag.get("name") or "").strip().lower()
                    count = abs(int(tag.get("count") or 0))
                    if name:
                        db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                                   (row["spotify_id"], name, kind(name), SOURCE,
                                    max(0.2, min(1.0, count / maximum))))
                db.execute(
                    """INSERT OR REPLACE INTO track_attributes
                       (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (row["spotify_id"], "recording", SOURCE, None, None,
                     json.dumps(hit, ensure_ascii=False, sort_keys=True), 0.95, now),
                )
                db.execute(
                    """INSERT INTO musicbrainz_status VALUES(?,'success',1,NULL,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='success',attempts=attempts+1,
                       last_error=NULL,updated_at=excluded.updated_at""",
                    (row["spotify_id"], now),
                )
            success += 1
        except HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            with db:
                if exc.code in {400, 404}:
                    db.execute("INSERT OR REPLACE INTO musicbrainz_status VALUES(?,'not_found',1,?,?)",
                               (row["spotify_id"], f"HTTP {exc.code}: {body}", now))
                    not_found += 1
                else:
                    db.execute(
                        """INSERT INTO musicbrainz_status VALUES(?,'failed',1,?,?)
                           ON CONFLICT(spotify_id) DO UPDATE SET status='failed',attempts=attempts+1,
                           last_error=excluded.last_error,updated_at=excluded.updated_at""",
                        (row["spotify_id"], f"HTTP {exc.code}: {body}", now),
                    )
                    errors += 1
        except LookupError as exc:
            with db:
                db.execute("INSERT OR REPLACE INTO musicbrainz_status VALUES(?,'not_found',1,?,?)",
                           (row["spotify_id"], str(exc), now))
            not_found += 1
        except Exception as exc:
            with db:
                db.execute(
                    """INSERT INTO musicbrainz_status VALUES(?,'failed',1,?,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='failed',attempts=attempts+1,
                       last_error=excluded.last_error,updated_at=excluded.updated_at""",
                    (row["spotify_id"], str(exc), now),
                )
            errors += 1
        time.sleep(args.delay)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), success,
                      f"not_found={not_found},errors={errors}")
    print(f"MusicBrainz: enriched={success}, not_found={not_found}, errors={errors}")


if __name__ == "__main__":
    main()

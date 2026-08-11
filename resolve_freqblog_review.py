#!/usr/bin/env python3
"""Resolve the FreqBlog needs_review backlog: accept the certain, reject the absurd.

WHAT: walks `freqblog_review_candidates` and splits it three ways.
  ACCEPT  - normalised title AND artist are byte-identical to the provider's,
            and no ISRC conflict contradicts them. Written through the
            enricher's own save_success(), so the row lands exactly as a
            normally-matched track would.
  REJECT  - title AND artist similarity both below REJECT_RATIO. These are not
            near-misses, they are different songs; they become 'not_found'.
  KEEP    - everything else stays in review, untouched.

WHY: the automatic matcher parked 3,686 tracks it was not confident about.
Most are genuinely ambiguous, but a subset is provably right and a subset is
provably wrong, and leaving all of them unresolved denies the certain ones
their data.

WHY SO STRICT: this writes BPM, key and mood into a DJ database. A wrong value
is worse than a missing one, so acceptance demands exact equality after
normalisation — not fuzzy similarity — and an ISRC that disagrees vetoes the
match even when the names line up, since that usually means a different
recording or remaster.

HOW TO TWEAK: REJECT_RATIO controls only the rejection side; raising it rejects
more aggressively. Acceptance has no threshold to tune on purpose — it is exact
equality or nothing. Run with no arguments for a dry run; pass --apply to write.
Every changed row is backed up to data/ first.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import enrich_freqblog as fb
from musicdb import connect, connect_readonly

ROOT = Path(__file__).resolve().parent
REJECT_RATIO = 0.5      # below this on BOTH title and artist = a different song


def isrc_clean(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def classify(row) -> tuple[str, float, float]:
    """Return (verdict, title_ratio, artist_ratio) for one review candidate."""
    ptitle, partist = fb.norm(row["provider_track"]), fb.norm(row["provider_artist"])
    stitle = fb.norm(row["title"])
    sartist = fb.norm(fb.first_artist(row["artist_names"]))
    t = SequenceMatcher(None, stitle, ptitle).ratio()
    a = SequenceMatcher(None, sartist, partist).ratio()
    theirs, ours = isrc_clean(row["provider_isrc"]), isrc_clean(row["isrc"])
    conflict = bool(theirs and ours and theirs != ours)
    if ptitle and partist and ptitle == stitle and partist == sartist and not conflict:
        return "accept", t, a
    if t < REJECT_RATIO and a < REJECT_RATIO:
        return "reject", t, a
    return "keep", t, a


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="cap rows processed, for a cautious first pass")
    args = parser.parse_args()

    with connect_readonly() as db:
        rows = db.execute(
            """SELECT c.spotify_id, c.match_confidence, c.match_method, c.provider_track,
                      c.provider_artist, c.provider_isrc, c.raw_json,
                      t.title, t.artist_names, t.isrc
               FROM freqblog_review_candidates c JOIN tracks t USING(spotify_id)"""
        ).fetchall()

    buckets: dict[str, list] = {"accept": [], "reject": [], "keep": []}
    for row in rows:
        verdict, t, a = classify(row)
        buckets[verdict].append((row, t, a))

    print(f"review backlog: {len(rows):,}")
    for name in ("accept", "reject", "keep"):
        print(f"  {name:7} {len(buckets[name]):6,}")
    for name in ("accept", "reject"):
        for row, t, a in buckets[name][:3]:
            print(f"    [{name}] '{row['title']}' / '{fb.first_artist(row['artist_names'])}'"
                  f"  <-  '{row['provider_track']}' / '{row['provider_artist']}'"
                  f"  (title {t:.2f}, artist {a:.2f})")

    if not args.apply:
        print("\ndry run — nothing written. Pass --apply to commit these changes.")
        return

    stamp = datetime.now(timezone.utc)
    backup = ROOT / "data" / f"backup_freqblog_review_{stamp:%Y%m%dT%H%M%SZ}.json"
    backup.write_text(json.dumps(
        {name: [dict(r) for r, _, _ in items] for name, items in buckets.items()},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nbacked up every candidate row -> {backup.name}")

    now = stamp.isoformat()
    db = connect()
    db.execute("PRAGMA busy_timeout=120000")
    accepted = rejected = failed = 0
    todo = buckets["accept"] if not args.limit else buckets["accept"][:args.limit]
    for row, t, a in todo:
        try:
            data = json.loads(row["raw_json"])
            # match_method records WHY this was accepted, so the provenance of a
            # reviewed row is never confused with an automatic match.
            fb.save_success(db, row, data, now, match_score=0.95,
                            match_method="review_exact_name_artist")
            with db:
                db.execute("DELETE FROM freqblog_review_candidates WHERE spotify_id=?",
                           (row["spotify_id"],))
            accepted += 1
        except Exception as exc:                       # never let one bad row stop the pass
            failed += 1
            print(f"  FAILED {row['spotify_id']}: {type(exc).__name__}: {exc}")
    todo = buckets["reject"] if not args.limit else buckets["reject"][:args.limit]
    for row, t, a in todo:
        with db:
            db.execute(
                """INSERT INTO freqblog_status(spotify_id,status,attempts,next_retry_at,
                                               last_error,updated_at,match_confidence,match_method)
                   VALUES(?,'not_found',1,NULL,'review: title and artist both unrelated',?,0.0,'review_rejected')
                   ON CONFLICT(spotify_id) DO UPDATE SET status='not_found',next_retry_at=NULL,
                     last_error=excluded.last_error,updated_at=excluded.updated_at,
                     match_confidence=0.0,match_method='review_rejected'""",
                (row["spotify_id"], now))
            db.execute("DELETE FROM freqblog_review_candidates WHERE spotify_id=?",
                       (row["spotify_id"],))
        rejected += 1
    print(f"accepted={accepted} rejected={rejected} failed={failed} kept={len(buckets['keep'])}")


if __name__ == "__main__":
    main()

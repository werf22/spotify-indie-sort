#!/usr/bin/env python3
"""Command-line front end for the similarity engine.

The ranking itself lives in `similarity_engine.py` — the same module the app
uses, so the terminal and the app can never disagree about what "similar" means.

USAGE
  ./.venv/bin/python similar_tracks.py --query "iLee Lila" --limit 50
  ./.venv/bin/python similar_tracks.py --id 4vgKa... --limit 100 --bpm-window 3 --same-key
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import similarity_engine as engine


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id")
    ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--spotify-only", action="store_true",
                    help="only tracks that exist on Spotify (needed for a playlist)")
    ap.add_argument("--bpm-window", type=float, default=0.0, help="hard filter, percent")
    ap.add_argument("--same-key", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="keep every mix of the same song")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    if not args.id and not args.query:
        ap.error("give --id or --query")
    print("loading embeddings (about a minute the first time) …", flush=True)
    engine.warm()

    ref = args.id
    if not ref:
        hits = engine.search(args.query, limit=5)
        if not hits:
            sys.exit(f"no track matches {args.query!r}")
        ref = hits[0]["spotify_id"]
        print(f"reference: {hits[0]['artist']} — {hits[0]['title']}  ({ref})")

    rows = engine.similar(ref, limit=args.limit, spotify_only=args.spotify_only,
                          bpm_window=args.bpm_window, same_key=args.same_key,
                          dedupe=not args.no_dedupe)
    print(f"\ntop {len(rows)}:")
    for i, r in enumerate(rows, 1):
        w = r.get("why", {})
        print(f"{i:3}. {r['score']:6.2f} audio={w.get('audio', 0):5.2f} tag={w.get('tags', 0):.2f} "
              f"rhythm={w.get('rhythm', 0):6.2f} key={w.get('key')} "
              f"{str(r['bpm'] or ''):>5} {str(r['key'] or ''):>9}  "
              f"{r['artist'][:24]:26} {r['title'][:36]}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=1))
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

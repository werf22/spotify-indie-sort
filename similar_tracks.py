#!/usr/bin/env python3
"""Command-line front end for the similarity engine.

The ranking lives in `similarity_engine.py` — the same module the app uses, so
the terminal and the app can never disagree about what "similar" means.

USAGE
  ./.venv/bin/python similar_tracks.py --list-signals
  ./.venv/bin/python similar_tracks.py --query "iLee Lila" --limit 50
  ./.venv/bin/python similar_tracks.py --query "iLee Lila" --groups audio
  ./.venv/bin/python similar_tracks.py --query "iLee Lila" --groups tags,musical --same-key
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import similarity_engine as engine


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id")
    ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--spotify-only", action="store_true",
                    help="only tracks that exist on Spotify (needed for a playlist)")
    ap.add_argument("--groups", help="comma list: audio,tags,numbers,musical "
                                     "(default: every signal marked on)")
    ap.add_argument("--signals", help="comma list of exact signal ids, overrides --groups")
    ap.add_argument("--list-signals", action="store_true", help="show everything comparable")
    ap.add_argument("--bpm-window", type=float, default=0.0, help="hard filter, percent")
    ap.add_argument("--same-key", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true", help="keep every mix of a song")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    print("loading signals (about two minutes the first time) …", flush=True)
    engine.warm()
    catalogue = engine.signals()

    if args.list_signals:
        group = None
        for s in catalogue:
            if s["group"] != group:
                group = s["group"]
                print(f"\n[{group}]")
            mark = "x" if s["default"] else " "
            print(f"  [{mark}] {s['id']:<28} {s['coverage']:>7,} trackov   {s['note']}")
        return

    if not args.id and not args.query:
        ap.error("give --id or --query")
    ref = args.id
    if not ref:
        hits = engine.search(args.query, limit=5)
        if not hits:
            sys.exit(f"no track matches {args.query!r}")
        ref = hits[0]["spotify_id"]
        print(f"reference: {hits[0]['artist']} — {hits[0]['title']}  ({ref})")

    enabled = None
    if args.signals:
        enabled = [s.strip() for s in args.signals.split(",") if s.strip()]
    elif args.groups:
        want = {g.strip() for g in args.groups.split(",")}
        enabled = [s["id"] for s in catalogue if s["group"] in want and s["default"]]

    payload = engine.similar(ref, limit=args.limit, spotify_only=args.spotify_only,
                             bpm_window=args.bpm_window, same_key=args.same_key,
                             dedupe=not args.no_dedupe, enabled=enabled)
    rows = payload["results"]
    print(f"\ncompared using: {payload['signals_used']}")
    for i, r in enumerate(rows, 1):
        why = " · ".join(r["why"][:3])
        print(f"{i:3}. {r['score']:6.2f} {str(r['bpm'] or ''):>5} {str(r['key'] or ''):>9}  "
              f"{r['artist'][:24]:26} {r['title'][:34]:36} {why}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=1))
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

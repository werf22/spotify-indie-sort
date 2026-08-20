#!/usr/bin/env python3
"""Reclaim disk from analysis work that is already FINISHED — and nothing else.

WHY: the pipeline stages a ~6.5 MB clip per track, then copies those clips again
into each shard directory alongside the tar it builds from them. With the upload
broken for five days the backlog grew to 96 GB of clips plus 20 GB of shard
directories, and the orchestrator refuses to build a shard below 45 GB free — so
the disk, not money, became the thing blocking analysis.

THE SAFETY RULE: a clip is deleted ONLY when its track already has all four
stages in the database, and a shard directory ONLY when every track in its
manifest does. Anything unfinished, unreadable, or unknown is kept. Deleting a
clip we still need costs a re-transcode; keeping one costs disk, so the bias is
deliberate.

USAGE
  ./.venv/bin/python gc_analysis_workspace.py            # dry run, deletes nothing
  ./.venv/bin/python gc_analysis_workspace.py --apply    # actually delete
"""
from __future__ import annotations
import argparse, csv, glob, os, shutil, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "data" / "cloud_full" / "clips"
SHARDS = ROOT / "data" / "cloud_full_shards"
STAGES = ("rhythm_full", "maest_full", "essentia_full", "clap_full")


def finished_ids() -> set[str]:
    db = sqlite3.connect(ROOT / "data" / "music.db", timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    try:
        marks = ",".join("?" * len(STAGES))
        return {r[0] for r in db.execute(
            f"""SELECT spotify_id FROM audio_analysis_artifacts WHERE stage IN ({marks})
                GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=?""", (*STAGES, len(STAGES)))}
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    done = finished_ids()
    print(f"tracks with all four stages: {len(done):,}")

    # 1) staged clips whose track is finished
    clip_bytes = clip_n = 0
    victims = []
    for path in glob.glob(str(CLIPS / "*.opus")):
        if Path(path).stem in done:
            victims.append(path)
            clip_bytes += os.path.getsize(path)
            clip_n += 1
    print(f"finished clips        : {clip_n:,}  ({clip_bytes/1e9:.1f} GB)")

    # 2) shard directories whose EVERY manifest track is finished
    shard_dirs, shard_bytes = [], 0
    for manifest in glob.glob(str(SHARDS / "*" / "manifest.csv")):
        d = Path(manifest).parent
        try:
            with open(manifest, encoding="utf-8", newline="") as fh:
                ids = [r.get("spotify_id") for r in csv.DictReader(fh)]
            ids = [i for i in ids if i]
        except OSError:
            continue
        if not ids or any(i not in done for i in ids):
            continue                      # unfinished or unreadable -> KEEP
        size = sum(os.path.getsize(os.path.join(p, f))
                   for p, _, fs in os.walk(d) for f in fs
                   if os.path.exists(os.path.join(p, f)))
        shard_dirs.append(d)
        shard_bytes += size
    print(f"fully-analysed shards : {len(shard_dirs):,}  ({shard_bytes/1e9:.1f} GB)")
    print(f"TOTAL RECLAIMABLE     : {(clip_bytes+shard_bytes)/1e9:.1f} GB")
    free = shutil.disk_usage(ROOT).free / 1024**3
    print(f"free now {free:.1f} GiB -> after {(free + (clip_bytes+shard_bytes)/1024**3):.1f} GiB")

    if not args.apply:
        print("\nDRY RUN — nothing deleted. Re-run with --apply.")
        return
    for path in victims:
        try: os.remove(path)
        except OSError: pass
    for d in shard_dirs:
        shutil.rmtree(d, ignore_errors=True)
    print(f"deleted {clip_n:,} clips and {len(shard_dirs)} shard dirs; "
          f"free now {shutil.disk_usage(ROOT).free/1024**3:.1f} GiB")


if __name__ == "__main__":
    main()

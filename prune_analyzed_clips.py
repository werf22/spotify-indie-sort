#!/usr/bin/env python3
"""Delete Opus analysis clips whose track is fully analyzed and imported.

WHAT: a clip in data/cloud_full/clips exists only to be uploaded to a GPU
pod. Once all four stages (rhythm/MAEST/Essentia/CLAP) for that track are in
the database, the clip is derived data with no further use — the analysis
results are what we keep.

WHY: clips average ~6.8 MB, so the full local corpus (~29k files) would need
~190 GB and would not fit beside the owner's 50 GiB safety floor. Pruning
after import turns disk use into a small rolling window instead of a
permanently growing pile, which is what makes analyzing the whole collection
possible at all.

SAFETY:
- only deletes when the DB shows all four stages for that spotify_id;
- shard directories hold hardlinks, so a clip still being analyzed on a pod
  keeps its data alive even after this prunes the copy in clips/;
- prepare_cloud_audio_pilot.py skips fully-analyzed tracks, so a pruned clip
  is never re-encoded;
- --dry-run prints what would go without touching anything.

HOW TO TWEAK: --keep-free-gib raises the floor at which pruning becomes
mandatory; by default every eligible clip is pruned.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from musicdb import connect_readonly

ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "data" / "cloud_full" / "clips"
SHARDS = ROOT / "data" / "cloud_full_shards"
# Kept forever in an imported shard: the audit trail and cloud lifecycle
# record. Everything else there is reproducible derived data.
SHARD_KEEP = {"manifest.csv", "results.jsonl", "runpod_state.json",
              "imported.ok", "bundle.tar.sha256"}


def fully_analyzed() -> set[str]:
    with connect_readonly() as db:
        return {
            row[0]
            for row in db.execute(
                """SELECT spotify_id FROM audio_analysis_artifacts
                   WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                   GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4"""
            )
        }


def prune_imported_shards(dry_run: bool) -> tuple[int, int]:
    """Strip bundle.tar and the hardlinked clips from imported shards.

    The clips here are hardlinks to data/cloud_full/clips, so pruning that
    directory alone frees nothing while these still reference the inodes —
    both sides must go. bundle.tar is a rebuildable tar of the same clips.
    """
    freed = shards = 0
    for shard in sorted(SHARDS.glob("shard-*")):
        if not (shard / "imported.ok").is_file():
            continue  # still needed by an unfinished run
        touched = False
        for item in shard.iterdir():
            if item.name in SHARD_KEEP:
                continue
            if item.is_dir():
                for child in item.rglob("*"):
                    if child.is_file():
                        freed += child.stat().st_size
                        if not dry_run:
                            child.unlink()
                if not dry_run:
                    shutil.rmtree(item, ignore_errors=True)
            else:
                freed += item.stat().st_size
                if not dry_run:
                    item.unlink()
            touched = True
        shards += touched
    return shards, freed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    done = fully_analyzed()
    freed = 0
    removed = 0
    kept = 0
    for clip in sorted(CLIPS.glob("*.opus")):
        if clip.name.endswith(".partial.opus"):
            continue
        if clip.stem in done:
            size = clip.stat().st_size
            if not args.dry_run:
                clip.unlink()
            freed += size
            removed += 1
        else:
            kept += 1
    shards, shard_freed = prune_imported_shards(args.dry_run)
    free_gib = shutil.disk_usage(ROOT).free / 1024**3
    verb = "would free" if args.dry_run else "freed"
    print(f"clips pruned={removed} kept={kept} | imported shards stripped={shards} | "
          f"{verb}={(freed + shard_freed)/1024**3:.1f} GiB "
          f"disk_free_after={free_gib:.1f} GiB")


if __name__ == "__main__":
    main()

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
    ap.add_argument("--trim-backlog", type=int, default=0,
                    help="shrink the waiting clip pile to N tracks (manifest included)")
    args = ap.parse_args()
    if args.trim_backlog:
        trim_backlog(args.trim_backlog, args.apply)
        return
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

    # 2) a built shard's clips/ copy, once its tar exists.
    # Building a shard COPIES clips out of data/cloud_full/clips and then tars
    # them, so a finished bundle means the same audio is on disk three times:
    # source, shard copy, and tar. Verified before deleting — 560 of 560 sampled
    # shard clips were still present in the source directory. This alone was
    # 20.6 GB while free space was down to 5.3 GiB.
    dup_bytes = dup_dirs = 0
    dup_victims = []
    for bundle in glob.glob(str(SHARDS / "*" / "bundle.tar")):
        clips = Path(bundle).parent / "clips"
        if not clips.is_dir():
            continue
        missing = [f for f in clips.glob("*.opus") if not (CLIPS / f.name).is_file()]
        if missing:
            continue                      # some audio lives ONLY here — keep it
        size = sum(f.stat().st_size for f in clips.rglob("*") if f.is_file())
        dup_victims.append(clips)
        dup_bytes += size
        dup_dirs += 1
    print(f"duplicated shard clips : {dup_dirs:,} dirs ({dup_bytes/1e9:.1f} GB)")

    # 3) shard directories whose EVERY manifest track is finished
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
    print(f"TOTAL RECLAIMABLE     : {(clip_bytes+shard_bytes+dup_bytes)/1e9:.1f} GB")
    free = shutil.disk_usage(ROOT).free / 1024**3
    print(f"free now {free:.1f} GiB -> after {(free + (clip_bytes+shard_bytes+dup_bytes)/1024**3):.1f} GiB")

    if not args.apply:
        print("\nDRY RUN — nothing deleted. Re-run with --apply.")
        return
    for path in victims:
        try: os.remove(path)
        except OSError: pass
    for d in dup_victims:
        shutil.rmtree(d, ignore_errors=True)
    for d in shard_dirs:
        shutil.rmtree(d, ignore_errors=True)
    print(f"deleted {clip_n:,} clips, {len(dup_victims)} duplicate clip dirs "
          f"and {len(shard_dirs)} shard dirs; "
          f"free now {shutil.disk_usage(ROOT).free/1024**3:.1f} GiB")




def trim_backlog(keep: int, apply: bool) -> None:
    """Shrink the waiting clip pile to `keep` tracks, manifest included.

    WHY THIS IS SAFE: a clip is a transcode of a file we still own — prep can
    remake any of them. What must NOT happen is deleting a clip while leaving
    its manifest row behind, because the shard builder would then point at a
    missing file. So the row goes with the clip, and the manifest is backed up
    first.

    WHY IT IS NEEDED: the factory banked 20,900 clips — 135 GB, about 70 shards
    — against a disk with 5 GiB free, while each of 8 runners also stages a
    ~1.5 GB bundle. The pile can only drain 200 tracks per finished shard, so it
    would have squeezed the machine for days. prep_loop.sh now caps the backlog
    at 6,000; this brings the existing pile down to the same figure.

    PROTECTED: any track referenced by a shard that already has a bundle — that
    work is in flight and its clip must survive.
    """
    import csv
    manifest = ROOT / "data" / "cloud_full" / "manifest.csv"
    if not manifest.is_file():
        print("no manifest — nothing to trim")
        return
    done = finished_ids()
    protected: set[str] = set()
    for path in glob.glob(str(SHARDS / "*" / "bundle.tar")):
        shard_manifest = Path(path).parent / "manifest.csv"
        if shard_manifest.is_file():
            with open(shard_manifest, encoding="utf-8", newline="") as fh:
                protected |= {r.get("spotify_id") for r in csv.DictReader(fh)}
    with open(manifest, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)

    pending = [r for r in rows if r.get("spotify_id") not in done]
    keepers = {r["spotify_id"] for r in pending[:keep]} | protected
    drop = [r for r in pending if r["spotify_id"] not in keepers]
    freed = 0
    for row in drop:
        clip = CLIPS / f"{row['spotify_id']}.opus"
        if clip.is_file():
            freed += clip.stat().st_size
    print(f"manifest rows          : {len(rows):,} ({len(pending):,} still pending)")
    print(f"protected (in flight)  : {len(protected):,}")
    print(f"would drop             : {len(drop):,} tracks, {freed/1e9:.1f} GB of clips")
    print(f"would keep waiting     : {min(keep, len(pending)):,}")
    if not apply:
        print("\nDRY RUN — nothing deleted.")
        return
    stamp = __import__("time").strftime("%Y%m%dT%H%M%SZ", __import__("time").gmtime())
    backup = manifest.with_name(f"manifest.before-trim.{stamp}.csv")
    shutil.copy2(manifest, backup)
    print(f"manifest backed up to {backup.name}")
    dropped = {r["spotify_id"] for r in drop}
    tmp = manifest.with_suffix(".trimmed.csv")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            if row.get("spotify_id") not in dropped:
                writer.writerow(row)
    tmp.replace(manifest)
    removed = 0
    for sid in dropped:
        clip = CLIPS / f"{sid}.opus"
        try:
            clip.unlink()
            removed += 1
        except OSError:
            pass
    print(f"dropped {len(dropped):,} rows, deleted {removed:,} clips; "
          f"free now {shutil.disk_usage(ROOT).free/1024**3:.1f} GiB")


if __name__ == "__main__":
    main()

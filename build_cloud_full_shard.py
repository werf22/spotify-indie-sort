#!/usr/bin/env python3
"""Build a deterministic hard-linked production shard from ready full tracks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

from musicdb import connect


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "cloud_full"
DEST = ROOT / "data" / "cloud_full_shards"
ALL_STAGES = ("rhythm_full", "maest_full", "essentia_full", "clap_full")
SCRIPTS = [
    "cloud_audio_full.py", "analyze_local_genres.py", "analyze_local_semantics.py",
    "analyze_essentia_full.py", "analyze_local_rhythm.py", "audio_taxonomy.py",
    "musicdb.py", "requirements-cloud-audio.txt",
]
EXTRA_PATHS = ["vendor/essentia-models"]


def shard_clip_path(shard: Path, spotify_id: str, suffix: str) -> str:
    """Return the path used after the bundle is extracted in /workspace."""
    return str((shard / "clips" / f"{spotify_id}{suffix}").relative_to(ROOT))


def manifest_rows() -> list[dict]:
    with (SOURCE / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def completed_stages() -> dict[str, set[str]]:
    with connect() as db:
        rows = db.execute(
            """SELECT spotify_id,stage FROM audio_analysis_artifacts
               WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')"""
        )
        result: dict[str, set[str]] = {}
        for spotify_id, stage in rows:
            result.setdefault(spotify_id, set()).add(stage)
        return result


def next_index() -> int:
    existing = []
    for path in DEST.glob("shard-*"):
        try:
            existing.append(int(path.name.split("-")[-1]))
        except ValueError:
            continue
    return max(existing, default=0) + 1


def write_manifest(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    temporary = path.with_suffix(".partial.csv")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def build_bundle(shard: Path) -> Path:
    clips = shard / "clips"
    bundle = shard / "bundle.tar"
    temporary = shard / "bundle.partial.tar"
    command = ["tar", "-cf", str(temporary)]
    for script in SCRIPTS:
        command += ["-C", str(ROOT), script]
    for path in EXTRA_PATHS:
        command += ["-C", str(ROOT), path]
    command += ["-C", str(ROOT), str((shard / "manifest.csv").relative_to(ROOT)),
                str(clips.relative_to(ROOT))]
    subprocess.run(command, check=True)
    temporary.replace(bundle)
    digest = hashlib.sha256()
    with bundle.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    checksum = shard / "bundle.tar.sha256"
    checksum.write_text(f"{digest.hexdigest()}  bundle.tar\n", encoding="utf-8")
    return bundle


def repair_shard(shard: Path) -> dict:
    manifest = shard / "manifest.csv"
    if not manifest.is_file() or not (shard / "clips").is_dir():
        raise SystemExit(f"Shard manifest/clips missing: {shard}")
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"Empty shard: {shard}")
    done = completed_stages()
    pending_pairs = 0
    repaired_rows = []
    for row in rows:
        matches = list((shard / "clips").glob(f"{row['spotify_id']}.*"))
        if len(matches) != 1:
            raise SystemExit(f"Expected one bundled clip for {row['spotify_id']}: {matches}")
        row["clip_path"] = shard_clip_path(shard, row["spotify_id"], matches[0].suffix)
        missing = [stage for stage in ALL_STAGES
                   if stage not in done.get(row["spotify_id"], set())]
        if missing:
            row["required_stages"] = ",".join(missing)
            pending_pairs += len(missing)
            repaired_rows.append(row)
    if not repaired_rows:
        return {"status": "complete", "shard": str(shard), "tracks": 0,
                "pending_pairs": 0}
    write_manifest(manifest, repaired_rows)
    bundle = build_bundle(shard)
    return {"status": "repaired", "shard": str(shard),
            "tracks": len(repaired_rows), "pending_pairs": pending_pairs,
            "bytes": bundle.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=250)
    parser.add_argument("--minimum", type=int, default=250)
    parser.add_argument("--repair", type=Path,
                        help="Rewrite an existing shard manifest and bundle with remote-safe clip paths")
    args = parser.parse_args()
    if args.repair:
        print(json.dumps(repair_shard(args.repair.resolve())))
        return
    ready = manifest_rows()
    done = completed_stages()
    # Tracks already claimed by an existing, not-yet-imported shard must not be
    # selected again: with parallel shard runners the DB does not yet know about
    # in-flight work, and without this exclusion two shards would contain the
    # same tracks and the same GPU work would be paid for twice (D-027).
    claimed: set[str] = set()
    for shard_dir in DEST.glob("shard-*"):
        if (shard_dir / "imported.ok").is_file():
            continue
        existing = shard_dir / "manifest.csv"
        if existing.is_file():
            with existing.open(encoding="utf-8", newline="") as handle:
                claimed.update(r["spotify_id"] for r in csv.DictReader(handle))
    selected = []
    for row in ready:
        if row["spotify_id"] in claimed:
            continue
        missing = [stage for stage in ALL_STAGES if stage not in done.get(row["spotify_id"], set())]
        if missing and Path(row["clip_path"]).is_file():
            selected.append((row, missing))
        if len(selected) >= args.size:
            break
    if len(selected) < args.minimum:
        print(json.dumps({"status": "waiting", "ready_pending": len(selected)}))
        return
    index = next_index()
    shard = DEST / f"shard-{index:04d}"
    clips = shard / "clips"
    clips.mkdir(parents=True, exist_ok=False)
    bundled_rows = []
    for row, missing in selected:
        source = Path(row["clip_path"])
        os.link(source, clips / f"{row['spotify_id']}{source.suffix}")
        bundled = dict(row)
        bundled["clip_path"] = shard_clip_path(shard, row["spotify_id"], source.suffix)
        bundled["required_stages"] = ",".join(missing)
        bundled_rows.append(bundled)
    write_manifest(shard / "manifest.csv", bundled_rows)
    bundle = build_bundle(shard)
    print(json.dumps({"status": "ready", "shard": str(shard), "tracks": len(selected),
                      "bytes": bundle.stat().st_size}))


if __name__ == "__main__":
    main()

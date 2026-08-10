#!/usr/bin/env python3
"""Cheap A/B: does half precision change what the GPU stages actually say?

Half precision roughly doubles GPU throughput, but only matters if the
labels a DJ reads stay the same. This builds a tiny shard from tracks that
were ALREADY analysed in float32 (so the comparison costs nothing but the
new run), re-runs only MAEST and CLAP under AUDIO_FP16=1, and reports label
agreement against the stored float32 answers.

    ./.venv/bin/python validate_fp16.py --build --size 20   # make the shard
    # run it on a pod, then:
    ./.venv/bin/python validate_fp16.py --compare data/fp16_probe/results.jsonl

DECIDE ON: top-1 genre, top-3 genre set, and mood/instrument tag overlap.
A drop of a percent or two is the "small quality hit" the owner accepted;
anything larger means leave float32 in place.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "data" / "fp16_probe"
SHARDS = ROOT / "data" / "cloud_full_shards"
FIELDS = ["spotify_id", "track_name", "artist_names", "album_name", "isrc",
          "source_path", "clip_path", "segment_start", "segment_seconds",
          "coverage_mode", "genre_tags", "mood_tags", "rhythm_pattern",
          "prepared_at", "required_stages"]


def stored_results() -> dict[tuple[str, str], dict]:
    """The float32 answers we already paid for, keyed by (track, stage)."""
    found = {}
    for results in sorted(SHARDS.glob("shard-*/results.jsonl")):
        for line in results.open(encoding="utf-8"):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "success" and row.get("stage") in {"maest_full", "clap_full"}:
                found[(row["spotify_id"], row["stage"])] = row["result"]
    return found


def build(size: int) -> None:
    stored = stored_results()
    clips = {p.stem: p for p in (ROOT / "data" / "cloud_full" / "clips").glob("*.opus")
             if not p.name.endswith(".partial.opus")}
    # Only tracks whose clip survived pruning AND that have both stored stages.
    usable = [t for t in clips
              if (t, "maest_full") in stored and (t, "clap_full") in stored]
    chosen = usable[:size]
    if not chosen:
        raise SystemExit("no track has both a surviving clip and stored float32 results")
    (PROBE / "clips").mkdir(parents=True, exist_ok=True)
    rows = []
    for track in chosen:
        target = PROBE / "clips" / f"{track}.opus"
        if not target.exists():
            os.link(clips[track], target)
        rows.append({f: "" for f in FIELDS} | {
            "spotify_id": track,
            "clip_path": str(target.relative_to(ROOT)),
            "segment_seconds": f"{stored[(track, 'maest_full')].get('track_duration', 300):.3f}",
            "coverage_mode": "full_track",
            "required_stages": "maest_full,clap_full",
        })
    with (PROBE / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    subprocess.run(["tar", "-cf", str(PROBE / "bundle.tar"), "-C", str(ROOT),
                    *[s for s in ("cloud_audio_full.py", "analyze_local_genres.py",
                                  "analyze_local_semantics.py", "analyze_local_rhythm.py",
                                  "analyze_essentia_full.py", "audio_taxonomy.py",
                                  "musicdb.py", "requirements-cloud-audio.txt")],
                    str((PROBE / "manifest.csv").relative_to(ROOT)),
                    str((PROBE / "clips").relative_to(ROOT))], check=True)
    print(f"probe shard ready: {len(rows)} tracks, {PROBE}")
    print("run on a pod with AUDIO_FP16=1, only maest_full + clap_full stages")


def tags(result: dict, key: str, limit: int = 3) -> list[str]:
    return [item["tag"] for item in (result.get(key) or [])[:limit]]


def compare(path: Path) -> None:
    stored = stored_results()
    fresh = {}
    for line in path.open(encoding="utf-8"):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") == "success":
            fresh[(row["spotify_id"], row["stage"])] = row["result"]
    checks = {"genre top-1": 0, "genre top-3 set": 0, "mood top-3 set": 0}
    totals = {k: 0 for k in checks}
    for (track, stage), new in sorted(fresh.items()):
        old = stored.get((track, stage))
        if not old:
            continue
        if stage == "maest_full":
            a, b = tags(old, "genres"), tags(new, "genres")
            totals["genre top-1"] += 1
            checks["genre top-1"] += bool(a and b and a[0] == b[0])
            totals["genre top-3 set"] += 1
            checks["genre top-3 set"] += set(a) == set(b)
        else:
            a, b = tags(old, "moods"), tags(new, "moods")
            totals["mood top-3 set"] += 1
            checks["mood top-3 set"] += set(a) == set(b)
    for label, hits in checks.items():
        n = totals[label]
        print(f"  {label:<16} {hits}/{n}" + (f"  {100*hits/n:.0f}%" if n else "  (no data)"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.build:
        build(args.size)
    elif args.compare:
        compare(args.compare)
    else:
        parser.error("use --build or --compare")


if __name__ == "__main__":
    main()

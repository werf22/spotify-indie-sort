#!/usr/bin/env python3
"""Analyse chosen tracks IMMEDIATELY, ahead of the nightly queue.

WHY IT EXISTS: the normal pipeline batches 200 tracks per shard and works
through a backlog, so a track the owner just clicked could wait hours. This
takes the same four stages and the same code path, but on a shard of only the
tracks asked for.

WHY IT IS STILL THE CLOUD and not the Mac: three of the four models would run
here (Beat This, CLAP, MAEST are installed) but `essentia` is not, and it builds
badly on Apple Silicon. Running three stages locally and one remotely would mean
two code paths and two definitions of "analysed"; a small shard costs a few
minutes and keeps one.

WHY IT IS FAST ANYWAY: the cost of a normal shard is its 1.5 GB upload. Five
tracks are about 35 MB — seconds, not half an hour. The pod still needs ~5 min
to install dependencies, so expect roughly 8-12 minutes end to end.

USAGE
  ./.venv/bin/python analyze_now.py --ids 4vgKa...,3hv5I...
  ./.venv/bin/python analyze_now.py --ids ... --json     # machine-readable
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "cloud_full"
SHARDS = ROOT / "data" / "cloud_full_shards"
POD_ATTEMPTS = 5     # community hosts fail to boot often enough to matter
STAGES = ("rhythm_full", "maest_full", "essentia_full", "clap_full")


def log(msg: str, machine: bool) -> None:
    print(json.dumps({"msg": msg}) if machine else msg, flush=True)


def already_done(ids: list[str]) -> set[str]:
    import sqlite3
    db = sqlite3.connect(ROOT / "data" / "music.db", timeout=60)
    try:
        marks = ",".join("?" * len(ids))
        rows = db.execute(
            f"""SELECT spotify_id FROM audio_analysis_artifacts
                WHERE spotify_id IN ({marks}) AND stage IN (?,?,?,?)
                GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4""",
            (*ids, *STAGES)).fetchall()
        return {r[0] for r in rows}
    finally:
        db.close()


def ensure_clips(ids: list[str], machine: bool) -> list[str]:
    """Transcode any missing clips, using the normal clip factory."""
    clips = SOURCE / "clips"
    missing = [i for i in ids if not (clips / f"{i}.opus").is_file()]
    if missing:
        log(f"pripravujem {len(missing)} klipov…", machine)
        subprocess.run([str(ROOT / ".audio-venv/bin/python"),
                        "prepare_cloud_audio_pilot.py", "--ids", ",".join(missing),
                        "--codec", "opus", "--full-track", "--workers", "4",
                        "--output", "data/cloud_full"],
                       cwd=ROOT, capture_output=True, timeout=1800)
    return [i for i in ids if (clips / f"{i}.opus").is_file()]


def build_express_shard(ids: list[str], machine: bool) -> Path:
    """A shard directory holding only these tracks."""
    with (SOURCE / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = {r["spotify_id"]: r for r in csv.DictReader(handle)}
        fields = list(next(iter(rows.values())).keys())
    picked = [rows[i] for i in ids if i in rows]
    if not picked:
        raise SystemExit("žiadny z týchto trackov nemá pripravený klip")

    shard = SHARDS / f"express-{time.strftime('%Y%m%d-%H%M%S')}"
    (shard / "clips").mkdir(parents=True, exist_ok=True)
    for row in picked:
        src = SOURCE / "clips" / f"{row['spotify_id']}.opus"
        dst = shard / "clips" / src.name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
        # the pod reads clips relative to the shard, not the staging area
        row["clip_path"] = str(dst.relative_to(ROOT))
    with (shard / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(picked)

    # Use the REAL bundle builder, not a hand-rolled tar. The pod runs
    # cloud_audio_full.py and its helpers FROM the bundle, and an express tar of
    # only the manifest and clips left the pod with no analysis code at all:
    # "python: can't open file '/workspace/cloud_audio_full.py'". Sharing this
    # function means the express path can never drift from the nightly one.
    import build_cloud_full_shard as builder
    builder.build_bundle(shard)
    size = (shard / "bundle.tar").stat().st_size / 1e6
    log(f"shard {shard.name}: {len(picked)} trackov, {size:.0f} MB", machine)
    return shard


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", required=True, help="comma-separated spotify ids")
    ap.add_argument("--json", action="store_true", help="one JSON object per line")
    args = ap.parse_args()
    machine = args.json

    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    if not ids:
        sys.exit("no ids given")
    done = already_done(ids)
    todo = [i for i in ids if i not in done]
    if done:
        log(f"{len(done)} už zanalyzovaných, preskakujem", machine)
    if not todo:
        log("všetky vybrané tracky sú už hotové", machine)
        return

    ready = ensure_clips(todo, machine)
    if not ready:
        sys.exit("nepodarilo sa pripraviť ani jeden klip (chýba súbor?)")
    shard = build_express_shard(ready, machine)

    # A community pod that never boots is common and is NOT a reason to fail the
    # whole request — the nightly loop just takes the next one, and someone
    # waiting on a single track deserves the same. Try a few hosts before giving
    # up, and say which attempt is running so the app can show it.
    for attempt in range(1, POD_ATTEMPTS + 1):
        log(f"spúšťam pod… (pokus {attempt}/{POD_ATTEMPTS})", machine)
        proc = subprocess.run([str(ROOT / ".venv/bin/python"), "runpod_full_shard.py",
                               "--shard", str(shard)],
                              cwd=ROOT, capture_output=True, text=True, timeout=5400)
        if proc.returncode == 0:
            break
        tail = " ".join((proc.stderr or proc.stdout).split())[-220:]
        if attempt == POD_ATTEMPTS:
            log(f"CHYBA: {tail}", machine)
            sys.exit(1)
        log(f"pod nenabehol ({tail[-90:]}) — skúšam iný", machine)
    got = already_done(ready)
    log(f"hotovo: {len(got)} z {len(ready)} zanalyzovaných", machine)


if __name__ == "__main__":
    main()

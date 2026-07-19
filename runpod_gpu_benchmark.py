#!/usr/bin/env python3
"""Bounded three-track GPU price/performance benchmark; never funds an account."""

from __future__ import annotations

import json
import os
import shlex
import statistics
import subprocess
import time
from pathlib import Path

import runpod_pilot as rp


ROOT = Path(__file__).resolve().parent
GPU = os.getenv("BENCHMARK_GPU", "NVIDIA GeForce RTX 4090")
WORK = ROOT / "data" / ("gpu_benchmark_" + GPU.rsplit(" ", 1)[-1].lower())
RESULTS = WORK / "results.jsonl"
WORK.mkdir(parents=True, exist_ok=True)

rp.PILOT = WORK
rp.BUNDLE = ROOT / "data" / "cloud_full_smoke" / "cloud-full-smoke.tar"
rp.CHECKSUM = rp.BUNDLE.with_suffix(".tar.sha256")
rp.STATE = WORK / "runpod_state.json"
rp.RESULTS = RESULTS
rp.GPU_CANDIDATES = (GPU,)


def upload(command: str) -> None:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [str(rp.BUNDLE), f"{target}:/workspace/benchmark.tar"]
    rp.run(args, timeout=900)
    rp.save_state(status="uploaded")


def analyze(command: str) -> float:
    remote = r"""set -euo pipefail
cd /workspace
tar -xf benchmark.tar
if ! command -v ffmpeg >/dev/null; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
export FFMPEG_PATH="$(command -v ffmpeg)"
python -m venv --system-site-packages /workspace/musicdb-venv
source /workspace/musicdb-venv/bin/activate
python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt
out=data/cloud_full_smoke/benchmark-results.jsonl
python cloud_audio_full.py --manifest data/cloud_full_smoke/manifest.csv --output "$out" --stage essentia_full --device cuda &
essentia_pid=$!
python cloud_audio_full.py --manifest data/cloud_full_smoke/manifest.csv --output "$out" --stage rhythm_full --device cuda
python cloud_audio_full.py --manifest data/cloud_full_smoke/manifest.csv --output "$out" --stage maest_full --device cuda
python cloud_audio_full.py --manifest data/cloud_full_smoke/manifest.csv --output "$out" --stage clap_full --device cuda
wait "$essentia_pid"
"""
    started = time.monotonic()
    proc = subprocess.run(rp.ssh_args(command) + ["bash", "-lc", shlex.quote(remote)],
                          cwd=ROOT, timeout=2100)
    if proc.returncode:
        raise RuntimeError(f"benchmark failed with exit code {proc.returncode}")
    return time.monotonic() - started


def download(command: str) -> None:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [f"{target}:/workspace/data/cloud_full_smoke/benchmark-results.jsonl",
             str(RESULTS)]
    rp.run(args, timeout=300)


def main() -> None:
    rp.verify_bundle()
    rp.account_ready()
    pod_id = rp.create_pod()
    command = None
    wall = None
    try:
        command = rp.wait_for_ssh(pod_id)
        upload(command)
        wall = analyze(command)
        download(command)
    finally:
        rp.terminate(pod_id)
    rows = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines()]
    successes = [row for row in rows if row.get("status") == "success"]
    if len({(row["spotify_id"], row["stage"]) for row in successes}) != 12:
        raise SystemExit("Benchmark did not produce 12 successful track-stages")
    means = {}
    for stage in ("rhythm_full", "maest_full", "essentia_full", "clap_full"):
        means[stage] = statistics.mean(
            float(row["elapsed_seconds"]) for row in successes if row["stage"] == stage
        )
    state = rp.read_state()
    summary = {
        "gpu": state.get("gpu"), "hourly_cost_usd": state.get("hourly_cost_usd"),
        "tracks": 3, "wall_seconds_including_setup": wall, "mean_stage_seconds": means,
    }
    (WORK / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

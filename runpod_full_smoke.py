#!/usr/bin/env python3
"""Bounded-cost RunPod validation of the full-coverage audio pipeline."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import runpod_pilot as rp


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "data" / "cloud_full_smoke"
RESULTS = WORK / "runpod-full-results.jsonl"

# Reuse the already audited account, SSH, price-ceiling and cleanup helpers.
rp.PILOT = WORK
rp.BUNDLE = WORK / "cloud-full-smoke.tar"
rp.CHECKSUM = WORK / "cloud-full-smoke.tar.sha256"
rp.STATE = WORK / "runpod_state.json"
rp.RESULTS = RESULTS


def complete() -> bool:
    if not RESULTS.is_file():
        return False
    found = set()
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("status") == "success":
                found.add((row.get("spotify_id"), row.get("stage")))
        except json.JSONDecodeError:
            continue
    return len(found) == 12


def upload(command: str) -> None:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [str(rp.BUNDLE), f"{target}:/workspace/cloud-full-smoke.tar"]
    rp.run(args, timeout=900)
    rp.save_state(status="uploaded")


def analyze(command: str) -> None:
    remote = r"""set -euo pipefail
cd /workspace
tar -xf cloud-full-smoke.tar
if ! command -v ffmpeg >/dev/null; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
export FFMPEG_PATH="$(command -v ffmpeg)"
python -m venv --system-site-packages /workspace/musicdb-venv
source /workspace/musicdb-venv/bin/activate
python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt
python - <<'PY'
import torch
assert torch.cuda.is_available(), 'CUDA unavailable'
print('CUDA:', torch.cuda.get_device_name(0), flush=True)
PY
python cloud_audio_full.py \
  --manifest data/cloud_full_smoke/manifest.csv \
  --output data/cloud_full_smoke/results.jsonl \
  --stage all --device cuda
"""
    proc = subprocess.run(rp.ssh_args(command) + ["bash", "-lc", shlex.quote(remote)],
                          cwd=ROOT, timeout=2100)
    if proc.returncode:
        raise RuntimeError(f"full smoke analysis failed with exit code {proc.returncode}")
    rp.save_state(status="analysis_complete")


def download(command: str) -> bool:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [f"{target}:/workspace/data/cloud_full_smoke/results.jsonl", str(RESULTS)]
    proc = rp.run(args, timeout=300, check=False)
    if proc.returncode == 0 and RESULTS.is_file():
        rp.save_state(status="results_downloaded",
                      result_rows=sum(1 for line in RESULTS.open(encoding="utf-8") if line.strip()))
        return True
    return False


def main() -> None:
    if complete():
        print(f"Full smoke already complete: {RESULTS}")
        return
    rp.verify_bundle()
    rp.account_ready()  # Existing balance only; this cannot add funds.
    state = rp.read_state()
    pod_id = state.get("pod_id")
    command = state.get("ssh_command") if state.get("status") != "terminated" else None
    if not pod_id or state.get("status") == "terminated":
        pod_id = rp.create_pod()
    try:
        command = command or rp.wait_for_ssh(pod_id)
        if rp.read_state().get("status") not in {"uploaded", "analysis_complete", "results_downloaded"}:
            upload(command)
        if rp.read_state().get("status") not in {"analysis_complete", "results_downloaded"}:
            analyze(command)
        if not download(command):
            raise RuntimeError("full smoke result download failed")
    finally:
        if command:
            download(command)
        rp.terminate(pod_id)
    if not complete():
        raise SystemExit("Full smoke did not produce exactly 12 successful track-stages")
    print(f"Full smoke complete: {RESULTS}")


if __name__ == "__main__":
    main()

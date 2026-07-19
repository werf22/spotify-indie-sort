#!/usr/bin/env python3
"""Run one MAEST+CLAP production shard under strict balance and time caps."""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
from datetime import timedelta
from pathlib import Path

import runpod_pilot as rp


ROOT = Path(__file__).resolve().parent
ALL_STAGES = {"rhythm_full", "maest_full", "essentia_full", "clap_full"}


def row_count(manifest: Path) -> int:
    with manifest.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def successful(results: Path) -> set[tuple[str, str]]:
    found = set()
    if not results.is_file():
        return found
    with results.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if row.get("status") == "success" and row.get("stage") in ALL_STAGES:
                    found.add((row["spotify_id"], row["stage"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return found


def required_pairs(manifest: Path) -> set[tuple[str, str]]:
    pairs = set()
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("required_stages") or "").strip()
            stages = ({item.strip() for item in raw.split(",") if item.strip()}
                      if raw else ALL_STAGES)
            pairs.update((row["spotify_id"], stage) for stage in stages)
    return pairs


def create_pod(shard: Path) -> str:
    started = rp.now()
    failures = []
    payload = selected_gpu = None
    for gpu in rp.GPU_CANDIDATES:
        command = [
            str(rp.RUNPODCTL), "pod", "create", "--template-id", "runpod-torch-v280",
            "--gpu-id", gpu, "--gpu-count", "1", "--cloud-type", "COMMUNITY",
            "--name", f"music-db-{shard.name}", "--public-ip", "--ssh", "--ports", "22/tcp",
            "--container-disk-in-gb", "30", "--volume-in-gb", "10",
            "--volume-mount-path", "/workspace",
            "--stop-after", rp.iso(started + timedelta(minutes=180)),
            "--terminate-after", rp.iso(started + timedelta(minutes=210)),
        ]
        proc = rp.run(command, timeout=120, check=False)
        if proc.returncode:
            failures.append(f"{gpu}: {(proc.stderr or proc.stdout)[-250:]}")
            continue
        try:
            payload = json.loads(proc.stdout)
            selected_gpu = gpu
            break
        except json.JSONDecodeError:
            failures.append(f"{gpu}: invalid response")
    if not payload:
        raise RuntimeError("No bounded GPU available: " + " | ".join(failures))
    pod_id = str(payload.get("id") or payload.get("pod", {}).get("id") or "")
    rp.save_state(pod_id=pod_id, status="created", created_at=rp.iso(started), gpu=selected_gpu,
                  ssh_command=None, termination_response=None, result_rows=0,
                  stop_after=rp.iso(started + timedelta(minutes=180)),
                  terminate_after=rp.iso(started + timedelta(minutes=210)))
    details = rp.ctl("pod", "get", pod_id, check=False)
    hourly = float(details.get("costPerHr") or details.get("costPerHour") or 0)
    if hourly > rp.MAX_HOURLY_USD:
        rp.terminate(pod_id)
        raise RuntimeError(f"Pod price ${hourly:.3f}/h exceeds ceiling")
    rp.save_state(hourly_cost_usd=hourly or None)
    return pod_id


def upload(command: str, bundle: Path, results: Path) -> None:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [str(bundle), f"{target}:/workspace/full-shard.tar"]
    rp.run(args, timeout=2400)
    if results.is_file() and results.stat().st_size:
        resume_args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
        if port:
            resume_args += ["-P", port]
        if identity:
            resume_args += ["-i", identity]
        resume_args += [str(results), f"{target}:/workspace/resume-results.jsonl"]
        rp.run(resume_args, timeout=600)
    rp.save_state(status="uploaded")


def analyze(command: str, relative: str) -> None:
    remote = f"""set -euo pipefail
cd /workspace
tar -xf full-shard.tar
if ! command -v ffmpeg >/dev/null; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
export FFMPEG_PATH=\"$(command -v ffmpeg)\"
python -m venv --system-site-packages /workspace/musicdb-venv
source /workspace/musicdb-venv/bin/activate
python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt
mkdir -p {relative}
if [[ -s /workspace/resume-results.jsonl ]]; then cp /workspace/resume-results.jsonl {relative}/results.jsonl; fi
python cloud_audio_full.py --manifest {relative}/manifest.csv --output {relative}/results.jsonl --stage essentia_full --device cuda &
essentia_pid=$!
python cloud_audio_full.py --manifest {relative}/manifest.csv --output {relative}/results.jsonl --stage rhythm_full --device cuda
python cloud_audio_full.py --manifest {relative}/manifest.csv --output {relative}/results.jsonl --stage maest_full --device cuda
python cloud_audio_full.py --manifest {relative}/manifest.csv --output {relative}/results.jsonl --stage clap_full --device cuda
wait "$essentia_pid"
"""
    proc = subprocess.run(rp.ssh_args(command) + ["bash", "-lc", shlex.quote(remote)],
                          cwd=ROOT, timeout=10500)
    if proc.returncode:
        raise RuntimeError(f"Remote shard failed with exit code {proc.returncode}")
    rp.save_state(status="analysis_complete")


def download(command: str, remote_path: str, results: Path) -> bool:
    target, port, identity = rp.connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [f"{target}:/workspace/{remote_path}/results.jsonl", str(results)]
    proc = rp.run(args, timeout=600, check=False)
    if proc.returncode == 0 and results.is_file():
        rp.save_state(status="results_downloaded", result_rows=len(successful(results)))
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=Path, required=True)
    args = parser.parse_args()
    shard = args.shard.resolve()
    manifest, bundle = shard / "manifest.csv", shard / "bundle.tar"
    results, state = shard / "results.jsonl", shard / "runpod_state.json"
    count = row_count(manifest)
    required = required_pairs(manifest)
    if required <= successful(results):
        print(f"Shard already complete: {shard}")
        return
    rp.PILOT, rp.BUNDLE = shard, bundle
    rp.CHECKSUM, rp.STATE, rp.RESULTS = shard / "bundle.tar.sha256", state, results
    rp.verify_bundle()
    rp.account_ready()  # Existing credit only. No funding endpoint exists here.
    saved = rp.read_state()
    pod_id = saved.get("pod_id")
    command = saved.get("ssh_command") if saved.get("status") != "terminated" else None
    if not pod_id or saved.get("status") == "terminated":
        pod_id = create_pod(shard)
    remote_path = str(shard.relative_to(ROOT))
    try:
        command = command or rp.wait_for_ssh(pod_id)
        if rp.read_state().get("status") not in {"uploaded", "analysis_complete", "results_downloaded"}:
            upload(command, bundle, results)
        if rp.read_state().get("status") not in {"analysis_complete", "results_downloaded"}:
            analyze(command, remote_path)
        if not download(command, remote_path, results):
            raise RuntimeError("Shard result download failed")
    finally:
        if command:
            download(command, remote_path, results)
        rp.terminate(pod_id)
    if not required <= successful(results):
        raise SystemExit("Shard is incomplete")
    subprocess.run([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "import_full_audio_results.py"),
        "--results", str(results), "--manifest", str(manifest),
    ], cwd=ROOT, check=True, timeout=1800)
    print(f"Shard complete: {shard} tracks={count}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the fp16 validation probe on one bounded pod. NO database import.

Executes only MAEST+CLAP over the 20-track probe shard with AUDIO_FP16=1,
downloads results.jsonl for validate_fp16.py --compare, and deletes the pod.
Results are deliberately never imported: they would overwrite production
float32 artifacts for those tracks (the importer replaces by track/stage).

Detached remote execution + marker polling per the standing rule: a local
network drop cannot kill the paid run.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import runpod_pilot as rp

ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "data" / "fp16_probe"
rp.PILOT, rp.STATE, rp.RESULTS = PROBE, PROBE / "runpod_state.json", PROBE / "results.jsonl"

REMOTE = """set -uo pipefail
cd /workspace
tar -xf probe.tar
if ! command -v ffmpeg >/dev/null 2>&1; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
export FFMPEG_PATH="$(command -v ffmpeg)"
python -m venv --system-site-packages /workspace/venv
source /workspace/venv/bin/activate
python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt
export AUDIO_FP16=1
python cloud_audio_full.py --manifest data/fp16_probe/manifest.csv --output data/fp16_probe/results.jsonl --stage maest_full --device cuda
python cloud_audio_full.py --manifest data/fp16_probe/manifest.csv --output data/fp16_probe/results.jsonl --stage clap_full --device cuda
touch /workspace/probe.done
"""


def create_pod() -> str:
    started = rp.now()
    failures = []
    for gpu in rp.GPU_CANDIDATES:
        proc = rp.run([
            str(rp.RUNPODCTL), "pod", "create", "--template-id", "runpod-torch-v280",
            "--gpu-id", gpu, "--gpu-count", "1", "--cloud-type", "COMMUNITY",
            "--name", "probe-fp16-musicdb", "--public-ip", "--ssh", "--ports", "22/tcp",
            "--container-disk-in-gb", "30", "--volume-in-gb", "10",
            "--volume-mount-path", "/workspace",
            "--stop-after", rp.iso(started + timedelta(minutes=45)),
            "--terminate-after", rp.iso(started + timedelta(minutes=55)),
        ], timeout=120, check=False)
        if proc.returncode:
            failures.append(f"{gpu}: {' '.join((proc.stderr or proc.stdout).split())[:120]}")
            continue
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failures.append(f"{gpu}: invalid response")
            continue
        pod_id = str(payload.get("id") or payload.get("pod", {}).get("id") or "")
        details = rp.ctl("pod", "get", pod_id, check=False)
        hourly = float(details.get("costPerHr") or details.get("costPerHour") or 0)
        if hourly > rp.MAX_HOURLY_USD:
            rp.terminate(pod_id)
            failures.append(f"{gpu}: ${hourly:.2f}/h over ceiling")
            continue
        rp.save_state(pod_id=pod_id, status="created", gpu=gpu,
                      hourly_cost_usd=hourly, created_at=rp.iso(started))
        print(f"probe pod {pod_id} on {gpu} at ${hourly:.2f}/h", flush=True)
        return pod_id
    raise SystemExit("no GPU available for probe: " + " | ".join(failures))


def main() -> None:
    funds = float(rp.ctl("user").get("clientBalance") or 0)
    if funds < 1.0:
        raise SystemExit(f"balance ${funds:.2f} below the $1 floor; not starting")
    # Community hosts are flaky (dead SSH, dropped uploads). Each failed
    # attempt costs cents and cleanup is verified, so try up to 3 pods before
    # giving up rather than needing a human relaunch per bad host.
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            run_probe()
            return
        except (RuntimeError, TimeoutError, SystemExit) as exc:
            last_error = exc
            print(f"probe attempt {attempt} failed: {str(exc)[:160]}", flush=True)
            time.sleep(30)
    raise SystemExit(f"all probe attempts failed; last: {last_error}")


def run_probe() -> None:
    pod_id = create_pod()
    try:
        command = rp.wait_for_ssh(pod_id)
        target, port, identity = rp.connection_parts(command)
        scp = ["scp", *rp.SSH_HARDENING]
        if port:
            scp += ["-P", port]
        if identity:
            scp += ["-i", identity]
        for attempt in range(1, 4):
            try:
                rp.run(scp + [str(PROBE / "bundle.tar"), f"{target}:/workspace/probe.tar"],
                       timeout=900)
                break
            except Exception as exc:
                if attempt == 3:
                    raise
                print(f"upload attempt {attempt} failed ({str(exc)[:80]}); retrying", flush=True)
                time.sleep(20 * attempt)
        write = subprocess.run(rp.ssh_args(command) + ["cat > /workspace/probe.sh"],
                               input=REMOTE, text=True, capture_output=True, timeout=60)
        if write.returncode:
            raise SystemExit("writing probe.sh failed: " + write.stderr[-300:])
        start = subprocess.run(
            rp.ssh_args(command)
            + ["nohup bash /workspace/probe.sh > /workspace/probe.log 2>&1 & echo go"],
            text=True, capture_output=True, timeout=60)
        if start.returncode or "go" not in start.stdout:
            raise SystemExit("launch failed: " + (start.stderr or start.stdout)[-300:])
        print("detached probe running; polling for the done marker", flush=True)
        deadline = time.monotonic() + 40 * 60
        log_tail = ""
        while time.monotonic() < deadline:
            time.sleep(20)
            try:
                query = subprocess.run(
                    rp.ssh_args(command)
                    + ["ls /workspace/probe.done 2>/dev/null; echo @@; tail -c 300 /workspace/probe.log 2>/dev/null"],
                    text=True, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                continue
            if query.returncode:
                continue
            head, _, log_tail = query.stdout.partition("@@")
            if "probe.done" in head:
                break
        else:
            raise SystemExit(f"probe timed out; log tail: {log_tail[-300:]}")
        rp.run(scp + [f"{target}:/workspace/data/fp16_probe/results.jsonl",
                      str(PROBE / "results.jsonl")], timeout=300)
        print("results downloaded", flush=True)
    finally:
        rp.terminate(pod_id)
    print("probe complete; pod deleted", flush=True)


if __name__ == "__main__":
    main()

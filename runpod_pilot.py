#!/usr/bin/env python3
"""Launch, run, retrieve and destroy the bounded RunPod audio pilot.

Safety invariants:
- refuse to start without a funded account or a verified local bundle;
- one bounded community GPU on demand, with a $0.40/hour ceiling;
- server-side stop after 25 minutes and terminate after 35 minutes;
- always attempt result retrieval and Pod deletion in ``finally``;
- persist non-secret state so an interrupted local run can resume cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNPODCTL = Path.home() / ".local" / "bin" / "runpodctl"
PILOT = ROOT / "data" / "cloud_pilot"
BUNDLE = PILOT / "cloud-audio-pilot.tar"
CHECKSUM = BUNDLE.with_suffix(".tar.sha256")
STATE = PILOT / "runpod_state.json"
RESULTS = PILOT / "runpod-results.jsonl"
# Tried in order; anything over MAX_HOURLY_USD is handed straight back and
# the next candidate is tried. Ordered cheapest-capable first. RTX 3090
# community stock is frequently "Low", which is what starves throughput, so
# the list keeps several sub-ceiling alternatives.
GPU_CANDIDATES = (
    "NVIDIA GeForce RTX 3090",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A4000",
    "NVIDIA GeForce RTX 4090",
)
MAX_HOURLY_USD = 0.40


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(args: list[str], timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess:
    # errors='replace': pod output is not guaranteed valid UTF-8 (progress bars,
    # non-ASCII tags in track names, a transfer truncated mid-codepoint). A
    # decode error here used to kill the whole run rather than the one line.
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          errors='replace', timeout=timeout)
    if check and proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args[:3])}: {(proc.stderr or proc.stdout)[-1500:]}")
    return proc


def ctl(*args: str, timeout: int = 60, check: bool = True):
    proc = run([str(RUNPODCTL), *args], timeout=timeout, check=check)
    if not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid runpodctl JSON: {proc.stdout[-1200:]}") from exc


def verify_bundle() -> None:
    if not RUNPODCTL.is_file():
        raise SystemExit(f"runpodctl missing: {RUNPODCTL}")
    if not BUNDLE.is_file() or not CHECKSUM.is_file():
        raise SystemExit("cloud pilot bundle/checksum missing; run build_cloud_pilot_bundle.sh")
    expected = CHECKSUM.read_text(encoding="utf-8").split()[0]
    digest = hashlib.sha256()
    with BUNDLE.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise SystemExit("cloud pilot bundle SHA-256 mismatch")


def account_ready() -> dict:
    account = ctl("user")
    balance = float(account.get("clientBalance") or 0)
    if balance < 1.0:
        raise SystemExit(f"RunPod account needs credit before pilot (current balance ${balance:.2f})")
    if float(account.get("currentSpendPerHr") or 0) > MAX_HOURLY_USD:
        raise SystemExit("RunPod already has unexpected hourly spend; refusing to add a Pod")
    return account


def pilot_complete() -> bool:
    if not RESULTS.is_file():
        return False
    successful = set()
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("status") == "success":
                successful.add((row.get("spotify_id"), row.get("stage")))
        except json.JSONDecodeError:
            continue
    return len(successful) >= 300


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(**values) -> dict:
    state = {**read_state(), **values, "updated_at": iso(now())}
    tmp = STATE.with_suffix(".partial.json")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE)
    return state


def create_pod() -> str:
    started = now()
    payload = None
    selected_gpu = None
    failures = []
    for gpu in GPU_CANDIDATES:
        command = [
            str(RUNPODCTL), "pod", "create", "--template-id", "runpod-torch-v280",
            "--gpu-id", gpu, "--gpu-count", "1", "--cloud-type", "COMMUNITY",
            "--name", "music-db-audio-pilot", "--public-ip", "--ssh",
            "--ports", "22/tcp", "--container-disk-in-gb", "30",
            "--volume-in-gb", "10", "--volume-mount-path", "/workspace",
            "--stop-after", iso(started + timedelta(minutes=25)),
            "--terminate-after", iso(started + timedelta(minutes=35)),
        ]
        proc = run(command, timeout=120, check=False)
        if proc.returncode:
            failures.append(f"{gpu}: {(proc.stderr or proc.stdout)[-300:]}")
            continue
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failures.append(f"{gpu}: invalid response {proc.stdout[-300:]}")
            continue
        selected_gpu = gpu
        break
    if not payload or not selected_gpu:
        raise RuntimeError("no bounded-price GPU available: " + " | ".join(failures))
    pod_id = str(payload.get("id") or payload.get("pod", {}).get("id") or "")
    if not pod_id:
        raise RuntimeError(f"Pod creation returned no id: {payload}")
    save_state(pod_id=pod_id, status="created", created_at=iso(started), gpu=selected_gpu,
               ssh_command=None, termination_response=None, result_rows=0,
               stop_after=iso(started + timedelta(minutes=25)),
               terminate_after=iso(started + timedelta(minutes=35)))
    details = ctl("pod", "get", pod_id, check=False)
    hourly = float(details.get("costPerHr") or details.get("costPerHour") or 0)
    if hourly > MAX_HOURLY_USD:
        terminate(pod_id)
        raise RuntimeError(f"Pod price ${hourly:.3f}/h exceeds ${MAX_HOURLY_USD:.2f}/h ceiling")
    save_state(hourly_cost_usd=hourly or None)
    return pod_id


def find_ssh_command(value) -> str | None:
    strings = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found = find_ssh_command(child)
            if found:
                strings.append(found)
    elif isinstance(value, list):
        for child in value:
            found = find_ssh_command(child)
            if found:
                strings.append(found)
    # Prefer full SSH over public IP because it supports SCP.
    for item in strings:
        if item.strip().startswith("ssh ") and "root@" in item and "ssh.runpod.io" not in item:
            return item.strip()
    return next((item.strip() for item in strings if item.strip().startswith("ssh ")), None)


def pod_alive(pod_id: str) -> bool:
    """Does this pod still exist on the account?

    A runner that cannot reach its pod must know WHY. "Connection refused" looks
    identical whether sshd is still booting or the pod was terminated ten
    minutes ago, and retrying a dead pod burns the whole retry budget while
    holding an upload slot the orchestrator counts as busy. One cheap list call
    settles it. On an API error we answer True: assuming a pod is gone when we
    simply could not ask would abandon healthy paid work.
    """
    try:
        pods = ctl("pod", "list", check=False)
    except Exception:
        return True
    if not isinstance(pods, list):
        return True
    return any(str(p.get("id")) == str(pod_id) for p in pods if isinstance(p, dict))


def wait_for_ssh(pod_id: str, timeout_seconds: int = 330) -> str:
    """Wait for a new pod's SSH, then give up fast.

    MEASURED, not guessed: across 33 healthy shards the time from pod creation
    to SSH ready was 0-1 minutes (median 0, max 1). The old 600 s therefore did
    nothing for a good pod and billed a DUD for a full ten minutes before the
    runner moved on — and duds are common on community cloud: 152 of these
    timeouts are in the log. 180 s is three times the worst healthy case, so it
    still cannot fail a slow-but-fine pod, while a dud now costs ~3 minutes
    instead of 10.

    Raised 180 -> 330 s on 24 Aug: an on-demand analysis died outright with
    "Pod SSH not ready within 180s". A nightly shard can shrug that off and take
    the next pod; a track the owner is waiting for cannot. 330 s still abandons
    a genuinely dead host in well under six minutes.
    """
    deadline = time.monotonic() + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        info = ctl("ssh", "info", pod_id, check=False)
        command = find_ssh_command(info)
        if command and "ssh.runpod.io" not in command:
            base = ssh_args(command)
            probe = [*base[:-1], "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", base[-1], "true"]
            result = run(probe, timeout=15, check=False)
            if result.returncode == 0:
                save_state(status="ssh_ready", ssh_command=command)
                return command
            last = (result.stderr or result.stdout)[-500:]
        time.sleep(8)
    raise TimeoutError(f"Pod SSH not ready within {timeout_seconds}s: {last}")


# Shared hardening for every ssh/scp call. Community pods sit on consumer
# links that stall for tens of seconds; without keepalives a stalled TCP
# session hangs until the command timeout and the whole shard is abandoned.
SSH_HARDENING = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
    "-o", "ConnectTimeout=30",      # fail a dead host fast instead of hanging
    "-o", "ServerAliveInterval=15",  # detect a silently dropped session
    "-o", "ServerAliveCountMax=4",
]


def ssh_args(command: str) -> list[str]:
    target, port, identity = connection_parts(command)
    args = ["ssh", *SSH_HARDENING]
    if port:
        args += ["-p", port]
    if identity:
        args += ["-i", identity]
    return [*args, target]


def connection_parts(command: str) -> tuple[str, str | None, str | None]:
    tokens = shlex.split(command)
    target = next((token for token in tokens if "@" in token and not token.startswith("-")), None)
    port = tokens[tokens.index("-p") + 1] if "-p" in tokens else None
    identity = tokens[tokens.index("-i") + 1] if "-i" in tokens else None
    if not target:
        raise RuntimeError(f"could not parse SSH target: {command}")
    return target, port, identity


def upload(command: str) -> None:
    target, port, identity = connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [str(BUNDLE), f"{target}:/workspace/cloud-audio-pilot.tar"]
    run(args, timeout=600)
    save_state(status="uploaded")


def remote_analyze(command: str) -> None:
    remote = r"""set -euo pipefail
cd /workspace
tar -xf cloud-audio-pilot.tar
if ! command -v ffmpeg >/dev/null; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
export FFMPEG_PATH="$(command -v ffmpeg)"
python -m venv --system-site-packages /workspace/musicdb-venv
source /workspace/musicdb-venv/bin/activate
python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt
python - <<'PY'
import torch
assert torch.cuda.is_available(), 'CUDA is unavailable'
print('CUDA:', torch.cuda.get_device_name(0), flush=True)
PY
python cloud_audio_pilot.py --manifest data/cloud_pilot/manifest.csv --output data/cloud_pilot/results.jsonl --stage all --device cuda
"""
    args = ssh_args(command) + ["bash", "-lc", shlex.quote(remote)]
    proc = subprocess.run(args, cwd=ROOT, timeout=1200)
    if proc.returncode:
        raise RuntimeError(f"remote analysis failed with exit code {proc.returncode}")
    save_state(status="analysis_complete")


def download(command: str) -> bool:
    target, port, identity = connection_parts(command)
    args = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    args += [f"{target}:/workspace/data/cloud_pilot/results.jsonl", str(RESULTS)]
    result = run(args, timeout=300, check=False)
    if result.returncode == 0 and RESULTS.is_file():
        rows = sum(1 for line in RESULTS.open(encoding="utf-8") if line.strip())
        save_state(status="results_downloaded", result_rows=rows)
        return True
    return False


def terminate(pod_id: str) -> None:
    """Delete the pod, but only record it as gone once RunPod confirms deletion.

    A transient network/DNS failure here must never be mistaken for a successful
    delete: ``ctl(..., check=False)`` swallows non-zero exits, and an error payload
    on stdout still parses as JSON, so the old code saved status="terminated"
    unconditionally. That let one shard's cleanup fail silently while the pod kept
    running and billing, untracked, and the next invocation created a second pod
    for the same shard (see docs/DECISIONS.md D-023).
    """
    result: dict = {}
    for attempt in range(3):
        result = ctl("pod", "delete", pod_id, check=False)
        if isinstance(result, dict) and result.get("deleted") is True:
            save_state(status="terminated", termination_response=result)
            return
        if attempt < 2:
            time.sleep(5)
    save_state(status="termination_unconfirmed", termination_response=result)
    print(
        f"WARNING: RunPod did not confirm pod {pod_id} was deleted "
        f"(last response: {result!r}). It may still be running and billing. "
        f"Verify manually: runpodctl pod list | grep {pod_id}",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    state = read_state()
    pod_id = state.get("pod_id")
    if args.cleanup_only:
        if pod_id:
            terminate(pod_id)
        return
    if pilot_complete():
        print(f"RunPod pilot already complete: {RESULTS}")
        return
    verify_bundle()
    account_ready()
    command = state.get("ssh_command") if state.get("status") not in {"terminated"} else None
    if not pod_id or state.get("status") == "terminated":
        pod_id = create_pod()
    try:
        command = command or wait_for_ssh(pod_id)
        if read_state().get("status") not in {"uploaded", "analysis_complete", "results_downloaded"}:
            upload(command)
        if read_state().get("status") not in {"analysis_complete", "results_downloaded"}:
            remote_analyze(command)
        if not download(command):
            raise RuntimeError("pilot result download failed")
    finally:
        if command:
            download(command)
        terminate(pod_id)
    print(f"RunPod pilot complete: {RESULTS}")


if __name__ == "__main__":
    main()

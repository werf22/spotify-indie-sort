#!/usr/bin/env python3
"""Run one full-audio production shard on a bounded RunPod GPU.

Cost-safety design (D-025):
- The analysis runs DETACHED on the pod (nohup + marker files), so a local
  network drop no longer kills paid work; the runner reconnects and resumes.
- Results are pulled INCREMENTALLY (byte-offset tail), so a crash loses at
  most one poll interval of work, never a whole shard.
- A stall watchdog aborts when results stop growing; server-side stop and
  terminate deadlines are computed from the actual pending work, not fixed.
- The pod also carries its own self-stop guard: once the run is done/failed
  and nobody collected it for ~15 minutes, it stops itself (best effort via
  the pod-scoped runpodctl credential RunPod injects into pods).
- Import is guaranteed and serialized: a shard whose results are complete is
  ALWAYS imported (idempotent), even on a resumed/crashed run — otherwise the
  builder would re-buy already-paid GPU work for those tracks.

HOW TO TWEAK: timing knobs live in the CONSTANTS block below.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import shlex
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import runpod_pilot as rp


ROOT = Path(__file__).resolve().parent
ALL_STAGES = {"rhythm_full", "maest_full", "essentia_full", "clap_full"}

# --- CONSTANTS (safe to tweak) -------------------------------------------
POLL_SECONDS = 60          # how often the runner checks the pod
SETUP_GRACE_MIN = 25       # no-progress allowance while models install/download
STALL_MIN = 15             # abort when results stop growing this long (post-grace)
DONE_SELF_STOP_MIN = 15    # pod stops itself this long after done/fail markers
MAX_RELAUNCH = 2           # remote pipeline restarts before giving up
PER_STAGE_SECONDS = {"rhythm_full": 30, "maest_full": 10,
                     "essentia_full": 12, "clap_full": 10}
CAP_SAFETY = 1.35          # multiplier on the per-stage estimate
CAP_BASE_MIN = 25          # fixed setup+margin minutes added to the cap
IMPORT_LOCK = ROOT / "data" / "cloud_full_shards" / "import.lock"


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


def estimate_caps(pending: set[tuple[str, str]]) -> tuple[timedelta, timedelta]:
    """Stop/terminate offsets sized to the actual pending work of this shard."""
    seconds = sum(PER_STAGE_SECONDS.get(stage, 15) for _, stage in pending)
    stop = timedelta(minutes=CAP_BASE_MIN, seconds=seconds * CAP_SAFETY)
    stop = max(timedelta(minutes=45), min(stop, timedelta(hours=6)))
    return stop, stop + timedelta(minutes=30)


def create_pod(shard: Path, pending: set[tuple[str, str]]) -> str:
    started = rp.now()
    stop_off, term_off = estimate_caps(pending)
    failures = []
    payload = selected_gpu = None
    for gpu in rp.GPU_CANDIDATES:
        command = [
            str(rp.RUNPODCTL), "pod", "create", "--template-id", "runpod-torch-v280",
            "--gpu-id", gpu, "--gpu-count", "1", "--cloud-type", "COMMUNITY",
            "--name", f"music-db-{shard.name}", "--public-ip", "--ssh", "--ports", "22/tcp",
            "--container-disk-in-gb", "30", "--volume-in-gb", "10",
            "--volume-mount-path", "/workspace",
            "--stop-after", rp.iso(started + stop_off),
            "--terminate-after", rp.iso(started + term_off),
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
    rp.save_state(pod_id=pod_id, status="created", created_at=rp.iso(started),
                  gpu=selected_gpu, ssh_command=None, termination_response=None,
                  result_rows=0, pending_pairs=len(pending),
                  stop_after=rp.iso(started + stop_off),
                  terminate_after=rp.iso(started + term_off))
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
    rp.run(args + [str(bundle), f"{target}:/workspace/full-shard.tar"], timeout=2400)
    if results.is_file() and results.stat().st_size:
        rp.run(args + [str(results), f"{target}:/workspace/resume-results.jsonl"], timeout=600)
    rp.save_state(status="uploaded")


def remote_script(shard_rel: str) -> str:
    """The detached pipeline the pod runs on its own; markers report the outcome."""
    return f"""set -uo pipefail
cd /workspace
SHARD="{shard_rel}"
trap 'touch "$SHARD/run.fail"' ERR
if [[ ! -f /workspace/.setup_done ]]; then
  tar -xf full-shard.tar
  if ! command -v ffmpeg >/dev/null 2>&1; then apt-get update -qq && apt-get install -y -qq ffmpeg; fi
  python -m venv --system-site-packages /workspace/musicdb-venv
  source /workspace/musicdb-venv/bin/activate
  python -m pip install --disable-pip-version-check -q -r requirements-cloud-audio.txt && touch /workspace/.setup_done
else
  source /workspace/musicdb-venv/bin/activate
fi
export FFMPEG_PATH="$(command -v ffmpeg)"
if [[ -s /workspace/resume-results.jsonl && ! -s "$SHARD/results.jsonl" ]]; then
  cp /workspace/resume-results.jsonl "$SHARD/results.jsonl"
fi
rm -f "$SHARD/run.done" "$SHARD/run.fail"
(
  while true; do
    sleep 240
    if [[ -f "$SHARD/run.done" || -f "$SHARD/run.fail" ]]; then
      sleep {DONE_SELF_STOP_MIN * 60}
      if [[ -f "$SHARD/run.done" || -f "$SHARD/run.fail" ]] \\
         && command -v runpodctl >/dev/null 2>&1 && [[ -n "${{RUNPOD_POD_ID:-}}" ]]; then
        runpodctl stop pod "$RUNPOD_POD_ID" || true
      fi
      exit 0
    fi
  done
) >/dev/null 2>&1 &
set -e
python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage essentia_full --device cuda &
ESSENTIA_PID=$!
python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage rhythm_full --device cuda
python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage maest_full --device cuda
python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage clap_full --device cuda
wait "$ESSENTIA_PID"
touch "$SHARD/run.done"
"""


def launch_remote(command: str, shard_rel: str) -> None:
    script = remote_script(shard_rel)
    write = subprocess.run(rp.ssh_args(command) + ["cat > /workspace/run.sh"],
                          input=script, text=True, cwd=ROOT, timeout=60,
                          capture_output=True)
    if write.returncode:
        raise RuntimeError(f"could not write run.sh: {write.stderr[-400:]}")
    start = subprocess.run(
        rp.ssh_args(command)
        + ["nohup bash /workspace/run.sh > /workspace/run.log 2>&1 & echo launched"],
        text=True, cwd=ROOT, timeout=60, capture_output=True)
    if start.returncode or "launched" not in start.stdout:
        raise RuntimeError(f"could not launch run.sh: {(start.stderr or start.stdout)[-400:]}")
    rp.save_state(status="analysis_started")


def poll(command: str, shard_rel: str) -> dict | None:
    """One cheap SSH round-trip: markers, results size, runner liveness, log tail."""
    probe = (f'for f in run.done run.fail; do [ -f "{shard_rel}/$f" ] && echo "$f"; done; echo @@; '
             f'stat -c %s "{shard_rel}/results.jsonl" 2>/dev/null || echo 0; echo @@; '
             f'pgrep -f "cloud_audio_full.py --manifest {shard_rel}" >/dev/null && echo alive || echo dead; echo @@; '
             f'tail -n 2 /workspace/run.log 2>/dev/null | tr "\\n" "|"')
    proc = subprocess.run(rp.ssh_args(command) + [f"cd /workspace && {probe}"],
                          text=True, cwd=ROOT, timeout=40, capture_output=True)
    if proc.returncode:
        return None
    parts = proc.stdout.split("@@")
    if len(parts) < 4:
        return None
    try:
        size = int(parts[1].strip() or 0)
    except ValueError:
        size = 0
    return {"done": "run.done" in parts[0], "fail": "run.fail" in parts[0],
            "size": size, "alive": "alive" in parts[2], "log": parts[3].strip()[-300:]}


def fetch_delta(command: str, shard_rel: str, results: Path) -> None:
    """Append only the new bytes of the remote results file (append-only JSONL)."""
    offset = results.stat().st_size if results.is_file() else 0
    proc = subprocess.run(
        rp.ssh_args(command) + [f"tail -c +{offset + 1} /workspace/{shard_rel}/results.jsonl"],
        cwd=ROOT, timeout=300, capture_output=True)
    if proc.returncode == 0 and proc.stdout:
        with results.open("ab") as handle:
            handle.write(proc.stdout)
        rp.save_state(result_rows=len(successful(results)))


def drive(command: str, shard_rel: str, results: Path) -> None:
    """Babysit the detached run until done; raise on stall/failure/deadline."""
    state = rp.read_state()
    deadline = datetime.fromisoformat(state["terminate_after"].replace("Z", "+00:00"))
    launched_at = rp.now()
    last_size, last_growth = -1, time.monotonic()
    relaunches = ssh_failures = 0
    status = poll(command, shard_rel)
    if status is None or not (status["alive"] or status["done"] or status["fail"]):
        launch_remote(command, shard_rel)
    while True:
        time.sleep(POLL_SECONDS)
        if rp.now() > deadline + timedelta(minutes=10):
            raise RuntimeError("terminate_after deadline passed; pod is gone server-side")
        status = poll(command, shard_rel)
        if status is None:
            ssh_failures += 1
            if ssh_failures % 5 == 0:
                print(f"pod unreachable x{ssh_failures}; work continues detached", flush=True)
            continue
        ssh_failures = 0
        if status["size"] != last_size:
            last_size, last_growth = status["size"], time.monotonic()
            fetch_delta(command, shard_rel, results)
        if status["done"]:
            fetch_delta(command, shard_rel, results)
            rp.save_state(status="analysis_complete")
            return
        if status["fail"]:
            fetch_delta(command, shard_rel, results)
            raise RuntimeError(f"remote pipeline failed: {status['log']}")
        grace = (rp.now() - launched_at) < timedelta(minutes=SETUP_GRACE_MIN)
        stalled = (time.monotonic() - last_growth) > STALL_MIN * 60
        if not status["alive"] and not grace:
            if relaunches < MAX_RELAUNCH:
                relaunches += 1
                print(f"runner died; relaunching ({relaunches}/{MAX_RELAUNCH})", flush=True)
                launch_remote(command, shard_rel)
                last_growth = time.monotonic()
                continue
            raise RuntimeError("remote runner died repeatedly")
        if stalled and not grace:
            raise RuntimeError(f"no result growth for {STALL_MIN} min; log: {status['log']}")


def run_import(results: Path, manifest: Path) -> None:
    """Serialized, idempotent import; the lock keeps parallel runners civil."""
    IMPORT_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with IMPORT_LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        subprocess.run([
            str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "import_full_audio_results.py"),
            "--results", str(results), "--manifest", str(manifest),
        ], cwd=ROOT, check=True, timeout=1800)
    (results.parent / "imported.ok").write_text(rp.iso(rp.now()) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=Path, required=True)
    args = parser.parse_args()
    shard = args.shard.resolve()
    manifest, bundle = shard / "manifest.csv", shard / "bundle.tar"
    results, state = shard / "results.jsonl", shard / "runpod_state.json"
    required = required_pairs(manifest)
    if required <= successful(results):
        run_import(results, manifest)  # idempotent; heals crashed-before-import runs
        print(f"Shard already complete, import verified: {shard}")
        return
    rp.PILOT, rp.BUNDLE = shard, bundle
    rp.CHECKSUM, rp.STATE, rp.RESULTS = shard / "bundle.tar.sha256", state, results
    rp.verify_bundle()
    rp.account_ready()  # Existing credit only. No funding endpoint exists here.
    saved = rp.read_state()
    pod_id = saved.get("pod_id")
    dead = saved.get("status") in {"terminated", "termination_unconfirmed"}
    command = saved.get("ssh_command") if not dead else None
    if not pod_id or dead:
        pod_id = create_pod(shard, required - successful(results))
    shard_rel = str(shard.relative_to(ROOT))
    try:
        command = command or rp.wait_for_ssh(pod_id)
        if rp.read_state().get("status") not in {"uploaded", "analysis_started",
                                                 "analysis_complete", "results_downloaded"}:
            upload(command, bundle, results)
        drive(command, shard_rel, results)
        rp.save_state(status="results_downloaded", result_rows=len(successful(results)))
    finally:
        if command:
            try:
                fetch_delta(command, shard_rel, results)
            except Exception:
                pass  # best effort; incremental copies already banked the work
        rp.terminate(pod_id)
    if not required <= successful(results):
        raise SystemExit("Shard is incomplete")
    run_import(results, manifest)
    print(f"Shard complete: {shard} tracks={row_count(manifest)}")


if __name__ == "__main__":
    main()

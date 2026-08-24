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
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonl_io
import runpod_pilot as rp


ROOT = Path(__file__).resolve().parent
ALL_STAGES = {"rhythm_full", "maest_full", "essentia_full", "clap_full"}

# --- CONSTANTS (safe to tweak) -------------------------------------------
POLL_SECONDS = 60          # how often the runner checks the pod
SETUP_GRACE_MIN = 40       # no-progress allowance while models install/download (setup is silent; slow hosts need it)
STALL_MIN = 15             # abort when results stop growing this long (post-grace)
BARREN_MIN = 8             # abort when rows keep arriving but NONE succeed
MIN_VCPU = 12              # reject only the thinnest hosts. 16 was too greedy for
                           # the actual market: the log showed 21 rejections in
                           # 300 lines (8 and 12 vCPU offers), each costing a
                           # create+terminate cycle, to chase a measured 8%
                           # end-to-end gain (D-044). 12 still skips the 8-vCPU
                           # hosts, which a load of 5.65/6 showed are saturated.
VCPU_ATTEMPTS = 2          # one floored sweep, then take whatever is free
                           # (bounds the create/terminate churn a thin market causes)
DONE_SELF_STOP_MIN = 15    # pod stops itself this long after done/fail markers
MAX_RELAUNCH = 2           # remote pipeline restarts before giving up
# Wall-clock seconds per TRACK, not per stage-pair: since D-037 the four stages
# run concurrently, so a shard's duration is set by the slowest stage, not by
# their sum. The old model summed 62 s of per-stage time per track and produced
# a 5.1 h cap for a shard that actually takes 0.4-0.9 h — meaning a wedged pod
# whose local runner had died could bill five hours before the server-side stop.
# 17 s is the worst of the last twelve measured shards (median is ~8 s).
WALL_SECONDS_PER_TRACK = 17
CAP_SAFETY = 1.5           # multiplier on the wall-clock estimate
CAP_BASE_MIN = 30          # fixed setup+upload margin added to the cap
IMPORT_LOCK = ROOT / "data" / "cloud_full_shards" / "import.lock"


def row_count(manifest: Path) -> int:
    with manifest.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def successful(results: Path) -> set[tuple[str, str]]:
    found = set()
    if not jsonl_io.exists(results):
        return found
    with jsonl_io.open_jsonl(results) as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if row.get("status") == "success" and row.get("stage") in ALL_STAGES:
                    found.add((row["spotify_id"], row["stage"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return found


MAX_PAIR_ATTEMPTS = 3  # a (track, stage) pair that failed this often has a
                       # deterministic cause (unreadable clip, degenerate
                       # embedding); retrying it buys a GPU pod that CANNOT
                       # succeed. Raise only if a transient cause is proven.

# Failures caused by the POD, not by the track. These must never count toward
# the quarantine: one host with a wedged CUDA driver wrote 375 of them in a
# single run (D-041), and counting those would have permanently retired 375
# perfectly analysable tracks — silent data loss dressed up as a clean finish.
ENVIRONMENTAL_ERRORS = ("CUDA", "cuDNN", "No CUDA GPUs", "out of memory",
                        "ModuleNotFoundError", "Can't load the model",
                        "Connection", "Timeout", "device-side assert")


def environmental(error: str) -> bool:
    return any(token.lower() in (error or "").lower() for token in ENVIRONMENTAL_ERRORS)


def poisoned(results: Path, pending: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """Pending pairs that already failed MAX_PAIR_ATTEMPTS times, with the last error.

    Without this a single unanalysable track keeps a 200-track shard forever
    "incomplete", so the orchestrator re-buys a pod for it on every cycle —
    observed on shard-0130: 21 identical EffNet failures, 21 paid launches.
    """
    if not jsonl_io.exists(results) or not pending:
        return {}
    attempts: dict[tuple[str, str], int] = {}
    last: dict[tuple[str, str], str] = {}
    with jsonl_io.open_jsonl(results) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (row.get("spotify_id"), row.get("stage"))
            if key in pending and row.get("status") != "success":
                error = str(row.get("error") or "unknown")[:200]
                if environmental(error):
                    continue          # the pod failed, not the track
                attempts[key] = attempts.get(key, 0) + 1
                last[key] = error
    return {key: last[key] for key, count in attempts.items()
            if count >= MAX_PAIR_ATTEMPTS}


def analysable(manifest: Path, results: Path) -> set[tuple[str, str]]:
    """Required pairs minus the ones proven unanalysable (see poisoned()).

    Quarantined pairs are written to quarantine.json next to the results so the
    loss is auditable instead of silent — the shard then counts as complete and
    its other 199 tracks get imported.
    """
    required = required_pairs(manifest)
    dead = poisoned(results, required - successful(results))
    if dead:
        (results.parent / "quarantine.json").write_text(
            json.dumps({f"{tid}:{stage}": err for (tid, stage), err in sorted(dead.items())},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    return required - set(dead)


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
    """Stop/terminate offsets sized to the actual pending work of this shard.

    These are the LAST line of defence: they only matter when the local runner
    has died and no watchdog is left to notice. Everything else — the barren
    check, the stall check, the orphan sweep — acts within minutes. So this cap
    should comfortably clear a healthy shard and nothing more.
    """
    tracks = len({track for track, _ in pending})       # stages run concurrently
    stop = timedelta(minutes=CAP_BASE_MIN, seconds=tracks * WALL_SECONDS_PER_TRACK * CAP_SAFETY)
    # Ceiling sits just above pod_reaper.MAX_POD_MINUTES (75) so the two guards
    # tell one story: the reaper kills an idle pod at 75 min, and if the reaper
    # itself is dead RunPod kills it at 90. Both are far above a healthy shard
    # (0.4-0.9 h measured) and far below the old 5.1 h.
    stop = max(timedelta(minutes=60), min(stop, timedelta(minutes=90)))
    return stop, stop + timedelta(minutes=20)


def create_pod(shard: Path, pending: set[tuple[str, str]], vcpu_floor: int = 0) -> str:
    """Create one bounded pod. `vcpu_floor` rejects CPU-starved hosts.

    Measured on three live pods, all RTX 3090 at the SAME $0.22/h: enforced
    cgroup quotas of 6, 17.9 and 27.2 CPUs (advertised vcpuCount 8, 21, 32 —
    the advertised number does track the real quota). Every stage in this
    pipeline is CPU-bound at some point (HPSS in rhythm, TensorFlow in
    essentia), so an 8-vCPU host does the same shard for the same hourly price
    while taking far longer. vcpuCount is readable seconds after creation, long
    before the 1.3 GB upload, so a thin pod costs pennies to reject.
    """
    started = rp.now()
    stop_off, term_off = estimate_caps(pending)
    failures = []
    payload = selected_gpu = None
    selected_vcpus = 0
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
            # Keep the HEAD of stderr: CLI tools print the real reason first
            # and then dump usage, so the tail is just help text. Logging the
            # tail hid every actual cause behind "volume mount path ...".
            reason = " ".join((proc.stderr or proc.stdout).split())[:220]
            failures.append(f"{gpu}: {reason}")
            continue
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failures.append(f"{gpu}: invalid response")
            continue
        candidate_id = str(payload.get("id") or payload.get("pod", {}).get("id") or "")
        details = rp.ctl("pod", "get", candidate_id, check=False)
        hourly = float(details.get("costPerHr") or details.get("costPerHour") or 0)
        if hourly > rp.MAX_HOURLY_USD:
            # Over the owner's ceiling: give the pod back and try the NEXT
            # candidate. Previously this aborted the whole attempt, so when
            # 3090 stock ran out and only pricier 4090s were free, every
            # cycle created-and-destroyed a 4090 and never reached the
            # cheaper A4000/A5000 tiers below it.
            rp.terminate(candidate_id)
            failures.append(f"{gpu}: ${hourly:.3f}/h over ${rp.MAX_HOURLY_USD:.2f} ceiling")
            continue
        vcpus = int(details.get("vcpuCount") or 0)
        if vcpu_floor and vcpus and vcpus < vcpu_floor:
            rp.terminate(candidate_id)
            failures.append(f"{gpu}: {vcpus} vCPU below {vcpu_floor} floor")
            continue
        pod_id, selected_gpu, selected_hourly = candidate_id, gpu, hourly
        selected_vcpus = vcpus
        break
    else:
        raise RuntimeError("No bounded GPU available: " + " | ".join(failures))
    rp.save_state(pod_id=pod_id, status="created", created_at=rp.iso(started),
                  gpu=selected_gpu, ssh_command=None, termination_response=None,
                  result_rows=0, pending_pairs=len(pending),
                  hourly_cost_usd=selected_hourly or None, vcpu_count=selected_vcpus or None,
                  stop_after=rp.iso(started + stop_off),
                  terminate_after=rp.iso(started + term_off))
    return pod_id


UPLOAD_SLOTS = 2  # concurrent 1.5 GB bundle uploads; more saturates the home
                  # uplink and starves the SSH polls of already-running pods


UPLOAD_ATTEMPTS = 3  # whole-transfer retries; each one RESUMES (see push_bundle)
CHUNK_BYTES = 4 * 1024 * 1024    # SMALLER THAN THE OBSERVED STALL POINT.
CHUNK_TIMEOUT = 90               # a stalled chunk must die FAST.
# Measured 23 Aug, second pass: 212 TimeoutExpired and every attempt moved only
# 4-7 MB before the transfer froze — so a 32 MB chunk could never finish and
# each one burned the full timeout for a few megabytes. The chunk is now smaller
# than the distance the link reliably carries, which turns a guaranteed failure
# into a series of small successes. It costs ~380 ssh handshakes per bundle
# (~12 min); the alternative was no progress at all.
# Earlier note, kept because the reasoning still holds: A chunk would move 10-25 MB,
# the connection would freeze, and the old 900 s limit then held a BILLING pod
# and one of only two upload slots for a further quarter of an hour before
# giving up. At even 0.5 MB/s a 32 MB chunk needs ~65 s, so 240 s is nearly
# four times the worst honest case — and a freeze now costs 4 minutes, not 15.
# Nothing is lost by failing early: the next attempt asks the pod how many
# bytes it already holds and resumes from exactly there.
CHUNK_RETRIES = 12               # consecutive chunk failures before giving up
# ABANDON A SLOW POD instead of nursing it. Community-cloud hosts are strangers'
# machines and their upstream varies wildly: one gave a measured 5 MB/s, another
# stalled every transfer after 4-7 MB and moved a bundle at ~0.05 MB/s. The line
# at this end was proven healthy at the same moment (0% packet loss, 35 ms, both
# APIs answering in under 0.5 s), so a crawl is the POD's fault. A replacement
# costs ~2 minutes and pods are plentiful; an hour spent crawling is not.
MIN_UPLOAD_MBPS = 0.40           # below this, the pod is not worth the wait
SPEED_CHECK_AFTER_MB = 24        # judge only once there is enough to judge on  # a stalled consumer link should not scrap a paid pod


def gpu_healthy(command: str) -> tuple[bool, str]:
    """Prove the pod's GPU actually computes, BEFORE paying to upload 1.3 GB.

    RunPod occasionally hands out a host whose driver is wedged: nvidia-smi
    answers but every CUDA context fails. Such a pod bills full price and fails
    100% of tracks, and the old byte-growth watchdog could not see it because
    failure rows grow results.jsonl exactly like successes do (observed on
    shard-0153: 375 tracks, 375 CUDA errors, still "progressing").
    """
    probe = ("python -c \"import torch;"
             "assert torch.cuda.is_available();"
             "x=torch.randn(64,64,device='cuda');"
             "assert float((x@x).sum().abs())>=0;"
             "print('gpu-ok',torch.cuda.get_device_name(0))\" 2>&1 | tail -2")
    try:
        proc = subprocess.run(rp.ssh_args(command) + [probe],
                              text=True, cwd=ROOT, timeout=180, capture_output=True)
    except subprocess.TimeoutExpired:
        return False, "gpu probe timed out"
    out = (proc.stdout or proc.stderr or "").strip()
    return ("gpu-ok" in out), " ".join(out.split())[:200]


def acquire_upload_slot():
    """Block until one of UPLOAD_SLOTS is free, and return the locked handle.

    Acquired BEFORE the pod is created, not before the upload. The pod used to
    be created first and then queue for a slot, which is invisible at 1-2 pods
    and ruinous at 16: with only two slots, fourteen pods would sit at $0.22/h
    each doing nothing but waiting their turn to receive a bundle. A pod must
    never exist unless it can start receiving work immediately.
    """
    slots = [IMPORT_LOCK.parent / f"upload-slot-{i}.lock" for i in range(UPLOAD_SLOTS)]
    IMPORT_LOCK.parent.mkdir(parents=True, exist_ok=True)
    while True:
        for slot in slots:
            handle = slot.open("w")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except BlockingIOError:
                handle.close()
        time.sleep(10)


def release_upload_slot(handle) -> None:
    """Release the slot the moment the bundle has landed — analysis does not need it."""
    try:
        handle.close()
    except OSError:
        pass


def prewarm(command: str) -> bool:
    """Start the dependency install while the 1.3 GB bundle is still uploading.

    Measured across 11 shards: 20.2 min of a 29.8 min shard is fixed overhead
    and only 9.6 min is analysis — 68% of every paid shard. Two of those
    overhead blocks are independent: the bundle upload (~8-10 min of pod time
    spent receiving) and apt+venv+pip (~8-10 min of torch/librosa/essentia).
    They ran strictly back to back because the installer lives inside run.sh,
    which only launches once the upload lands. Overlapping them removes the
    shorter of the two from every shard.

    Fail-safe by construction: if this returns False, or the install dies
    halfway, run.sh still performs the identical setup itself. The worst case
    is no speedup, never a broken shard.
    """
    target, port, identity = rp.connection_parts(command)
    args = ["scp", *rp.SSH_HARDENING]
    if port:
        args += ["-P", port]
    if identity:
        args += ["-i", identity]
    try:
        proc = rp.run(args + [str(ROOT / "requirements-cloud-audio.txt"),
                              f"{target}:/workspace/requirements-cloud-audio.txt"],
                      timeout=120, check=False)
        if proc.returncode:
            return False
        script = (
            "set -uo pipefail; cd /workspace; touch .setup_running\n"
            "if ! command -v ffmpeg >/dev/null 2>&1; then apt-get update -qq && "
            "apt-get install -y -qq ffmpeg; fi\n"
            "python -m venv --system-site-packages /workspace/musicdb-venv\n"
            "source /workspace/musicdb-venv/bin/activate\n"
            "python -m pip install --disable-pip-version-check -q "
            "-r /workspace/requirements-cloud-audio.txt && touch /workspace/.setup_done\n"
            "rm -f /workspace/.setup_running\n")
        launch = (f"cat > /workspace/prewarm.sh <<'PREWARM_EOF'\n{script}PREWARM_EOF\n"
                  "nohup bash /workspace/prewarm.sh > /workspace/prewarm.log 2>&1 & echo prewarming")
        out = subprocess.run(rp.ssh_args(command) + [launch],
                             text=True, cwd=ROOT, timeout=120, capture_output=True)
        return "prewarming" in (out.stdout or "")
    except (subprocess.TimeoutExpired, OSError):
        return False


def _ssh_args(port, identity, share: str | None = None) -> list[str]:
    """SSH arguments, optionally REUSING one connection for every chunk.

    THE REASON THIS EXISTS: the bundle goes up in 4 MB pieces, each previously a
    brand-new ssh session. A handshake to a community pod costs seconds, so at
    ~380 pieces per bundle the connection setup, not the data, became the
    transfer: pods measured 0.09-0.24 MB/s while the line itself was proven to
    do 1.96 MB/s in an independent test. Multiplexing opens ONE connection and
    every later chunk rides it, which removes that cost entirely.

    ControlPersist keeps the master alive between chunks; the socket lives in a
    per-shard path so two shards never share or clobber one another's channel.
    """
    args = ["ssh", *rp.SSH_HARDENING]
    if share:
        args += ["-o", "ControlMaster=auto", "-o", f"ControlPath={share}",
                 "-o", "ControlPersist=300"]
    if port:
        args += ["-p", port]
    if identity:
        args += ["-i", identity]
    return args


def _remote_bytes(ssh: list[str], target: str, path: str) -> int:
    """How much of the bundle is already on the pod (0 if nothing)."""
    try:
        proc = rp.run(ssh + [target, f"stat -c %s {path} 2>/dev/null || echo 0"],
                      timeout=120)
        return int((proc.stdout or "0").strip().split()[-1])
    except Exception:
        return 0


def push_bundle(ssh: list[str], target: str, bundle: Path, remote: str) -> None:
    """Send the bundle in CHUNKS that resume, instead of one 34-minute stream.

    WHY: a 1.4 GB bundle over this line takes ~34 min, and the upload saturates
    the very link its own SSH keepalives ride on — so the session was being
    dropped mid-transfer and `scp` restarted from zero every time. 555 upload
    attempts in a row failed and not one succeeded; five days of pods were
    created, billed, and terminated without analysing a single track.

    Each chunk is written straight into place with `dd seek=`, so it is
    idempotent: after any failure we ask the pod how many bytes it already has
    and carry on from exactly there. A dropped connection now costs one chunk
    (~2 min), not the whole transfer, and progress survives retries.

    HOW TO TWEAK: CHUNK_BYTES trades resume granularity against per-chunk
    overhead — smaller is more resilient on a bad line, larger is slightly
    faster on a good one.
    """
    size = bundle.stat().st_size
    sent = _remote_bytes(ssh, target, remote)
    if sent > size:                       # stale/corrupt remnant: start over
        rp.run(ssh + [target, f"rm -f {remote}"], timeout=120)
        sent = 0
    if sent:
        print(f"resuming upload at {sent/1e6:.0f} MB of {size/1e6:.0f} MB", flush=True)

    stalls = 0
    started_at, started_bytes = time.monotonic(), sent
    while sent < size:
        count = min(CHUNK_BYTES, size - sent)
        command = (f"dd of={remote} bs=1M seek={sent // (1 << 20)} "
                   f"conv=notrunc status=none")
        try:
            with bundle.open("rb") as handle:
                handle.seek(sent)
                payload = handle.read(count)
                proc = subprocess.run(ssh + [target, command], input=payload,
                                      capture_output=True, timeout=CHUNK_TIMEOUT)
            if proc.returncode:
                raise RuntimeError((proc.stderr or b"")[-300:].decode("utf-8", "replace"))
        except Exception as exc:
            stalls += 1
            # STOP retrying a pod that no longer exists. A terminated pod refuses
            # connections exactly like one whose sshd is still booting, so the
            # runner used to spend its whole retry budget talking to nothing —
            # and while it did, it held an upload slot and a shard slot that the
            # orchestrator counted as busy. Eight runners once sat like this with
            # ZERO pods alive: the pipeline was stopped while reporting itself
            # healthy.
            if not rp.pod_alive(rp.read_state().get("pod_id", "")):
                raise RuntimeError("pod disappeared mid-upload; abandoning this shard")
            if stalls > CHUNK_RETRIES:
                raise RuntimeError(f"upload stuck at {sent/1e6:.0f}/{size/1e6:.0f} MB: {exc}")
            print(f"chunk at {sent/1e6:.0f} MB failed ({str(exc)[:70]}); retrying", flush=True)
            time.sleep(10 * stalls)
            sent = _remote_bytes(ssh, target, remote)   # trust the pod, not us
            continue
        stalls = 0
        sent = _remote_bytes(ssh, target, remote)
        moved = (sent - started_bytes) / 1e6
        elapsed = time.monotonic() - started_at
        if moved >= SPEED_CHECK_AFTER_MB and elapsed > 0:
            rate = moved / elapsed
            if rate < MIN_UPLOAD_MBPS:
                raise RuntimeError(
                    f"pod uploads at {rate:.2f} MB/s (floor {MIN_UPLOAD_MBPS}); "
                    "abandoning it for a faster one")
        # HEARTBEAT. pod_reaper judges a pod by the freshness of this state file
        # (D-067) and, failing that, by results.jsonl — which does not exist yet
        # during an upload. With two upload slots sharing the uplink a bundle
        # takes ~45 min, so a silent runner looked dead exactly as the 45 min
        # setup grace expired: six pods in a row were killed at 45-47 min with
        # "0.0 MB pulled", minutes from finishing. Writing progress here is what
        # keeps them alive.
        rp.save_state(status="uploading", uploaded_mb=round(sent / 1e6),
                      upload_total_mb=round(size / 1e6))
        print(f"  uploaded {sent/1e6:.0f}/{size/1e6:.0f} MB", flush=True)

    # Prove the bytes arrived intact before a pod spends GPU time on them.
    digest = Path(str(bundle) + ".sha256").read_text().split()[0]
    proc = rp.run(ssh + [target, f"sha256sum {remote} | cut -d' ' -f1"], timeout=600)
    got = (proc.stdout or "").strip()
    if got != digest:
        rp.run(ssh + [target, f"rm -f {remote}"], timeout=120, check=False)
        raise RuntimeError(f"bundle checksum mismatch (pod {got[:12]} vs local {digest[:12]})")
    print("bundle verified on the pod", flush=True)


def upload(command: str, bundle: Path, results: Path) -> None:
    target, port, identity = rp.connection_parts(command)
    # One multiplexed channel for this shard's whole upload.
    share = f"/tmp/rp-mux-{os.getpid()}-%C"
    ssh = _ssh_args(port, identity, share=share)
    for attempt in range(1, UPLOAD_ATTEMPTS + 1):
        try:
            push_bundle(ssh, target, bundle, "/workspace/full-shard.tar")
            break
        except Exception as exc:
            # A vanished pod cannot be retried into existence — push_bundle has
            # already checked. Retrying it just burned the attempt budget and
            # logged three identical failures.
            if "pod disappeared" in str(exc) or attempt == UPLOAD_ATTEMPTS:
                raise
            print(f"upload attempt {attempt} failed ({str(exc)[:90]}); retrying", flush=True)
            time.sleep(20 * attempt)

    if results.is_file() and results.stat().st_size:
        scp = ["scp", *rp.SSH_HARDENING]
        if port:
            scp += ["-P", port]
        if identity:
            scp += ["-i", identity]
        try:
            rp.run(scp + [str(results), f"{target}:/workspace/resume-results.jsonl"], timeout=600)
        except Exception as exc:
            # Resume data is an optimization; losing it only means the pod
            # redoes work it would otherwise have skipped.
            print(f"resume upload failed, continuing without it: {str(exc)[:90]}", flush=True)
    rp.save_state(status="uploaded")


def remote_script(shard_rel: str) -> str:
    """The detached pipeline the pod runs on its own; markers report the outcome."""
    return f"""set -uo pipefail
cd /workspace
SHARD="{shard_rel}"
# RunPod injects RUNPOD_POD_ID into PID 1 and /etc/rp_environment, NOT into ssh
# sessions. Without this the self-stop guard below tested an unset variable and
# so never fired even once — a dead guard is worse than no guard, because the
# cost model assumed a finished pod would stop itself within minutes.
if [[ -f /etc/rp_environment ]]; then source /etc/rp_environment; fi
if [[ -z "${{RUNPOD_POD_ID:-}}" && -r /proc/1/environ ]]; then
  export RUNPOD_POD_ID="$(tr '\0' '\n' < /proc/1/environ | sed -n 's/^RUNPOD_POD_ID=//p')"
fi
echo "self-stop guard armed for pod ${{RUNPOD_POD_ID:-UNKNOWN}}"
trap 'touch "$SHARD/run.fail"' ERR
# A prewarm may already be installing dependencies (started during the upload).
# Wait for it rather than racing it into the same venv; fall through to doing
# the work here if it never finishes, so this path never depends on prewarm.
for _ in $(seq 1 180); do   # 15 min ceiling: the install fits inside the upload window
  [[ -f /workspace/.setup_done ]] && break
  [[ -f /workspace/.setup_running ]] || break
  sleep 5
done
# Extraction is keyed on the clips actually being present, NOT on .setup_done:
# a successful prewarm sets that flag without ever having seen the bundle.
[[ -d "$SHARD/clips" ]] || tar -xf full-shard.tar
if [[ ! -f /workspace/.setup_done ]]; then
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
      # Best effort only, and known NOT to work on current pods: the
      # RUNPOD_API_KEY RunPod injects is rejected by its own API ("Error:
      # Unauthorized", verified on a live pod both from the environment and
      # after an explicit `runpodctl config --apiKey`). A pod therefore CANNOT
      # be relied on to stop itself. The guarantees that do hold are all
      # outside the pod: the runner terminates it on completion, the
      # orchestrator's orphan sweep deletes any pod no live runner explains,
      # and --stop-after/--terminate-after are enforced by RunPod itself and
      # survive the local machine dying entirely.
      if [[ -f "$SHARD/run.done" || -f "$SHARD/run.fail" ]] \\
         && command -v runpodctl >/dev/null 2>&1 && [[ -n "${{RUNPOD_POD_ID:-}}" ]]; then
        runpodctl stop pod "$RUNPOD_POD_ID" || true
      fi
      exit 0
    fi
  done
) >/dev/null 2>&1 &
# All four stages run CONCURRENTLY so neither resource ever idles: the GPU
# schedules Beat This + MAEST + CLAP forward passes between each other while
# the CPU cores run Essentia-TF, HPSS, mel/feature extraction and decodes.
# Safe because each stage is its own process with its own model, results
# appends are flock-serialized, and (track, stage) keys are disjoint. Thread
# caps stop the four processes from oversubscribing the ~6 vCPUs. Exit codes
# are collected per stage: done only when every stage succeeded.
set +e
# Size thread pools from the container's REAL cgroup quota. nproc reports the
# host (128 on a measured pod) while the quota allowed 17.85 CPUs, and the
# previous hardcoded caps assumed 6 — so most of the paid allocation sat idle.
CPUS=$(python3 -c "
from pathlib import Path
def quota():
    try:                                   # cgroup v2
        q,p=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if q!='max': return int(float(q)/float(p))
    except Exception: pass
    try:                                   # cgroup v1 (older RunPod hosts)
        q=int(Path('/sys/fs/cgroup/cpu/cpu.cfs_quota_us').read_text())
        p=int(Path('/sys/fs/cgroup/cpu/cpu.cfs_period_us').read_text())
        if q>0: return q//p
    except Exception: pass
    return 8                               # NEVER os.cpu_count(): that is the
                                           # 128-core HOST, not our slice
print(max(2,min(32,quota())))")
ESSENTIA_T=$(( CPUS / 4 )); [ "$ESSENTIA_T" -lt 2 ] && ESSENTIA_T=2
# rhythm is the tail stage and the only CPU-bound one left at the end of a
# shard. Measured on a live 17.85-CPU pod: its HPSS pool runs 4 windows at
# OMP=2 = 8 threads, and /proc/loadavg read 8.44 — i.e. half the paid CPU idle
# while the GPU waited. Doubling its threads fills the box; thread count is a
# parallelism knob only, so per-window results are unchanged.
RHYTHM_T=$(( CPUS / 4 )); [ "$RHYTHM_T" -lt 2 ] && RHYTHM_T=2
FEATURE_T=$(( CPUS / 8 )); [ "$FEATURE_T" -lt 1 ] && FEATURE_T=1
echo "cpu quota=$CPUS essentia_threads=$ESSENTIA_T rhythm_threads=$RHYTHM_T feature_threads=$FEATURE_T"
OMP_NUM_THREADS=$ESSENTIA_T TF_NUM_INTRAOP_THREADS=$ESSENTIA_T TF_NUM_INTEROP_THREADS=2 \
  python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage essentia_full --device cuda &
ESSENTIA_PID=$!
OMP_NUM_THREADS=$RHYTHM_T python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage rhythm_full --device cuda &
RHYTHM_PID=$!
OMP_NUM_THREADS=$FEATURE_T python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage maest_full --device cuda &
MAEST_PID=$!
OMP_NUM_THREADS=$FEATURE_T python cloud_audio_full.py --manifest "$SHARD/manifest.csv" --output "$SHARD/results.jsonl" --stage clap_full --device cuda &
CLAP_PID=$!
RC=0
for pid in "$ESSENTIA_PID" "$RHYTHM_PID" "$MAEST_PID" "$CLAP_PID"; do
  wait "$pid" || RC=1
done
if [ "$RC" -eq 0 ]; then
  touch "$SHARD/run.done"
else
  touch "$SHARD/run.fail"
fi
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
             f'pgrep -f "[c]loud_audio_full.py --manifest {shard_rel}" >/dev/null && echo alive || echo dead; echo @@; '
             f'tail -n 5 /workspace/run.log 2>/dev/null | tr "\\n" "|"')
    try:
        proc = subprocess.run(rp.ssh_args(command) + [f"cd /workspace && {probe}"],
                              text=True, cwd=ROOT, timeout=40, capture_output=True)
    except subprocess.TimeoutExpired:
        # A slow/saturated uplink (e.g. parallel bundle uploads) must count as
        # "pod unreachable", never crash the runner: an uncaught timeout here
        # once killed seven healthy pods mid-analysis at once.
        return None
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
    try:
        proc = subprocess.run(
            rp.ssh_args(command) + [f"tail -c +{offset + 1} /workspace/{shard_rel}/results.jsonl"],
            cwd=ROOT, timeout=300, capture_output=True)
    except subprocess.TimeoutExpired:
        return  # transient; the next poll retries the same offset
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
    # Progress is measured in SUCCESSES: a broken GPU writes failure rows just
    # as fast as a healthy one writes results, so byte growth alone is not
    # evidence that the pod is doing anything worth paying for.
    last_ok, last_ok_growth = len(successful(results)), time.monotonic()
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
            ok_now = len(successful(results))
            if ok_now > last_ok:
                last_ok, last_ok_growth = ok_now, time.monotonic()
        if status["done"]:
            fetch_delta(command, shard_rel, results)
            rp.save_state(status="analysis_complete")
            return
        if status["fail"]:
            fetch_delta(command, shard_rel, results)
            raise RuntimeError(f"remote pipeline failed: {status['log']}")
        grace = (rp.now() - launched_at) < timedelta(minutes=SETUP_GRACE_MIN)
        stalled = (time.monotonic() - last_growth) > STALL_MIN * 60
        # Rows arriving but none of them succeeding = a pod that cannot work.
        if not grace and (time.monotonic() - last_ok_growth) > BARREN_MIN * 60:
            raise RuntimeError(f"{BARREN_MIN} min of results with no successes "
                               f"(rows grew, work did not); log: {status['log']}")
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
    # No archiving here: the per-window timelines are already stored in the DB
    # (audio_analysis_artifacts.payload_blob, json+zlib), so results.jsonl is a
    # redundant copy once imported. prune_analyzed_clips.py reclaims it, and the
    # imported.ok check in main() is what makes its absence safe.
    (results.parent / "imported.ok").write_text(rp.iso(rp.now()) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=Path, required=True)
    args = parser.parse_args()
    shard = args.shard.resolve()
    manifest, bundle = shard / "manifest.csv", shard / "bundle.tar"
    results, state = shard / "results.jsonl", shard / "runpod_state.json"
    required = analysable(manifest, results)
    if (shard / "imported.ok").is_file():
        print(f"Shard already imported: {shard}")
        return
    if required <= successful(results):
        run_import(results, manifest)  # idempotent; heals crashed-before-import runs
        print(f"Shard already complete, import verified: {shard}")
        return
    rp.PILOT, rp.BUNDLE = shard, bundle
    rp.CHECKSUM, rp.STATE, rp.RESULTS = shard / "bundle.tar.sha256", state, results
    rp.verify_bundle()
    # Balance-only gate (existing credit, never funding). The account-level
    # spend sanity check lives in the orchestrator, which knows how many
    # sibling pods it is running (D-028); rp.account_ready() would refuse to
    # start any parallel runner because siblings already bill >$0.40/hr.
    funds = float(rp.ctl("user").get("clientBalance") or 0)
    if funds < 1.0:
        raise SystemExit(f"RunPod balance ${funds:.2f} below $1 floor; owner action required")
    saved = rp.read_state()
    pod_id = saved.get("pod_id")
    dead = saved.get("status") in {"terminated", "termination_unconfirmed"}
    command = saved.get("ssh_command") if not dead else None
    needs_upload = (not pod_id or dead or rp.read_state().get("status") not in
                    {"uploaded", "analysis_started", "analysis_complete", "results_downloaded"})
    # THE SLOT COMES FIRST. Creating the pod before queueing for an upload slot
    # is invisible at 1-2 pods and ruinous at 16: with UPLOAD_SLOTS=2, the other
    # fourteen would bill $0.22/h each while waiting their turn to receive a
    # bundle. Waiting here costs nothing because no pod exists yet.
    slot = acquire_upload_slot() if needs_upload else None
    try:
        if not pod_id or dead:
            # Hunt for a well-provisioned host first; settle for any pod on the last
            # attempt so a thin market can never stall the shard entirely.
            for attempt in range(VCPU_ATTEMPTS):
                floor = MIN_VCPU if attempt < VCPU_ATTEMPTS - 1 else 0
                try:
                    pod_id = create_pod(shard, required - successful(results), vcpu_floor=floor)
                    break
                except RuntimeError as exc:
                    if attempt == VCPU_ATTEMPTS - 1:
                        raise
                    print(f"no pod with >={MIN_VCPU} vCPU ({exc}); retrying", flush=True)
    except BaseException:
        if slot:
            release_upload_slot(slot)
        raise
    shard_rel = str(shard.relative_to(ROOT))
    try:
        command = command or rp.wait_for_ssh(pod_id)
        if needs_upload:
            healthy, detail = gpu_healthy(command)
            if not healthy:
                raise RuntimeError(f"pod GPU unusable before upload: {detail}")
            if prewarm(command):
                print("dependency install started; uploading bundle alongside it", flush=True)
            upload(command, bundle, results)
        if slot:                       # analysis does not need the uplink
            release_upload_slot(slot)
            slot = None
        drive(command, shard_rel, results)
        rp.save_state(status="results_downloaded", result_rows=len(successful(results)))
    finally:
        if slot:
            release_upload_slot(slot)
        if command:
            try:
                fetch_delta(command, shard_rel, results)
            except Exception:
                pass  # best effort; incremental copies already banked the work
        rp.terminate(pod_id)
    required = analysable(manifest, results)  # re-check: this run may have proven a pair dead
    if not required <= successful(results):
        raise SystemExit("Shard is incomplete")
    run_import(results, manifest)
    print(f"Shard complete: {shard} tracks={row_count(manifest)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independent watchdog: no RunPod pod may bill unless it is provably working.

WHAT IT DOES
Every REAP_INTERVAL seconds it lists every `music-db-*` pod on the account and
judges each one against evidence, then terminates the ones that fail:

  UNMANAGED  no runner process owns this shard      -> kill after 3 min
  EXPIRED    pod older than MAX_POD_MINUTES         -> kill
  STALLED    past setup grace, results not growing  -> kill after 12 min
  WORKING    results grew recently                  -> left alone

WHY IT EXISTS SEPARATELY
The runner babysits its own pod and the orchestrator sweeps orphans, but both
died together on 2026-08-11 when a large upload saturated the uplink: two pods
kept billing with nobody watching (D-049). A guard that shares a process — or a
failure mode — with the thing it guards is not a guard. This runs on its own,
holds no locks, and needs only `runpodctl` plus the local results files.

WHY IT JUDGES ON LOCAL FILES, NOT SSH
Results are pulled to `data/cloud_full_shards/<shard>/results.jsonl` as they are
produced, so growth in that file is direct proof the pod is doing paid work.
That check costs nothing, cannot hang, and stays honest when SSH is unreachable
— which is exactly when pods get abandoned.

HOW TO TWEAK
The four constants below are the whole policy. MAX_POD_MINUTES is the hard time
box: no pod outlives it, whatever it claims to be doing. Raise SETUP_GRACE_MIN
if pods legitimately need longer before their first result (slow uplink, big
bundles); lower NO_PROGRESS_MIN to reap stalled pods sooner, at the risk of
killing a pod that is merely slow.

USAGE
  ./.venv/bin/python pod_reaper.py --once --dry-run   # show verdicts, kill nothing
  ./.venv/bin/python pod_reaper.py --once             # one pass, real kills
  ./.venv/bin/python pod_reaper.py                    # loop forever (run detached)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import runpod_pilot as rp

ROOT = Path(__file__).resolve().parent
SHARDS = ROOT / "data" / "cloud_full_shards"
LOG = ROOT / "data" / "pod_reaper.log"

# --- POLICY (safe to tweak) ----------------------------------------------
REAP_INTERVAL = 120     # seconds between passes
MAX_POD_MINUTES = 100   # HARD time box. Measured reality after D-065: the
                        # 1.4 GB bundle needs ~34 min on a 685 KB/s uplink and
                        # the four stages ~25 min, so a HEALTHY shard runs ~60
                        # min. At the old 75 a slow night killed pods minutes
                        # before they delivered. Worst case a wedged pod now
                        # bills 100 min (~$0.37) before the box ends it.
SETUP_GRACE_MIN = 45    # no results expected before this. Must exceed the real
                        # upload time or the reaper kills pods mid-transfer: at
                        # the measured 685 KB/s a 1.3 GB bundle needs ~32 min,
                        # and killing then throws away everything already sent.
NO_PROGRESS_MIN = 12    # after grace, results must grow within this or the pod dies
# Statuses that mean the runner is actively doing paid work.
WORKING_STATUSES = {"ssh_ready", "uploading", "uploaded", "analysis_started"}
UNMANAGED_GRACE_MIN = 3 # a pod whose shard has no runner process (covers spawn races)


def log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} {message}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


# A runner is a PYTHON process running the script — not any process whose
# command line merely mentions it. Matching loosely is dangerous in the
# permissive direction: a monitor, a grep, or an editor holding the filename
# would make an abandoned pod look managed and spare it from the reaper.
# Caught live: a shell wrapper containing the string was counted as a runner
# while no runner existed at all.
# Anchored on a python interpreter so a shell wrapper or grep cannot pose as a
# runner, but the PATHS must tolerate spaces: this project lives under
# "/Users/jakub/Appky Claude/...". An earlier \S*-based pattern could not span
# that space, matched nothing, and so declared every pod unmanaged — the reaper
# then killed healthy pods every 3 minutes and stalled the pipeline completely.
# `(?!-)` rejects `python -c "...runpod_full_shard.py --shard ..."` and `python
# -m ...`: a real runner is invoked as `python <path>/runpod_full_shard.py`, so
# the token after the interpreter is a PATH, never a flag. Without this an
# unrelated python one-liner quoting the pattern registers as a runner and can
# spare the very pod the reaper exists to kill.
RUNNER_RE = re.compile(
    r"^\S*[Pp]ython[0-9.]*\s+(?!-)\S*.*?runpod_full_shard\.py\s+--shard\s+(.+?)\s*$")


def live_runner_shards() -> set[str]:
    """Shard names that currently have a real runner process babysitting them."""
    try:
        out = subprocess.run(["ps", "-eo", "args="],
                             capture_output=True, text=True, timeout=30).stdout
    except (subprocess.TimeoutExpired, OSError):
        return set()                      # unknown: the caller must not kill on this
    found = set()
    for line in out.splitlines():
        match = RUNNER_RE.match(line.strip())
        if match:
            found.add(Path(match.group(1)).name)
    return found


def results_progress(shard: Path) -> tuple[int, float]:
    """(bytes of results pulled so far, minutes since that file last grew)."""
    results = shard / "results.jsonl"
    if not results.is_file():
        return 0, 1e9
    stat = results.stat()
    age_min = (time.time() - stat.st_mtime) / 60
    return stat.st_size, age_min


def pod_age_minutes(pod_id: str, state: dict) -> float:
    """Minutes since the pod was created, from our own state file."""
    created = state.get("created_at")
    if not created:
        return 0.0
    try:
        born = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (datetime.now(timezone.utc) - born).total_seconds() / 60


def shard_for_pod(pod_name: str) -> Path | None:
    """music-db-shard-0123 -> the shard directory that owns it."""
    if not pod_name.startswith("music-db-"):
        return None
    candidate = SHARDS / pod_name[len("music-db-"):]
    return candidate if candidate.is_dir() else None


def judge(pod: dict, runners: set[str], runners_known: bool) -> tuple[str, str]:
    """Return (verdict, reason). Only WORKING survives."""
    name = str(pod.get("name") or "")
    shard = shard_for_pod(name)
    if shard is None:
        return "KILL", "no shard directory owns this pod"

    state_file = shard / "runpod_state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}

    age = pod_age_minutes(str(pod.get("id") or ""), state)
    if age > MAX_POD_MINUTES:
        return "KILL", f"past the {MAX_POD_MINUTES} min hard time box (age {age:.0f} min)"

    # A pod nobody is driving cannot finish, collect, or terminate itself.
    if runners_known and shard.name not in runners and age > UNMANAGED_GRACE_MIN:
        return "KILL", f"no runner process owns {shard.name} (age {age:.0f} min)"

    # The runner records every step it completes (created -> ssh_ready ->
    # uploaded -> analysis_started) in runpod_state.json. That file is the ONLY
    # early proof a pod is working: results.jsonl does not appear until the very
    # end, so judging on results alone made a healthy shard look dead for its
    # whole ~34 min upload and ~25 min analysis, and the 45+12 min rule killed
    # it at 57 min — right before it would have delivered. A pod whose runner is
    # still reporting progress is working; one whose state has gone quiet is not.
    try:
        state_idle = (time.time() - state_file.stat().st_mtime) / 60
    except OSError:
        state_idle = 1e9
    if state.get("status") in WORKING_STATUSES and state_idle <= NO_PROGRESS_MIN:
        return "WORKING", (f"runner reported '{state.get('status')}' "
                           f"{state_idle:.0f} min ago (age {age:.0f} min)")

    size, file_idle = results_progress(shard)
    # A pod cannot be blamed for time that predates it. A RESUMED shard already
    # has a results file from an earlier run, and its mtime can be days old —
    # which killed brand-new pods with "no results in 2053 min (age 3 min)" all
    # night, over and over, because the grace below only applied to an EMPTY
    # file. Clamping to the pod's own age fixes both halves of that.
    idle_min = min(file_idle, age)
    if age <= SETUP_GRACE_MIN:
        return "WORKING", (f"in setup grace ({age:.0f}/{SETUP_GRACE_MIN} min, "
                           f"{size/1e6:.1f} MB carried over)")
    if idle_min > NO_PROGRESS_MIN:
        return "KILL", (f"no results in {idle_min:.0f} min "
                        f"(age {age:.0f} min, {size/1e6:.1f} MB pulled)")
    return "WORKING", f"results grew {idle_min:.0f} min ago ({size/1e6:.1f} MB)"


def reap(dry_run: bool) -> int:
    pods = rp.ctl("pod", "list", check=False)
    if not isinstance(pods, list):
        log("could not list pods (API unreachable); will retry next pass")
        return 0
    ours = [p for p in pods if str(p.get("name") or "").startswith("music-db-")]
    # Anything else on the account still costs money. The bitrate probe billed
    # ~2.5 h unwatched after finishing, purely because its name did not start
    # with music-db- and nothing here looked at it. Ours get the full evidence
    # test; a foreign pod gets the hard time box only, and is always LOGGED so
    # no pod can ever bill silently unnoticed.
    others = [p for p in pods if not str(p.get("name") or "").startswith("music-db-")]
    for pod in others:
        name, pod_id = str(pod.get("name") or ""), str(pod.get("id") or "")
        uptime_min = float(pod.get("uptimeSeconds") or 0) / 60
        if uptime_min > MAX_POD_MINUTES:
            log(f"KILL {name} ({pod_id}): non-shard pod past the "
                f"{MAX_POD_MINUTES} min box (up {uptime_min:.0f} min)")
            if not dry_run:
                try:
                    rp.terminate(pod_id)
                except Exception as exc:
                    log(f"     terminate failed: {type(exc).__name__}")
        else:
            log(f"NOTE {name} ({pod_id}): non-shard pod billing, up {uptime_min:.0f} min")
    if not ours:
        return 0

    # If pgrep itself failed we cannot distinguish "no runners" from "cannot
    # tell", and killing on a false negative would destroy healthy paid work.
    try:
        subprocess.run(["ps", "-eo", "args="], capture_output=True, timeout=30, check=True)
        runners_known = True
    except (subprocess.TimeoutExpired, OSError, subprocess.CalledProcessError):
        runners_known = False
    raw = live_runner_shards() if runners_known else set()

    killed = 0
    for pod in ours:
        verdict, reason = judge(pod, raw, runners_known)
        name, pod_id = pod.get("name"), str(pod.get("id") or "")
        if verdict == "WORKING":
            log(f"OK   {name}: {reason}")
            continue
        if dry_run:
            log(f"WOULD KILL {name} ({pod_id}): {reason}")
            continue
        log(f"KILL {name} ({pod_id}): {reason}")
        try:
            rp.terminate(pod_id)
            killed += 1
        except Exception as exc:                     # never let one failure stop the sweep
            log(f"     terminate failed: {type(exc).__name__}: {str(exc)[:120]}")
    return killed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="single pass, then exit")
    parser.add_argument("--dry-run", action="store_true", help="report verdicts, kill nothing")
    args = parser.parse_args()
    log(f"reaper starting (box={MAX_POD_MINUTES}min grace={SETUP_GRACE_MIN}min "
        f"stall={NO_PROGRESS_MIN}min dry_run={args.dry_run})")
    while True:
        try:
            reap(args.dry_run)
        except Exception as exc:                     # a watchdog must never die
            log(f"pass failed: {type(exc).__name__}: {str(exc)[:160]}")
        if args.once:
            return
        time.sleep(REAP_INTERVAL)


if __name__ == "__main__":
    main()

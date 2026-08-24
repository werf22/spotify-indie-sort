#!/usr/bin/env python3
"""Continuously prepare and run bounded full-audio GPU shards.

Cost-control design (D-026):
- runs 1-2 shard runners in PARALLEL, gated by account balance;
- sweeps ORPHANED pods every cycle: any RunPod pod named ``music-db-*`` that
  no shard state tracks (or that a state says was terminated long ago) is
  deleted immediately — a paid pod may never exist without owned work;
- compares actual account spend/hr against the spend the tracked pods
  explain; a mismatch blocks new launches and raises a loud status;
- appends a per-shard COST LEDGER so speed and price stay measurable;
- never funds anything (D-012): below $1 it parks and waits for the owner.

HOW TO TWEAK: the CONSTANTS block below (shard size, parallelism, balance
thresholds). EXPECTED is the immutable first-batch target (D-011).
"""

from __future__ import annotations

import csv
import fcntl
import json
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect_readonly, DB_PATH
from runpod_full_shard import required_pairs, successful


ROOT = Path(__file__).resolve().parent
SHARDS = ROOT / "data" / "cloud_full_shards"
MANIFEST = ROOT / "data" / "cloud_full" / "manifest.csv"
STATUS = SHARDS / "orchestrator_status.json"
LEDGER = SHARDS / "cost_ledger.jsonl"
LOCK = SHARDS / "orchestrator.lock"
RUNPODCTL = Path.home() / ".local" / "bin" / "runpodctl"

# --- CONSTANTS (safe to tweak) -------------------------------------------
SHARD_SIZE = 200       # bigger shards amortize pod setup cost (D-026)
MIN_BALANCE = 1.0      # below this: park and wait for the owner (D-012)
SHARD_COST_EST = 0.5   # measured ~$0.44/200-track shard; used to scale parallelism
MAX_PARALLEL = 5       # Bounded by the UPLINK, not by funds or by GPU supply.
                       # Each shard must push a 1.3 GB bundle through one of
                       # UPLOAD_SLOTS=2, which takes ~9 min, so the home line
                       # can start ~13 shards/h; a shard then occupies its pod
                       # for ~0.45 h, so ~6 pods can be kept genuinely busy.
                       # 8 leaves headroom for resumed shards that skip the
                       # upload. The old 16 was justified when a shard ran ~2 h
                       # and the upload was a rounding error; D-037 cut that to
                       # ~0.45 h and inverted the ratio. Runners above this
                       # limit are harmless since D-047 (they wait for a slot
                       # BEFORE creating a pod) but they add nothing and their
                       # polling contends for runpodctl.
                       # 3 -> 5 on 24 Aug: the bottleneck MOVED. Multiplexing the
                       # ssh connection took the upload from 0.2 MB/s to 3.6, so
                       # a 1.5 GB bundle now takes ~7 min instead of ~45 and the
                       # uplink can feed roughly eight shards an hour. Analysis
                       # (~25 min) is the slow half again, which is exactly what
                       # more pods DO help with. Earlier note, still true:
                       # 8 -> 3 on 23 Aug, from measurement rather than theory.
                       # The best hour the pipeline has ever had produced 1,400
                       # tracks — 7 shards — with about three pods working. The
                       # night it ran at 8 produced 200/h and NINE of eleven
                       # shards returned nothing: the uplink is fixed, so extra
                       # pods do not upload faster, they simply sit billing
                       # while the same bytes trickle out. Arithmetic that
                       # matches the peak: a 1.5 GB bundle at the measured
                       # 3-5 MB/s is ~8 min of upload, analysis is ~25 min, so
                       # three pods keep the line saturated and the GPUs busy.
DEAD_RUNNER_QUIET_MIN = 4  # a runner whose pod vanished is ended after this
SPEND_TOLERANCE = 0.10 # allowed gap between actual and explained spend/hr
CYCLE_SECONDS = 45
# Each shard writes a ~1.3 GB bundle before its pod starts, and build-ahead
# stacks several. With the owner's library still growing on the same disk that
# quietly ate the free space down to 29 GiB while eight shards were staged, so
# stop staging new ones when headroom gets thin. Running shards are never
# interrupted — they finish and their bundles are pruned on import.
MIN_FREE_GIB_TO_BUILD = 8.0
# 45 GiB reserved thirty times the ~3 GB a shard actually stages, and with the
# clip factory filling the same disk it deadlocked: prep ran the free space down
# to 40 GiB, the builder refused to start below 45, and nothing could ever
# consume the clips to free space again. 25 GiB still leaves ~8x headroom for a
# bundle plus its build-ahead spare. The clip factory is the greedy one and must
# yield first (its own floor is 70 GiB, well above this).
# Lowered again 22 Aug: the factory had banked 20,835 clips (140 GB) — about 70
# shards, far more than the uplink can carry — and left 22 GiB, which parked the
# builder at the old 25 GiB floor with credit sitting unused. 12 GiB is still 4x
# what one shard stages. The real fix is the BACKLOG CAP in prep_loop.sh: disk
# alone was never the right thing to throttle the factory on.
# 8 GiB from 22 Aug 13:45. With the factory paused by that cap, NOTHING adds
# clips any more, and every finished shard hands ~1.3 GB back through the GC —
# so free space can now only rise. The floor just has to be low enough to let
# the first shard through and start that recovery.


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(**values) -> None:
    SHARDS.mkdir(parents=True, exist_ok=True)
    current = {}
    try:
        current = json.loads(STATUS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    current.update(values)
    current["updated_at"] = utcnow()
    temporary = STATUS.with_suffix(".partial.json")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2,
                                    sort_keys=True), encoding="utf-8")
    temporary.replace(STATUS)


def ctl_json(*args: str, timeout: int = 60):
    proc = subprocess.run([str(RUNPODCTL), *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout)[-1000:])
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def balance() -> tuple[float, float]:
    """Account balance and current spend.

    A MISSING field is not a zero balance. `or 0` turned any partial or empty
    API response into "$0.00", which reads as "out of credit" and parks the whole
    pipeline in waiting_for_user_credit — unattended, that wastes the night for a
    transient API blip. Seen live on 20 Aug: the status tool reported $0.00 and
    0 pods while the account actually held $9.37 and two pods were analysing.
    Raising instead lets the caller retry, which is what a read failure deserves.
    """
    data = ctl_json("user")
    if not isinstance(data, dict) or "clientBalance" not in data:
        raise RuntimeError(f"balance read returned no clientBalance: {str(data)[:200]}")
    return float(data["clientBalance"] or 0), float(data.get("currentSpendPerHr") or 0)


def ready_count() -> int:
    if not MANIFEST.is_file():
        return 0
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def pending_pool() -> int:
    """Prepared tracks that still need analysing.

    NOT `ready - done`. `ready` counts rows in the CURRENT manifest while `done`
    counts every track ever analysed, so once the lifetime total passed the
    manifest size the subtraction went negative and clamped to zero — the
    orchestrator reported "waiting_for_full_tracks" and built nothing while
    12,256 tracks with clips already on disk sat idle. Compare the manifest
    against the finished set directly; the two numbers then mean the same thing.
    """
    if not MANIFEST.is_file():
        return 0
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        ids = [row.get("spotify_id") for row in csv.DictReader(handle)]
    ids = [i for i in ids if i]
    if not ids:
        return 0
    # NOT connect_readonly(): a WAL database with no live writer cannot
    # materialise its -shm from a mode=ro handle and fails with the bare
    # "unable to open database file" — which put the orchestrator into
    # `retrying` the moment no shard was writing. A plain connection reads
    # fine and, because nothing here runs DDL, never takes the write lock.
    for attempt in range(3):
        try:
            db = sqlite3.connect(DB_PATH, timeout=60)
            try:
                db.execute("PRAGMA busy_timeout=60000")
                finished = {r[0] for r in db.execute(
                    """SELECT spotify_id FROM audio_analysis_artifacts
                       WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                       GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4""")}
            finally:
                db.close()
            return sum(1 for i in ids if i not in finished)
        except sqlite3.OperationalError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return 0


def completed_count() -> int:
    with connect_readonly() as db:
        return int(db.execute(
            """SELECT COUNT(*) FROM (
                 SELECT spotify_id FROM audio_analysis_artifacts
                 WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                 GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4
               )"""
        ).fetchone()[0])


def target_count() -> int:
    """Dynamic queue size: every locally-matched track (catalog or
    local-only), not a fixed number (D-011's original 5,394 was the first
    immutable batch; the queue is append-only from here per docs/TASKS.md).
    """
    with connect_readonly() as db:
        return int(db.execute(
            "SELECT COUNT(DISTINCT spotify_id) FROM audio_files WHERE scan_status='matched'"
        ).fetchone()[0])


def shard_state(shard: Path) -> dict:
    try:
        return json.loads((shard / "runpod_state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def quarantined_pairs(shard: Path) -> set[tuple[str, str]]:
    """(track, stage) pairs this shard has already given up on, permanently.

    The runner writes them to quarantine.json with the reason — decode failures
    on damaged media, mostly. They cannot be retried into existence, so for the
    question "is this shard finished?" they count as settled.
    """
    path = shard / "quarantine.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    pairs = set()
    for key in (data or {}):
        track, _, stage = str(key).partition(":")
        if track and stage:
            pairs.add((track, stage))
    return pairs


def incomplete_shards() -> list[Path]:
    found = []
    for shard in sorted(SHARDS.glob("shard-*")):
        manifest = shard / "manifest.csv"
        if not manifest.is_file() or not (shard / "bundle.tar").is_file():
            continue
        # A track whose audio cannot be decoded will NEVER succeed, and the run
        # already recorded that in quarantine.json. Counting those pairs as
        # outstanding made the shard permanently "incomplete": the orchestrator
        # respawned a runner for it forever, and each zombie held one of only
        # five parallel slots. Two finished shards (792 and 799 rows, both with
        # imported.ok) were blocking 40% of the pipeline this way.
        required = required_pairs(manifest) - quarantined_pairs(shard)
        if not required <= successful(shard / "results.jsonl"):
            found.append(shard)
        elif not (shard / "imported.ok").is_file():
            found.append(shard)  # results complete but import never confirmed
    return found


def build(minimum: int) -> Path | None:
    proc = subprocess.run([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "build_cloud_full_shard.py"),
        "--size", str(SHARD_SIZE), "--minimum", str(minimum),
    ], cwd=ROOT, capture_output=True, text=True, timeout=1800)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout)[-1500:])
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return Path(payload["shard"]) if payload.get("status") == "ready" else None


def sweep_orphans(active: dict | None = None) -> list[str]:
    """Delete any music-db pod that no LIVE runner explains.

    A pod is not safe merely because some shard state names it: if that
    shard has no runner in `active`, nobody is polling the pod, collecting
    its results, or going to delete it — the runner died (a crash, or the
    orchestrator being restarted, which kills its children). Observed
    2026-07-29: pod 9sc258b9ht5xsy billed 3h10m in state "created" with
    zero results because its state file still "owned" it. Only the
    orchestrator spawns runners, so `active` is the authoritative answer to
    "is anyone actually working on this shard".
    """
    pods = ctl_json("pod", "list")
    if not isinstance(pods, list):
        return []
    live_shards = {s.name for s in (active or {})}
    states = {}
    for shard in SHARDS.glob("shard-*"):
        data = shard_state(shard)
        if data.get("pod_id"):
            states[data["pod_id"]] = (data, shard.name)
    deleted = []
    for pod in pods:
        pod_id = str(pod.get("id") or "")
        name = str(pod.get("name") or "")
        if not name.startswith("music-db-"):
            continue  # never touch pods this project did not create
        tracked = states.get(pod_id)
        stale = False
        if tracked is None:
            stale = True
        else:
            data, shard_name = tracked
            updated = data.get("updated_at", "1970-01-01T00:00:00Z")
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(updated.replace("Z", "+00:00"))).total_seconds()
            if data.get("status") in {"terminated", "termination_unconfirmed"}:
                stale = age > 900
            elif shard_name not in live_shards:
                # Tracked, non-terminal, but no runner is working it: an
                # abandoned pod. Grace period covers the gap between spawn()
                # and the shard appearing in `active`.
                stale = age > 600
        if stale:
            subprocess.run([str(RUNPODCTL), "pod", "delete", pod_id], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
            deleted.append(pod_id)
            print(f"ORPHAN SWEEP: deleted untracked pod {pod_id} ({name})", flush=True)
    return deleted



def sweep_dead_runners(active: dict, spawned_at: dict | None = None) -> list[str]:
    """Kill a runner whose pod no longer exists.

    THE MIRROR OF sweep_orphans. That one deletes a pod no runner owns; this one
    ends a runner whose pod is already gone. Without it the runner keeps polling
    a host that will never answer while HOLDING one of only two upload slots and
    one of three shard slots, so the orchestrator counts it as busy and starts
    nothing. Seen repeatedly: eight runners alive against a single live pod,
    expected spend $1.61 against a real $0.23, and the pipeline stopped for
    hours while every status line said `running_shards`.

    A pod is only judged missing when the pod LIST was actually readable and the
    shard's state has been quiet for a while — a runner that has just created a
    pod, or an unreadable API, must never be mistaken for a dead one.
    """
    try:
        pods = ctl_json("pod", "list")
    except Exception:
        return []                       # could not ask; assume everything is fine
    if not isinstance(pods, list):
        return []
    live = {str(p.get("id")) for p in pods if isinstance(p, dict)}
    killed = []
    for shard, proc in list(active.items()):
        state = shard_state(shard)
        pod_id = str(state.get("pod_id") or "")
        if not pod_id or pod_id in live:
            continue
        try:
            written = (shard / "runpod_state.json").stat().st_mtime
        except OSError:
            continue
        started = (spawned_at or {}).get(shard, 0)
        # THE STATE MUST BELONG TO **THIS** RUN. A shard file still names the pod
        # from the previous attempt, so judging on it alone killed every fresh
        # runner within seconds of starting — "starting shard runner" and "DEAD
        # RUNNER" alternated forever and no pod was ever created. Only act once
        # this runner has written its own state and then gone quiet.
        if written <= started:
            continue
        if (time.time() - written) / 60 < DEAD_RUNNER_QUIET_MIN:
            continue
        print(f"DEAD RUNNER: {shard.name} pod {pod_id} is gone; ending it", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass
        active.pop(shard, None)
        killed.append(shard.name)
    return killed


def ledger_append(shard: Path) -> None:
    data = shard_state(shard)
    try:
        start = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        hours = max(0.0, (end - start).total_seconds() / 3600)
        entry = {"shard": shard.name, "pod_id": data.get("pod_id"),
                 "gpu": data.get("gpu"), "hourly_usd": data.get("hourly_cost_usd"),
                 "hours": round(hours, 3),
                 "est_cost_usd": round(hours * float(data.get("hourly_cost_usd") or 0), 4),
                 "result_rows": data.get("result_rows"), "ts": utcnow()}
        with LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (KeyError, ValueError, TypeError):
        pass


def ledger_totals() -> dict:
    total_cost = total_hours = entries = 0
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                total_cost += float(row.get("est_cost_usd") or 0)
                total_hours += float(row.get("hours") or 0)
                entries += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return {"shards": entries, "hours": round(total_hours, 2),
            "cost_usd": round(total_cost, 2)}


def allowed_parallel(funds: float) -> int:
    """Concurrent pods scaled to spendable headroom above the D-012 floor.

    Each extra pod is only allowed when the balance can absorb roughly one
    more shard (~$0.50). Total cost is the same at any parallelism — this
    only controls how fast the same money is spent (D-028).
    """
    if funds < MIN_BALANCE:
        return 0
    return min(MAX_PARALLEL, max(1, int((funds - MIN_BALANCE) / SHARD_COST_EST)))


def spawn(shard: Path) -> subprocess.Popen:
    print(f"starting shard runner: {shard.name}", flush=True)
    return subprocess.Popen([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "runpod_full_shard.py"),
        "--shard", str(shard),
    ], cwd=ROOT)


def main() -> None:
    SHARDS.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        active: dict[Path, subprocess.Popen] = {}
        cooldown: dict[Path, float] = {}
        failures = 0
        spawned_at: dict = {}
        while True:
            try:
                for shard, proc in list(active.items()):
                    if proc.poll() is None:
                        continue
                    del active[shard]
                    if proc.returncode == 0:
                        failures = 0
                        ledger_append(shard)
                    else:
                        failures += 1
                        cooldown[shard] = time.monotonic() + min(300 * failures, 1800)
                done, ready, target_n = completed_count(), ready_count(), target_count()
                funds, hourly = balance()
                swept = sweep_orphans(active)
                sweep_dead_runners(active, spawned_at)
                # Compare POD COUNT, not recorded prices: a runner that has just
                # spawned has no hourly_cost_usd yet, so summing prices made
                # expected spend look like $0.22 against a real $0.90 and
                # tripped "unexplained_spend", freezing new launches while the
                # balance drained. Ours are all named music-db-*, and the sweep
                # above has already removed any pod no live runner explains, so
                # "more of our pods alive than shards we launched" is the real
                # signal — and it is immune to state-write timing.
                try:
                    ours = [x for x in (ctl_json("pod", "list") or [])
                            if str(x.get("name") or "").startswith("music-db-")]
                except Exception:
                    ours = []
                expected_spend = sum(
                    float(shard_state(s).get("hourly_cost_usd") or 0) for s in active)
                overspend = len(ours) > len(active) and not swept
                if done >= target_n and not active and not incomplete_shards():
                    write_status(phase="complete", completed_tracks=done,
                                 ready_tracks=ready, balance_usd=funds,
                                 hourly_usd=hourly, ledger=ledger_totals())
                    return
                target = 0 if overspend else allowed_parallel(funds)
                if target and len(active) < target:
                    candidates = [s for s in incomplete_shards()
                                  if s not in active
                                  and cooldown.get(s, 0) < time.monotonic()]
                    while len(active) < target:
                        if candidates:
                            shard = candidates.pop(0)
                        else:
                            if shutil.disk_usage(ROOT).free / 1024**3 < MIN_FREE_GIB_TO_BUILD:
                                break  # no headroom to stage another bundle
                            pool = pending_pool()
                            built = build(SHARD_SIZE if pool >= SHARD_SIZE else 1)
                            if built is None:
                                break
                            shard = built
                        active[shard] = spawn(shard)
                        spawned_at[shard] = time.time()
                # Build-ahead: keep exactly one spare shard bundled while all
                # slots are busy, so a finishing pod never waits ~2 min for
                # tar/bundling before its successor can launch (time win only;
                # the spare costs nothing until a runner picks it up).
                if target and len(active) >= target:
                    spare = [s for s in incomplete_shards() if s not in active]
                    pool = max(0, pending_pool() - len(active) * SHARD_SIZE)
                    if (not spare and pool >= 1
                            and shutil.disk_usage(ROOT).free / 1024**3 >= MIN_FREE_GIB_TO_BUILD):
                        build(SHARD_SIZE if pool >= SHARD_SIZE else 1)
                phase = ("waiting_for_user_credit" if funds < MIN_BALANCE
                         else "unexplained_spend" if overspend
                         else "running_shards" if active
                         else "waiting_for_full_tracks")
                write_status(
                    phase=phase, completed_tracks=done, ready_tracks=ready,
                    balance_usd=funds, hourly_usd=hourly,
                    expected_hourly_usd=round(expected_spend, 3),
                    active_shards={s.name: {
                        "pod_id": shard_state(s).get("pod_id"),
                        "status": shard_state(s).get("status"),
                        "result_rows": shard_state(s).get("result_rows"),
                    } for s in active},
                    swept_orphans=swept or None,
                    consecutive_failures=failures, last_error=None,
                    ledger=ledger_totals(),
                    note=("No automatic funding; user action required."
                          if funds < MIN_BALANCE else None))
            except Exception as exc:
                failures += 1
                write_status(phase="retrying", consecutive_failures=failures,
                             last_error=repr(exc)[-2000:])
                time.sleep(min(60 * failures, 600))
                continue
            time.sleep(CYCLE_SECONDS if funds >= MIN_BALANCE else 600)


if __name__ == "__main__":
    main()

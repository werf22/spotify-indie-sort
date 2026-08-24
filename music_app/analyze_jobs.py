#!/usr/bin/env python3
"""Run analyze_now.py in the background and let the UI watch it.

WHY A JOB REGISTRY: analysing even a handful of tracks takes minutes (a pod has
to be created and its dependencies installed), which is far too long to hold an
HTTP request open. The browser starts a job, gets an id, and polls.

ONE AT A TIME, ALWAYS. Every job used to start its own process, so asking for a
second track while the first was still going created a SECOND pod — twice the
money for work that fits on one machine. Jobs now go into a queue and a single
worker drains it. Better still, the worker takes everything that is waiting in
one go: three tracks queued while a pod is booting are analysed by one pod
instead of three, and a pod boot is the expensive part.

Jobs live in memory only. If the app is restarted mid-analysis the POD keeps
working and its results still land in the database through the normal import —
the only thing lost is the progress bar, which is the right thing to lose.
"""
from __future__ import annotations

import subprocess
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_jobs: dict[str, dict] = {}
_queue: list[str] = []                 # job ids waiting their turn, in order
_lock = threading.Lock()
_wake = threading.Event()
_worker: threading.Thread | None = None
_running = [0]                         # how many tracks the pod is chewing on now


def start(ids: list[str]) -> dict:
    """Queue a set of tracks. Returns immediately; the UI polls status()."""
    ids = [i.strip() for i in ids if i and i.strip()]
    if not ids:
        raise RuntimeError("nevybral si žiadny track")
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "ids": ids, "state": "queued", "lines": [],
           "started": time.time(), "done": 0, "total": len(ids)}
    with _lock:
        _jobs[job_id] = job
        _queue.append(job_id)
        job["ahead"] = _ahead(job_id)
        _ensure_worker()
    _wake.set()
    return _public(job)


def _ahead(job_id: str) -> int:
    """Caller holds the lock. Jobs in front of this one, plus one if a run is
    already under way — that is what the owner actually wants to know."""
    pos = _queue.index(job_id) if job_id in _queue else 0
    return pos + (1 if _running[0] else 0)


def _ensure_worker() -> None:
    """Caller holds the lock. One worker for the life of the process."""
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_drain, daemon=True)
        _worker.start()


def _drain() -> None:
    while True:
        _wake.wait(timeout=5)
        _wake.clear()
        with _lock:
            batch = [_jobs[j] for j in _queue]
            del _queue[:]
            for job in batch:
                job["state"] = "running"
                job["ahead"] = 0
            _running[0] = sum(len(j["ids"]) for j in batch)
        if not batch:
            continue
        # ONE process for everything that was waiting — one pod, not one each.
        every: list[str] = []
        for job in batch:
            for track in job["ids"]:
                if track not in every:
                    every.append(track)
        _run_batch(batch, every)


def _run_batch(batch: list[dict], ids: list[str]) -> None:
    def emit(line: str) -> None:
        with _lock:
            for job in batch:
                job["lines"] = (job["lines"] + [line])[-40:]

    if len(batch) > 1:
        emit(f"spojené {len(batch)} požiadavky do jedného behu ({len(ids)} trackov)")
    try:
        proc = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "analyze_now.py", "--ids", ",".join(ids)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        for line in proc.stdout:
            line = line.strip()
            if line:
                emit(line)
        proc.wait()
        state = "done" if proc.returncode == 0 else "failed"
    except Exception as exc:                      # never leave a job "running"
        emit(f"{type(exc).__name__}: {exc}")
        state = "failed"
    with _lock:
        for job in batch:
            job["state"] = state
            job["finished"] = time.time()
        _running[0] = 0


def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "ids"} | {"count": len(job["ids"])}


def status(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return {"error": "taká úloha neexistuje"}
        if job["state"] == "queued":
            job["ahead"] = _ahead(job_id)
        return _public(job)


def recent(limit: int = 5) -> list[dict]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j["started"])[:limit]
    return [{"id": j["id"], "state": j["state"], "total": j["total"],
             "started": j["started"]} for j in jobs]

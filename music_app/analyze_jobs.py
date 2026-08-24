#!/usr/bin/env python3
"""Run analyze_now.py in the background and let the UI watch it.

WHY A JOB REGISTRY: analysing even a handful of tracks takes minutes (a pod has
to be created and its dependencies installed), which is far too long to hold an
HTTP request open. The browser starts a job, gets an id, and polls.

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
_lock = threading.Lock()


def start(ids: list[str]) -> dict:
    ids = [i.strip() for i in ids if i and i.strip()]
    if not ids:
        raise RuntimeError("nevybral si žiadny track")
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "ids": ids, "state": "running", "lines": [],
           "started": time.time(), "done": 0, "total": len(ids)}
    with _lock:
        _jobs[job_id] = job

    def run() -> None:
        try:
            proc = subprocess.Popen(
                [str(ROOT / ".venv/bin/python"), "analyze_now.py",
                 "--ids", ",".join(ids)],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            for line in proc.stdout:
                line = line.strip()
                if line:
                    with _lock:
                        job["lines"] = (job["lines"] + [line])[-40:]
            proc.wait()
            job["state"] = "done" if proc.returncode == 0 else "failed"
        except Exception as exc:                  # never leave a job "running"
            job["state"] = "failed"
            job["lines"].append(f"{type(exc).__name__}: {exc}")
        job["finished"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return job


def status(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return {"error": "taká úloha neexistuje"}
    return {k: v for k, v in job.items() if k != "ids"} | {"count": len(job["ids"])}


def recent(limit: int = 5) -> list[dict]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j["started"])[:limit]
    return [{"id": j["id"], "state": j["state"], "total": j["total"],
             "started": j["started"]} for j in jobs]

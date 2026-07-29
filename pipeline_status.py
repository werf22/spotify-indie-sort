#!/usr/bin/env python3
"""One command, full oversight: money, pods, audio progress, workers, ETA.

Read-only and safe to run any time:
    ./.venv/bin/python pipeline_status.py

WHAT: aggregates RunPod account+pods, orchestrator phase, cost ledger,
full-audio stage counts, enrichment queue one-liners and worker liveness.
WHY: previously this needed five commands and three docs (backlog item).
HOW TO TWEAK: each section is one small function; add/remove freely.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from musicdb import connect_readonly

ROOT = Path(__file__).resolve().parent
RUNPODCTL = Path.home() / ".local" / "bin" / "runpodctl"
SHARDS = ROOT / "data" / "cloud_full_shards"


def runpod_section() -> None:
    try:
        user = json.loads(subprocess.run([str(RUNPODCTL), "user"], capture_output=True,
                                         text=True, timeout=30).stdout or "{}")
        pods = json.loads(subprocess.run([str(RUNPODCTL), "pod", "list"], capture_output=True,
                                         text=True, timeout=30).stdout or "[]")
        print(f"RunPod balance: ${float(user.get('clientBalance') or 0):.2f}  "
              f"spend/hr: ${float(user.get('currentSpendPerHr') or 0):.3f}  "
              f"pods: {len(pods) if isinstance(pods, list) else '?'}")
        for pod in pods if isinstance(pods, list) else []:
            print(f"  pod {pod.get('id')} {pod.get('name')} ${pod.get('costPerHr')}/hr")
    except Exception as exc:  # offline is a state, not a crash
        print(f"RunPod: unreachable ({str(exc)[:80]})")


def orchestrator_section() -> None:
    try:
        status = json.loads((SHARDS / "orchestrator_status.json").read_text(encoding="utf-8"))
        print(f"Orchestrator: {status.get('phase')}  completed {status.get('completed_tracks')}"
              f"/{status.get('ready_tracks')} ready  updated {status.get('updated_at', '')[:19]}")
        for name, info in (status.get("active_shards") or {}).items():
            print(f"  {name}: {info.get('status')} rows={info.get('result_rows')} pod={info.get('pod_id')}")
        ledger = status.get("ledger") or {}
        if ledger.get("shards"):
            per_track = None
            if ledger.get("cost_usd") and status.get("completed_tracks"):
                per_track = ledger["cost_usd"] / max(1, status["completed_tracks"])
            print(f"  ledger: {ledger['shards']} shards, {ledger['hours']}h, "
                  f"${ledger['cost_usd']}" + (f", ~${per_track:.4f}/track" if per_track else ""))
        if status.get("last_error"):
            print(f"  last_error: {status['last_error'][:140]}")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Orchestrator: no status file")


def audio_section() -> None:
    try:
        with connect_readonly() as db:
            full = db.execute(
                """SELECT COUNT(*) FROM (
                     SELECT spotify_id FROM audio_analysis_artifacts
                     WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                     GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4)"""
            ).fetchone()[0]
            target = db.execute(
                "SELECT COUNT(DISTINCT spotify_id) FROM audio_files WHERE scan_status='matched'"
            ).fetchone()[0]
            local_only = db.execute(
                "SELECT COUNT(*) FROM tracks WHERE library_sources='local_only'"
            ).fetchone()[0]
            stages = dict(db.execute(
                """SELECT stage, COUNT(*) FROM audio_analysis_artifacts
                   WHERE stage LIKE '%_full' GROUP BY stage"""))
            print(f"Full audio: {full}/{target} tracks all-4-stages "
                  f"(rhythm {stages.get('rhythm_full', 0)}, maest {stages.get('maest_full', 0)}, "
                  f"essentia {stages.get('essentia_full', 0)}, clap {stages.get('clap_full', 0)}) "
                  f"— of which {local_only} local_only (not in the 68,075-track Spotify catalog)")
    except Exception as exc:
        print(f"Full audio: db busy ({str(exc)[:60]})")


def providers_section() -> None:
    queries = {
        "FreqBlog": "SELECT COUNT(*) FROM freqblog_status WHERE status='success'",
        "ReccoBeats": "SELECT COUNT(*) FROM reccobeats_status WHERE status='success'",
        "Deezer": "SELECT COUNT(*) FROM deezer_status WHERE status='success'",
        "Last.fm artists": "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE source='last.fm:artist'",
        "OneTagger Discogs": "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE source='onetagger:discogs'",
    }
    parts = []
    try:
        with connect_readonly() as db:
            for name, query in queries.items():
                try:
                    parts.append(f"{name} {db.execute(query).fetchone()[0]:,}")
                except Exception:
                    continue
        print("Providers: " + "; ".join(parts))
    except Exception as exc:
        print(f"Providers: db busy ({str(exc)[:60]})")


def workers_section() -> None:
    probe = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True)
    names = {"enrichment_daemon": "daemon", "cloud_production_orchestrator": "orchestrator",
             "prepare_cloud_audio_pilot": "opus-prep", "runpod_full_shard": "shard-runner"}
    # Match the script's full path form ("/<name>.py"), so a shell or grep
    # whose command line merely mentions the name is not counted as a running
    # worker — the same self-match class of bug that once made poll() see a
    # dead pod as alive.
    alive = [label for needle, label in names.items()
             if f"/{needle}.py" in probe.stdout]
    print("Workers alive: " + (", ".join(alive) if alive else "NONE"))


def main() -> None:
    runpod_section()
    orchestrator_section()
    audio_section()
    providers_section()
    workers_section()


if __name__ == "__main__":
    main()

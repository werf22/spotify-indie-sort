"""Independent, restart-safe cloud enrichment supervisor.

Each provider owns its own loop. A slow or unavailable API therefore never
blocks Spotify metadata, Last.fm, or any other source from taking its next
batch. The macOS LaunchAgent restarts this supervisor after login or a crash.
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
STOP = threading.Event()
CHILDREN: dict[str, subprocess.Popen] = {}
CHILD_LOCK = threading.Lock()
LOG_LOCK = threading.Lock()

JOBS = [
    ("spotify-metadata", ["enrich_spotify_metadata.py", "--limit", "250", "--delay", "0.05"], 21600),
    ("spotify-albums", ["enrich_spotify_albums.py", "--limit", "150", "--delay", "0.05"], 21600),
    ("spotify-genres", ["sync_spotify_genres.py", "--limit", "5000"], 3600),
    ("lastfm-artists", ["enrich_lastfm_artists.py", "--limit", "150", "--delay", "0.45"], 2),
    ("lastfm-tracks", ["enrich_lastfm_tracks.py", "--limit", "150", "--delay", "0.45"], 2),
    ("musicbrainz", ["enrich_musicbrainz.py", "--limit", "50", "--delay", "1.10"], 2),
    ("musicbrainz-genres", ["enrich_musicbrainz_genres.py", "--limit", "30", "--delay", "1.10"], 2),
    ("reccobeats", ["enrich_reccobeats.py", "--limit", "10000", "--concurrency", "3", "--per-minute", "60"], 21600),
    ("onetagger-discogs", ["onetagger_db_bridge.py", "--limit", "100", "--delay", "2.5", "--source", "discogs_v2"], 5),
    # OneTagger's current Beatport scraper no longer matches the redesigned
    # site. Traxsource/Juno also failed the catalog smoke test, so leave them
    # disabled instead of burning CPU on known misses. Bandcamp is working.
    ("onetagger-bandcamp", ["onetagger-db/target/release/onetagger-db", "--source", "bandcamp", "--limit", "40"], 20),
    ("deezer", ["enrich_deezer.py", "--limit", "500", "--delay", "0.35"], 10),
    ("theaudiodb", ["enrich_theaudiodb.py", "--limit", "25", "--delay", "2.10"], 60),
    ("spotify-history-resolver", ["resolve_stream_history.py", "--limit", "100", "--delay", "0.1"], 3600),
    ("semantic-derivation", ["derive_semantic_tags.py"], 3600),
]

# Local maintenance jobs do not need an internet connection. Heavy model
# inference is cloud-first by default so the laptop remains cool.
LOCAL_JOBS = [
    ("audio-verification", ["run_audio_verification.py"], 10),
    # Discover newly downloaded audio and give it a database identity. Both
    # steps are offline and idempotent. Without this the indexer only ever ran
    # by hand, so ~18k files downloaded after the last manual run stayed
    # invisible to prep and the pods (found 2026-07-29). Roots come from
    # AUDIO_LIBRARY_ROOTS in .env; the hourly cadence keeps the walk cheap.
    ("audio-index", ["index_audio_files.py"], 3600),
    # Undo fuzzy matches that a later-known duration disproves, before the
    # promoter hands out identities (D-032).
    ("audio-match-verify", ["verify_match_durations.py"], 3600),
    ("audio-identity", ["promote_unmatched_local_tracks.py"], 3600),
    # Transcode newly identified tracks into analysis clips. This used to be
    # the standalone com.jakub.music-db-cloud-full-prep agent, which exits on
    # success and never restarts — so anything indexed later sat unprepared
    # forever. Owning it here closes the discover -> identity -> prep ->
    # analyze loop. --output must be given: the script defaults to the old
    # cloud_pilot directory.
    ("audio-prep", ["prepare_cloud_audio_pilot.py", "--limit", "100000",
                    "--codec", "opus", "--workers", "4", "--full-track",
                    "--output", "data/cloud_full"], 1800),
    # Reclaim clips/bundles once their analysis is safely in the database.
    # Without this the ~19k-track backlog would need ~125 GB of clips at
    # once; pruned continuously it stays a small rolling window.
    ("audio-clip-prune", ["prune_analyzed_clips.py"], 1800),
    # Independent guard: pause the whole supervisor before the internal disk
    # reaches the user's 50 GiB safety floor.  It also emits a macOS alert.
    ("disk-guard", ["sync_control.py", "check-disk"], 60),
]


def enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if enabled("LOCAL_AUDIO_ANALYSIS_ENABLED"):
    # Explicit offline fallback only. The active production path uses RunPod.
    LOCAL_JOBS.insert(0, ("audio-pipeline", ["run_local_audio_pipeline.py"], 30))


if enabled("FREQBLOG_ENABLED") and os.getenv("FREQBLOG_API_KEY", "").strip():
    # A paid-plan 100-track pilot on 2026-07-18 measured /bulk at 26 seconds,
    # 0 transport errors, versus 68-80 seconds and frequent timeouts for
    # individual /lookup calls. Two concurrent 50-item batches stayed within
    # the provider's documented concurrency guidance and returned exact quota.
    JOBS.append(("freqblog", ["enrich_freqblog.py", "--limit", "2000", "--batch-size", "50", "--concurrency", "2", "--delay", "0.2"], 5))
    JOBS.append(("freqblog-tags", ["enrich_freqblog_tags.py", "--limit", "500", "--delay", "0.12"], 30))
if enabled("SOUNDNET_ENABLED") and os.getenv("SOUNDNET_RAPIDAPI_KEY", "").strip():
    JOBS.append(("soundnet", ["enrich_soundnet.py", "--limit", "500", "--concurrency", "20"], 2))


def write(log, message: str) -> None:
    with LOG_LOCK:
        log.write(message.rstrip() + "\n")
        log.flush()


def online() -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=8):
            return True
    except OSError:
        return False


def stop(*_) -> None:
    STOP.set()
    with CHILD_LOCK:
        for child in list(CHILDREN.values()):
            if child.poll() is None:
                child.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)


def run_job(name: str, args: list[str], success_delay: int, log, requires_online: bool = True) -> None:
    offline_reported = False
    while not STOP.is_set():
        if requires_online and not online():
            if not offline_reported:
                write(log, f"{name}: internet unavailable; waiting")
                offline_reported = True
            STOP.wait(60)
            continue
        offline_reported = False
        write(log, f"{name}: starting batch")
        try:
            executable = ROOT / args[0]
            python = ROOT / (".audio-venv" if name.startswith("audio-") else ".venv") / "bin" / "python"
            command = (
                [str(executable), *args[1:]]
                if executable.exists() and os.access(executable, os.X_OK)
                else [str(python), *args]
            )
            child = subprocess.Popen(
                command,
                cwd=ROOT, stdout=log, stderr=log,
            )
            with CHILD_LOCK:
                CHILDREN[name] = child
            # Prep transcodes the whole outstanding corpus in one pass and
            # re-validates every existing clip on the way, so a full run can
            # exceed the generic audio budget. Killing it mid-pass loses the
            # newest files repeatedly (the validation restarts from scratch),
            # so give it a much longer ceiling — it is idempotent and the
            # daemon relaunches it on its own schedule anyway.
            budget = (28800 if name == "audio-prep"
                      else 7200 if name.startswith("audio-") else 3600)
            code = child.wait(timeout=budget)
            delay = success_delay if code == 0 else 30
            if code:
                write(log, f"{name}: exited {code}; retry in {delay}s")
        except subprocess.TimeoutExpired:
            child.kill()
            write(log, f"{name}: timed out; retry in 30s")
            delay = 30
        except Exception as exc:
            write(log, f"{name}: supervisor error {exc!r}; retry in 30s")
            delay = 30
        finally:
            with CHILD_LOCK:
                CHILDREN.pop(name, None)
        STOP.wait(delay)


def main() -> None:
    log_path = ROOT / "data" / "enrichment_supervisor.log"
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open("a", buffering=1) as log:
        write(log, "\n--- independent supervisor started ---")
        threads = [
            threading.Thread(target=run_job, args=(name, args, delay, log, True), name=name, daemon=True)
            for name, args, delay in JOBS
        ] + [
            threading.Thread(target=run_job, args=(name, args, delay, log, False), name=name, daemon=True)
            for name, args, delay in LOCAL_JOBS
        ]
        for thread in threads:
            thread.start()
        while not STOP.wait(1):
            pass
        for thread in threads:
            thread.join(timeout=10)
        write(log, "--- independent supervisor stopped ---")


if __name__ == "__main__":
    main()

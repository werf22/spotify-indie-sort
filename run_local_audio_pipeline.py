"""Run one bounded, sequential local-audio enrichment cycle.

Rhythm and CLAP share the Apple GPU, so they run sequentially rather than
competing for memory. Every child checkpoints per track and is safe to rerun.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(args: list[str], timeout: int) -> int:
    command = [sys.executable, str(ROOT / args[0]), *args[1:]]
    print("audio pipeline:", " ".join(args), flush=True)
    try:
        return subprocess.run(command, cwd=ROOT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print(f"audio pipeline: timed out after {timeout}s: {args[0]}", flush=True)
        return 124


def main() -> None:
    default_roots = os.pathsep.join((str(Path.home() / "Music"), str(Path.home() / "Downloads")))
    roots = [x for x in os.getenv("AUDIO_LIBRARY_ROOTS", default_roots).split(os.pathsep) if x]
    index_args = ["index_audio_files.py"]
    for root in roots:
        index_args += ["--root", root]
    run(index_args, 1800)
    rhythm_limit = os.getenv("LOCAL_RHYTHM_BATCH", "100")
    genre_limit = os.getenv("LOCAL_GENRE_BATCH", "60")
    semantic_limit = os.getenv("LOCAL_SEMANTIC_BATCH", "40")
    run(["analyze_local_rhythm.py", "--limit", rhythm_limit, "--segment-seconds", "45", "--device", "auto"], 3300)
    run(["analyze_local_genres.py", "--limit", genre_limit, "--device", "auto"], 3300)
    run(["analyze_local_semantics.py", "--limit", semantic_limit, "--device", "auto"], 3300)


if __name__ == "__main__":
    main()

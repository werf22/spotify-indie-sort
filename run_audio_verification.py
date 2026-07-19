#!/usr/bin/env python3
"""Bounded, restart-safe local file verification cycle."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(mode: str, limit: int) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "verify_audio_files.py"), "--mode", mode, "--limit", str(limit)],
        cwd=ROOT,
    ).returncode


def main() -> None:
    if run("quick", 500) == 0:
        run("deep", 100)


if __name__ == "__main__":
    main()

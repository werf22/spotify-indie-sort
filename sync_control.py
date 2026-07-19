#!/usr/bin/env python3
"""Pause/resume the sync system and enforce the free-space safety threshold."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect


ROOT = Path(__file__).resolve().parent
PLIST = Path.home() / "Library/LaunchAgents/com.jakub.local-dj-enrichment.plist"
DOMAIN = f"gui/{os.getuid()}"
LABEL = "com.jakub.local-dj-enrichment"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_paused(paused: bool, reason: str | None) -> None:
    db = connect()
    with db:
        db.execute(
            "UPDATE sync_control SET paused=?,pause_reason=?,updated_at=? WHERE id=1",
            (int(paused), reason, now()),
        )


def pause_all(reason: str = "manual") -> None:
    set_paused(True, reason)
    subprocess.run(["launchctl", "bootout", DOMAIN, str(PLIST)], capture_output=True)
    print(f"Paused: {reason}")


def resume_all() -> None:
    db = connect()
    control = db.execute("SELECT output_root,min_free_gib FROM sync_control WHERE id=1").fetchone()
    root = Path(control["output_root"] or Path.home()).expanduser()
    usage = shutil.disk_usage(root if root.exists() else Path.home())
    free = usage.free / (1024**3)
    if free <= float(control["min_free_gib"]):
        raise SystemExit(f"Cannot resume: only {free:.1f} GiB free")
    set_paused(False, None)
    subprocess.run(["launchctl", "bootstrap", DOMAIN, str(PLIST)], capture_output=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"{DOMAIN}/{LABEL}"], capture_output=True)
    print("Resumed")


def check_disk() -> None:
    db = connect()
    control = db.execute("SELECT * FROM sync_control WHERE id=1").fetchone()
    root = Path(control["output_root"] or Path.home()).expanduser()
    usage = shutil.disk_usage(root if root.exists() else Path.home())
    free = usage.free / (1024**3)
    threshold = float(control["min_free_gib"])
    if free <= threshold and not control["paused"]:
        set_paused(True, f"disk_low:{free:.1f}GiB")
        subprocess.run(
            ["osascript", "-e", f'display notification "Voľné miesto {free:.1f} GiB. Acquisition bol pozastavený." with title "Music Library Sync"'],
            capture_output=True,
        )
    print(f"free={free:.1f}GiB threshold={threshold:.1f}GiB paused={int(free <= threshold or control['paused'])}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pause-all")
    sub.add_parser("resume-all")
    sub.add_parser("check-disk")
    args = parser.parse_args()
    if args.command == "pause-all":
        pause_all()
    elif args.command == "resume-all":
        resume_all()
    else:
        check_disk()


if __name__ == "__main__":
    main()

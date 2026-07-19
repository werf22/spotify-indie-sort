#!/usr/bin/env python3
"""Follow the full-track manifest and run resumable rhythm timelines locally."""

from __future__ import annotations

import argparse
import csv
import subprocess
import time
from pathlib import Path

from cloud_audio_full import append, completed, run_rhythm


ROOT = Path(__file__).resolve().parent


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def import_new(results: Path, manifest: Path, state: Path) -> None:
    proc = subprocess.run([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "import_full_audio_results.py"),
        "--results", str(results), "--manifest", str(manifest), "--state", str(state),
    ], cwd=ROOT, timeout=600)
    if proc.returncode:
        raise RuntimeError(f"Importer failed with exit code {proc.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--expected", type=int, default=0)
    args = parser.parse_args()
    imported_since = 0
    failures = {}
    while True:
        rows = read_rows(args.manifest)
        done = completed(args.output)
        pending = [row for row in rows if (row["spotify_id"], "rhythm_full") not in done
                   and failures.get(row["spotify_id"], 0) < 4]
        for row in pending:
            if not Path(row["clip_path"]).is_file():
                row["clip_path"] = str(args.manifest.parent / "clips" /
                                       f"{row['spotify_id']}.opus")
            started = time.monotonic()
            try:
                result = run_rhythm(row, args.device)
                payload = {"spotify_id": row["spotify_id"], "stage": "rhythm_full",
                           "status": "success", "elapsed_seconds": time.monotonic() - started,
                           "result": result}
                imported_since += 1
            except Exception as exc:
                failures[row["spotify_id"]] = failures.get(row["spotify_id"], 0) + 1
                payload = {"spotify_id": row["spotify_id"], "stage": "rhythm_full",
                           "status": "error", "elapsed_seconds": time.monotonic() - started,
                           "error": repr(exc)[-2000:]}
            append(args.output, payload)
            print(f"rhythm-follow {row['spotify_id']} {payload['status']}", flush=True)
            if imported_since >= 25:
                import_new(args.output, args.manifest, args.state)
                imported_since = 0
        done = completed(args.output)
        successful = sum((row["spotify_id"], "rhythm_full") in done for row in rows)
        if imported_since and not pending:
            import_new(args.output, args.manifest, args.state)
            imported_since = 0
        print(f"rhythm-follow ready={len(rows)} successful={successful}", flush=True)
        if args.expected and len(rows) >= args.expected and successful >= args.expected:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()

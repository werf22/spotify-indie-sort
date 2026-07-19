#!/usr/bin/env python3
"""Run the measured audio-analysis pilot on a CUDA host.

The output is append-only JSONL and therefore survives pod restarts.  Each
track/stage is checkpointed immediately and reruns skip completed work.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import time
import zlib
from pathlib import Path


def completed_keys(path: Path) -> set[tuple[str, str]]:
    done = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if row.get("status") == "success":
                    done.add((row["spotify_id"], row["stage"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def append(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_rhythm(rows, output: Path, done, device: str):
    from analyze_local_rhythm import BeatTracker, VERSION, analyze, decode_segment

    tracker = BeatTracker(device)
    for index, row in enumerate(rows, 1):
        key = (row["spotify_id"], "rhythm")
        if key in done:
            continue
        started = time.monotonic()
        try:
            audio, start, duration = decode_segment(row["clip_path"], float(row["segment_seconds"]), 45.0)
            result = analyze(audio, tracker)
            payload = {"spotify_id": row["spotify_id"], "stage": "rhythm", "status": "success",
                       "model": f"beat-this+librosa/{VERSION}", "segment_start": start,
                       "segment_duration": duration, "elapsed_seconds": time.monotonic() - started,
                       "result": result}
            done.add(key)
        except Exception as exc:
            payload = {"spotify_id": row["spotify_id"], "stage": "rhythm", "status": "error",
                       "elapsed_seconds": time.monotonic() - started, "error": repr(exc)[-1500:]}
        append(output, payload)
        print(f"rhythm {index}/{len(rows)} {row['spotify_id']} {payload['status']}", flush=True)


def run_maest(rows, output: Path, done, device: str):
    from analyze_local_genres import EMBEDDING_KEY, GenreModel, decode, tags_from_probs

    model = GenreModel(device)
    for index, row in enumerate(rows, 1):
        key = (row["spotify_id"], "maest")
        if key in done:
            continue
        started = time.monotonic()
        try:
            audio, start, duration = decode(row["clip_path"], float(row["segment_seconds"]))
            probs, logits = model(audio)
            broad, styles, raw = tags_from_probs(model.labels, probs)
            packed = base64.b64encode(zlib.compress(logits.astype("<f2").tobytes(), 6)).decode("ascii")
            result = {
                "genres": [{"tag": tag, "confidence": confidence, "probability": probability}
                           for tag, confidence, probability in broad],
                "styles": [{"tag": tag, "confidence": confidence, "probability": probability}
                           for tag, confidence, probability in styles],
                "top_predictions": raw,
                "logits": {"encoding": "float16+zlib+base64", "dimensions": int(logits.size),
                           "data": packed},
            }
            payload = {"spotify_id": row["spotify_id"], "stage": "maest", "status": "success",
                       "model": EMBEDDING_KEY, "segment_start": start, "segment_duration": duration,
                       "elapsed_seconds": time.monotonic() - started, "result": result}
            done.add(key)
        except Exception as exc:
            payload = {"spotify_id": row["spotify_id"], "stage": "maest", "status": "error",
                       "elapsed_seconds": time.monotonic() - started, "error": repr(exc)[-1500:]}
        append(output, payload)
        print(f"maest {index}/{len(rows)} {row['spotify_id']} {payload['status']}", flush=True)


def run_clap(rows, output: Path, done, device: str):
    from analyze_local_semantics import EMBEDDING_KEY, SemanticModel, decode

    model = SemanticModel(device)
    for index, row in enumerate(rows, 1):
        key = (row["spotify_id"], "clap")
        if key in done:
            continue
        started = time.monotonic()
        try:
            audio, start, duration = decode(row["clip_path"], float(row["segment_seconds"]))
            vector = model.embed(audio)
            result = model.score(vector)
            array = vector[0].float().cpu().numpy().astype("<f2")
            result["_embedding"] = {
                "encoding": "float16+zlib+base64", "dimensions": int(array.size),
                "data": base64.b64encode(zlib.compress(array.tobytes(), 6)).decode("ascii"),
            }
            payload = {"spotify_id": row["spotify_id"], "stage": "clap", "status": "success",
                       "model": EMBEDDING_KEY, "segment_start": start, "segment_duration": duration,
                       "elapsed_seconds": time.monotonic() - started, "result": result}
            done.add(key)
        except Exception as exc:
            payload = {"spotify_id": row["spotify_id"], "stage": "clap", "status": "error",
                       "elapsed_seconds": time.monotonic() - started, "error": repr(exc)[-1500:]}
        append(output, payload)
        print(f"clap {index}/{len(rows)} {row['spotify_id']} {payload['status']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("data/cloud_pilot/manifest.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/cloud_pilot/results.jsonl"))
    parser.add_argument("--stage", choices=("all", "rhythm", "maest", "clap"), default="all")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--limit", type=int, default=0, help="0 means all manifest rows")
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if args.limit > 0:
        rows = rows[:args.limit]
    # The manifest records the original Mac paths for provenance. After the
    # bundle is extracted on a pod, transparently rebase clips beside it.
    for row in rows:
        if not Path(row["clip_path"]).is_file():
            suffix = Path(row["clip_path"]).suffix or ".flac"
            row["clip_path"] = str(args.manifest.parent / "clips" / f"{row['spotify_id']}{suffix}")
    done = completed_keys(args.output)
    stages = ("rhythm", "maest", "clap") if args.stage == "all" else (args.stage,)
    for stage in stages:
        {"rhythm": run_rhythm, "maest": run_maest, "clap": run_clap}[stage](
            rows, args.output, done, args.device
        )
    requested_ids = {row["spotify_id"] for row in rows}
    success = sum(1 for sid, stage in completed_keys(args.output)
                  if sid in requested_ids and stage in stages)
    print(f"cloud pilot complete: successful requested track-stages={success}/{len(rows) * len(stages)}",
          flush=True)
    if success != len(rows) * len(stages):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

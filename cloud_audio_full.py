#!/usr/bin/env python3
"""Quality-first, full-coverage cloud audio analysis.

The models themselves have short context windows.  This runner therefore
tiles the complete track, retains a temporal profile, and computes robust
track-level summaries.  Output is append-only and track/stage resumable.
"""

from __future__ import annotations

import argparse
import base64
import csv
import fcntl
import json
import os
import shutil
import subprocess
import time
import zlib
from collections import Counter
from pathlib import Path

import numpy as np


def append(path: Path, payload: dict) -> None:
    """Append one result line, safe against concurrent stage processes.

    Stages run in parallel and share this file, and these lines are large —
    CLAP reaches ~940 KB, MAEST ~380 KB — while POSIX only guarantees
    O_APPEND atomicity up to PIPE_BUF. Interleaving was NOT reproduced in a
    4-writer stress test (120/120 lines intact on APFS, with and without
    this lock), so treat it as insurance rather than a fixed bug: the pods
    run a different OS and filesystem, and the lock costs nothing measurable
    next to model inference.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def completed(path: Path) -> set[tuple[str, str]]:
    found = set()
    if not path.is_file():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if row.get("status") == "success":
                    found.add((row["spotify_id"], row["stage"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return found


def ffmpeg_path() -> str:
    return (os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg") or
            str(Path.home() / ".local" / "bin" / "ffmpeg"))


def decode_full(path: str, sample_rate: int, expected_seconds: float) -> np.ndarray:
    command = [
        ffmpeg_path(), "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1",
        "-ar", str(sample_rate), "-f", "f32le", "pipe:1",
    ]
    proc = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=max(180, int(expected_seconds * 1.5)),
    )
    if proc.returncode or len(proc.stdout) < sample_rate * 4:
        error = proc.stderr.decode("utf-8", "replace")[-1500:]
        raise RuntimeError(error or "full-track audio decode failed")
    return np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)


def full_windows(audio: np.ndarray, sample_rate: int, seconds: float,
                 hop_seconds: float | None = None) -> list[tuple[float, np.ndarray]]:
    size = max(1, int(round(seconds * sample_rate)))
    hop = max(1, int(round((hop_seconds or seconds) * sample_rate)))
    if len(audio) <= size:
        return [(0.0, audio)]
    starts = list(range(0, len(audio) - size + 1, hop))
    last = len(audio) - size
    if not starts or starts[-1] != last:
        starts.append(last)
    return [(start / sample_rate, audio[start:start + size]) for start in starts]


def pack(array: np.ndarray) -> dict:
    array = np.asarray(array, dtype="<f2")
    return {
        "encoding": "float16+zlib+base64",
        "shape": list(array.shape),
        "data": base64.b64encode(zlib.compress(array.tobytes(), 6)).decode("ascii"),
    }


def energy_weights(windows: list[tuple[float, np.ndarray]]) -> np.ndarray:
    rms = np.asarray([np.sqrt(np.mean(audio * audio) + 1e-12) for _, audio in windows])
    # Silence remains represented, but cannot dominate a long intro/outro.
    floor = max(float(np.percentile(rms, 20)) * 0.35, 1e-5)
    weights = np.maximum(rms, floor)
    return weights / weights.sum()


def model_batches(items, size: int):
    for offset in range(0, len(items), size):
        yield offset, items[offset:offset + size]


def run_maest(row: dict, device: str) -> dict:
    import torch
    from analyze_local_genres import (EMBEDDING_KEY, GenreModel, SR,
                                      tags_from_probs)

    expected = float(row["segment_seconds"])
    audio = decode_full(row["clip_path"], SR, expected)
    windows = full_windows(audio, SR, 10.0)
    weights = energy_weights(windows)
    model = run_maest.model if hasattr(run_maest, "model") else GenreModel(device)
    run_maest.model = model
    all_logits = []
    for _, batch in model_batches(windows, 24):
        inputs = model.extractor(
            [clip for _, clip in batch], sampling_rate=SR,
            return_tensors="pt", padding=True,
        )
        inputs = {key: (value.to(model.device).half()
                        if getattr(model, "fp16", False) and value.is_floating_point()
                        else value.to(model.device))
                  for key, value in inputs.items()}
        with torch.inference_mode():
            logits = model.model(**inputs).logits.float().cpu().numpy()
        all_logits.append(logits)
    logits = np.concatenate(all_logits, axis=0)
    shifted = logits - logits.max(axis=1, keepdims=True)
    probs = np.exp(shifted)
    probs /= probs.sum(axis=1, keepdims=True)
    aggregate = np.average(probs, axis=0, weights=weights)
    broad, styles, raw = tags_from_probs(model.labels, aggregate)
    timeline = []
    for index, ((start, clip), window_probs) in enumerate(zip(windows, probs)):
        order = np.argsort(window_probs)[::-1][:5]
        timeline.append({
            "index": index, "start": start, "duration": len(clip) / SR,
            "top": [{"label": model.labels[int(i)], "probability": float(window_probs[i])}
                    for i in order],
        })
    return {
        "model": EMBEDDING_KEY, "coverage_mode": "full_track_tiled",
        "trust_level": "candidate_only_until_supervised_consensus",
        "track_duration": len(audio) / SR, "window_seconds": 10.0,
        "window_count": len(windows),
        "genres": [{"tag": tag, "confidence": confidence, "probability": probability}
                   for tag, confidence, probability in broad],
        "styles": [{"tag": tag, "confidence": confidence, "probability": probability}
                   for tag, confidence, probability in styles],
        "top_predictions": raw, "timeline": timeline,
        "segment_logits": pack(logits), "aggregate_probabilities": pack(aggregate),
    }


def run_clap(row: dict, device: str) -> dict:
    import torch
    from analyze_local_semantics import (EMBEDDING_KEY, SR, SemanticModel,
                                         feature_tensor)

    expected = float(row["segment_seconds"])
    audio = decode_full(row["clip_path"], SR, expected)
    windows = full_windows(audio, SR, 10.0)
    weights = energy_weights(windows)
    model = run_clap.model if hasattr(run_clap, "model") else SemanticModel(device)
    run_clap.model = model
    vectors = []
    for _, batch in model_batches(windows, 16):
        clips = [clip for _, clip in batch]
        try:
            inputs = model.processor(audio=clips, sampling_rate=SR,
                                     return_tensors="pt", padding=True)
        except TypeError:
            inputs = model.processor(audios=clips, sampling_rate=SR,
                                     return_tensors="pt", padding=True)
        inputs = {key: (value.to(model.device).half()
                        if getattr(model, "fp16", False) and value.is_floating_point()
                        else value.to(model.device))
                  for key, value in inputs.items()}
        with torch.inference_mode():
            vector = feature_tensor(model.model.get_audio_features(**inputs)).float()
        vector = vector / vector.norm(dim=-1, keepdim=True)
        vectors.append(vector.float().cpu().numpy())
    matrix = np.concatenate(vectors, axis=0)
    aggregate = np.average(matrix, axis=0, weights=weights)
    aggregate /= max(float(np.linalg.norm(aggregate)), 1e-12)
    aggregate_tensor = torch.from_numpy(aggregate).to(model.device).unsqueeze(0)
    summary = model.score(aggregate_tensor)
    timeline = []
    for index, ((start, clip), vector) in enumerate(zip(windows, matrix)):
        scores = model.score(torch.from_numpy(vector).to(model.device).unsqueeze(0))
        timeline.append({
            "index": index, "start": start, "duration": len(clip) / SR,
            "mood": scores["mood"], "instrument": scores["instrument"],
            "voice": scores["voice"],
        })
    # Coverage makes stable tags distinguishable from one-section peaks.
    for kind in ("mood", "instrument", "voice"):
        counts = Counter(item["tag"] for segment in timeline for item in segment[kind])
        for item in summary[kind]:
            item["section_coverage"] = counts[item["tag"]] / len(timeline)
    return {
        "model": EMBEDDING_KEY, "coverage_mode": "full_track_tiled",
        "track_duration": len(audio) / SR, "window_seconds": 10.0,
        "window_count": len(windows), **summary, "timeline": timeline,
        "segment_embeddings": pack(matrix), "aggregate_embedding": pack(aggregate),
    }


def run_essentia(row: dict, device: str) -> dict:
    from analyze_essentia_full import EssentiaFullModel

    expected = float(row["segment_seconds"])
    audio = decode_full(row["clip_path"], 16000, expected)
    model = (run_essentia.model if hasattr(run_essentia, "model")
             else EssentiaFullModel())
    run_essentia.model = model
    result = model(audio)
    result["track_duration"] = len(audio) / 16000
    result["trust_level"] = "supervised_primary"
    return result


# Adaptive rhythm coverage (D-034): probe size and the tempo agreement it
# demands before trusting a uniform verdict. Raising PROBE_WINDOWS trades
# savings for caution; both were tuned on 4,061 replayed tracks.
PROBE_WINDOWS = 4
PROBE_BPM_SPREAD = 1.0


def weighted_mean(values, key: str) -> float:
    return float(np.mean([float(value[key]) for value in values]))


def run_rhythm(row: dict, device: str) -> dict:
    from analyze_local_rhythm import BeatTracker, SR, VERSION, analyze

    expected = float(row["segment_seconds"])
    audio = decode_full(row["clip_path"], SR, expected)
    windows = full_windows(audio, SR, 45.0, 40.0)
    tracker = run_rhythm.tracker if hasattr(run_rhythm, "tracker") else BeatTracker(device)
    run_rhythm.tracker = tracker
    # Harmonic/percussive separation is ~3 s of single-threaded CPU per window
    # and dominates this stage — it was the reason a GPU pod spent most of its
    # paid time with an idle GPU. librosa releases the GIL inside it, so doing
    # all windows concurrently up front cuts the stage ~3x on the pod's 6 vCPU.
    # The beat-tracker calls below stay sequential: identical results, and no
    # concurrent forward passes through one Torch model.
    import librosa
    from concurrent.futures import ThreadPoolExecutor

    def analyse_indices(indices: list[int]) -> dict[int, dict]:
        """Analyse the given windows; HPSS concurrently, tracker sequentially."""
        chosen = [(i, windows[i]) for i in indices]
        with ThreadPoolExecutor(max_workers=min(6, len(chosen) or 1)) as pool:
            percussives = list(pool.map(
                lambda item: librosa.effects.hpss(item[1][1])[1], chosen))
        out = {}
        for (i, (start, clip)), perc in zip(chosen, percussives):
            result = analyze(clip, tracker, precomputed_percussive=perc)
            out[i] = {"index": i, "start": start,
                      "duration": len(clip) / SR, **result}
        return out

    # Adaptive coverage (D-034). A probe of PROBE_WINDOWS evenly spaced windows
    # that unanimously agrees on rhythm pattern, beat presence AND tempo means
    # the track is uniform, so the remaining windows can only restate it.
    # Measured on 4,061 already-analysed tracks: identical pattern, presence and
    # BPM (within 0.5) in 100% of cases, while skipping 28% of the work. When
    # the probe disagrees — exactly the layered or shifting tracks worth looking
    # at closely — the full track is analysed as before.
    probe_ids = ([round(i * (len(windows) - 1) / (PROBE_WINDOWS - 1))
                  for i in range(PROBE_WINDOWS)]
                 if len(windows) > PROBE_WINDOWS else list(range(len(windows))))
    probe_ids = sorted(set(probe_ids))
    analysed = analyse_indices(probe_ids)
    probe = [analysed[i] for i in probe_ids]
    bpms = [float(w["bpm"]) for w in probe if w.get("bpm")]
    uniform = (
        len({w["rhythm_pattern"] for w in probe}) == 1
        and len({w["beat_presence"] for w in probe}) == 1
        and len(bpms) == len(probe)
        and (max(bpms) - min(bpms)) <= PROBE_BPM_SPREAD
    )
    if not uniform:
        analysed.update(analyse_indices([i for i in range(len(windows))
                                         if i not in analysed]))
    timeline = [analysed[i] for i in sorted(analysed)]
    patterns = Counter(item["rhythm_pattern"] for item in timeline)
    presences = Counter(item["beat_presence"] for item in timeline)
    dominant_pattern, pattern_count = patterns.most_common(1)[0]
    pattern_coverage = pattern_count / len(timeline)
    if pattern_coverage < 0.60:
        dominant_pattern = "mixed_or_variable"
    bpms = [float(item["bpm"]) for item in timeline if item.get("bpm")]
    beat_coverage = sum(item["beat_presence"] == "beat" for item in timeline) / len(timeline)
    summary = {
        "beat_presence": presences.most_common(1)[0][0],
        "beat_presence_score": weighted_mean(timeline, "beat_presence_score"),
        "beat_confidence": weighted_mean(timeline, "beat_confidence"),
        "beat_section_coverage": beat_coverage,
        "rhythm_pattern": dominant_pattern,
        "rhythm_pattern_coverage": pattern_coverage,
        "rhythm_pattern_confidence": weighted_mean(timeline, "rhythm_pattern_confidence"),
        "bpm": float(np.median(bpms)) if bpms else None,
        "four_on_floor_score": weighted_mean(timeline, "four_on_floor_score"),
        "broken_beat_score": weighted_mean(timeline, "broken_beat_score"),
        "syncopation_score": weighted_mean(timeline, "syncopation_score"),
        "rhythm_regularity": weighted_mean(timeline, "rhythm_regularity"),
        "tempo_stability": weighted_mean(timeline, "tempo_stability"),
        "kick_on_quarter_ratio": weighted_mean(timeline, "kick_on_quarter_ratio"),
        "offbeat_kick_ratio": weighted_mean(timeline, "offbeat_kick_ratio"),
    }
    return {
        "model": f"beat-this+librosa/{VERSION}",
        # Be explicit about how much was actually listened to: an adaptive run
        # analyses a probe when the track proves uniform, so window_count must
        # not claim coverage the run did not pay for (D-001 provenance).
        "coverage_mode": ("full_track_overlapping_windows"
                          if len(timeline) == len(windows)
                          else "adaptive_probe_uniform_track"),
        "track_duration": len(audio) / SR, "window_seconds": 45.0,
        "hop_seconds": 40.0,
        "window_count": len(timeline),
        "window_count_available": len(windows),
        **summary, "timeline": timeline,
    }


RUNNERS = {
    "rhythm_full": run_rhythm,
    "maest_full": run_maest,
    "essentia_full": run_essentia,
    "clap_full": run_clap,
}


def stage_required(row: dict, stage: str) -> bool:
    raw = (row.get("required_stages") or "").strip()
    return not raw or stage in {item.strip() for item in raw.split(",") if item.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--stage", choices=("all", *RUNNERS), default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows = rows[:args.limit] if args.limit else rows
    for row in rows:
        if not Path(row["clip_path"]).is_file():
            suffix = Path(row["clip_path"]).suffix or ".opus"
            row["clip_path"] = str(args.manifest.parent / "clips" /
                                   f"{row['spotify_id']}{suffix}")
        if row.get("coverage_mode") != "full_track":
            raise SystemExit(f"Refusing non-full-track manifest row: {row['spotify_id']}")
    stages = tuple(RUNNERS) if args.stage == "all" else (args.stage,)
    done = completed(args.output)
    failures = 0
    for stage in stages:
        runner = RUNNERS[stage]
        stage_rows = [row for row in rows if stage_required(row, stage)]
        for index, row in enumerate(stage_rows, 1):
            key = (row["spotify_id"], stage)
            if key in done:
                continue
            started = time.monotonic()
            try:
                result = runner(row, args.device)
                payload = {"spotify_id": row["spotify_id"], "stage": stage,
                           "status": "success", "elapsed_seconds": time.monotonic() - started,
                           "result": result}
                done.add(key)
            except Exception as exc:
                failures += 1
                payload = {"spotify_id": row["spotify_id"], "stage": stage,
                           "status": "error", "elapsed_seconds": time.monotonic() - started,
                           "error": repr(exc)[-2000:]}
            append(args.output, payload)
            print(f"{stage} {index}/{len(stage_rows)} {row['spotify_id']} {payload['status']}", flush=True)
    expected = sum(stage_required(row, stage) for row in rows for stage in stages)
    success = sum((row["spotify_id"], stage) in done
                  for row in rows for stage in stages if stage_required(row, stage))
    print(f"full-coverage complete: success={success}/{expected} errors={failures}", flush=True)
    if success != expected:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

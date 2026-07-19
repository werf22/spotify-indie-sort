"""Audio-verified beat presence and rhythm-pattern analysis.

The expensive neural beat tracker is run once per process. Each result is
checkpointed immediately, so a crash, sleep or shutdown loses at most one file.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import librosa
import numpy as np
import torch
from beat_this.inference import Audio2Frames
from beat_this.model.postprocessor import Postprocessor

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from musicdb import connect, record_source_run  # noqa: E402

SOURCE = "local-audio:rhythm-v1"
VERSION = "rhythm-v1.0.5"
SR = 22050
HOP = 512


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return float(min(high, max(low, value)))


def sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -40, 40)
    return 1.0 / (1.0 + np.exp(-values))


def decode_segment(path: str, duration: float | None, seconds: float) -> tuple[np.ndarray, float, float]:
    total = float(duration or 0)
    if total > seconds + 5:
        # Mid-track is more representative than intros/outros for DJ material.
        start = max(0.0, total * 0.5 - seconds * 0.5)
        take = seconds
    else:
        start, take = 0.0, max(1.0, total or seconds)
    command = [
        os.getenv("FFMPEG_PATH", str(Path.home() / ".local" / "bin" / "ffmpeg")),
        "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{take:.3f}", "-i", path,
        "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1",
    ]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    if proc.returncode or len(proc.stdout) < SR * 4:
        error = proc.stderr.decode("utf-8", "replace")[-1000:]
        raise RuntimeError(f"ffmpeg decode failed ({proc.returncode}): {error}")
    audio = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)
    peak = float(np.max(np.abs(audio)))
    if not np.isfinite(peak) or peak < 1e-7:
        raise RuntimeError("decoded audio is silent or invalid")
    return audio, start, len(audio) / SR


class BeatTracker:
    def __init__(self, device: str):
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        try:
            self.frames = Audio2Frames(checkpoint_path="final0", device=device, float16=False)
        except Exception:
            if device != "cpu":
                self.device = "cpu"
                self.frames = Audio2Frames(checkpoint_path="final0", device="cpu", float16=False)
            else:
                raise
        self.post = Postprocessor(type="minimal", fps=50)

    def __call__(self, y: np.ndarray):
        with torch.inference_mode():
            beat_logits, downbeat_logits = self.frames(y, SR)
        beats, downbeats = self.post(beat_logits, downbeat_logits)
        beat_prob = sigmoid(beat_logits.detach().float().cpu().numpy())
        downbeat_prob = sigmoid(downbeat_logits.detach().float().cpu().numpy())
        return np.asarray(beats), np.asarray(downbeats), beat_prob, downbeat_prob


def sample_curve(curve: np.ndarray, times: np.ndarray, fps: float, radius: int = 3) -> np.ndarray:
    if not len(times) or not len(curve):
        return np.zeros(0, dtype=np.float32)
    positions = np.clip(np.rint(times * fps).astype(int), 0, len(curve) - 1)
    values = []
    for position in positions:
        left, right = max(0, position - radius), min(len(curve), position + radius + 1)
        values.append(float(np.max(curve[left:right])))
    return np.asarray(values, dtype=np.float32)


def robust_unit(values: np.ndarray) -> np.ndarray:
    if not len(values):
        return values.astype(np.float32)
    floor, ceiling = np.percentile(values, [20, 97])
    if ceiling <= floor + 1e-9:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip((values - floor) / (ceiling - floor), 0, 1).astype(np.float32)


def analyze(y: np.ndarray, tracker: BeatTracker) -> dict:
    beats, downbeats, beat_prob, downbeat_prob = tracker(y)
    if len(beats) < 4:
        # Conservative fallback: librosa can occasionally recover a pulse where
        # the neural model deliberately emits no >0.5 peaks.
        onset_fallback = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
        _, fallback = librosa.beat.beat_track(onset_envelope=onset_fallback, sr=SR, hop_length=HOP)
        fallback_times = librosa.frames_to_time(fallback, sr=SR, hop_length=HOP)
        if len(fallback_times) > len(beats):
            beats = fallback_times

    intervals = np.diff(beats)
    plausible = intervals[(intervals >= 0.24) & (intervals <= 1.5)]
    bpm = float(60.0 / np.median(plausible)) if len(plausible) else None
    regularity = clamp(1.0 - (float(np.std(plausible) / np.mean(plausible)) if len(plausible) > 3 else 1.0))
    tempo_stability = clamp(1.0 - (float(np.percentile(plausible, 90) - np.percentile(plausible, 10)) /
                                   max(float(np.median(plausible)), 1e-6) if len(plausible) > 5 else 1.0))

    # Harmonic/percussive separation provides an independent beat-presence clue.
    harmonic, percussive = librosa.effects.hpss(y)
    total_rms = float(np.sqrt(np.mean(y * y)) + 1e-9)
    perc_rms = float(np.sqrt(np.mean(percussive * percussive)))
    percussive_ratio = clamp(perc_rms / total_rms)

    # The percussive component suppresses sustained bass notes that would
    # otherwise look like off-beat kicks in the low-frequency onset curve.
    spect = np.abs(librosa.stft(percussive, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    low_energy = np.mean(spect[freqs <= 180.0], axis=0)
    low_onsets = np.maximum(0.0, np.diff(np.log1p(low_energy), prepend=np.log1p(low_energy[0])))
    low_onsets = robust_unit(low_onsets)
    fps = SR / HOP
    kick_at_beats = sample_curve(low_onsets, beats, fps)
    midpoint_times = beats[:-1] + np.diff(beats) * 0.5 if len(beats) > 1 else np.zeros(0)
    kick_offbeats = sample_curve(low_onsets, midpoint_times, fps, radius=2)
    kick_on_quarter = float(np.mean(kick_at_beats >= 0.36)) if len(kick_at_beats) else 0.0
    offbeat_kick = float(np.mean(kick_offbeats >= 0.36)) if len(kick_offbeats) else 0.0

    detected_idx = np.clip(np.rint(beats * 50).astype(int), 0, max(0, len(beat_prob) - 1))
    model_conf = float(np.mean(beat_prob[detected_idx])) if len(detected_idx) and len(beat_prob) else 0.0
    top_activation = float(np.percentile(beat_prob, 95)) if len(beat_prob) else 0.0
    beat_rate = len(beats) / max(len(y) / SR, 1.0)
    density_score = clamp(beat_rate / 1.7)
    pulse_presence = clamp(0.48 * model_conf + 0.17 * top_activation + 0.15 * percussive_ratio +
                           0.12 * regularity + 0.08 * density_score)
    # Beat trackers also find an abstract pulse in piano/orchestral music. The
    # user's "has a beat" means an audible rhythmic/percussive beat, so gate
    # the metrical pulse by measured percussive energy.
    percussive_gate = clamp((percussive_ratio - 0.08) / 0.26)
    presence = clamp(pulse_presence * (0.25 + 0.75 * percussive_gate))

    syncopation = clamp(0.58 * offbeat_kick + 0.42 * (1.0 - kick_on_quarter))
    four_score = clamp(presence * (0.62 * kick_on_quarter + 0.28 * regularity +
                                   0.10 * tempo_stability) * (1.0 - 0.25 * offbeat_kick))
    broken_score = clamp(presence * (0.72 * syncopation + 0.18 * (1.0 - kick_on_quarter) +
                                     0.10 * regularity))

    if presence < 0.34 or len(beats) < 5:
        beat_presence, pattern = "beatless", "beatless"
        beat_conf = clamp(max(0.55, 1.0 - presence))
        pattern_conf = beat_conf
    elif presence < 0.52:
        beat_presence, pattern = "unknown", "unknown"
        beat_conf = clamp(0.35 + abs(presence - 0.43))
        pattern_conf = beat_conf
    else:
        beat_presence = "beat"
        beat_conf = clamp(0.55 + (presence - 0.52))
        margin = abs(four_score - broken_score)
        kick_contrast = kick_on_quarter - offbeat_kick
        # Require a meaningful score margin. Near-ties are perceptually
        # ambiguous and can otherwise flip between broken/four-on-floor after
        # a harmless codec or resampler change.
        if (kick_on_quarter >= 0.42 and kick_contrast >= 0.07 and four_score >= 0.45
                and four_score - broken_score >= 0.04):
            pattern = "steady_four_on_floor"
        elif (kick_on_quarter < 0.40 and syncopation >= 0.35 and broken_score >= 0.38
              and broken_score - four_score >= 0.04):
            pattern = "broken_beat"
        else:
            pattern = "mixed_or_variable"
        pattern_conf = clamp(0.50 + margin)

    return {
        "beat_presence": beat_presence,
        "beat_presence_score": presence,
        "beat_confidence": beat_conf,
        "rhythm_pattern": pattern,
        "rhythm_pattern_confidence": pattern_conf,
        "four_on_floor_score": four_score,
        "broken_beat_score": broken_score,
        "syncopation_score": syncopation,
        "rhythm_regularity": regularity,
        "tempo_stability": tempo_stability,
        "kick_on_quarter_ratio": kick_on_quarter,
        "offbeat_kick_ratio": offbeat_kick,
        "percussive_ratio": percussive_ratio,
        "pulse_presence_score": pulse_presence,
        "model_activation": model_conf,
        "bpm": bpm,
        "beat_count": int(len(beats)),
        "downbeat_count": int(len(downbeats)),
    }


def pending_rows(db, limit: int, spotify_id: str | None = None):
    query = """
      SELECT * FROM (
        SELECT f.*, ROW_NUMBER() OVER (
          PARTITION BY f.spotify_id
          ORDER BY f.match_confidence DESC,
                   CASE f.codec WHEN 'flac' THEN 1 WHEN 'wav' THEN 2 WHEN 'aiff' THEN 3
                                WHEN 'm4a' THEN 4 WHEN 'mp3' THEN 5 ELSE 6 END,
                   f.file_size DESC
        ) AS choice
        FROM audio_files f
        WHERE f.spotify_id IS NOT NULL AND f.scan_status='matched'
          AND f.match_confidence>=0.82 AND f.attempts<4
          AND (? IS NULL OR f.spotify_id=?)
          AND NOT EXISTS (
            SELECT 1 FROM local_audio_analysis a
            WHERE a.spotify_id=f.spotify_id AND a.analyzer_version=?
          )
      ) WHERE choice=1 LIMIT ?
    """
    return list(db.execute(query, (spotify_id, spotify_id, VERSION, limit)))


def persist(db, row, result: dict, segment_start: float, segment_duration: float):
    now = datetime.now(timezone.utc).isoformat()
    sid, path = row["spotify_id"], row["path"]
    attrs = {
        "beat_presence": (result["beat_presence"], None, result["beat_confidence"]),
        "rhythm_pattern": (result["rhythm_pattern"], None, result["rhythm_pattern_confidence"]),
        "beat_presence_score": (None, result["beat_presence_score"], result["beat_confidence"]),
        "four_on_floor_score": (None, result["four_on_floor_score"], result["rhythm_pattern_confidence"]),
        "broken_beat_score": (None, result["broken_beat_score"], result["rhythm_pattern_confidence"]),
        "syncopation_score": (None, result["syncopation_score"], result["rhythm_pattern_confidence"]),
        "rhythm_regularity": (None, result["rhythm_regularity"], result["beat_confidence"]),
        "tempo_stability": (None, result["tempo_stability"], result["beat_confidence"]),
        "kick_on_quarter_ratio": (None, result["kick_on_quarter_ratio"], result["rhythm_pattern_confidence"]),
        "offbeat_kick_ratio": (None, result["offbeat_kick_ratio"], result["rhythm_pattern_confidence"]),
    }
    raw = json.dumps({**result, "segment_start": segment_start, "segment_duration": segment_duration,
                      "analyzer_version": VERSION}, ensure_ascii=False, sort_keys=True)
    rhythm_tag = {
        "beatless": "beatless", "steady_four_on_floor": "four-on-the-floor",
        "broken_beat": "broken-beat", "mixed_or_variable": "mixed-rhythm",
        "unknown": "rhythm-unknown",
    }[result["rhythm_pattern"]]
    with db:
        db.execute(
            """INSERT OR REPLACE INTO local_audio_analysis VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, path, "beat-this+librosa", VERSION, segment_start, segment_duration,
             result["beat_presence_score"], result["beat_confidence"], result["rhythm_pattern"],
             result["rhythm_pattern_confidence"], result["four_on_floor_score"],
             result["broken_beat_score"], result["syncopation_score"], result["rhythm_regularity"],
             result["tempo_stability"], result["kick_on_quarter_ratio"], result["offbeat_kick_ratio"],
             result["bpm"], raw, now),
        )
        db.execute("DELETE FROM track_attributes WHERE spotify_id=? AND source=?", (sid, SOURCE))
        db.executemany(
            """INSERT INTO track_attributes
               (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            [(sid, name, SOURCE, text, number, raw, confidence, now)
             for name, (text, number, confidence) in attrs.items()],
        )
        db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, SOURCE))
        db.execute("INSERT INTO tags VALUES(?,?,?,?,?)", (sid, rhythm_tag, "rhythm", SOURCE,
                                                           result["rhythm_pattern_confidence"]))
        db.execute(
            """INSERT OR REPLACE INTO audio_features
               (spotify_id,source,source_id,bpm,key,mode,time_signature,danceability,energy,valence,
                acousticness,instrumentalness,speechiness,liveness,loudness,confidence,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, SOURCE, path, result["bpm"], None, None, None,
             clamp(result["beat_presence_score"] * 0.55 + result["rhythm_regularity"] * 0.45),
             None, None, None, None, None, None, None, result["beat_confidence"], raw, now),
        )
        db.execute(
            "UPDATE audio_files SET analysis_status='done',analysis_version=?,last_error=NULL,updated_at=? WHERE path=?",
            (VERSION, now, path),
        )
        db.execute(
            """UPDATE audio_files SET analysis_status='duplicate_skipped',analysis_version=?,updated_at=?
               WHERE spotify_id=? AND path<>? AND analysis_status IN ('queued','running','retry')""",
            (VERSION, now, sid, path),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--segment-seconds", type=float, default=75.0)
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    parser.add_argument("--spotify-id")
    args = parser.parse_args()
    db = connect()
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with db:
        db.execute(
            "UPDATE audio_files SET analysis_status='retry' WHERE analysis_status='running' AND updated_at<?",
            (stale,),
        )
    rows = pending_rows(db, args.limit, args.spotify_id)
    if not rows:
        print("Local rhythm: no pending matched audio")
        return
    print(f"Loading Beat This! on {args.device}; pending batch={len(rows)}", flush=True)
    tracker = BeatTracker(args.device)
    completed = failed = 0
    for index, row in enumerate(rows, 1):
        now = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute(
                "UPDATE audio_files SET analysis_status='running',attempts=attempts+1,updated_at=? WHERE path=?",
                (now, row["path"]),
            )
        try:
            y, start, duration = decode_segment(row["path"], row["duration_seconds"], args.segment_seconds)
            result = analyze(y, tracker)
            persist(db, row, result, start, duration)
            completed += 1
            print(f"[{index}/{len(rows)}] {row['spotify_id']} {result['rhythm_pattern']} "
                  f"beat={result['beat_presence_score']:.2f} bpm={result['bpm'] or 0:.1f}", flush=True)
        except Exception as exc:
            failed += 1
            with db:
                db.execute(
                    "UPDATE audio_files SET analysis_status='retry',last_error=?,updated_at=? WHERE path=?",
                    (repr(exc)[-1500:], datetime.now(timezone.utc).isoformat(), row["path"]),
                )
            print(f"[{index}/{len(rows)}] FAILED {row['path']}: {exc}", flush=True)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), completed,
                      f"version={VERSION},completed={completed},failed={failed},device={tracker.device}")
    print(f"Local rhythm batch complete: completed={completed}, failed={failed}")


if __name__ == "__main__":
    main()

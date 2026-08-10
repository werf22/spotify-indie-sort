"""Audio-verified Discogs400 genre/style tagging with MAEST.

MAEST was trained on 3.3M Discogs-linked tracks and is substantially more
reliable for genre than unconstrained CLAP prompting. It runs locally and the
400-dimensional output is stored for similarity search and later calibration.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import sys
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from musicdb import connect, record_source_run  # noqa: E402

MODEL = os.getenv("MAEST_MODEL", "mtg-upf/discogs-maest-10s-dw-75e")
MODEL_REVISION = os.getenv(
    "MAEST_MODEL_REVISION", "d298f3a38365aa566b6a4417560423061ed82380"
)
VERSION = f"maest-discogs400-v1.0.3-{MODEL_REVISION[:8]}"
SOURCE = "local-audio:maest-discogs400"
EMBEDDING_KEY = f"{MODEL}@{MODEL_REVISION}"
SR = 16000
SEGMENT_SECONDS = 10.0


def decode(path: str, duration: float | None) -> tuple[np.ndarray, float, float]:
    total = float(duration or 0)
    start = max(0.0, total * 0.5 - SEGMENT_SECONDS * 0.5) if total > SEGMENT_SECONDS else 0.0
    command = [
        os.getenv("FFMPEG_PATH", str(Path.home() / ".local" / "bin" / "ffmpeg")),
        "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-t", str(SEGMENT_SECONDS), "-i", path,
        "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1",
    ]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    if proc.returncode or len(proc.stdout) < SR * 4:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-1000:] or "audio decode failed")
    audio = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)
    return audio, start, len(audio) / SR


class GenreModel:
    def __init__(self, device: str):
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = torch.device(device)
        self.extractor = AutoFeatureExtractor.from_pretrained(
            MODEL, revision=MODEL_REVISION, trust_remote_code=True
        )
        self.model = AutoModelForAudioClassification.from_pretrained(
            MODEL, revision=MODEL_REVISION, trust_remote_code=True
        )
        self.model = self.model.to(self.device).eval()
        # Optional half precision (AUDIO_FP16=1), CUDA only — MPS/CPU keep
        # float32 where fp16 is slow or unsupported. Validated against stored
        # float32 results before being switched on for production (D-035).
        if os.getenv("AUDIO_FP16") == "1" and self.device.type == "cuda":
            self.model = self.model.half()
        self.fp16 = os.getenv("AUDIO_FP16") == "1" and self.device.type == "cuda"
        self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]

    def __call__(self, audio: np.ndarray):
        inputs = self.extractor(audio, sampling_rate=SR, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.inference_mode():
            logits = self.model(**inputs).logits[0]
        probs = torch.softmax(logits.float(), dim=-1).cpu().numpy()
        logits_np = logits.float().cpu().numpy()
        return probs, logits_np


def tags_from_probs(labels: list[str], probs: np.ndarray):
    order = np.argsort(probs)[::-1]
    top = float(probs[order[0]])
    style_rows = []
    broad_scores = defaultdict(float)
    raw = []
    for idx in order[:25]:
        label = labels[int(idx)]
        broad, style = label.split("---", 1) if "---" in label else (label, label)
        broad_scores[broad] += float(probs[idx])
        raw.append({"label": label, "probability": float(probs[idx])})
        if len(style_rows) < 8 and float(probs[idx]) >= max(0.008, top * 0.055):
            relative = float(probs[idx]) / max(top, 1e-9)
            confidence = min(0.97, 0.45 + 0.50 * math.sqrt(relative))
            style_rows.append((style.casefold(), confidence, float(probs[idx])))
    broad_order = sorted(broad_scores.items(), key=lambda item: item[1], reverse=True)
    broad_rows = []
    if broad_order:
        peak = broad_order[0][1]
        for broad, score in broad_order[:3]:
            if score >= peak * 0.18:
                broad_rows.append((broad.casefold().replace("folk, world, & country", "world music"),
                                   min(0.97, 0.50 + 0.45 * math.sqrt(score / max(peak, 1e-9))), score))
    return broad_rows, style_rows, raw


def pending(db, limit: int):
    return list(db.execute(
        """SELECT * FROM (
             SELECT f.*, ROW_NUMBER() OVER (
               PARTITION BY f.spotify_id ORDER BY f.match_confidence DESC,
                 CASE f.codec WHEN 'flac' THEN 1 WHEN 'wav' THEN 2 WHEN 'aiff' THEN 3
                              WHEN 'm4a' THEN 4 WHEN 'mp3' THEN 5 ELSE 6 END,
                 f.file_size DESC
             ) choice
             FROM audio_files f
             WHERE f.spotify_id IS NOT NULL AND f.scan_status='matched' AND f.match_confidence>=0.82
               AND NOT EXISTS (SELECT 1 FROM audio_embeddings e
                               WHERE e.spotify_id=f.spotify_id AND e.model=?)
               AND COALESCE((SELECT attempts FROM audio_model_jobs j
                             WHERE j.path=f.path AND j.model=? AND j.version=?),0)<4
           ) WHERE choice=1 LIMIT ?""",
        (EMBEDDING_KEY, MODEL, VERSION, limit),
    ))


def set_job(db, path: str, status: str, error: str | None = None, increment: bool = False):
    now = datetime.now(timezone.utc).isoformat()
    with db:
        db.execute(
            """INSERT INTO audio_model_jobs(path,model,version,status,attempts,last_error,updated_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(path,model,version) DO UPDATE SET status=excluded.status,
                 attempts=audio_model_jobs.attempts+?,last_error=excluded.last_error,
                 updated_at=excluded.updated_at""",
            (path, MODEL, VERSION, status, 1 if increment else 0, error, now, 1 if increment else 0),
        )


def persist(db, row, logits: np.ndarray, broad, styles, raw, start: float, duration: float):
    sid, path = row["spotify_id"], row["path"]
    now = datetime.now(timezone.utc).isoformat()
    array = logits.astype(np.float16)
    blob = sqlite3.Binary(zlib.compress(array.tobytes(), level=6))
    payload = json.dumps({"model": MODEL, "version": VERSION, "segment_start": start,
                          "segment_duration": duration, "top_predictions": raw},
                         ensure_ascii=False, sort_keys=True)
    existing = {
        str(x["tag"]).casefold() for x in db.execute(
            "SELECT tag FROM tags WHERE spotify_id=? AND source<>? AND tag_type IN ('genre','subgenre','style')",
            (sid, SOURCE),
        )
    }
    tag_rows = [(sid, tag, "genre", SOURCE, confidence) for tag, confidence, _ in broad]
    for tag, confidence, probability in styles:
        # A specific catalog label can verify a broader audio prediction
        # ("afro house" verifies "house"), but broad "house" must not verify
        # a more specific and potentially wrong "electro house" prediction.
        agrees = tag in existing or any(tag in old for old in existing if len(old) >= 5)
        # Discogs400 is excellent as an audio-family verifier but can confuse
        # neighbouring club styles. Only consensus/high-certainty labels enter
        # the canonical subgenre set; all others remain searchable candidates.
        tag_type = "subgenre" if agrees or probability >= 0.45 else "audio_style_candidate"
        tag_rows.append((sid, tag, tag_type, SOURCE, confidence if agrees else min(confidence, 0.58)))
    with db:
        db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, SOURCE))
        db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", tag_rows)
        db.execute(
            """INSERT OR REPLACE INTO audio_embeddings
               (spotify_id,path,model,dimensions,dtype,vector,segment_start,segment_duration,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (sid, path, EMBEDDING_KEY, len(array), "float16+zlib", blob, start, duration, now),
        )
        db.execute(
            """INSERT OR REPLACE INTO track_attributes
               (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (sid, "audio_genre_profile", SOURCE, None, None, payload,
             max((x[1] for x in broad + styles), default=0.0), now),
        )
    set_job(db, path, "done")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    args = parser.parse_args()
    db = connect()
    rows = pending(db, args.limit)
    if not rows:
        print("Local MAEST genres: no pending matched audio")
        return
    print(f"Loading {MODEL} on {args.device}; pending batch={len(rows)}", flush=True)
    model = GenreModel(args.device)
    completed = failed = 0
    for index, row in enumerate(rows, 1):
        set_job(db, row["path"], "running", increment=True)
        try:
            audio, start, duration = decode(row["path"], row["duration_seconds"])
            probs, logits = model(audio)
            broad, styles, raw = tags_from_probs(model.labels, probs)
            persist(db, row, logits, broad, styles, raw, start, duration)
            completed += 1
            print(f"[{index}/{len(rows)}] {row['spotify_id']} genres={','.join(x[0] for x in broad)} "
                  f"styles={','.join(x[0] for x in styles[:4])}", flush=True)
        except Exception as exc:
            failed += 1
            set_job(db, row["path"], "retry", repr(exc)[-1500:])
            print(f"[{index}/{len(rows)}] FAILED {row['path']}: {exc}", flush=True)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), completed,
                      f"model={MODEL},version={VERSION},completed={completed},failed={failed}")
    print(f"Local MAEST genre batch complete: completed={completed}, failed={failed}")


if __name__ == "__main__":
    main()

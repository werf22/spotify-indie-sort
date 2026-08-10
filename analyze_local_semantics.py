"""Rich zero-shot mood, genre, subgenre, instrument and voice tagging.

CLAP embeds audio and text into the same vector space. This lets us use a
large DJ-specific vocabulary without paying per track or retraining a model.
All similarities and the audio embedding are retained for future calibration.
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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from transformers import ClapModel, ClapProcessor

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from audio_taxonomy import INSTRUMENTS, MOODS, VOICE_TAGS  # noqa: E402
from musicdb import connect, record_source_run  # noqa: E402

MODEL = os.getenv("CLAP_MODEL", "laion/larger_clap_music")
VERSION = "clap-taxonomy-v1.1.0"
SOURCE = "local-audio:clap-v1"
EMBEDDING_KEY = f"{MODEL}@{VERSION}"
SR = 48000
SEGMENT_SECONDS = 30.0


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
    y = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)
    return y, start, len(y) / SR


def prompt(kind: str, label: str) -> str:
    if kind == "mood":
        return f"A music track with a {label} mood and emotional atmosphere"
    if kind == "genre":
        return f"A professionally produced {label} music track"
    if kind == "subgenre":
        return f"A music track in the {label} genre or subgenre"
    if kind == "instrument":
        return f"A music track featuring clearly audible {label}"
    return f"A music track with {label}"


def feature_tensor(output):
    """Support both Transformers 4.x tensors and 5.x model-output objects."""
    if isinstance(output, torch.Tensor):
        return output
    for name in ("text_embeds", "audio_embeds", "pooler_output"):
        value = getattr(output, name, None)
        if isinstance(value, torch.Tensor):
            return value
    if getattr(output, "last_hidden_state", None) is not None:
        return output.last_hidden_state.mean(dim=1)
    raise TypeError(f"Unsupported CLAP feature output: {type(output)!r}")


class SemanticModel:
    def __init__(self, device: str):
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = torch.device(device)
        self.processor = ClapProcessor.from_pretrained(MODEL)
        self.model = ClapModel.from_pretrained(MODEL).to(self.device).eval()
        if os.getenv("AUDIO_FP16") == "1" and self.device.type == "cuda":
            self.model = self.model.half()
        self.fp16 = os.getenv("AUDIO_FP16") == "1" and self.device.type == "cuda"
        self.vocab = {
            "mood": MOODS,
            "instrument": INSTRUMENTS,
            "voice": VOICE_TAGS,
        }
        self.text_features = {}
        for kind, labels in self.vocab.items():
            texts = [prompt(kind, label) for label in labels]
            vectors = []
            for offset in range(0, len(texts), 64):
                inputs = self.processor(text=texts[offset:offset + 64], return_tensors="pt", padding=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                with torch.inference_mode():
                    batch = feature_tensor(self.model.get_text_features(**inputs))
                vectors.append(batch / batch.norm(dim=-1, keepdim=True))
            # Text features are tiny and computed once; keep them float32 even
            # when the model runs half, so score() never mixes dtypes with the
            # float32 audio vectors (observed: "float != c10::Half" crash that
            # zeroed the whole CLAP stage on the fp16 probe).
            self.text_features[kind] = torch.cat(vectors, dim=0).float()

    def embed(self, audio: np.ndarray) -> torch.Tensor:
        window = 10 * SR
        clips = [audio[offset:offset + window] for offset in range(0, min(len(audio), 3 * window), window)]
        clips = [clip for clip in clips if len(clip) >= SR]
        payload = clips if len(clips) > 1 else clips[0]
        try:
            inputs = self.processor(audio=payload, sampling_rate=SR, return_tensors="pt", padding=True)
        except TypeError:  # Transformers 4.x
            inputs = self.processor(audios=payload, sampling_rate=SR, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.inference_mode():
            vector = feature_tensor(self.model.get_audio_features(**inputs))
        vector = vector / vector.norm(dim=-1, keepdim=True)
        vector = vector.mean(dim=0, keepdim=True)
        return vector / vector.norm(dim=-1, keepdim=True)

    def score(self, vector: torch.Tensor):
        output = {}
        for kind, labels in self.vocab.items():
            similarities = (vector @ self.text_features[kind].T)[0].float().cpu().numpy()
            median = float(np.median(similarities))
            spread = max(float(np.std(similarities)), 1e-5)
            ranking = np.argsort(similarities)[::-1]
            limits = {"mood": 7, "instrument": 5, "voice": 3}
            selected = []
            for rank, idx in enumerate(ranking[:limits[kind]]):
                zscore = (float(similarities[idx]) - median) / spread
                # A conservative relative confidence. Raw cosine is retained so
                # this mapping can be recalibrated on hand-labelled examples.
                confidence = 1.0 / (1.0 + math.exp(-(zscore - 0.45) * 1.15))
                confidence = float(min(0.94, max(0.35, confidence)))
                required = 0.55 if kind == "mood" else 0.52
                if confidence >= required:
                    selected.append({"tag": labels[idx], "confidence": confidence,
                                     "cosine": float(similarities[idx]), "zscore": zscore})
            output[kind] = selected
        return output


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


def persist(db, row, vector: torch.Tensor, scores: dict, start: float, duration: float):
    sid, path = row["spotify_id"], row["path"]
    now = datetime.now(timezone.utc).isoformat()
    array = vector[0].float().cpu().numpy().astype(np.float16)
    blob = sqlite3.Binary(zlib.compress(array.tobytes(), level=6))
    raw = json.dumps({"model": MODEL, "version": VERSION, "segment_start": start,
                      "segment_duration": duration, "scores": scores}, ensure_ascii=False, sort_keys=True)
    rows = []
    for kind, values in scores.items():
        stored_kind = {"instrument": "instrument_candidate", "voice": "voice_candidate"}.get(kind, kind)
        for item in values:
            rows.append((sid, item["tag"], stored_kind, SOURCE, item["confidence"]))
    with db:
        db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, SOURCE))
        db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", rows)
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
            (sid, "audio_semantic_profile", SOURCE, None, None, raw,
             max((x["confidence"] for values in scores.values() for x in values), default=0.0), now),
        )
    set_job(db, path, "done")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    args = parser.parse_args()
    db = connect()
    rows = pending(db, args.limit)
    if not rows:
        print("Local semantics: no pending matched audio")
        return
    print(f"Loading {MODEL} on {args.device}; pending batch={len(rows)}", flush=True)
    model = SemanticModel(args.device)
    completed = failed = 0
    for index, row in enumerate(rows, 1):
        set_job(db, row["path"], "running", increment=True)
        try:
            audio, start, duration = decode(row["path"], row["duration_seconds"])
            vector = model.embed(audio)
            scores = model.score(vector)
            persist(db, row, vector, scores, start, duration)
            completed += 1
            print(f"[{index}/{len(rows)}] {row['spotify_id']} "
                  f"moods={len(scores['mood'])} instruments={len(scores['instrument'])} voices={len(scores['voice'])}", flush=True)
        except Exception as exc:
            failed += 1
            set_job(db, row["path"], "retry", repr(exc)[-1500:])
            print(f"[{index}/{len(rows)}] FAILED {row['path']}: {exc}", flush=True)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), completed,
                      f"model={MODEL},version={VERSION},completed={completed},failed={failed}")
    print(f"Local semantic batch complete: completed={completed}, failed={failed}")


if __name__ == "__main__":
    main()

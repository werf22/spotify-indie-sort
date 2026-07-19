#!/usr/bin/env python3
"""Full-track supervised tagging with Essentia's Discogs-EffNet heads."""

from __future__ import annotations

import argparse
import base64
import json
import os
import tempfile
import urllib.request
import zlib
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.getenv("ESSENTIA_MODEL_DIR", ROOT / "vendor" / "essentia-models"))
EMBEDDING_STEM = "discogs-effnet-bs64-1"
EMBEDDING_BASE = "https://essentia.upf.edu/models/music-style-classification/discogs-effnet"

# Every head below reuses the same 1280-dimensional full-track embedding.
# This broad set is intentional: raw probabilities and provenance are kept so
# later calibration never requires re-running the expensive audio encoder.
HEADS = {
    "moodtheme": ("mtg_jamendo_moodtheme", "mtg_jamendo_moodtheme-discogs-effnet-1"),
    "genre_jamendo": ("mtg_jamendo_genre", "mtg_jamendo_genre-discogs-effnet-1"),
    "instrument": ("mtg_jamendo_instrument", "mtg_jamendo_instrument-discogs-effnet-1"),
    "top50tags": ("mtg_jamendo_top50tags", "mtg_jamendo_top50tags-discogs-effnet-1"),
    "genre_electronic": ("genre_electronic", "genre_electronic-discogs-effnet-1"),
    "mood_aggressive": ("mood_aggressive", "mood_aggressive-discogs-effnet-1"),
    "mood_happy": ("mood_happy", "mood_happy-discogs-effnet-1"),
    "mood_party": ("mood_party", "mood_party-discogs-effnet-1"),
    "mood_relaxed": ("mood_relaxed", "mood_relaxed-discogs-effnet-1"),
    "mood_sad": ("mood_sad", "mood_sad-discogs-effnet-1"),
    "mood_acoustic": ("mood_acoustic", "mood_acoustic-discogs-effnet-1"),
    "mood_electronic": ("mood_electronic", "mood_electronic-discogs-effnet-1"),
    "danceability": ("danceability", "danceability-discogs-effnet-1"),
    "approachability": ("approachability", "approachability_3c-discogs-effnet-1"),
    "engagement": ("engagement", "engagement_3c-discogs-effnet-1"),
    "voice_instrumental": ("voice_instrumental", "voice_instrumental-discogs-effnet-1"),
    "voice_gender": ("gender", "gender-discogs-effnet-1"),
    "timbre": ("timbre", "timbre-discogs-effnet-1"),
    "tonal_atonal": ("tonal_atonal", "tonal_atonal-discogs-effnet-1"),
}


def files() -> list[tuple[str, Path]]:
    result = [
        (f"{EMBEDDING_BASE}/{EMBEDDING_STEM}.pb", MODEL_DIR / f"{EMBEDDING_STEM}.pb"),
        (f"{EMBEDDING_BASE}/{EMBEDDING_STEM}.json", MODEL_DIR / f"{EMBEDDING_STEM}.json"),
    ]
    base = "https://essentia.upf.edu/models/classification-heads"
    for folder, stem in HEADS.values():
        result.extend([
            (f"{base}/{folder}/{stem}.pb", MODEL_DIR / f"{stem}.pb"),
            (f"{base}/{folder}/{stem}.json", MODEL_DIR / f"{stem}.json"),
        ])
    return result


def download_models() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for url, target in files():
        if target.is_file() and target.stat().st_size > 1000:
            continue
        fd, temporary = tempfile.mkstemp(prefix=target.name, suffix=".partial", dir=MODEL_DIR)
        os.close(fd)
        try:
            print(f"download {target.name}", flush=True)
            urllib.request.urlretrieve(url, temporary)
            Path(temporary).replace(target)
        finally:
            Path(temporary).unlink(missing_ok=True)


def prediction_output(metadata: dict) -> str:
    outputs = metadata["schema"]["outputs"]
    preferred = next((item for item in outputs if item.get("output_purpose") == "predictions"), outputs[0])
    return preferred["name"]


def pack(array: np.ndarray) -> dict:
    array = np.asarray(array, dtype="<f2")
    return {
        "encoding": "float16+zlib+base64", "shape": list(array.shape),
        "data": base64.b64encode(zlib.compress(array.tobytes(), 6)).decode("ascii"),
    }


class EssentiaFullModel:
    def __init__(self):
        from essentia.standard import TensorflowPredict2D, TensorflowPredictEffnetDiscogs

        missing = [str(path) for _, path in files() if not path.is_file()]
        if missing:
            raise FileNotFoundError("Essentia model files missing: " + ", ".join(missing[:3]))
        self.embedder = TensorflowPredictEffnetDiscogs(
            graphFilename=str(MODEL_DIR / f"{EMBEDDING_STEM}.pb"),
            output="PartitionedCall:1", batchSize=64,
        )
        self.heads = {}
        self.metadata = {}
        for key, (_, stem) in HEADS.items():
            metadata = json.loads((MODEL_DIR / f"{stem}.json").read_text(encoding="utf-8"))
            input_name = metadata["schema"]["inputs"][0]["name"]
            output_name = prediction_output(metadata)
            self.heads[key] = TensorflowPredict2D(
                graphFilename=str(MODEL_DIR / f"{stem}.pb"),
                input=input_name, output=output_name,
            )
            self.metadata[key] = metadata

    def __call__(self, audio: np.ndarray) -> dict:
        embeddings = np.asarray(self.embedder(audio), dtype=np.float32)
        if embeddings.ndim != 2 or not len(embeddings):
            raise RuntimeError(f"Unexpected EffNet embeddings shape: {embeddings.shape}")
        results = {}
        for key, model in self.heads.items():
            predictions = np.asarray(model(embeddings), dtype=np.float32)
            if predictions.ndim == 1:
                predictions = predictions[None, :]
            labels = self.metadata[key]["classes"]
            mean = predictions.mean(axis=0)
            p90 = np.percentile(predictions, 90, axis=0)
            coverage = (predictions >= 0.5).mean(axis=0)
            order = np.argsort(mean)[::-1]
            results[key] = {
                "classes": labels,
                "mean": [float(x) for x in mean],
                "p90": [float(x) for x in p90],
                "selected": [
                    {"tag": labels[int(i)], "mean": float(mean[i]), "p90": float(p90[i]),
                     "section_coverage": float(coverage[i])}
                    for i in order[:min(12, len(labels))]
                ],
                "temporal_predictions": pack(predictions),
            }
        return {
            "model": f"essentia/{EMBEDDING_STEM}+{len(self.heads)}-supervised-heads",
            "coverage_mode": "full_track_native_patches",
            "prediction_rate_hz": 1.008,
            "patch_count": int(len(embeddings)),
            "embedding_dimensions": int(embeddings.shape[1]),
            "aggregate_embedding": pack(embeddings.mean(axis=0)),
            "temporal_embeddings": pack(embeddings),
            "tasks": results,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.download:
        download_models()
    if args.audio:
        from essentia.standard import MonoLoader

        audio = MonoLoader(filename=str(args.audio), sampleRate=16000, resampleQuality=4)()
        result = EssentiaFullModel()(audio)
        text = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Loads every signal the similarity ranking compares, once, into memory.

WHAT IS LOADED (all aligned to one master row order, so every comparison is a
numpy operation instead of a Python loop):

  embeddings   3 models, how the track actually SOUNDS          float16
  rhythm       12 numbers describing the drums: four-on-floor,  standardised
               broken-beat, syncopation, tempo stability, kick
               placement, beat confidence …
  features     energy, danceability, valence, acousticness,     standardised
               instrumentalness, speechiness, liveness
  tags         4.2M rows as an INVERTED index (tag -> tracks)   weighted
  musical      bpm and key, kept raw for exact DJ arithmetic

WHY AN INVERTED TAG INDEX: comparing the reference's ~65 tags against 42,900
tracks one by one is 2.8M set operations per query. Inverted, we look up only
the tags the reference actually has and add their weights straight into a
result array — the same answer, a fraction of the work.

WHY STANDARDISE rhythm and features: raw columns have wildly different ranges
(bpm ~120, scores 0-1). Without it, one column with a big range silently becomes
the whole distance.

HOW TO TWEAK: TAG_WEIGHTS decides which KIND of tag counts most; RHYTHM_KEYS and
FEATURE_KEYS decide which numbers are compared at all.
"""
from __future__ import annotations

import json
import sqlite3
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

MODELS = {
    "laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate": 512,
    "mtg-upf/discogs-maest-10s-dw-75e@d298f3a38365aa566b6a4417560423061ed82380/aggregate-probabilities": 400,
    "essentia/discogs-effnet-bs64-1+19-supervised-heads/aggregate-embedding": 1280,
}
RHYTHM_KEYS = ["four_on_floor_score", "broken_beat_score", "syncopation_score",
               "tempo_stability", "rhythm_regularity", "kick_on_quarter_ratio",
               "offbeat_kick_ratio", "beat_confidence", "beat_presence_score",
               "beat_section_coverage", "rhythm_pattern_confidence",
               "rhythm_pattern_coverage"]
FEATURE_KEYS = ["energy", "danceability", "valence", "acousticness",
                "instrumentalness", "speechiness", "liveness"]
# How much a KIND of tag says about "same track". Genre and style are the
# strongest statement; a loudness band is nearly free of information.
TAG_WEIGHTS = {
    "genre": 1.0, "subgenre": 1.0, "style": 0.9, "genre_audio_candidate": 0.8,
    "audio_style_candidate": 0.8, "mood": 0.8, "mood_candidate": 0.5,
    "instrument": 0.7, "instrument_candidate": 0.45, "voice": 0.6,
    "voice_candidate": 0.4, "vocal_character": 0.5, "rhythm": 0.9,
    "production_style": 0.6, "harmonic_mode": 0.5, "tempo_band": 0.5,
    "acoustic_character": 0.4, "energy_level": 0.4, "energy_band": 0.3,
    "danceability_level": 0.4, "danceability_band": 0.3, "valence_level": 0.4,
    "label": 0.3, "version": 0.2, "onetagger": 0.1,
}
DEFAULT_TAG_WEIGHT = 0.3


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    return db


def _decode(blob: bytes, dim: int):
    try:
        vec = np.frombuffer(zlib.decompress(blob), dtype=np.float16)
    except Exception:
        return None
    return vec if vec.size == dim else None


def _standardise(matrix: np.ndarray, present: np.ndarray) -> np.ndarray:
    """Zero-mean/unit-variance per column, using only the rows that HAVE data.
    Missing rows end up at 0, i.e. exactly average — they neither gain nor lose."""
    out = np.zeros_like(matrix, dtype=np.float32)
    if present.sum() == 0:
        return out
    block = matrix[present]
    mean = np.nanmean(block, axis=0)
    std = np.nanstd(block, axis=0)
    std[std == 0] = 1.0
    filled = np.where(np.isnan(matrix), mean, matrix)
    out = ((filled - mean) / std).astype(np.float32)
    out[~present] = 0.0
    return out


class Library:
    """Everything needed to rank the library, held in memory."""

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.pos: dict[str, int] = {}
        self.models: dict[str, dict] = {}
        self.rhythm = self.features = None
        self.has_rhythm = self.has_features = None
        self.bpm = self.key = None
        self.tag_index: dict[str, tuple] = {}
        self.tag_sum: np.ndarray | None = None
        self.tag_types: dict[str, set] = {}

    # ---------------------------------------------------------------- load
    def load(self) -> None:
        db = connect()
        raw = {}
        for model, dim in MODELS.items():
            rows = {}
            for sid, blob in db.execute(
                    """SELECT spotify_id, vector FROM audio_embeddings
                       WHERE model=? AND (segment_start IS NULL OR segment_start=0.0)""",
                    (model,)):
                vec = _decode(blob, dim)
                if vec is not None:
                    rows[sid] = vec
            if rows:
                raw[model] = rows

        every = set()
        for rows in raw.values():
            every |= rows.keys()
        self.ids = sorted(every)
        self.pos = {sid: i for i, sid in enumerate(self.ids)}
        n = len(self.ids)

        for model, rows in raw.items():
            order = [sid for sid in self.ids if sid in rows]
            matrix = np.vstack([rows[sid] for sid in order]).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.models[model] = {
                "matrix": (matrix / norms).astype(np.float16),
                "rows": np.array([self.pos[sid] for sid in order], dtype=np.int32),
                "index": {sid: i for i, sid in enumerate(order)},
            }

        self._load_rhythm(db, n)
        self._load_features(db, n)
        self._load_tags(db, n)
        db.close()

    def _load_rhythm(self, db, n: int) -> None:
        matrix = np.full((n, len(RHYTHM_KEYS)), np.nan, dtype=np.float32)
        present = np.zeros(n, dtype=bool)
        bpm = np.full(n, np.nan, dtype=np.float32)
        for sid, blob in db.execute(
                "SELECT spotify_id, payload_blob FROM audio_analysis_artifacts WHERE stage='rhythm_full'"):
            i = self.pos.get(sid)
            if i is None:
                continue
            try:
                p = json.loads(zlib.decompress(blob))
            except Exception:
                continue
            matrix[i] = [float(p.get(k)) if isinstance(p.get(k), (int, float)) else np.nan
                         for k in RHYTHM_KEYS]
            present[i] = True
            if isinstance(p.get("bpm"), (int, float)):
                bpm[i] = float(p["bpm"])
        for sid, value in db.execute(
                "SELECT spotify_id, bpm FROM audio_features WHERE bpm IS NOT NULL AND source='freqblog'"):
            i = self.pos.get(sid)
            if i is not None and np.isnan(bpm[i]):
                bpm[i] = float(value)
        self.rhythm, self.has_rhythm, self.bpm = _standardise(matrix, present), present, bpm

    def _load_features(self, db, n: int) -> None:
        matrix = np.full((n, len(FEATURE_KEYS)), np.nan, dtype=np.float32)
        present = np.zeros(n, dtype=bool)
        key = np.array([None] * n, dtype=object)
        cols = ",".join(FEATURE_KEYS)
        # freqblog covers the most tracks; reccobeats only fills gaps.
        for source in ("reccobeats", "freqblog"):
            for row in db.execute(
                    f"SELECT spotify_id,{cols},key FROM audio_features WHERE source=?", (source,)):
                i = self.pos.get(row[0])
                if i is None:
                    continue
                values = [float(v) if isinstance(v, (int, float)) else np.nan
                          for v in row[1:1 + len(FEATURE_KEYS)]]
                if any(not np.isnan(v) for v in values):
                    matrix[i] = values
                    present[i] = True
                if row[-1]:
                    key[i] = str(row[-1])
        self.features, self.has_features, self.key = _standardise(matrix, present), present, key

    def _load_tags(self, db, n: int) -> None:
        buckets: dict[str, list] = {}
        total = np.zeros(n, dtype=np.float32)
        types: dict[str, set] = {}
        for sid, ttype, tag, conf in db.execute(
                "SELECT spotify_id, tag_type, tag, confidence FROM tags WHERE tag IS NOT NULL"):
            i = self.pos.get(sid)
            if i is None:
                continue
            weight = TAG_WEIGHTS.get(ttype, DEFAULT_TAG_WEIGHT) * (
                float(conf) if isinstance(conf, (int, float)) else 0.6)
            if weight <= 0:
                continue
            buckets.setdefault(f"{ttype}:{str(tag).lower()}", []).append((i, weight))
            total[i] += weight
            types.setdefault(sid, set()).add(f"{ttype}:{str(tag).lower()}")
        self.tag_index = {tag: (np.array([r for r, _ in v], dtype=np.int32),
                                np.array([w for _, w in v], dtype=np.float32))
                          for tag, v in buckets.items()}
        self.tag_sum, self.tag_types = total, types

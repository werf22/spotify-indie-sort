#!/usr/bin/env python3
"""Loads EVERY comparable signal in the library into memory, once.

The point of this file is that nothing is hardcoded to three tag types or six
numbers. It discovers what the database actually holds — all 40 tag types, every
musical number — and hands the engine a registry it can switch on and off.

WHAT IT BUILDS (all aligned to one master row order, so comparisons are numpy
operations rather than Python loops):

  embeddings  3 models, how the track actually SOUNDS
  tags        an inverted index PER TAG TYPE, weighted by confidence, so genre
              can be compared independently of mood, label, instrument …
  numbers     every musical number (energy, valence, syncopation, loudness …)
              standardised, so "closest value" means the same thing in each

WHY AN INVERTED INDEX: comparing the reference's tags against 42,900 tracks one
by one is millions of set operations per query. Inverted, we touch only the tags
the reference actually has.

WHY SOME NUMBERS ARE EXCLUDED: the attribute table also holds identifiers and
catalogue trivia — album.id, track.rank, how many fans a label has. Two tracks
having a close `album.id` means they were uploaded near each other, not that
they sound alike. EXCLUDE_NUMBERS keeps that noise out of the score.

HOW TO TWEAK: MIN_COVERAGE decides how rare a signal may be and still be
offered; EXCLUDE_NUMBERS is the junk list; TAG_TYPE_HINTS only sets which
checkboxes start ticked.
"""
from __future__ import annotations

import json
import re
import sqlite3
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

MODELS = {
    "laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate":
        (512, "CLAP", "nálada a textúra zvuku"),
    "mtg-upf/discogs-maest-10s-dw-75e@d298f3a38365aa566b6a4417560423061ed82380/aggregate-probabilities":
        (400, "MAEST", "žáner a štýl"),
    "essentia/discogs-effnet-bs64-1+19-supervised-heads/aggregate-embedding":
        (1280, "Essentia", "celková hudobná podoba"),
}

MIN_COVERAGE = 400          # a signal fewer tracks than this have is not useful

# Identifiers, catalogue trivia and pure duplicates. A close `album.id` means two
# records were uploaded near each other — nothing about how they sound.
EXCLUDE_NUMBERS = re.compile(
    r"(^|\.)(id|rank|fans|available|readable|explicit.*|genre_id|nb_tracks|"
    r"disk_number|track_position|gain|tuning_frequency|.*_confidence|"
    r"representative_segment.*|bpm_snapped|bpm_alt|isrc|album\.duration)$")

# Which checkboxes start ticked. Everything else is offered but off, so the
# default search stays about the music instead of the paperwork.
TAG_DEFAULT_ON = {"genre", "subgenre", "style", "mood", "instrument", "voice",
                  "rhythm", "audio_style_candidate", "genre_audio_candidate",
                  "mood_candidate", "production_style", "harmonic_mode",
                  "tempo_band", "energy_level", "danceability_level",
                  "valence_level", "acoustic_character", "vocal_character",
                  "timbre", "tonality", "theme"}
NUMBER_DEFAULT_ON = {"energy", "danceability", "valence", "acousticness",
                     "instrumentalness", "speechiness", "liveness", "loudness",
                     "loudness_db", "four_on_floor_score", "broken_beat_score",
                     "syncopation_score", "tempo_stability", "rhythm_regularity",
                     "beat_presence_score", "mode", "time_signature",
                     "dynamic_complexity", "onset_rate"}


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


class Library:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.pos: dict[str, int] = {}
        self.models: dict[str, dict] = {}
        # tag_type -> {tag: (rows, weights, artist_level)} — the third array marks
        # entries that describe the ARTIST rather than this track.
        self.tag_index: dict[str, dict] = {}
        self.tag_sum: dict[str, np.ndarray] = {} # tag_type -> per-track weight total
        self.tag_of: dict[str, dict] = {}        # tag_type -> {track: set(tags)}
        self.numbers: dict[str, np.ndarray] = {} # attribute -> standardised values
        self.number_present: dict[str, np.ndarray] = {}
        # Raw mean/std per number, so a TARGET the owner types in real units
        # ("energy 0.8") can be placed on the same standardised scale.
        self.number_stats: dict[str, tuple[float, float]] = {}
        self.bpm = None
        self.key = None

    # ---------------------------------------------------------------- load
    def load(self) -> None:
        db = connect()
        raw = {}
        for model, (dim, _, _) in MODELS.items():
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

        every: set[str] = set()
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
            self.models[model] = {"matrix": (matrix / norms).astype(np.float16),
                                  "rows": np.array([self.pos[s] for s in order], dtype=np.int32),
                                  "index": {s: i for i, s in enumerate(order)}}
        self._load_tags(db, n)
        self._load_numbers(db, n)
        db.close()

    def _load_tags(self, db, n: int) -> None:
        buckets: dict[str, dict] = {}
        sums: dict[str, np.ndarray] = {}
        of: dict[str, dict] = {}
        # WHO SAID SO MATTERS AS MUCH AS HOW SURE THEY WERE. `last.fm:artist` is
        # the single largest source of genre tags (449k rows) and it describes
        # the ARTIST, not the track — so a drum'n'bass producer's 120 BPM house
        # remix carries "drum and bass" at confidence 1.0. Measured: dropping
        # artist-level sources lifts the drum'n'bass filter from 60 % to 73 % of
        # tracks actually in dnb tempo. The flag rides along with each entry so
        # a filter can ask for track-level evidence only.
        for sid, ttype, tag, conf, source in db.execute(
                "SELECT spotify_id, tag_type, tag, confidence, source FROM tags "
                "WHERE tag IS NOT NULL"):
            i = self.pos.get(sid)
            if i is None or not ttype:
                continue
            weight = float(conf) if isinstance(conf, (int, float)) and conf else 0.6
            key = str(tag).strip().lower()
            artist_level = "artist" in (source or "")
            buckets.setdefault(ttype, {}).setdefault(key, []).append((i, weight, artist_level))
            arr = sums.setdefault(ttype, np.zeros(n, dtype=np.float32))
            arr[i] += weight
            of.setdefault(ttype, {}).setdefault(sid, set()).add(key)
        for ttype, tags in buckets.items():
            self.tag_index[ttype] = {
                tag: (np.array([r for r, _, _ in v], dtype=np.int32),
                      np.array([w for _, w, _ in v], dtype=np.float32),
                      np.array([a for _, _, a in v], dtype=bool))
                for tag, v in tags.items()}
            self.tag_sum[ttype] = sums[ttype]
            self.tag_of[ttype] = of[ttype]

    def _add_number(self, name: str, values: np.ndarray, present: np.ndarray) -> None:
        if present.sum() < MIN_COVERAGE or EXCLUDE_NUMBERS.search(name):
            return
        block = values[present]
        mean, std = float(block.mean()), float(block.std()) or 1.0
        out = np.zeros_like(values, dtype=np.float32)
        out[present] = (block - mean) / std
        self.numbers[name] = out
        self.number_present[name] = present
        self.number_stats[name] = (mean, std)

    def _load_numbers(self, db, n: int) -> None:
        pools: dict[str, np.ndarray] = {}
        seen: dict[str, np.ndarray] = {}

        def put(name: str, i: int, value) -> None:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return
            if name not in pools:
                pools[name] = np.zeros(n, dtype=np.float32)
                seen[name] = np.zeros(n, dtype=bool)
            if not seen[name][i]:                # first source to supply it wins
                pools[name][i] = float(value)
                seen[name][i] = True

        for sid, attr, value in db.execute(
                "SELECT spotify_id, attribute, value_num FROM track_attributes WHERE value_num IS NOT NULL"):
            i = self.pos.get(sid)
            if i is not None:
                put(str(attr), i, value)
        cols = ["energy", "danceability", "valence", "acousticness", "instrumentalness",
                "speechiness", "liveness", "loudness", "time_signature", "mode"]
        for source in ("reccobeats", "freqblog"):
            for row in db.execute(
                    f"SELECT spotify_id,{','.join(cols)} FROM audio_features WHERE source=?", (source,)):
                i = self.pos.get(row[0])
                if i is None:
                    continue
                for name, value in zip(cols, row[1:]):
                    put(name, i, value)

        for name in list(pools):
            self._add_number(name, pools[name], seen[name])

        bpm = np.full(n, np.nan, dtype=np.float32)
        for sid, blob in db.execute(
                "SELECT spotify_id, payload_blob FROM audio_analysis_artifacts WHERE stage='rhythm_full'"):
            i = self.pos.get(sid)
            if i is None:
                continue
            try:
                value = json.loads(zlib.decompress(blob)).get("bpm")
            except Exception:
                continue
            if isinstance(value, (int, float)):
                bpm[i] = float(value)
        for sid, value in db.execute(
                "SELECT spotify_id, bpm FROM audio_features WHERE bpm IS NOT NULL AND source='freqblog'"):
            i = self.pos.get(sid)
            if i is not None and np.isnan(bpm[i]):
                bpm[i] = float(value)
        self.bpm = bpm

        key = np.array([None] * n, dtype=object)
        for source in ("reccobeats", "freqblog"):
            for sid, value in db.execute(
                    "SELECT spotify_id, key FROM audio_features WHERE source=? AND key IS NOT NULL", (source,)):
                i = self.pos.get(sid)
                if i is not None and key[i] is None:
                    key[i] = str(value)
        # WHAT THE OWNER TYPED WINS, over every provider and over our own
        # analysis. Detection misses things — the seed that started this had no
        # key at all, which silently emptied every key-filtered profile — and a
        # DJ who knows the key should be able to say so once and have it stick.
        # Overrides live in their own table so re-analysis can never erase them.
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS user_overrides (
                              spotify_id TEXT NOT NULL,
                              field      TEXT NOT NULL,
                              value_text TEXT,
                              value_num  REAL,
                              updated_at TEXT DEFAULT (datetime('now')),
                              PRIMARY KEY (spotify_id, field))""")
        except Exception:
            pass                       # a read-only connection cannot create it
        for sid, field, vtext, vnum in db.execute(
                "SELECT spotify_id, field, value_text, value_num FROM user_overrides"):
            i = self.pos.get(sid)
            if i is None:
                continue
            if field == "key" and vtext:
                key[i] = str(vtext)
            elif field == "bpm" and vnum:
                bpm[i] = float(vnum)
        self.key = key

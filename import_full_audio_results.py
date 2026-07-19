#!/usr/bin/env python3
"""Import full-coverage cloud/local audio results with conservative trust rules."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import sqlite3
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from musicdb import connect, record_source_run


RHYTHM_SOURCE = "audio-full:beat-this-v2"
MAEST_SOURCE = "audio-full:maest-v2"
ESSENTIA_SOURCE = "audio-full:essentia-supervised-v2"
CLAP_SOURCE = "audio-full:clap-candidates-v2"
CONSENSUS_SOURCE = "audio-full:consensus-v2"
RHYTHM_VERSION = "rhythm-full-v2.0.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def unpack_blob(value: dict) -> tuple[bytes, list[int]]:
    if value.get("encoding") != "float16+zlib+base64":
        raise ValueError(f"Unsupported packed value: {value.get('encoding')}")
    return base64.b64decode(value["data"]), [int(x) for x in value["shape"]]


def without_packed(value):
    if isinstance(value, dict):
        if value.get("encoding") == "float16+zlib+base64":
            return {"stored_separately": True, "shape": value.get("shape"),
                    "encoding": "float16+zlib"}
        return {key: without_packed(child) for key, child in value.items()}
    if isinstance(value, list):
        return [without_packed(child) for child in value]
    return value


def manifests(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["spotify_id"]: row for row in csv.DictReader(handle)}


def successes(path: Path) -> dict[tuple[str, str], dict]:
    rows = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "success":
                rows[(row["spotify_id"], row["stage"])] = row
    return rows


def store_artifact(db, sid: str, path: str, stage: str, result: dict, timestamp: str):
    model = str(result.get("model") or stage)
    payload = json.dumps(without_packed(result), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode()
    db.execute(
        """INSERT OR REPLACE INTO audio_analysis_artifacts
           VALUES(?,?,?,?,?,?,?,?)""",
        (sid, path, stage, model, result.get("coverage_mode"), "json+zlib",
         sqlite3.Binary(zlib.compress(payload, 7)), timestamp),
    )


def store_embedding(db, sid: str, path: str, model: str, packed: dict,
                    duration: float, timestamp: str):
    blob, shape = unpack_blob(packed)
    dimensions = shape[-1]
    db.execute(
        """INSERT OR REPLACE INTO audio_embeddings
           (spotify_id,path,model,dimensions,dtype,vector,segment_start,segment_duration,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (sid, path, model, dimensions, "float16+zlib", sqlite3.Binary(blob),
         0.0, duration, timestamp),
    )


def store_temporal(db, sid: str, path: str, model: str, feature_set: str,
                   packed: dict, hop: float | None, timestamp: str):
    blob, shape = unpack_blob(packed)
    frames = shape[0] if len(shape) > 1 else 1
    dimensions = shape[-1]
    db.execute(
        """INSERT OR REPLACE INTO audio_temporal_features
           (spotify_id,path,model,feature_set,frames,dimensions,hop_seconds,dtype,values_blob,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (sid, path, model, feature_set, frames, dimensions, hop,
         "float16+zlib", sqlite3.Binary(blob), timestamp),
    )


def attribute(db, sid: str, name: str, source: str, *, text=None, number=None,
              payload=None, confidence=None, timestamp: str):
    db.execute(
        """INSERT OR REPLACE INTO track_attributes
           (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (sid, name, source, text, number,
         json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None,
         confidence, timestamp),
    )


def tag(db, sid: str, value: str, kind: str, source: str, confidence: float):
    if value:
        db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                   (sid, value.casefold().strip(), kind, source, clamp(confidence)))


def import_rhythm(db, sid: str, path: str, result: dict, timestamp: str):
    beat_confidence = float(result.get("beat_confidence",
                                       0.5 + 0.45 * result.get("beat_section_coverage", 0)))
    pattern_confidence = float(result.get("rhythm_pattern_confidence",
                                          0.45 + 0.5 * result.get("rhythm_pattern_coverage", 0)))
    timeline = result.get("timeline") or []
    kick = float(result.get("kick_on_quarter_ratio") or
                 np.mean([x.get("kick_on_quarter_ratio", 0) for x in timeline]) if timeline else 0)
    offbeat = float(result.get("offbeat_kick_ratio") or
                    np.mean([x.get("offbeat_kick_ratio", 0) for x in timeline]) if timeline else 0)
    raw = json.dumps(without_packed(result), ensure_ascii=False, sort_keys=True)
    db.execute(
        """INSERT OR REPLACE INTO local_audio_analysis VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, path, "beat-this+librosa-full", RHYTHM_VERSION, 0.0,
         result["track_duration"], result["beat_presence_score"], beat_confidence,
         result["rhythm_pattern"], pattern_confidence, result["four_on_floor_score"],
         result["broken_beat_score"], result["syncopation_score"],
         result["rhythm_regularity"], result["tempo_stability"], kick, offbeat,
         result.get("bpm"), raw, timestamp),
    )
    rhythm_tag = {
        "beatless": "beatless", "steady_four_on_floor": "four-on-the-floor",
        "broken_beat": "broken-beat", "mixed_or_variable": "mixed-rhythm",
        "unknown": "rhythm-unknown",
    }.get(result["rhythm_pattern"], "mixed-rhythm")
    tag(db, sid, rhythm_tag, "rhythm", RHYTHM_SOURCE, pattern_confidence)
    values = {
        "beat_presence": (result["beat_presence"], None),
        "rhythm_pattern": (result["rhythm_pattern"], None),
        "beat_presence_score": (None, result["beat_presence_score"]),
        "beat_section_coverage": (None, result["beat_section_coverage"]),
        "rhythm_pattern_coverage": (None, result["rhythm_pattern_coverage"]),
        "four_on_floor_score": (None, result["four_on_floor_score"]),
        "broken_beat_score": (None, result["broken_beat_score"]),
        "syncopation_score": (None, result["syncopation_score"]),
        "rhythm_regularity": (None, result["rhythm_regularity"]),
        "tempo_stability": (None, result["tempo_stability"]),
    }
    for name, (text, number) in values.items():
        attribute(db, sid, name, RHYTHM_SOURCE, text=text, number=number,
                  confidence=beat_confidence if "pattern" not in name else pattern_confidence,
                  timestamp=timestamp)
    db.execute(
        """INSERT OR REPLACE INTO audio_features
           (spotify_id,source,source_id,bpm,key,mode,time_signature,danceability,energy,valence,
            acousticness,instrumentalness,speechiness,liveness,loudness,confidence,raw_json,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, RHYTHM_SOURCE, path, result.get("bpm"), None, None, None,
         clamp(result["beat_presence_score"] * 0.55 + result["rhythm_regularity"] * 0.45),
         None, None, None, None, None, None, None, beat_confidence, raw, timestamp),
    )


def agrees_with_catalog(db, sid: str, value: str, source: str) -> bool:
    needle = value.casefold()
    existing = [str(row[0]).casefold() for row in db.execute(
        """SELECT tag FROM tags WHERE spotify_id=? AND source<>?
           AND tag_type IN ('genre','subgenre','style')""", (sid, source)
    )]
    return needle in existing or any(needle in old for old in existing if len(old) >= 5)


def import_maest(db, sid: str, path: str, result: dict, timestamp: str):
    duration = float(result["track_duration"])
    model = str(result["model"])
    store_embedding(db, sid, path, model + "/aggregate-probabilities",
                    result["aggregate_probabilities"], duration, timestamp)
    store_temporal(db, sid, path, model, "segment_logits", result["segment_logits"],
                   result.get("window_seconds"), timestamp)
    db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, MAEST_SOURCE))
    for item in result.get("genres", []):
        tag(db, sid, item["tag"], "genre", MAEST_SOURCE, item["confidence"])
    for item in result.get("styles", []):
        agrees = agrees_with_catalog(db, sid, item["tag"], MAEST_SOURCE)
        canonical = agrees or float(item.get("probability", 0)) >= 0.45
        tag(db, sid, item["tag"], "subgenre" if canonical else "audio_style_candidate",
            MAEST_SOURCE, item["confidence"] if canonical else min(0.58, item["confidence"]))
    confidence = max([x["confidence"] for x in result.get("genres", []) + result.get("styles", [])]
                     or [0.0])
    attribute(db, sid, "audio_genre_profile_full", MAEST_SOURCE,
              payload={key: result.get(key) for key in ("genres", "styles", "top_predictions",
                                                        "window_count", "track_duration")},
              confidence=confidence, timestamp=timestamp)


def task_probability(task: dict, wanted: str) -> float | None:
    try:
        return float(task["mean"][task["classes"].index(wanted)])
    except (ValueError, IndexError, KeyError):
        return None


def import_essentia(db, sid: str, path: str, result: dict, timestamp: str):
    model = str(result["model"])
    duration = float(result["track_duration"])
    store_embedding(db, sid, path, model + "/aggregate-embedding",
                    result["aggregate_embedding"], duration, timestamp)
    store_temporal(db, sid, path, model, "effnet_embeddings", result["temporal_embeddings"],
                   1.0 / float(result["prediction_rate_hz"]), timestamp)
    tasks = result["tasks"]
    for name, task in tasks.items():
        store_temporal(db, sid, path, model, "predictions:" + name,
                       task["temporal_predictions"], 1.0 / float(result["prediction_rate_hz"]), timestamp)
        attribute(db, sid, "essentia_" + name, ESSENTIA_SOURCE,
                  payload={"classes": task["classes"], "mean": task["mean"],
                           "p90": task["p90"], "selected": task["selected"]},
                  confidence=float(task["selected"][0]["mean"]) if task["selected"] else 0,
                  timestamp=timestamp)

    db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, ESSENTIA_SOURCE))
    for item in tasks["moodtheme"]["selected"]:
        mean, p90 = float(item["mean"]), float(item["p90"])
        if mean >= 0.10 and p90 >= 0.18:
            tag(db, sid, item["tag"], "mood", ESSENTIA_SOURCE,
                clamp(0.48 + mean * 1.5 + item["section_coverage"] * 0.12))
        elif mean >= 0.04:
            tag(db, sid, item["tag"], "mood_candidate", ESSENTIA_SOURCE,
                clamp(0.35 + mean * 1.5))
    # Binary mood heads are strong but small-domain models. Require both a
    # high positive probability and support from the larger Jamendo head.
    jamendo = {item["tag"]: float(item["mean"])
               for item in tasks["moodtheme"]["selected"]}
    support_floor = {"happy": 0.08, "sad": 0.08, "relaxed": 0.08,
                     "aggressive": 0.06, "party": 0.04}
    for name, positive in (
        ("mood_aggressive", "aggressive"), ("mood_happy", "happy"),
        ("mood_party", "party"), ("mood_relaxed", "relaxed"),
        ("mood_sad", "sad"),
    ):
        probability = task_probability(tasks[name], positive)
        if (probability is not None and probability >= 0.75
                and jamendo.get(positive, 0.0) >= support_floor[positive]):
            tag(db, sid, positive, "mood", ESSENTIA_SOURCE, probability)
    for name, positive in (("mood_acoustic", "acoustic"),
                           ("mood_electronic", "electronic")):
        probability = task_probability(tasks[name], positive)
        if probability is not None and probability >= 0.65:
            tag(db, sid, positive, "production_style", ESSENTIA_SOURCE, probability)
    for item in tasks["genre_jamendo"]["selected"]:
        mean, p90 = float(item["mean"]), float(item["p90"])
        if mean < 0.12 or p90 < 0.22:
            continue
        canonical = agrees_with_catalog(db, sid, item["tag"], ESSENTIA_SOURCE)
        tag(db, sid, item["tag"], "genre" if canonical else "genre_audio_candidate",
            ESSENTIA_SOURCE, clamp(0.42 + mean * 0.7 + (0.15 if canonical else 0)))
    for item in tasks["genre_electronic"]["selected"]:
        if float(item["mean"]) >= 0.32 and float(item["p90"]) >= 0.45:
            canonical = agrees_with_catalog(db, sid, item["tag"], ESSENTIA_SOURCE)
            tag(db, sid, item["tag"], "subgenre" if canonical else "audio_style_candidate",
                ESSENTIA_SOURCE, clamp(0.40 + float(item["mean"])))
    for item in tasks["instrument"]["selected"]:
        mean, p90 = float(item["mean"]), float(item["p90"])
        if mean >= 0.20 and p90 >= 0.40:
            tag(db, sid, item["tag"], "instrument", ESSENTIA_SOURCE,
                clamp(0.40 + mean * 0.65 + item["section_coverage"] * 0.15))

    dance = task_probability(tasks["danceability"], "danceable")
    electronic = task_probability(tasks["mood_electronic"], "electronic")
    instrumental = task_probability(tasks["voice_instrumental"], "instrumental")
    raw = json.dumps({"model": model, "supervised": True}, sort_keys=True)
    db.execute(
        """INSERT OR REPLACE INTO audio_features
           (spotify_id,source,source_id,bpm,key,mode,time_signature,danceability,energy,valence,
            acousticness,instrumentalness,speechiness,liveness,loudness,confidence,raw_json,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, ESSENTIA_SOURCE, path, None, None, None, None, dance, None, None,
         None if electronic is None else 1.0 - electronic, instrumental,
         None, None, None, 0.82, raw, timestamp),
    )


def import_clap(db, sid: str, path: str, result: dict, timestamp: str):
    model = str(result["model"])
    duration = float(result["track_duration"])
    store_embedding(db, sid, path, model + "/full-aggregate",
                    result["aggregate_embedding"], duration, timestamp)
    store_temporal(db, sid, path, model, "segment_embeddings",
                   result["segment_embeddings"], result.get("window_seconds"), timestamp)
    db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, CLAP_SOURCE))
    for kind in ("mood", "instrument", "voice"):
        for item in result.get(kind, []):
            confidence = float(item["confidence"]) * (0.65 + 0.35 * float(item.get("section_coverage", 0)))
            tag(db, sid, item["tag"], kind + "_candidate", CLAP_SOURCE, min(0.69, confidence))
    attribute(db, sid, "clap_semantic_profile_full", CLAP_SOURCE,
              payload={key: result.get(key) for key in ("mood", "instrument", "voice",
                                                        "window_count", "track_duration")},
              confidence=0.55, timestamp=timestamp)


def derive_consensus(db, sid: str):
    db.execute("DELETE FROM tags WHERE spotify_id=? AND source=?", (sid, CONSENSUS_SOURCE))
    # Promote exact mood agreement between supervised and open-vocabulary audio.
    rows = db.execute(
        """SELECT e.tag,e.confidence,c.confidence
           FROM tags e JOIN tags c ON c.spotify_id=e.spotify_id AND c.tag=e.tag
           WHERE e.spotify_id=? AND e.source=? AND e.tag_type='mood'
             AND c.source=? AND c.tag_type='mood_candidate'""",
        (sid, ESSENTIA_SOURCE, CLAP_SOURCE),
    )
    for value, first, second in rows:
        tag(db, sid, value, "mood", CONSENSUS_SOURCE,
            1.0 - (1.0 - float(first or 0)) * (1.0 - float(second or 0)))
    # Promote genre/style only when at least two independent sources agree.
    rows = db.execute(
        """SELECT a.tag,COUNT(DISTINCT b.source)+1 sources,
                  MAX(MAX(a.confidence),MAX(b.confidence)) confidence
           FROM tags a JOIN tags b ON b.spotify_id=a.spotify_id AND b.tag=a.tag
           WHERE a.spotify_id=? AND a.source IN (?,?) AND b.source<>a.source
             AND a.tag_type IN ('genre','subgenre','audio_style_candidate','genre_audio_candidate')
             AND b.tag_type IN ('genre','subgenre','style','audio_style_candidate','genre_audio_candidate')
           GROUP BY a.tag""", (sid, MAEST_SOURCE, ESSENTIA_SOURCE)
    )
    broad = {"electronic", "rock", "pop", "jazz", "classical", "hip hop", "folk",
             "reggae", "latin", "blues", "country", "world music"}
    for value, sources, confidence in rows:
        tag(db, sid, value, "genre" if value in broad else "subgenre", CONSENSUS_SOURCE,
            clamp(max(0.70, float(confidence or 0))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--state", type=Path,
                        help="Optional checkpoint; import only unseen successful track-stages")
    args = parser.parse_args()
    manifest = manifests(args.manifest)
    rows = successes(args.results)
    already = set()
    if args.state and args.state.is_file():
        try:
            already = {tuple(item) for item in json.loads(args.state.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, TypeError):
            already = set()
    rows = {key: value for key, value in rows.items() if key not in already}
    db = connect()
    imported = 0
    touched = set()
    for (sid, stage), row in sorted(rows.items()):
        if sid not in manifest:
            continue
        source_path = manifest[sid]["source_path"]
        result = row["result"]
        timestamp = now()
        with db:
            store_artifact(db, sid, source_path, stage, result, timestamp)
            if stage == "rhythm_full":
                import_rhythm(db, sid, source_path, result, timestamp)
            elif stage == "maest_full":
                import_maest(db, sid, source_path, result, timestamp)
            elif stage == "essentia_full":
                import_essentia(db, sid, source_path, result, timestamp)
            elif stage == "clap_full":
                import_clap(db, sid, source_path, result, timestamp)
            else:
                continue
        imported += 1
        touched.add(sid)
    with db:
        for sid in touched:
            derive_consensus(db, sid)
    record_source_run(db, "audio-full:import-v2", now(), imported,
                      f"tracks={len(touched)},results={args.results}")
    if args.state and imported:
        args.state.parent.mkdir(parents=True, exist_ok=True)
        updated = sorted(already | set(rows))
        temporary = args.state.with_suffix(".partial.json")
        temporary.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")
        temporary.replace(args.state)
    print(f"Full audio import: track_stages={imported} tracks={len(touched)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Cheap A/B: does halving the clip bitrate change what the analysis says?

THE QUESTION THIS ANSWERS
Clips are Opus 192 kbps mono. The uplink measures 685 KB/s, so the 25,665 tracks
still outstanding are 136 GB and about 55 hours of pure upload — the binding
constraint on finishing, far more than GPU cost ($13). At 96 kbps that becomes
~27 hours. The only thing standing in the way is whether the models notice.

WHY IT IS ANSWERABLE FOR FREE
Tracks already analysed have their per-window results in the database. Re-encode
their clips at 96 kbps, re-run the SAME four stages on one small pod, and compare
against the stored 192 kbps answers. The only cost is minutes of one pod.

WHAT DECIDES IT
BPM is the strictest test and the one a DJ actually reads — a tempo that moves is
disqualifying on its own. Then genre top-1, and mood/instrument tag overlap.
The owner accepted "a small quality drop if it saves enough"; a BPM disagreement
is not a small drop, it is a wrong number in a DJ library.

    ./.venv/bin/python validate_bitrate.py --build --size 25
    ./.venv/bin/python probe_bitrate_run.py            # runs it on one pod
    ./.venv/bin/python validate_bitrate.py --compare data/bitrate_probe/results.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import zlib
from pathlib import Path

import jsonl_io
from musicdb import connect_readonly

ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "data" / "bitrate_probe"
CLIPS = ROOT / "data" / "cloud_full" / "clips"
TEST_BITRATE = "96k"
STAGES = ("rhythm_full", "maest_full", "essentia_full", "clap_full")
FIELDS = ["spotify_id", "clip_path", "segment_seconds", "coverage_mode",
          "required_stages", "track_name", "artist_names", "album_name", "isrc"]


def stored() -> dict[tuple[str, str], dict]:
    """The per-stage payloads already computed from 192 kbps clips."""
    out: dict[tuple[str, str], dict] = {}
    with connect_readonly() as db:
        for sid, stage, blob in db.execute(
                "SELECT spotify_id,stage,payload_blob FROM audio_analysis_artifacts "
                "WHERE stage IN (?,?,?,?)", STAGES):
            try:
                out[(sid, stage)] = json.loads(zlib.decompress(blob).decode())
            except Exception:
                continue
    return out


def build(size: int) -> None:
    have = stored()
    # Clips are pruned once their track is analysed, so the 192 kbps side of the
    # comparison is the STORED result, and the 96 kbps side is encoded fresh from
    # the same source file with the same settings the pipeline uses.
    with connect_readonly() as db:
        sources = {sid: path for sid, path in db.execute(
            "SELECT spotify_id, path FROM audio_files WHERE scan_status='matched'")}
    usable = [sid for sid, path in sources.items()
              if all((sid, s) in have for s in STAGES) and Path(path).is_file()]
    if not usable:
        raise SystemExit("no analysed track has a readable source file")
    chosen = usable[:size]
    clips = {sid: Path(sources[sid]) for sid in chosen}
    (PROBE / "clips").mkdir(parents=True, exist_ok=True)
    rows = []
    for track in chosen:
        target = PROBE / "clips" / f"{track}.opus"
        # Re-encode the EXISTING clip rather than the source: that is exactly what
        # a lower-bitrate pipeline would ship, and it keeps the comparison to the
        # one variable being tested.
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-y", "-i", str(clips[track]), "-c:a", "libopus",
                        "-b:a", TEST_BITRATE, "-vbr", "on", "-compression_level", "10",
                        "-ar", "48000", "-ac", "1", str(target)], check=True)
        duration = (have[(track, "clap_full")].get("track_duration")
                    or have[(track, "maest_full")].get("track_duration") or 300)
        rows.append({f: "" for f in FIELDS} | {
            "spotify_id": track,
            "clip_path": str(target.relative_to(ROOT)),
            "segment_seconds": f"{float(duration):.3f}",
            "coverage_mode": "full_track",
            "required_stages": ",".join(STAGES),
        })
    with (PROBE / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    # Compare against what the pipeline's 192k clip WOULD weigh (5.3 MB mean
    # measured across 965 real clips), not against the source file.
    new = sum((PROBE / "clips" / f"{t}.opus").stat().st_size for t in chosen)
    old = int(5.3e6 * len(chosen))
    subprocess.run(["tar", "-cf", str(PROBE / "bundle.tar"), "-C", str(ROOT),
                    "cloud_audio_full.py", "analyze_local_genres.py",
                    "analyze_local_semantics.py", "analyze_local_rhythm.py",
                    "analyze_essentia_full.py", "audio_taxonomy.py", "musicdb.py",
                    "requirements-cloud-audio.txt",
                    str((PROBE / "manifest.csv").relative_to(ROOT)),
                    str((PROBE / "clips").relative_to(ROOT))], check=True)
    print(f"probe shard ready: {len(rows)} tracks at {TEST_BITRATE}")
    print(f"  size {old/1e6:.1f} MB -> {new/1e6:.1f} MB  ({new/old*100:.0f}% of original)")
    print(f"  projected upload for 25,665 tracks: "
          f"{25665*5.3*new/old/1000:.0f} GB, {25665*5.3e6*new/old/685_000/3600:.0f} h")


def top_genre(payload: dict) -> str:
    preds = payload.get("top_predictions") or payload.get("genres") or []
    if isinstance(preds, list) and preds:
        first = preds[0]
        return str(first.get("label") if isinstance(first, dict) else first)
    return ""


def labels(payload: dict, key: str) -> set[str]:
    value = payload.get(key) or []
    if isinstance(value, dict):
        value = list(value)
    return {str(v.get("label") if isinstance(v, dict) else v) for v in value}


def compare(path: Path) -> None:
    have = stored()
    fresh: dict[tuple[str, str], dict] = {}
    with jsonl_io.open_jsonl(path) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "success":
                fresh[(row["spotify_id"], row["stage"])] = row.get("result") or {}

    bpm_same = bpm_n = 0
    bpm_worst = 0.0
    genre_same = genre_n = 0
    mood_hits = mood_total = 0
    for (sid, stage), new in sorted(fresh.items()):
        old = have.get((sid, stage))
        if not old:
            continue
        if stage == "rhythm_full":
            a, b = old.get("bpm"), new.get("bpm")
            if a and b:
                bpm_n += 1
                drift = abs(a - b)
                bpm_worst = max(bpm_worst, drift)
                bpm_same += drift < 0.5
        elif stage == "maest_full":
            genre_n += 1
            genre_same += top_genre(old) == top_genre(new)
        elif stage == "clap_full":
            for key in ("mood", "instrument"):
                o, n = labels(old, key), labels(new, key)
                if o:
                    mood_total += len(o)
                    mood_hits += len(o & n)

    print(f"compared {len(fresh)} stage results at {TEST_BITRATE} against stored 192k\n")
    if bpm_n:
        print(f"  BPM identical (<0.5):  {bpm_same}/{bpm_n}   worst drift {bpm_worst:.2f}")
    if genre_n:
        print(f"  genre top-1 identical: {genre_same}/{genre_n}")
    if mood_total:
        print(f"  mood/instrument labels retained: {mood_hits}/{mood_total} "
              f"({mood_hits/mood_total*100:.0f}%)")
    print("\nVERDICT: adopt 96k only if BPM is identical on every track — a tempo that "
          "moves is a wrong number in a DJ library, not a 'small quality drop'.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--size", type=int, default=25)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.build:
        build(args.size)
    elif args.compare:
        compare(args.compare)
    else:
        parser.error("use --build or --compare")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Find the tracks that sound closest to one reference track.

WHAT IT COMPARES: not tag strings, but the three audio EMBEDDINGS our GPU pass
produced for ~42,900 tracks — each a numeric fingerprint of how the track
actually sounds:

    laion/larger_clap_music   512   mood, texture, "vibe" (audio-text space)
    mtg-upf/discogs-maest     400   genre and style
    essentia/discogs-effnet  1280   general musical representation

WHY ALL THREE: each model is confidently wrong in its own way. CLAP hears mood
but confuses genres; MAEST knows genre but ignores energy. A track that ranks
high on all three is similar in every sense we can measure, which is what
"basically the same track" means.

HOW THE SCORE IS BUILT: cosine similarity per model, then each model's scores are
converted to z-scores ACROSS THE WHOLE LIBRARY before averaging. Raw cosines are
not comparable between models — one model may put every track between 0.85 and
0.99 and another between 0.1 and 0.6, so a plain average silently lets the
narrow model dominate. Tag overlap (Jaccard) and musical distance (BPM, key,
rhythm class) are added as smaller terms; the audio still decides.

HOW TO TWEAK: WEIGHTS is the whole opinion. Raise `tags` to favour tracks
labelled alike, raise `audio` to favour tracks that sound alike. `--bpm-window`
and `--same-key` turn the musical terms into hard filters for DJ use.

USAGE
  ./.venv/bin/python similar_tracks.py --query "iLee Lila" --limit 50
  ./.venv/bin/python similar_tracks.py --id 4vgKa... --limit 50 --spotify-only
"""
from __future__ import annotations
import argparse, json, sqlite3, sys, zlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"
# EXACT model identifiers — these strings are matched literally in SQL, and an
# abbreviated one silently matches nothing (every model "skipped", zero results).
MODELS = {
    "laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate": 512,
    "mtg-upf/discogs-maest-10s-dw-75e@d298f3a38365aa566b6a4417560423061ed82380/aggregate-probabilities": 400,
    "essentia/discogs-effnet-bs64-1+19-supervised-heads/aggregate-embedding": 1280,
}
WEIGHTS = {"audio": 1.0, "tags": 0.35, "musical": 0.25}


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    db.row_factory = sqlite3.Row
    return db


def decode(blob: bytes, dim: int) -> np.ndarray | None:
    try:
        vec = np.frombuffer(zlib.decompress(blob), dtype=np.float16).astype(np.float32)
    except Exception:
        return None
    return vec if vec.size == dim else None


def load_model(db, model: str, dim: int) -> tuple[list[str], np.ndarray]:
    """All aggregate vectors for one model, L2-normalised so a dot product IS
    the cosine similarity."""
    ids, rows = [], []
    for sid, blob in db.execute(
            """SELECT spotify_id, vector FROM audio_embeddings
               WHERE model=? AND (segment_start IS NULL OR segment_start=0.0)""", (model,)):
        vec = decode(blob, dim)
        if vec is None:
            continue
        ids.append(sid)
        rows.append(vec)
    matrix = np.vstack(rows) if rows else np.zeros((0, dim), dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return ids, matrix / norms


def tag_sets(db) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for sid, ttype, tag in db.execute(
            "SELECT spotify_id, tag_type, tag FROM tags WHERE tag IS NOT NULL"):
        out.setdefault(sid, set()).add(f"{ttype}:{tag}".lower())
    return out


def musical(db) -> dict[str, dict]:
    """BPM, key and rhythm class per track, from our own analysis first."""
    out: dict[str, dict] = {}
    for sid, blob in db.execute(
            "SELECT spotify_id, payload_blob FROM audio_analysis_artifacts WHERE stage='rhythm_full'"):
        try:
            p = json.loads(zlib.decompress(blob))
        except Exception:
            continue
        out[sid] = {"bpm": p.get("bpm"), "rhythm": p.get("rhythm_pattern")}
    for sid, key in db.execute("SELECT spotify_id, key FROM audio_features WHERE source='freqblog' AND key IS NOT NULL"):
        out.setdefault(sid, {})["key"] = key
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id"); ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--spotify-only", action="store_true",
                    help="only tracks with a real 22-char Spotify id")
    ap.add_argument("--bpm-window", type=float, default=0.0, help="hard filter, percent")
    ap.add_argument("--same-key", action="store_true")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    db = connect()
    if args.query and not args.id:
        words = args.query.split()
        sql = "SELECT spotify_id,title,artist_names FROM tracks WHERE " + \
              " AND ".join(["(title LIKE ? OR artist_names LIKE ?)"] * len(words))
        params = [x for w in words for x in (f"%{w}%", f"%{w}%")]
        hits = db.execute(sql, params).fetchall()
        if not hits:
            sys.exit(f"no track matches {args.query!r}")
        args.id = hits[0]["spotify_id"]
        print(f"reference: {hits[0]['artist_names']} — {hits[0]['title']}  ({args.id})")
    ref = args.id

    scores: dict[str, list[float]] = {}
    for model, dim in MODELS.items():
        ids, matrix = load_model(db, model, dim)
        if ref not in ids:
            print(f"  ! reference missing from {model.split('/')[0]}, skipping that model")
            continue
        index = {sid: i for i, sid in enumerate(ids)}
        cos = matrix @ matrix[index[ref]]
        # z-score ACROSS the library so models with different spreads combine fairly
        z = (cos - cos.mean()) / (cos.std() or 1.0)
        for sid, value in zip(ids, z):
            scores.setdefault(sid, []).append(float(value))
        print(f"  {model.split('/')[0]:10} compared against {len(ids):,} tracks")

    tags, mus = tag_sets(db), musical(db)
    ref_tags, ref_mus = tags.get(ref, set()), mus.get(ref, {})
    print(f"  reference: {len(ref_tags)} tags, bpm={ref_mus.get('bpm')}, "
          f"key={ref_mus.get('key')}, rhythm={ref_mus.get('rhythm')}")

    rows = []
    for sid, zs in scores.items():
        if sid == ref or len(zs) < 2:
            continue
        # A length test is NOT enough: local-only ids look like
        # "local_c1e89649e0ddf452", which is exactly 22 characters — the same
        # length as a real Spotify id. Nine of them reached a playlist before
        # this was caught, where Spotify would simply have rejected them.
        if args.spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        audio = sum(zs) / len(zs)
        t = tags.get(sid, set())
        jac = len(ref_tags & t) / len(ref_tags | t) if (ref_tags and t) else 0.0
        m = mus.get(sid, {})
        bpm_pen = key_bonus = 0.0
        if ref_mus.get("bpm") and m.get("bpm"):
            diff = abs(float(m["bpm"]) - float(ref_mus["bpm"])) / float(ref_mus["bpm"])
            if args.bpm_window and diff * 100 > args.bpm_window:
                continue
            bpm_pen = -min(diff * 4, 1.0)
        if ref_mus.get("key") and m.get("key"):
            same = str(m["key"]).strip().lower() == str(ref_mus["key"]).strip().lower()
            if args.same_key and not same:
                continue
            key_bonus = 0.5 if same else 0.0
        if ref_mus.get("rhythm") and m.get("rhythm") == ref_mus.get("rhythm"):
            key_bonus += 0.3
        total = (WEIGHTS["audio"] * audio + WEIGHTS["tags"] * jac * 4
                 + WEIGHTS["musical"] * (bpm_pen + key_bonus))
        rows.append((total, audio, jac, sid, m))
    rows.sort(key=lambda r: -r[0])

    # DEDUPE BY SONG, not by row. The library holds the radio edit, the extended
    # mix and the remix of the same record as separate tracks, and they sit next
    # to each other in any similarity ranking — "Samsara" took three of the top
    # fifty slots. A playlist of near-identical versions wastes the slots, so the
    # highest-scoring version of each song wins and the rest are dropped.
    def song_key(title: str, artist: str) -> str:
        base = (title or "").lower()
        for cut in (" - ", " (", " ["):
            if cut in base:
                base = base.split(cut)[0]
        first = (artist or "").split(",")[0].strip().lower()
        return f"{base.strip()}|{first}"

    seen: set[str] = set()
    deduped = []
    for row in rows:
        info = db.execute("SELECT title, artist_names FROM tracks WHERE spotify_id=?",
                          (row[3],)).fetchone()
        key = song_key(info["title"] if info else "", info["artist_names"] if info else "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= args.limit:
            break
    dropped = len(rows[:args.limit * 3]) - len(deduped)
    rows = deduped

    out = []
    for total, audio, jac, sid, m in rows[:args.limit]:
        info = db.execute("SELECT title, artist_names FROM tracks WHERE spotify_id=?", (sid,)).fetchone()
        out.append({"spotify_id": sid, "title": info["title"] if info else "?",
                    "artist": info["artist_names"] if info else "?",
                    "score": round(total, 3), "audio_z": round(audio, 2),
                    "tag_overlap": round(jac, 3),
                    "bpm": m.get("bpm"), "key": m.get("key")})
    print(f"\ntop {len(out)} of {len(rows):,} candidates:")
    for i, r in enumerate(out, 1):
        print(f"{i:3}. {r['score']:6.2f} z={r['audio_z']:5.2f} tag={r['tag_overlap']:.2f} "
              f"{str(r['bpm'])[:5]:>5} {str(r['key'] or ''):>4}  "
              f"{r['artist'][:26]:28} {r['title'][:40]}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1))
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

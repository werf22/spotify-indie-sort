"""Index local audio files and match them conservatively to library tracks.

The scanner is restart-safe: unchanged files are skipped, matches are persisted,
and ambiguous files remain visible instead of being attached to the wrong track.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
from mutagen import File as MutagenFile

from musicdb import connect, record_source_run

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
SOURCE = "local-audio:index-v1"
AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".wav", ".aif", ".aiff", ".ogg", ".opus"}
SPOTIFY_ID_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{22})(?![A-Za-z0-9])")
LEADING_TRACK_RE = re.compile(r"^\s*\d{1,4}\s*[.\-_]\s*")


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def first(tags, *keys: str) -> str | None:
    if not tags:
        return None
    lowered = {str(k).casefold(): v for k, v in tags.items()}
    for key in keys:
        value = lowered.get(key.casefold())
        if value:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            if value is not None:
                return str(value).strip() or None
    return None


def raw_isrc(path: Path) -> str | None:
    try:
        audio = MutagenFile(path, easy=False)
        tags = getattr(audio, "tags", None)
        if not tags:
            return None
        for key, value in tags.items():
            key_norm = str(key).casefold()
            if "isrc" not in key_norm and key_norm not in {"tsrc", "----:com.apple.itunes:isrc"}:
                continue
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            if hasattr(value, "text"):
                value = value.text[0] if value.text else None
            if isinstance(value, bytes):
                value = value.decode("utf-8", "ignore")
            candidate = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
            if 10 <= len(candidate) <= 15:
                return candidate
    except Exception:
        return None
    return None


def read_metadata(path: Path) -> dict:
    result = {
        "title": None, "artists": None, "album": None, "isrc": None,
        "duration": None, "codec": path.suffix.lower().lstrip("."),
    }
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None:
            tags = getattr(audio, "tags", None)
            result["title"] = first(tags, "title")
            result["artists"] = first(tags, "artist", "albumartist", "album artist")
            result["album"] = first(tags, "album")
            result["isrc"] = first(tags, "isrc", "tsrc")
            length = getattr(getattr(audio, "info", None), "length", None)
            result["duration"] = round(float(length), 3) if length else None
    except Exception:
        pass
    if result["isrc"]:
        result["isrc"] = re.sub(r"[^A-Za-z0-9]", "", result["isrc"]).upper()
    else:
        result["isrc"] = raw_isrc(path)

    stem = LEADING_TRACK_RE.sub("", path.stem).strip()
    if (not result["title"] or not result["artists"]) and " - " in stem:
        artist, title = stem.split(" - ", 1)
        result["artists"] = result["artists"] or artist.strip()
        result["title"] = result["title"] or title.strip()
    result["title"] = result["title"] or stem
    return result


def load_catalog(db):
    tracks = {}
    by_isrc = defaultdict(list)
    by_title = defaultdict(list)
    for row in db.execute(
        "SELECT spotify_id,title,artist_names,isrc,duration_ms FROM tracks"
    ):
        item = dict(row)
        item["norm_title"] = norm(item["title"])
        item["norm_artists"] = norm(item["artist_names"])
        tracks[item["spotify_id"]] = item
        if item["isrc"]:
            by_isrc[re.sub(r"[^A-Za-z0-9]", "", item["isrc"]).upper()].append(item)
        if item["norm_title"]:
            by_title[item["norm_title"]].append(item)
    return tracks, by_isrc, by_title


def duration_score(file_seconds: float | None, track_ms: int | None) -> float:
    if not file_seconds or not track_ms:
        return 0.5
    delta = abs(file_seconds - track_ms / 1000.0)
    if delta <= 2.0:
        return 1.0
    if delta <= 8.0:
        return 0.8
    if delta <= 20.0:
        return 0.45
    return 0.0


def match(path: Path, meta: dict, tracks, by_isrc, by_title):
    direct = SPOTIFY_ID_RE.search(path.stem)
    if direct and direct.group(1) in tracks:
        return direct.group(1), "spotify_id_filename", 1.0

    isrc = meta.get("isrc")
    if isrc and len(by_isrc.get(isrc, [])) == 1:
        return by_isrc[isrc][0]["spotify_id"], "isrc_tag", 0.995

    title = norm(meta.get("title"))
    artists = norm(meta.get("artists"))
    candidates = by_title.get(title, [])
    scored = []
    for candidate in candidates:
        artist_score = SequenceMatcher(None, artists, candidate["norm_artists"]).ratio() if artists else 0.0
        if artists and (artists in candidate["norm_artists"] or candidate["norm_artists"] in artists):
            artist_score = max(artist_score, 0.94)
        d_score = duration_score(meta.get("duration"), candidate.get("duration_ms"))
        score = 0.72 * artist_score + 0.28 * d_score
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= 0.82:
        margin = scored[0][0] - (scored[1][0] if len(scored) > 1 else 0.0)
        if margin >= 0.08 or scored[0][0] >= 0.95:
            confidence = min(0.97, 0.82 + 0.15 * scored[0][0])
            return scored[0][1]["spotify_id"], "title_artist_duration", confidence
    return None, "unmatched", 0.0


def configured_roots(cli_roots: list[str]) -> list[Path]:
    values = cli_roots[:]
    if not values:
        values = [x for x in os.getenv("AUDIO_LIBRARY_ROOTS", "").split(os.pathsep) if x]
    if not values:
        values = [str(Path.home() / "Music")]
    roots = []
    for value in values:
        path = Path(value).expanduser().resolve()
        if path.exists() and path not in roots:
            roots.append(path)
    return roots


def excluded_paths() -> set[str]:
    # ~/Music/Music is the Apple Music managed library on this machine. Opening
    # it can block indefinitely while the media service is asleep, and the
    # actual imported audio roots live beside it.
    defaults = [Path.home() / "Music" / "Music"]
    configured = [Path(x).expanduser() for x in os.getenv("AUDIO_LIBRARY_EXCLUDES", "").split(os.pathsep) if x]
    return {str(path.resolve()) for path in defaults + configured}


def iter_audio(roots: list[Path]):
    seen = set()
    excluded = excluded_paths()
    for root in roots:
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            dirnames[:] = [
                name for name in dirnames
                if str((directory_path / name).resolve()) not in excluded
                and not name.casefold().endswith((".musiclibrary", ".band", ".logicx"))
            ]
            for name in filenames:
                path = directory_path / name
                if path.suffix.lower() not in AUDIO_EXTENSIONS:
                    continue
                resolved = str(path.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    yield Path(resolved)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[], help="Audio root; repeatable")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--rescan", action="store_true")
    parser.add_argument("--prune", action="store_true", help="Mark missing files without deleting history")
    args = parser.parse_args()

    db = connect()
    tracks, by_isrc, by_title = load_catalog(db)
    roots = configured_roots(args.root)
    now = datetime.now(timezone.utc).isoformat()
    existing = {
        row["path"]: (row["file_size"], row["mtime_ns"])
        for row in db.execute("SELECT path,file_size,mtime_ns FROM audio_files")
    }
    rows = []
    observed = set()
    scanned = matched = skipped = errors = 0
    for path in iter_audio(roots):
        if args.limit and scanned >= args.limit:
            break
        scanned += 1
        observed.add(str(path))
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if not args.rescan and existing.get(str(path)) == signature:
                skipped += 1
                continue
            meta = read_metadata(path)
            sid, method, confidence = match(path, meta, tracks, by_isrc, by_title)
            if sid:
                matched += 1
            rows.append((
                str(path), sid, meta.get("isrc"), meta.get("title"), meta.get("artists"),
                meta.get("album"), meta.get("duration"), stat.st_size, stat.st_mtime_ns,
                meta.get("codec"), method, confidence,
                "matched" if sid else "unmatched", "queued" if sid else "blocked_unmatched",
                None, 0, None, now,
            ))
            if len(rows) >= 250:
                with db:
                    db.executemany(
                        """INSERT INTO audio_files
                           (path,spotify_id,isrc,title,artist_names,album,duration_seconds,file_size,mtime_ns,
                            codec,match_method,match_confidence,scan_status,analysis_status,analysis_version,
                            attempts,last_error,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(path) DO UPDATE SET
                             spotify_id=excluded.spotify_id,isrc=excluded.isrc,title=excluded.title,
                             artist_names=excluded.artist_names,album=excluded.album,
                             duration_seconds=excluded.duration_seconds,file_size=excluded.file_size,
                             mtime_ns=excluded.mtime_ns,codec=excluded.codec,match_method=excluded.match_method,
                             match_confidence=excluded.match_confidence,scan_status=excluded.scan_status,
                             analysis_status=CASE
                               WHEN audio_files.mtime_ns<>excluded.mtime_ns OR audio_files.spotify_id IS NOT excluded.spotify_id
                               THEN excluded.analysis_status ELSE audio_files.analysis_status END,
                             updated_at=excluded.updated_at""",
                        rows,
                    )
                rows.clear()
        except Exception as exc:
            errors += 1
            print(f"index error: {path}: {exc}")
    if rows:
        with db:
            db.executemany(
                """INSERT OR REPLACE INTO audio_files
                   (path,spotify_id,isrc,title,artist_names,album,duration_seconds,file_size,mtime_ns,
                    codec,match_method,match_confidence,scan_status,analysis_status,analysis_version,
                    attempts,last_error,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
    if args.prune and not args.limit:
        for row in db.execute("SELECT path FROM audio_files"):
            if row["path"] not in observed and not Path(row["path"]).exists():
                db.execute(
                    "UPDATE audio_files SET scan_status='missing',analysis_status='blocked_missing',updated_at=? WHERE path=?",
                    (now, row["path"]),
                )
        db.commit()
    record_source_run(
        db, SOURCE, now, matched,
        json.dumps({"roots": [str(x) for x in roots], "scanned": scanned, "matched": matched,
                    "skipped": skipped, "errors": errors}, ensure_ascii=False),
    )
    total = db.execute("SELECT COUNT(*) FROM audio_files").fetchone()[0]
    total_matched = db.execute("SELECT COUNT(*) FROM audio_files WHERE spotify_id IS NOT NULL").fetchone()[0]
    print(f"Audio index: scanned={scanned:,} new/changed={scanned-skipped:,} matched={matched:,} "
          f"errors={errors:,}; database files={total:,}, matched={total_matched:,}")


if __name__ == "__main__":
    main()

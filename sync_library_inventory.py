#!/usr/bin/env python3
"""Reconcile Spotify DB, Traktor collection, Missing Tracks and local audio.

This script never downloads media. It builds the canonical, resumable queue
used by lawful purchase-download adapters and by the menu-bar status app.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from index_audio_files import duration_score, load_catalog, norm
from musicdb import connect, record_source_run


ROOT = Path(__file__).resolve().parent
DEFAULT_NML = Path.home() / "Documents/Native Instruments/Traktor 4.0.2/collection.nml"
DEFAULT_M3U = Path.home() / "Documents/Missing Tracks.m3u"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_missing(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def decode_traktor_dir(value: str) -> str:
    # NML encodes separators as '/:' (/:Users/:jakub/:Music/:).
    decoded = value.replace("/:", "/").replace(":/", "/")
    decoded = re.sub(r"/{2,}", "/", decoded)
    if not decoded.startswith("/"):
        decoded = "/" + decoded
    if not decoded.endswith("/"):
        decoded += "/"
    return decoded


def traktor_path(location: ET.Element) -> str:
    directory = decode_traktor_dir(location.get("DIR") or "/")
    filename = location.get("FILE") or ""
    volume = (location.get("VOLUME") or "").strip()
    if volume and volume.casefold() not in {"macintosh hd", "macintosh hd - data"}:
        return f"/{volume}{directory}{filename}"
    return f"{directory}{filename}"


def resolve_existing(original: str, volume: str) -> str | None:
    candidates = [Path(original)]
    # External Traktor volume paths are represented as /VOLUME/path in M3U,
    # while macOS normally mounts them under /Volumes/VOLUME/path.
    if volume and original.startswith(f"/{volume}/"):
        relative = original[len(volume) + 2 :]
        candidates.append(Path("/Volumes") / volume / relative)
    # This library was migrated from the old account name `test` to `jakub`.
    if "/Users/test/" in original:
        candidates.append(Path(original.replace("/Users/test/", "/Users/jakub/")))
        if volume and original.startswith(f"/{volume}/Users/test/"):
            suffix = original.split("/Users/test/", 1)[1]
            candidates.append(Path.home() / suffix)
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return str(candidate.resolve())
        except OSError:
            continue
    return None


def match_track(title: str, artists: str, duration: float | None, by_title) -> tuple[str | None, str, float]:
    candidates = by_title.get(norm(title), [])
    artist_norm = norm(artists)
    scored = []
    for candidate in candidates:
        candidate_artists = candidate["norm_artists"]
        artist_score = SequenceMatcher(None, artist_norm, candidate_artists).ratio() if artist_norm else 0.0
        artist_tokens = set(artist_norm.split())
        candidate_tokens = set(candidate_artists.split())
        if artist_tokens and candidate_tokens:
            overlap = len(artist_tokens & candidate_tokens) / max(1, min(len(artist_tokens), len(candidate_tokens)))
            artist_score = max(artist_score, overlap)
        d_score = duration_score(duration, candidate.get("duration_ms"))
        score = 0.78 * artist_score + 0.22 * d_score
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return None, "unmatched", 0.0
    best = scored[0]
    margin = best[0] - (scored[1][0] if len(scored) > 1 else 0.0)
    if best[0] >= 0.82 and (margin >= 0.07 or best[0] >= 0.95):
        return best[1]["spotify_id"], "title_artist_duration", round(min(0.97, best[0]), 4)
    return None, "ambiguous", round(best[0], 4)


def parse_collection(db, nml: Path, missing: set[str], batch_size: int = 500) -> dict:
    _, _, by_title = load_catalog(db)
    now = utcnow()
    rows = []
    counts = Counter()
    missing_by_basename: dict[str, list[str]] = defaultdict(list)
    for missing_path in missing:
        missing_by_basename[Path(missing_path).name].append(missing_path)
    source = str(nml.resolve())

    with db:
        db.execute("DELETE FROM traktor_entries WHERE source_nml=?", (source,))

    for _, entry in ET.iterparse(nml, events=("end",)):
        if entry.tag != "ENTRY":
            continue
        counts["entries"] += 1
        location = entry.find("LOCATION")
        if location is None:
            entry.clear()
            continue
        title = entry.get("TITLE") or ""
        artists = entry.get("ARTIST") or ""
        album_node = entry.find("ALBUM")
        info = entry.find("INFO")
        album = album_node.get("TITLE") if album_node is not None else None
        duration = None
        bitrate = None
        if info is not None:
            try:
                duration = float(info.get("PLAYTIME")) if info.get("PLAYTIME") else None
            except ValueError:
                duration = None
            try:
                bitrate = int(float(info.get("BITRATE"))) if info.get("BITRATE") else None
            except ValueError:
                bitrate = None
        original_path = traktor_path(location)
        is_missing = original_path in missing
        # Conservative fallback only when the basename is unique in Missing Tracks.
        if not is_missing and len(missing_by_basename.get(Path(original_path).name, ())) == 1:
            is_missing = True
        resolved = resolve_existing(original_path, location.get("VOLUME") or "")
        sid, method, confidence = match_track(title, artists, duration, by_title)
        if is_missing:
            counts["missing_entries"] += 1
        if resolved:
            counts["existing_paths"] += 1
        if sid:
            counts["spotify_matched"] += 1
        elif method == "ambiguous":
            counts["ambiguous"] += 1
        else:
            counts["unmatched"] += 1
        identity = "\0".join((source, original_path, title, artists))
        entry_id = hashlib.sha256(identity.encode("utf-8", "replace")).hexdigest()[:32]
        rows.append(
            (
                entry_id, source, original_path, title, artists, album, duration, bitrate,
                int(is_missing), int(bool(resolved)), resolved, sid, method, confidence, now,
            )
        )
        if len(rows) >= batch_size:
            with db:
                db.executemany(
                    """INSERT OR REPLACE INTO traktor_entries
                       (entry_id,source_nml,path,title,artist_names,album,duration_seconds,bitrate,
                        missing_manifest,path_exists,resolved_path,spotify_id,match_method,
                        match_confidence,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    rows,
                )
            rows.clear()
        entry.clear()
    if rows:
        with db:
            db.executemany(
                """INSERT OR REPLACE INTO traktor_entries
                   (entry_id,source_nml,path,title,artist_names,album,duration_seconds,bitrate,
                    missing_manifest,path_exists,resolved_path,spotify_id,match_method,
                    match_confidence,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
    return dict(counts)


def build_queue(db) -> dict:
    now = utcnow()
    physically_present: dict[str, str] = {}
    for row in db.execute(
        "SELECT spotify_id,path FROM audio_files WHERE spotify_id IS NOT NULL AND scan_status='matched'"
    ):
        if row["spotify_id"] in physically_present:
            continue
        try:
            if Path(row["path"]).is_file() and Path(row["path"]).stat().st_size > 0:
                physically_present[row["spotify_id"]] = row["path"]
        except OSError:
            pass
    verified = {
        row["path"]
        for row in db.execute("SELECT path FROM audio_verification WHERE status='valid'")
    }
    traktor: dict[str, dict[str, bool]] = defaultdict(lambda: {"missing": False, "present": False, "any": False})
    for row in db.execute(
        "SELECT spotify_id,missing_manifest,path_exists FROM traktor_entries WHERE spotify_id IS NOT NULL"
    ):
        state = traktor[row["spotify_id"]]
        state["any"] = True
        state["missing"] = state["missing"] or bool(row["missing_manifest"])
        state["present"] = state["present"] or bool(row["path_exists"])

    counts = Counter()
    rows = []
    for track in db.execute("SELECT spotify_id,library_sources FROM tracks"):
        sid = track["spotify_id"]
        path = physically_present.get(sid)
        tstate = traktor.get(sid, {"missing": False, "present": False, "any": False})
        liked = "liked songs" in (track["library_sources"] or "").casefold()
        priority = 40 if liked else 100
        if path and path in verified:
            local_state, acquisition_state, reason = "verified", "complete", "verified_local_audio"
        elif path:
            local_state, acquisition_state, reason = "present_unverified", "verify_local", "local_audio_index"
        elif tstate["present"]:
            local_state, acquisition_state, reason = "traktor_present", "locate_existing", "traktor_resolved_path"
        elif tstate["any"] and not tstate["missing"]:
            # User explicitly says entries outside Missing Tracks exist somewhere;
            # never send these to a downloader until relocation search is exhausted.
            local_state, acquisition_state, reason = "traktor_claimed_local", "locate_existing", "traktor_not_in_missing_manifest"
        elif tstate["missing"]:
            local_state, acquisition_state, reason = "missing", "needs_source", "traktor_missing_manifest"
        else:
            local_state, acquisition_state, reason = "missing", "needs_source", "spotify_only"
        counts[acquisition_state] += 1
        rows.append((sid, local_state, acquisition_state, reason, priority, path, now))
    with db:
        db.executemany(
            """INSERT INTO acquisition_queue
               (spotify_id,local_state,acquisition_state,reason,priority,verified_path,updated_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(spotify_id) DO UPDATE SET
                 local_state=excluded.local_state,
                 acquisition_state=CASE
                   WHEN acquisition_queue.acquisition_state IN ('downloading','purchased_download_ready')
                        AND excluded.acquisition_state='needs_source'
                   THEN acquisition_queue.acquisition_state
                   ELSE excluded.acquisition_state END,
                 reason=excluded.reason,priority=excluded.priority,
                 verified_path=COALESCE(excluded.verified_path,acquisition_queue.verified_path),
                 updated_at=excluded.updated_at""",
            rows,
        )
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", type=Path, default=DEFAULT_NML)
    parser.add_argument("--missing", type=Path, default=DEFAULT_M3U)
    args = parser.parse_args()
    if not args.collection.is_file():
        raise SystemExit(f"Traktor collection not found: {args.collection}")
    if not args.missing.is_file():
        raise SystemExit(f"Missing Tracks file not found: {args.missing}")

    db = connect()
    missing = read_missing(args.missing)
    collection_counts = parse_collection(db, args.collection, missing)
    queue_counts = build_queue(db)
    summary = {
        "missing_manifest_unique_paths": len(missing),
        "collection": collection_counts,
        "acquisition_queue": queue_counts,
    }
    now = utcnow()
    record_source_run(db, "traktor:inventory-v1", now, collection_counts.get("entries", 0), json.dumps(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

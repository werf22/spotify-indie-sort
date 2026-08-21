#!/usr/bin/env python3
"""The similarity screen's backend: search, ranking, audio streaming, playlists.

Kept out of server.py so the browser app stays readable. The ranking itself is
`similarity_engine.py` at the repo root — the same module the command line uses,
so the two can never disagree about what "similar" means.

WHAT EACH PIECE DOES
  search()          find the reference track the user means
  similar()         the ranked list (engine)
  audio_response()  streams the LOCAL file so playback is the full track, not a
                    30-second preview — with HTTP Range support, without which
                    Safari refuses to play at all and no browser can seek
  create_playlist() pushes the result to Spotify through the repo's existing
                    authenticated client
"""
from __future__ import annotations

import mimetypes
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import similarity_engine as engine        # noqa: E402

# Browsers cannot play every codec a DJ library holds; these are the ones that
# work natively in Chrome and Safari. Anything else falls back to the Spotify
# player in the UI.
PLAYABLE = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
            ".aac": "audio/aac", ".wav": "audio/wav", ".flac": "audio/flac",
            ".opus": "audio/ogg", ".ogg": "audio/ogg", ".aiff": "audio/aiff",
            ".aif": "audio/aiff"}


def track_path(track_id: str) -> Path | None:
    db = sqlite3.connect(ROOT / "data" / "music.db", timeout=60)
    try:
        row = db.execute("""SELECT path FROM audio_files
                            WHERE spotify_id=? AND path IS NOT NULL LIMIT 1""",
                         (track_id,)).fetchone()
    finally:
        db.close()
    if not row:
        return None
    path = Path(row[0])
    try:
        return path if path.is_file() else None
    except OSError:                        # unreadable media, e.g. a bad sector
        return None


def audio_response(handler, track_id: str) -> None:
    """Stream a local file, honouring Range requests.

    Safari will not start playback at all unless the server answers Range with
    206 and a Content-Range, and without it no browser can seek. Serving the
    whole body with 200 looks fine in Chrome and silently fails elsewhere.
    """
    path = track_path(track_id)
    if path is None:
        handler.send_error(404, "no local file for this track")
        return
    ctype = PLAYABLE.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] \
        or "application/octet-stream"
    size = path.stat().st_size
    start, end = 0, size - 1
    rng = handler.headers.get("Range")
    partial = False
    if rng and rng.startswith("bytes="):
        chunk = rng.split("=", 1)[1].split(",")[0]
        first, _, last = chunk.partition("-")
        if first.strip():
            start = int(first)
            end = int(last) if last.strip() else size - 1
        elif last.strip():                 # suffix range: last N bytes
            start = max(0, size - int(last))
        start = max(0, min(start, size - 1))
        end = max(start, min(end, size - 1))
        partial = True
    length = end - start + 1

    handler.send_response(206 if partial else 200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(length))
    if partial:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers()
    with path.open("rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            block = fh.read(min(262144, remaining))
            if not block:
                break
            try:
                handler.wfile.write(block)
            except (BrokenPipeError, ConnectionResetError):
                return                     # the user skipped tracks; not an error
            remaining -= len(block)


def create_playlist(name: str, description: str, track_ids: list[str]) -> dict:
    """Create a private Spotify playlist and fill it.

    Uses the repo's existing authenticated client, so no new credentials and no
    login flow inside the app. Local-only ids are dropped here as well as in the
    engine — Spotify rejects the whole request if one id is not a real track.
    """
    from spotify_client import SpotifyClient
    ids = [t for t in track_ids if t and len(t) == 22 and not t.startswith("local_")]
    if not ids:
        raise RuntimeError("none of these tracks exist on Spotify")
    client = SpotifyClient()
    me = client.current_user()
    playlist = client.create_playlist(me["id"], name, description, False)
    for i in range(0, len(ids), 100):      # Spotify caps one request at 100
        client.add_tracks(playlist["id"], [f"spotify:track:{t}" for t in ids[i:i + 100]])
    return {"id": playlist["id"], "url": f"https://open.spotify.com/playlist/{playlist['id']}",
            "added": len(ids), "skipped": len(track_ids) - len(ids)}

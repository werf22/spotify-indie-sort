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

def preview_response(handler, track_id: str) -> None:
    """Stream a 30-second preview for a track we do NOT have on disk.

    WHY IT IS FETCHED FRESH: the preview URLs captured during enrichment are
    signed and time-limited — every stored one now answers 403. The track's
    Deezer id does not expire, so the URL is requested at click time.

    WHY IT IS PROXIED rather than handed to the browser: the CDN does not send
    CORS headers, and going through this server also means the audio arrives in
    our own <audio> element — which is what makes it obey the chosen CUE output
    device. An iframe would ignore it and need a second click.
    """
    import json as _json
    import urllib.request as _req
    db = sqlite3.connect(ROOT / "data" / "music.db", timeout=60)
    try:
        row = db.execute("""SELECT value_num FROM track_attributes
                            WHERE spotify_id=? AND attribute='track.id'
                              AND value_num IS NOT NULL LIMIT 1""", (track_id,)).fetchone()
    finally:
        db.close()
    if not row:
        handler.send_error(404, "no preview for this track")
        return
    try:
        with _req.urlopen(f"https://api.deezer.com/track/{int(row[0])}", timeout=20) as api:
            url = (_json.loads(api.read()) or {}).get("preview")
        if not url:
            handler.send_error(404, "no preview offered")
            return
        with _req.urlopen(url, timeout=25) as audio:
            body = audio.read()
    except Exception as exc:
        handler.send_error(502, f"preview unavailable: {type(exc).__name__}")
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "audio/mpeg")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass


# ---------------------------------------------------------------------------
# SPOTIFY PLAYBACK
#
# Playing a WHOLE track inside the app uses Spotify's Web Playback SDK, which
# needs a short-lived access token in the page. The REFRESH token never leaves
# the server — only the one-hour access token is handed over, and only to the
# app's own page on localhost.
#
# The SDK also needs the `streaming` permission. If the stored token does not
# have it, `spotify_token()` says so plainly and the page falls back to the
# 30-second embed rather than failing silently.
_spotify_cache: dict = {"token": None, "until": 0.0, "streaming": None}


def spotify_token() -> dict:
    import time
    if _spotify_cache["token"] and time.time() < _spotify_cache["until"] - 60:
        return {"token": _spotify_cache["token"], "streaming": _spotify_cache["streaming"]}
    try:
        import requests
        import spotify_client as sc
        client = sc.SpotifyClient()
        resp = requests.post(sc.TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": client._token["refresh_token"],
            "client_id": sc.CLIENT_ID, "client_secret": sc.CLIENT_SECRET,
        }, timeout=20)
        if resp.status_code != 200:
            return {"error": f"Spotify odmietol prihlásenie ({resp.status_code})"}
        data = resp.json()
        scopes = (data.get("scope") or "").split()
        _spotify_cache.update({
            "token": data["access_token"],
            "until": time.time() + int(data.get("expires_in", 3600)),
            "streaming": "streaming" in scopes,
        })
        return {"token": _spotify_cache["token"], "streaming": _spotify_cache["streaming"]}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def spotify_play(track_id: str, device_id: str, position_ms: int = 0) -> dict:
    """Start a track on the device the page's SDK player registered."""
    auth = spotify_token()
    if "error" in auth:
        return auth
    import requests
    resp = requests.put(
        "https://api.spotify.com/v1/me/player/play",
        params={"device_id": device_id},
        headers={"Authorization": f"Bearer {auth['token']}"},
        json={"uris": [f"spotify:track:{track_id}"], "position_ms": int(position_ms)},
        timeout=20)
    if resp.status_code in (200, 202, 204):
        return {"ok": True}
    # 404 here means the device vanished; 403 usually means not Premium.
    return {"error": f"Spotify: {resp.status_code} {resp.text[:120]}"}

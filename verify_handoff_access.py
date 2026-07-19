#!/usr/bin/env python3
"""Verify local service access without printing credentials or consuming paid quota."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def protected(path: Path) -> bool:
    try:
        return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    except OSError:
        return False


def json_has_any(path: Path, names: tuple[str, ...]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return any(bool(payload.get(name)) for name in names)
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def live_spotify() -> bool:
    try:
        from spotify_client import SpotifyClient
        response = SpotifyClient().request("GET", "/me")
        return response.ok and bool(response.json().get("id"))
    except Exception:
        return False


def live_lastfm() -> bool:
    key = os.getenv("LASTFM_API_KEY", "").strip()
    user = os.getenv("LASTFM_USERNAME", "").strip()
    if not key or not user:
        return False
    try:
        response = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={"method": "user.getInfo", "user": user, "api_key": key, "format": "json"},
            timeout=20,
        )
        return response.ok and "user" in response.json()
    except Exception:
        return False


def live_musicbrainz() -> bool:
    agent = os.getenv("MUSICBRAINZ_USER_AGENT", "").strip()
    if not agent:
        return False
    try:
        response = requests.get(
            "https://musicbrainz.org/ws/2/recording/",
            params={"query": "recording:Silence", "limit": 1, "fmt": "json"},
            headers={"User-Agent": agent}, timeout=20,
        )
        return response.ok
    except Exception:
        return False


def live_runpod() -> bool:
    command = Path.home() / ".local" / "bin" / "runpodctl"
    try:
        proc = subprocess.run([str(command), "user"], capture_output=True, text=True, timeout=30)
        payload = json.loads(proc.stdout) if proc.returncode == 0 else {}
        return bool(payload.get("id")) and "clientBalance" in payload
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="Perform safe read-only Spotify/Last.fm/MusicBrainz/RunPod checks")
    args = parser.parse_args()
    spotify_mcp = ROOT.parent / "spotify-mcp-server" / "spotify-config.json"
    tidal_token = Path.home() / ".config" / "tidal_dl_ng-dev" / "token.json"
    runpod_config = Path.home() / ".runpod" / "config.toml"
    status = {
        "secret_files_protected": all(protected(path) for path in (
            ROOT / ".env", ROOT / "data" / "token.json", spotify_mcp,
            tidal_token, runpod_config,
        )),
        "spotify_env_configured": all(os.getenv(name, "").strip() for name in (
            "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
        )),
        "spotify_refresh_token_present": json_has_any(ROOT / "data" / "token.json",
                                                       ("refresh_token", "refreshToken")),
        "spotify_mcp_configured": json_has_any(spotify_mcp,
                                                ("refreshToken", "refresh_token", "accessToken")),
        "freqblog_configured": bool(os.getenv("FREQBLOG_API_KEY", "").strip()),
        "freqblog_existing_data": (ROOT / "data" / "music.db").is_file(),
        "lastfm_configured": all(os.getenv(name, "").strip() for name in (
            "LASTFM_API_KEY", "LASTFM_USERNAME",
        )),
        "musicbrainz_public_reads_configured": bool(
            os.getenv("MUSICBRAINZ_USER_AGENT", "").strip()
        ),
        "runpod_cli_configured": runpod_config.is_file(),
        "tidal_dl_ng_installed": (Path.home() / ".local" / "bin" / "tidal-dl-ng").is_file(),
        "tidal_token_present": json_has_any(tidal_token,
                                             ("access_token", "refresh_token", "token_type")),
    }
    if args.live:
        status.update({
            "spotify_live": live_spotify(),
            "lastfm_live": live_lastfm(),
            "musicbrainz_live": live_musicbrainz(),
            "runpod_live": live_runpod(),
        })
    print(json.dumps(status, indent=2, sort_keys=True))
    if not all(status.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

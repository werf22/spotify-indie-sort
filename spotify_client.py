"""
Minimal Spotify Web API client.
Inputs: SPOTIFY_CLIENT_ID/SECRET (.env) + a refresh token in data/token.json.
Outputs: authenticated requests.get/post/put/delete against api.spotify.com,
with automatic access-token refresh and 429 backoff.

Token bootstrap: data/token.json needs {"refresh_token": "..."} to start.
Easiest source: run the spotify-mcp-server's `npm run auth` once (sibling
project) and copy its refreshToken in — see README.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN_PATH = BASE_DIR / "data" / "token.json"
API_BASE = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()

# Spotify rejects requests faster than this in bursts across ~1400 playlists
# worth of pagination. Bump this up only if you start seeing 429s anyway.
REQUEST_PACING_SECONDS = 0.05


class SpotifyClient:
    def __init__(self) -> None:
        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError("SPOTIFY_CLIENT_ID/SECRET missing — fill in .env")
        if not TOKEN_PATH.exists():
            raise RuntimeError(
                f"{TOKEN_PATH} missing a refresh_token — see README 'Token bootstrap'"
            )
        self._token = json.loads(TOKEN_PATH.read_text())
        self._access_token: str | None = None
        self._expires_at: float = 0

    def _save_token(self) -> None:
        TOKEN_PATH.write_text(json.dumps(self._token, indent=2) + "\n")

    def _refresh(self) -> None:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._token["refresh_token"],
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + payload.get("expires_in", 3600) - 60
        # Spotify sometimes rotates the refresh token; keep it if it does.
        if payload.get("refresh_token"):
            self._token["refresh_token"] = payload["refresh_token"]
        self._save_token()

    def _ensure_token(self) -> str:
        if not self._access_token or time.time() >= self._expires_at:
            self._refresh()
        return self._access_token

    # A short 429 (a few seconds) is normal API throttling — worth an
    # automatic retry. Anything longer means Spotify has actually banned
    # this app for a while (e.g. after hammering it too hard); silently
    # sleeping for hours would hide that. Fail loudly instead so whoever's
    # running this finds out immediately, not hours later.
    MAX_AUTO_RETRY_WAIT_SECONDS = 120

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        for attempt in range(6):
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {self._ensure_token()}"
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "2")) + 1
                if wait > self.MAX_AUTO_RETRY_WAIT_SECONDS:
                    clear_at = time.strftime(
                        "%Y-%m-%d %H:%M:%S %Z", time.localtime(time.time() + wait)
                    )
                    raise RuntimeError(
                        f"Rate limited for {wait/3600:.1f}h (until ~{clear_at}) on "
                        f"{method} {path} — this app/token is banned, not just "
                        "throttled. Not waiting silently; re-run after that time."
                    )
                time.sleep(wait)
                continue
            if resp.status_code == 401:
                self._access_token = None
                continue
            resp.raise_for_status()
            time.sleep(REQUEST_PACING_SECONDS)
            return resp
        raise RuntimeError(f"Gave up on {method} {path} after repeated 429/401")

    def get_paginated(self, path: str, params: dict | None = None):
        """Yield items across Spotify's `next`-link pagination."""
        params = dict(params or {})
        params.setdefault("limit", 50)
        url: str | None = path
        first = True
        while url:
            resp = self.request("GET", url, params=params if first else None)
            first = False
            payload = resp.json()
            page = payload.get("items", payload)
            for item in page:
                yield item
            url = payload.get("next")

    # -- high-level helpers -------------------------------------------------

    def current_user(self) -> dict:
        return self.request("GET", "/me").json()

    def my_owned_playlists(self, user_id: str):
        for pl in self.get_paginated("/me/playlists"):
            if pl.get("owner", {}).get("id") == user_id:
                yield pl

    def playlist_tracks(self, playlist_id: str):
        fields = "items(added_at,track(id,name,uri,artists(id,name),album(name))),next"
        for item in self.get_paginated(
            f"/playlists/{playlist_id}/tracks", {"fields": fields}
        ):
            yield item

    def liked_songs(self):
        for item in self.get_paginated("/me/tracks"):
            yield item

    def several_artists_genres(self, artist_ids: list[str]) -> dict[str, list[str]]:
        genres: dict[str, list[str]] = {}
        for i in range(0, len(artist_ids), 50):
            chunk = artist_ids[i : i + 50]
            resp = self.request("GET", "/artists", params={"ids": ",".join(chunk)})
            for artist in resp.json().get("artists", []):
                if artist:
                    genres[artist["id"]] = artist.get("genres", [])
        return genres

    def create_playlist(self, user_id: str, name: str, description: str, public: bool):
        return self.request(
            "POST",
            f"/users/{user_id}/playlists",
            json={"name": name, "description": description, "public": public},
        ).json()

    def add_tracks(self, playlist_id: str, uris: list[str]) -> None:
        for i in range(0, len(uris), 100):
            chunk = uris[i : i + 100]
            self.request(
                "POST", f"/playlists/{playlist_id}/tracks", json={"uris": chunk}
            )

"""
Creates (once) or reuses the target playlist and adds every "keep" track
that isn't in it yet. Safe to re-run: state.json remembers the playlist id
and which track ids have already been added, so re-runs only add new ones.

Input: data/library_export.json + data/classification.json
Output: writes to the real Spotify playlist, data/state.json, data/run_log.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from spotify_client import SpotifyClient

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"
RUN_LOG_PATH = DATA_DIR / "run_log.json"

PLAYLIST_NAME = os.getenv("TARGET_PLAYLIST_NAME", "Indie Sort").strip()
DESCRIPTION = "Everything from my library that isn't afro/organic/shamanic house or ecstatic-dance grooves. Auto-sorted."


def log(msg: str) -> None:
    print(f"[build_playlist] {msg}", flush=True)


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"playlist_id": None, "added_track_ids": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_run_log(entry: dict) -> None:
    log_data = json.loads(RUN_LOG_PATH.read_text()) if RUN_LOG_PATH.exists() else []
    log_data.append(entry)
    RUN_LOG_PATH.write_text(json.dumps(log_data, indent=2, ensure_ascii=False))


def main() -> None:
    tracks = {t["id"]: t for t in json.loads((DATA_DIR / "library_export.json").read_text())}
    decisions = json.loads((DATA_DIR / "classification.json").read_text())
    keep_ids = [d["id"] for d in decisions if d["decision"] == "keep"]
    log(f"{len(keep_ids)} tracks marked keep out of {len(decisions)} classified")

    client = SpotifyClient()
    me = client.current_user()
    state = load_state()

    if not state["playlist_id"]:
        playlist = client.create_playlist(me["id"], PLAYLIST_NAME, DESCRIPTION, public=False)
        state["playlist_id"] = playlist["id"]
        log(f"created playlist '{PLAYLIST_NAME}' -> {playlist['external_urls']['spotify']}")
        save_state(state)
    else:
        log(f"reusing existing playlist id {state['playlist_id']}")

    already_added = set(state["added_track_ids"])
    new_ids = [tid for tid in keep_ids if tid not in already_added and tid in tracks]
    log(f"{len(new_ids)} new tracks to add ({len(already_added)} already added in prior runs)")

    if new_ids:
        uris = [tracks[tid]["uri"] for tid in new_ids]
        client.add_tracks(state["playlist_id"], uris)
        state["added_track_ids"] = sorted(already_added | set(new_ids))
        save_state(state)

    playlist_url = f"https://open.spotify.com/playlist/{state['playlist_id']}"
    log(f"done. playlist now has {len(state['added_track_ids'])} tracks total -> {playlist_url}")

    append_run_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "classified": len(decisions),
            "kept": len(keep_ids),
            "excluded": len(decisions) - len(keep_ids),
            "added_this_run": len(new_ids),
            "playlist_total": len(state["added_track_ids"]),
            "playlist_url": playlist_url,
        }
    )


if __name__ == "__main__":
    main()

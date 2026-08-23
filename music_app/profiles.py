#!/usr/bin/env python3
"""Saved similarity profiles — the owner's own preference sets.

WHAT A PROFILE IS: a named snapshot of everything the similarity screen can be
set to — which of the 77 signals are ticked, the four group weights, and the
filters (BPM window, same-key, result count, Spotify-only). Loading one is a
single click.

WHY ON DISK AND NOT IN THE BROWSER: localStorage dies with a cleared cache, a
new browser or a second window, and these are settings the owner tunes over
weeks. They live in data/similarity_profiles.json, which is also easy to back up
and to read by hand.

FOLDERS are just a path string ("Techno/Peak time") rather than a nested
structure. One flat list with a path per item can be rendered as any tree, while
真 nesting would need recursive moves, orphan handling and re-parenting for no
gain at this size.

WRITES ARE ATOMIC: written to a temp file and renamed, so an interrupted save
cannot leave a half-written file where every profile used to be.

HOW TO TWEAK: nothing here is tuned — it is storage. The interesting decisions
are in similarity_engine.py.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "similarity_profiles.json"

# Only these keys are stored, whatever the caller sends: a profile must not
# become a dumping ground for whatever the UI happens to have in scope.
FIELDS = ("name", "folder", "enabled", "group_weights", "filters",
          "pinned", "order", "note")


def _read() -> list[dict]:
    if not STORE.is_file():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write(profiles: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".partial.json")
    tmp.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STORE)


def list_profiles() -> list[dict]:
    """Pinned first, then the owner's own order, then name."""
    profiles = _read()
    profiles.sort(key=lambda p: (not p.get("pinned"), p.get("order", 1e9),
                                 (p.get("name") or "").lower()))
    return profiles


def save(payload: dict) -> dict:
    """Create or update. An id that is not already stored creates a new row."""
    profiles = _read()
    pid = str(payload.get("id") or "").strip()
    clean = {k: payload.get(k) for k in FIELDS if k in payload}
    clean["name"] = (clean.get("name") or "Bez názvu").strip()[:80]
    clean["folder"] = (clean.get("folder") or "").strip("/ ").strip()[:120]
    for existing in profiles:
        if existing.get("id") == pid and pid:
            existing.update(clean)
            existing["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _write(profiles)
            return existing
    row = {"id": pid or uuid.uuid4().hex[:12], **clean,
           "order": clean.get("order", len(profiles)),
           "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    profiles.append(row)
    _write(profiles)
    return row


def delete(pid: str) -> bool:
    profiles = _read()
    remaining = [p for p in profiles if p.get("id") != pid]
    if len(remaining) == len(profiles):
        return False
    _write(remaining)
    return True


def reorder(order: list[str]) -> list[dict]:
    """Apply a new order given as a list of ids, top to bottom."""
    rank = {pid: i for i, pid in enumerate(order)}
    profiles = _read()
    for p in profiles:
        if p.get("id") in rank:
            p["order"] = rank[p["id"]]
    _write(profiles)
    return list_profiles()


def rename_folder(old: str, new: str) -> int:
    """Rename a folder and everything nested under it."""
    old, new = old.strip("/ "), new.strip("/ ")
    profiles = _read()
    touched = 0
    for p in profiles:
        folder = p.get("folder") or ""
        if folder == old or folder.startswith(old + "/"):
            p["folder"] = (new + folder[len(old):]).strip("/ ")
            touched += 1
    if touched:
        _write(profiles)
    return touched

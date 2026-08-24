#!/usr/bin/env python3
"""Getting tracks from this app into Traktor, during a set.

THE HARD LIMIT, stated because it shapes everything else: a web page CANNOT drag
a file into a native application. The browser sandbox forbids handing a real
filesystem path to another app, and no amount of JavaScript changes that. So the
bridge is Finder: the app puts exactly the right thing in front of the owner and
he drags from there, which Traktor accepts natively.

TWO ROUTES, matching how a DJ actually works:
  reveal(one track)     -> Finder opens with the file selected, ready to drag
                           straight onto a deck.
  playlist(many tracks) -> writes an .m3u next to the music and reveals it;
                           dragging that one file into Traktor's playlist tree
                           imports the whole selection at once.

WHY .m3u AND NOT collection.nml: Traktor reads collection.nml when it STARTS.
Writing a playlist in there during a set would be invisible until a restart —
useless mid-gig, and risky besides. An .m3u is imported live.

HOW TO TWEAK: EXPORT_DIR is where the playlists land.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = Path.home() / "Music" / "From Similar App"


def paths_for(ids: list[str]) -> list[tuple[str, str, str]]:
    """(spotify_id, path, display) for tracks that really exist on disk."""
    if not ids:
        return []
    db = sqlite3.connect(ROOT / "data" / "music.db", timeout=60)
    db.row_factory = sqlite3.Row
    try:
        marks = ",".join("?" * len(ids))
        rows = db.execute(
            f"""SELECT t.spotify_id, t.title, t.artist_names,
                       (SELECT path FROM audio_files f
                        WHERE f.spotify_id=t.spotify_id AND f.path IS NOT NULL LIMIT 1) path
                FROM tracks t WHERE t.spotify_id IN ({marks})""", ids).fetchall()
    finally:
        db.close()
    order = {sid: i for i, sid in enumerate(ids)}
    found = []
    for r in sorted(rows, key=lambda r: order.get(r["spotify_id"], 1e9)):
        if not r["path"]:
            continue
        try:
            if not Path(r["path"]).is_file():
                continue
        except OSError:            # unreadable media
            continue
        found.append((r["spotify_id"], r["path"],
                      f"{r['artist_names'] or ''} - {r['title'] or ''}".strip(" -")))
    return found


def reveal(ids: list[str]) -> dict:
    """Show the file in Finder, selected and ready to drag onto a deck."""
    found = paths_for(ids)
    if not found:
        raise RuntimeError("tento track nemá súbor na disku")
    subprocess.run(["open", "-R", found[0][1]], check=False, timeout=30)
    return {"revealed": found[0][1], "count": 1}


def playlist(ids: list[str], name: str = "") -> dict:
    """Write the selection as an .m3u and reveal it for dragging into Traktor."""
    found = paths_for(ids)
    if not found:
        raise RuntimeError("ani jeden z vybraných trackov nemá súbor na disku")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\s.-]", "", (name or "").strip()) or time.strftime("Vyber %H-%M")
    target = EXPORT_DIR / f"{safe}.m3u"
    # #EXTM3U with absolute paths: what Traktor expects on import, and readable
    # by anything else the owner might use.
    lines = ["#EXTM3U"]
    for _, path, display in found:
        lines.append(f"#EXTINF:-1,{display}")
        lines.append(path)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["open", "-R", str(target)], check=False, timeout=30)
    return {"playlist": str(target), "count": len(found),
            "skipped": len(ids) - len(found)}


def file_list(ids: list[str]) -> dict:
    """Paths for a drag. The page needs them to build the drag payload."""
    return {"files": [{"id": sid, "path": path, "name": Path(path).name}
                      for sid, path, _ in paths_for(ids)]}

#!/usr/bin/env python3
"""Local web server for the track browser. Standard library only, no new deps.

WHAT: serves the single-page UI and a small JSON API over the library — read a
page, edit a cell, bulk-edit or find-and-replace inside one column, swap two
fields, add files, and kick off analysis.

WHY STDLIB: adding FastAPI to this project would be a stack change, and the app
needs nothing a framework provides. `http.server` with a thread pool is enough
for one person on one machine, and it means the app runs from a double-click
with no install step.

SAFETY: binds to 127.0.0.1 only — never exposed to the network. Writes go
through db.py, which uses BEGIN IMMEDIATE against a database four other
processes are writing to.

HOW TO TWEAK: PORT below; the UI lives in app.html next to this file.
"""

from __future__ import annotations

import json
import subprocess
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import db
import similar_api
import profiles
import analyze_jobs
import traktor_bridge

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8765


def run_detached(args: list[str]) -> None:
    """Fire a pipeline command and return immediately — the UI must never block
    on work that takes minutes."""
    subprocess.Popen(args, cwd=ROOT, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def pick_paths(folders: bool) -> list[str]:
    """Native macOS chooser. The browser cannot give real file paths (it only
    hands over content), and this app needs paths to analyse files in place."""
    kind = "folder" if folders else 'file with multiple selections allowed'
    script = (f'set sel to choose {kind}\n'
              'set out to ""\n'
              'if class of sel is list then\n'
              '  repeat with f in sel\n    set out to out & POSIX path of f & "\\n"\n  end repeat\n'
              'else\n  set out to POSIX path of sel\nend if\n'
              'return out')
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True,
                              text=True, timeout=300)
        return [p for p in (proc.stdout or "").splitlines() if p.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):        # keep the console quiet
        pass

    def _touch(self):
        LAST_REQUEST[0] = time.time()

    def _send(self, payload, status=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        # NEVER let the browser cache this app. Without it the owner kept seeing
        # a stale page after every change — panels empty, presets missing — and
        # it looked like the app had broken when the server was in fact serving
        # the right thing to a browser that refused to ask for it.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        self._touch()
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                return self._send((HERE / "app.html").read_bytes(), content_type="text/html")
            if url.path == "/api/columns":
                return self._send({"all": db.all_columns(),
                                   "editable": db.editable_columns()})
            if url.path == "/api/page":
                return self._send(db.page(
                    offset=int(query.get("offset", 0)), limit=int(query.get("limit", 100)),
                    search=query.get("search", ""), sort=query.get("sort", "title"),
                    only_missing=query.get("missing") or None))
            if url.path == "/api/stats":
                return self._send(db.stats())
            if url.path == "/api/pick":
                return self._send({"paths": pick_paths(query.get("folders") == "1")})
            if url.path in ("/similar.js", "/similar_panels.js"):
                return self._send((HERE / url.path.lstrip("/")).read_bytes(),
                                  content_type="application/javascript")
            if url.path in ("/similar", "/similar.html"):
                return self._send((HERE / "similar.html").read_bytes(),
                                  content_type="text/html")
            if url.path == "/api/similar/status":
                return self._send({**similar_api.engine.status(),
                                   "build": similar_api.build_stamp(),
                                   "started": STARTED})
            if url.path == "/api/similar/search":
                return self._send({"results": similar_api.engine.search(
                    query.get("q", ""), limit=int(query.get("limit", 25)))})
            if url.path == "/api/analyze/status":
                return self._send(analyze_jobs.status(query.get("job", "")))
            if url.path == "/api/analyze/recent":
                return self._send({"jobs": analyze_jobs.recent()})
            if url.path == "/api/profiles":
                return self._send({"profiles": profiles.list_profiles()})
            if url.path == "/api/track/fields":
                return self._send(similar_api.track_fields(query.get("id", "")))
            if url.path == "/api/similar/explain":
                return self._send(similar_api.engine.explain(query.get("id", "")))
            if url.path == "/api/similar/presets":
                return self._send({"presets": similar_api.engine.presets()})
            if url.path == "/api/similar/macros":
                return self._send({"macros": similar_api.engine.macros()})
            if url.path == "/api/similar/tag-values":
                return self._send({"values": similar_api.engine.tag_values()})
            if url.path == "/api/similar/signals":
                # Everything that CAN be compared, so the UI can draw a checkbox
                # per signal instead of hardcoding a list that goes stale.
                return self._send({"signals": similar_api.engine.signals()})
            if url.path == "/api/preview":
                return similar_api.preview_response(self, query["id"])
            if url.path == "/api/spotify/token":
                return self._send(similar_api.spotify_token())
            if url.path == "/api/audio":
                # Streams the file itself; must not go through _send(), which
                # buffers a whole body and cannot answer a Range request.
                return similar_api.audio_response(self, query["id"])
            self._send({"error": "not found"}, 404)
        except Exception as exc:                       # never let the UI see a blank failure
            self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self):
        self._touch()
        url = urlparse(self.path)
        try:
            body = self._body()
            if url.path == "/api/cell":
                db.update_cell(body["id"], body["column"], body["value"])
                return self._send({"ok": True})
            if url.path == "/api/bulk":
                n = db.bulk_update(body["column"], body["ids"], body["value"])
                return self._send({"ok": True, "changed": n})
            if url.path == "/api/replace":
                n = db.find_replace(body["column"], body["ids"], body["find"], body["replace"])
                return self._send({"ok": True, "changed": n})
            if url.path == "/api/swap":
                n = db.swap_columns(body["left"], body["right"], body["ids"])
                return self._send({"ok": True, "changed": n})
            if url.path == "/api/add":
                # Index the given files/folders, then give them an identity. The
                # normal loop (prep -> shard -> GPU) takes over by itself.
                paths = [p for p in body.get("paths", []) if p]
                if paths:
                    run_detached([str(ROOT / ".venv/bin/python"), "index_audio_files.py",
                                  "--roots", ":".join(paths)])
                return self._send({"ok": True, "queued": len(paths)})
            if url.path == "/api/traktor/paths":
                return self._send(traktor_bridge.file_list(body.get("ids") or []))
            if url.path == "/api/track/field":
                return self._send(similar_api.set_track_field(
                    body.get("id", ""), body.get("field", ""), body.get("value")))
            if url.path == "/api/spotify/play":
                return self._send(similar_api.spotify_play(
                    body.get("id", ""), body.get("device_id", ""),
                    int(body.get("position_ms") or 0)))
            if url.path == "/api/traktor/reveal":
                return self._send(traktor_bridge.reveal(body.get("ids") or []))
            if url.path == "/api/traktor/playlist":
                return self._send(traktor_bridge.playlist(
                    body.get("ids") or [], body.get("name") or ""))
            if url.path == "/api/analyze":
                return self._send(analyze_jobs.start(body.get("ids") or []))
            if url.path == "/api/profiles/save":
                return self._send(profiles.save(body))
            if url.path == "/api/profiles/delete":
                return self._send({"deleted": profiles.delete(body.get("id", ""))})
            if url.path == "/api/profiles/reorder":
                return self._send({"profiles": profiles.reorder(body.get("order") or [])})
            if url.path == "/api/profiles/rename-folder":
                return self._send({"changed": profiles.rename_folder(
                    body.get("old", ""), body.get("new", ""))})
            if url.path == "/api/similar":
                # POST, not GET: the enabled-signal list runs to 77 entries and
                # does not belong in a query string.
                return self._send(similar_api.engine.similar(
                    body.get("id") or "", refs=body.get("ids"),
                    limit=int(body.get("limit", 100)),
                    spotify_only=bool(body.get("spotify_only", True)),
                    bpm_window=float(body.get("bpm_window") or 0),
                    bpm_tol=float(body.get("bpm_tol") or 0),
                    same_key=bool(body.get("same_key")),
                    key_rules=body.get("key_rules"),
                    base_key=body.get("base_key"),
                    enabled=body.get("enabled"),
                    group_weights=body.get("group_weights"),
                    signal_weights=body.get("signal_weights"),
                    signal_modes=body.get("signal_modes"),
                    tag_rules=body.get("tag_rules")))
            if url.path == "/api/playlist":
                return self._send(similar_api.create_playlist(
                    body.get("name") or "Similar tracks",
                    body.get("description") or "", body.get("ids") or []))
            if url.path == "/api/resume":
                run_detached([str(ROOT / ".venv/bin/python"), "index_audio_files.py"])
                run_detached([str(ROOT / ".venv/bin/python"), "promote_unmatched_local_tracks.py"])
                return self._send({"ok": True})
            self._send({"error": "not found"}, 404)
        except Exception as exc:
            self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)


# HOW LONG the engine keeps running with nobody using it. It survives the app
# closing on purpose — reopening then costs nothing instead of the two and a
# half minutes it takes to read 165k embeddings, 5.5M tags and 8.3M numbers
# again. But it must not sit in memory forever, so it retires on its own once
# nothing has asked it anything for this long.
# TWEAK: raise it to keep the engine warm longer, lower it to free memory sooner.
IDLE_EXIT_MINUTES = 45


def retire_when_idle() -> None:
    while True:
        time.sleep(60)
        quiet = (time.time() - LAST_REQUEST[0]) / 60.0
        if quiet >= IDLE_EXIT_MINUTES:
            print(f"nikto sa {quiet:.0f} minút nič nepýtal — engine sa vypína")
            os._exit(0)


LAST_REQUEST = [time.time()]
# When this process began. If the code on disk is newer, the running server is
# stale and every change made since is invisible — the app says so out loud.
STARTED = time.time()


def main() -> None:
    # Load the embeddings in the BACKGROUND. It takes about a minute, and doing
    # it lazily on the first click would look like the app had frozen.
    threading.Thread(target=similar_api.engine.warm, daemon=True).start()
    threading.Thread(target=retire_when_idle, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Music database browser running at {url}")
    print("Close this window to stop it.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()

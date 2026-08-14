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
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import db

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

    def _send(self, payload, status=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
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
            self._send({"error": "not found"}, 404)
        except Exception as exc:                       # never let the UI see a blank failure
            self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self):
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
            if url.path == "/api/resume":
                run_detached([str(ROOT / ".venv/bin/python"), "index_audio_files.py"])
                run_detached([str(ROOT / ".venv/bin/python"), "promote_unmatched_local_tracks.py"])
                return self._send({"ok": True})
            self._send({"error": "not found"}, 404)
        except Exception as exc:
            self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)


def main() -> None:
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

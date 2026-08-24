#!/usr/bin/env python3
"""One-off: re-authorise Spotify with the `streaming` permission added.

WHY: playing a WHOLE track inside the app (instead of Spotify's 30-second
preview) uses Spotify's Web Playback SDK, and that needs the `streaming`
permission. The existing token has everything else already — this asks for the
same list plus that one, and rewrites data/token.json.

WHAT IT NEEDS FROM YOU, ONCE: a single click on "Agree" in the browser. Nothing
has to be added in the Spotify dashboard — this project now uses the same
Spotify app as dj-set-spotify, whose redirect URI is already registered there.

    ./.venv/bin/python spotify_authorize.py

Nothing secret is ever printed: not the client id, not the secret, not the
token. The browser does the login; this only catches the code that comes back.

TWEAK: SPOTIFY_REDIRECT_URI in .env — it has to stay one of the addresses
registered for that Spotify app, or Spotify refuses the login outright.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import shlex
import signal
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

import spotify_client as sc

# Read from .env so it always matches what the Spotify app has registered.
# spotify_client already loaded .env when it was imported above.
REDIRECT = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8787/spotify/callback")
PORT = int(urllib.parse.urlparse(REDIRECT).port or 8787)

# Everything the token already had, plus streaming. Losing a permission here
# would quietly break playlist creation, so the list is explicit.
SCOPES = [
    "streaming",
    "user-read-email", "user-read-private",
    "user-read-playback-state", "user-modify-playback-state",
    "user-read-currently-playing", "user-read-playback-position",
    "user-read-recently-played", "user-top-read",
    "user-library-read", "user-library-modify",
    "playlist-read-private", "playlist-read-collaborative",
    "playlist-modify-private", "playlist-modify-public",
]

_result: dict = {}


class Catch(http.server.BaseHTTPRequestHandler):
    def do_GET(self):                                   # noqa: N802
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _result.update({k: v[0] for k, v in query.items()})
        ok = "code" in _result
        body = ("<h2>Hotovo — vráť sa do terminálu.</h2>" if ok
                else f"<h2>Nepodarilo sa: {_result.get('error', '?')}</h2>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):                          # keep the console clean
        pass


def borrow_port(port: int):
    """Spotify only sends the code back to an address registered for the app,
    and the one registered here (:8787) is also where dj-set-spotify runs. So
    the port is borrowed for the half minute this takes and handed straight
    back — the other app is stopped and restarted with the exact command line
    it was already using. Returns a function that puts it back.

    If nothing is listening, this does nothing at all.
    """
    try:
        out = subprocess.run(["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        return lambda: None
    if not out:
        return lambda: None
    pid = int(out[0])
    try:
        cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        cwd = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=10).stdout
        cwd = next((l[1:] for l in cwd.splitlines() if l.startswith("n")), None)
    except Exception:
        cmd, cwd = "", None
    if not cmd:
        raise SystemExit(f"Port {port} niekto drží a neviem zistiť čo — zavri to a skús znova.")

    print(f"Port {port} drží iná appka; na chvíľu ju zastavím a hneď vrátim späť.")
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        time.sleep(0.25)
        still = subprocess.run(["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
                               capture_output=True, text=True).stdout.split()
        if not still:
            break

    # Split into argv and run WITHOUT a shell: the command line comes from ps,
    # and handing that to a shell would let any quoting in it be re-interpreted.
    argv = shlex.split(cmd)

    def give_back():
        try:
            subprocess.Popen(argv, cwd=cwd,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            print(f"Pôvodná appka na porte {port} je späť.")
        except Exception as exc:
            print(f"POZOR: nepodarilo sa ju vrátiť ({exc}). Spusti ju sám:\n  {cmd}")
    return give_back


def main() -> None:
    if not sc.CLIENT_ID or not sc.CLIENT_SECRET:
        raise SystemExit("V .env chýba SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET.")

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)

    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": sc.CLIENT_ID, "response_type": "code",
        "redirect_uri": REDIRECT, "scope": " ".join(SCOPES),
        "state": state, "code_challenge_method": "S256",
        "code_challenge": challenge,
    })

    give_back = borrow_port(PORT)
    try:
        server = http.server.HTTPServer(("127.0.0.1", PORT), Catch)
        threading.Thread(target=server.handle_request, daemon=True).start()

        print(f"Otváram Spotify prihlásenie… ak sa okno neotvorí, choď na:\n  {url}\n")
        webbrowser.open(url)
        print(f"Čakám na návrat na {REDIRECT} …  (stačí kliknúť na Agree)")
        for _ in range(600):                            # 5 minutes, then give up
            if _result:
                break
            threading.Event().wait(0.5)
        server.server_close()
    finally:
        give_back()          # the other app gets its port back no matter what

    if "code" not in _result:
        raise SystemExit(f"Nepodarilo sa: {_result.get('error', 'žiadna odpoveď')}. "
                         f"Je {REDIRECT} registrované pre túto Spotify aplikáciu?")
    if _result.get("state") != state:
        raise SystemExit("Bezpečnostná kontrola zlyhala (state nesedí) — skús znova.")

    resp = requests.post(sc.TOKEN_URL, data={
        "grant_type": "authorization_code", "code": _result["code"],
        "redirect_uri": REDIRECT, "client_id": sc.CLIENT_ID,
        "client_secret": sc.CLIENT_SECRET, "code_verifier": verifier,
    }, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"Výmena kódu zlyhala ({resp.status_code}).")
    data = resp.json()
    if "refresh_token" not in data:
        raise SystemExit("Spotify nevrátil refresh_token — skús to znova.")

    path = Path(sc.TOKEN_PATH)
    if path.exists():                                   # never lose the old one
        backup = path.with_suffix(".json.bak")
        backup.write_text(path.read_text())
        print(f"Starý token odložený do {backup.name}")
    path.write_text(json.dumps({"refresh_token": data["refresh_token"]}, indent=2) + "\n")
    granted = sorted((data.get("scope") or "").split())
    print("Hotovo. Povolenia:", ", ".join(granted))
    print("streaming:", "ÁNO" if "streaming" in granted else "NIE — prehrávanie celých skladieb nepôjde")


if __name__ == "__main__":
    main()

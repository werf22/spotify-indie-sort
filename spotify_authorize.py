#!/usr/bin/env python3
"""One-off: re-authorise Spotify with the `streaming` permission added.

WHY: playing a WHOLE track inside the app (instead of Spotify's 30-second
preview) uses Spotify's Web Playback SDK, and that needs the `streaming`
permission. The existing token has everything else already — this asks for the
same list plus that one, and rewrites data/token.json.

WHAT IT NEEDS FROM YOU, ONCE: the redirect address below has to be listed in
your Spotify app at https://developer.spotify.com/dashboard → your app →
Settings → Redirect URIs. Add it, save, then run this.

    python3 spotify_authorize.py

Nothing secret is ever printed: not the client id, not the secret, not the
token. The browser does the login; this only catches the code that comes back.

TWEAK: PORT/REDIRECT if 8899 is taken — change it here AND in the dashboard.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

import spotify_client as sc

PORT = 8899
REDIRECT = f"http://127.0.0.1:{PORT}/callback"

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
        "code_challenge": challenge, "show_dialog": "true",
    })

    server = http.server.HTTPServer(("127.0.0.1", PORT), Catch)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print(f"Otváram Spotify prihlásenie… ak sa okno neotvorí, choď na:\n  {url}\n")
    webbrowser.open(url)
    print(f"Čakám na návrat na {REDIRECT} …")
    for _ in range(600):                                # 5 minutes, then give up
        if _result:
            break
        threading.Event().wait(0.5)
    server.server_close()

    if "code" not in _result:
        raise SystemExit(f"Nepodarilo sa: {_result.get('error', 'žiadna odpoveď')}. "
                         f"Je {REDIRECT} pridané v dashboarde?")
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

#!/usr/bin/env python3
"""Most-similar tracks to a seed, using SPOTIFY DATA ONLY, as a Spotify playlist.

WHY THIS EXISTS SEPARATELY FROM similarity_engine.py: that engine listens to the
audio (CLAP, MAEST, Essentia). This one is not allowed to. It may use only what
Spotify itself says about a record.

WHAT SPOTIFY STILL OFFERS. Its own similarity endpoints are gone — verified
against this app's token, not assumed: /audio-features and /audio-analysis
answer 403, /recommendations and /artists/{id}/related-artists answer 404. What
survives is metadata, so that is what this ranks on:

  * the artist's Spotify genres      — the substance of the match
  * release date                     — a scene moves; records travel in waves
  * label                            — in this music the label IS the sound
  * artist popularity and followers  — a 20k-follower producer is not Calvin
                                       Harris, however well the genres line up

RARE GENRES COUNT FOR MORE. "afro house" covers 11,019 tracks here and "indie
dance" only 874, so matching on the second says far more than matching on the
first. Every genre is weighted by how rare it is (IDF) before the vectors are
compared, or the ranking just returns the biggest genre in the library.

    ./.venv/bin/python spotify_similar.py --seed 4vgKaYy4UtCWGhjiJwyvWR
        --limit 50 --name "Lila — Spotify similar"   [--dry-run]

HOW TO TWEAK: WEIGHTS decides what "similar" means. MAX_PER_ARTIST stops one
producer's back catalogue from filling the playlist.
"""
from __future__ import annotations

import argparse
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

import spotify_client as sc

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

WEIGHTS = {"genre": 0.68, "date": 0.14, "label": 0.10, "tier": 0.08}
MAX_PER_ARTIST = 2
SHORTLIST = 500              # how many get the extra artist lookup from the API
# A record two years either side of the seed is still the same wave; five years
# away is a different scene. TWEAK: raise for a more timeless playlist.
DATE_HALFLIFE_DAYS = 730.0

_STRIP = re.compile(r"\s*[\(\[-].*$|\s+(feat|ft)\.?\s.*$", re.I)


def plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def genre_set(value: str | None) -> set[str]:
    return {g.strip().lower() for g in (value or "").split(",") if g.strip()}


def to_days(date_text: str | None) -> float | None:
    """Spotify dates come as YYYY, YYYY-MM or YYYY-MM-DD — all three are used."""
    if not date_text:
        return None
    parts = (date_text.split("-") + ["1", "1"])[:3]
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return y * 365.25 + m * 30.44 + d


def load(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("""SELECT spotify_id, artist_names, title, album, genres, label,
                                release_date, popularity, artist_ids
                         FROM tracks
                         WHERE spotify_id NOT LIKE 'local\\_%' ESCAPE '\\'
                           AND genres IS NOT NULL AND genres <> ''""").fetchall()
    out = []
    for sid, artist, title, album, genres, label, date, pop, artist_ids in rows:
        out.append({"id": sid, "artist": artist or "", "title": title or "",
                    "album": album or "", "genres": genre_set(genres),
                    "label": (label or "").strip(), "date": date,
                    "days": to_days(date), "pop": pop,
                    "artist_id": (artist_ids or "").split(",")[0].strip()})
    return out


def idf(tracks: list[dict]) -> dict[str, float]:
    df = Counter(g for t in tracks for g in t["genres"])
    n = len(tracks)
    return {g: math.log(n / c) for g, c in df.items()}


def genre_score(seed: set[str], cand: set[str], w: dict[str, float]) -> float:
    """Cosine on IDF-weighted genre vectors: shared rarity over total rarity."""
    shared = sum(w.get(g, 0.0) ** 2 for g in seed & cand)
    if not shared:
        return 0.0
    a = math.sqrt(sum(w.get(g, 0.0) ** 2 for g in seed))
    b = math.sqrt(sum(w.get(g, 0.0) ** 2 for g in cand))
    return shared / (a * b) if a and b else 0.0


def artist_tiers(client, artist_ids: list[str]) -> dict[str, dict]:
    """Followers and popularity per artist, 50 at a time — Spotify's own numbers."""
    out: dict[str, dict] = {}
    ids = [a for a in dict.fromkeys(artist_ids) if a]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = client.request("GET", "/artists", params={"ids": ",".join(chunk)})
        if not r.ok:
            continue
        for a in r.json().get("artists") or []:
            if a:
                out[a["id"]] = {"followers": (a.get("followers") or {}).get("total") or 0,
                                "popularity": a.get("popularity") or 0,
                                "genres": {g.lower() for g in a.get("genres") or []}}
    return out


def rank(seed_id: str, limit: int, client) -> tuple[dict, list[dict]]:
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tracks = load(db)
    by_id = {t["id"]: t for t in tracks}

    seed = by_id.get(seed_id)
    if seed is None:                       # not in the library — ask Spotify itself
        r = client.request("GET", f"/tracks/{seed_id}")
        r.raise_for_status()
        d = r.json()
        aid = d["artists"][0]["id"]
        a = client.request("GET", f"/artists/{aid}").json()
        seed = {"id": seed_id, "artist": ", ".join(x["name"] for x in d["artists"]),
                "title": d["name"], "album": d["album"]["name"],
                "genres": {g.lower() for g in a.get("genres") or []},
                "label": "", "date": d["album"].get("release_date"),
                "days": to_days(d["album"].get("release_date")), "pop": d.get("popularity"),
                "artist_id": aid}
    db.close()
    if not seed["genres"]:
        raise SystemExit("Spotify o tomto tracku nemá ani jeden žáner — "
                         "čisto zo Spotify dát sa podobnosť nedá postaviť.")

    w = idf(tracks)
    seed_artist = plain(seed["artist"].split(",")[0])
    seed_title = _STRIP.sub("", plain(seed["title"])).strip()

    scored = []
    for t in tracks:
        if t["id"] == seed_id:
            continue
        # the same tune under another release is not a recommendation
        if (plain(t["artist"].split(",")[0]) == seed_artist
                and _STRIP.sub("", plain(t["title"])).strip() == seed_title):
            continue
        g = genre_score(seed["genres"], t["genres"], w)
        if g <= 0:
            continue
        t["s_genre"] = g
        scored.append(t)
    scored.sort(key=lambda t: -t["s_genre"])

    # Spotify's own numbers for the artists that got this far.
    short = scored[:SHORTLIST]
    tiers = artist_tiers(client, [t["artist_id"] for t in short] + [seed["artist_id"]])
    seed_tier = tiers.get(seed["artist_id"], {})
    seed_f = math.log10(max(1, seed_tier.get("followers", 0) or 1))

    for t in short:
        # date: how far into a different wave of the scene
        if t["days"] is not None and seed["days"] is not None:
            t["s_date"] = math.exp(-abs(t["days"] - seed["days"]) / DATE_HALFLIFE_DAYS)
        else:
            t["s_date"] = 0.0
        t["s_label"] = 1.0 if (t["label"] and seed.get("label")
                               and plain(t["label"]) == plain(seed["label"])) else 0.0
        info = tiers.get(t["artist_id"], {})
        f = math.log10(max(1, info.get("followers", 0) or 1))
        # one order of magnitude apart in followers halves this
        t["s_tier"] = math.exp(-abs(f - seed_f) / 1.5) if info else 0.0
        t["fit"] = sum(WEIGHTS[k] * t["s_" + k] for k in WEIGHTS)

    short.sort(key=lambda t: -t["fit"])

    picked, per_artist, seen = [], Counter(), set()
    for t in short:
        who = plain(t["artist"].split(",")[0])
        key = f"{who}|{_STRIP.sub('', plain(t['title'])).strip()}"
        if key in seen or per_artist[who] >= MAX_PER_ARTIST:
            continue
        seen.add(key)
        per_artist[who] += 1
        picked.append(t)
        if len(picked) >= limit:
            break
    return seed, picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="4vgKaYy4UtCWGhjiJwyvWR")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry-run", action="store_true", help="ukáž výsledok, nič nevytváraj")
    args = ap.parse_args()

    client = sc.SpotifyClient()
    seed, picked = rank(args.seed, args.limit, client)
    print(f"seed: {seed['artist']} — {seed['title']}")
    print(f"  Spotify žánre: {', '.join(sorted(seed['genres']))}")
    print(f"  vyšlo {seed['date']} · label {seed['label'] or '?'}\n")
    print(f"{'#':>3} {'fit':>5} {'žáner':>6}{'dátum':>7}{'label':>6}{'level':>6}  interpret — názov")
    for i, t in enumerate(picked, 1):
        print(f"{i:>3} {t['fit']:.3f} {t['s_genre']:>6.2f}{t['s_date']:>7.2f}"
              f"{t['s_label']:>6.0f}{t['s_tier']:>6.2f}  "
              f"{t['artist'][:30]} — {t['title'][:36]}  ({t['date'] or '?'})")

    if args.dry_run:
        print("\n(nasucho — playlist sa nevytvoril)")
        return 0

    me = client.current_user()
    name = args.name or f"{seed['artist']} — {seed['title']} · Spotify similar"
    desc = ("Najpodobnejšie tracky čisto podľa Spotify dát (žánre interpreta vážené "
            "vzácnosťou, dátum vydania, label, veľkosť interpreta). "
            "Spotify Recommendations a Audio Features API sú zrušené.")
    pl = client.create_playlist(me["id"], name, desc, public=False)
    client.add_tracks(pl["id"], [f"spotify:track:{t['id']}" for t in picked])

    # READ IT BACK. The creation response is a claim, not a fact — and it is
    # wrong about one thing: Spotify accepts public=false, answers 200 to a PUT
    # setting it again, and still leaves the playlist PUBLIC. Verified 3.9.2026
    # against a live playlist, five reads plus /me/playlists. So the privacy is
    # reported from what the API actually says afterwards, never from intent.
    back = client.request("GET", f"/playlists/{pl['id']}",
                          params={"fields": "public,tracks.total"}).json()
    print(f"\nplaylist: {pl['external_urls']['spotify']}")
    print(f"  v ňom naozaj je: {back['tracks']['total']} skladieb")
    if back.get("public"):
        print("  POZOR: Spotify ho nechal VEREJNÝ napriek public=false.")
        print("  Súkromný sa dá spraviť len v appke: playlist -> ... -> "
              "Odstrániť z profilu / Make private.")
    else:
        print("  súkromný (overené spätným čítaním)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

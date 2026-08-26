#!/usr/bin/env python3
"""Build the Ecstatic Dance set and write it as a Traktor playlist.

THE SHAPE OF THE NIGHT. An ecstatic-dance set is a wave, not a ladder: people
arrive, open up, go wild, come down, land. The owner asked for a DRIVING one, so
the wave here never drops to ambient — it starts at a walking groove and lands
on one, instead of starting and ending in silence.

THE HARMONIC RULE. One base key carries the set; +-2 and +-7 on the Camelot
wheel are allowed but rationed, because "primarily in one key" is a quota, not a
preference. PHASES and KEY_QUOTA below are the two knobs that shape everything.

Run:  ./.venv/bin/python ecstatic_set.py [--tracks 27] [--out PATH]

HOW TO TWEAK: PHASES is the wave — each row is (name, how many, bpm from, bpm
to, which feelings matter extra here). Add a row for a longer night. KEY_QUOTA
must add up to the number of tracks; the base key should stay the biggest share.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
import re
from pathlib import Path

import nml_write
from ecstatic_signals import CORE_FLOOR, FLAVOUR_FLOOR, ORIENT_ARTISTS

# Camelot position of the base key, in the wheel numbering used by
# similarity_engine.camelot(). NOTE: that numbering is rotated seven steps from
# the Mixed In Key labels — engine "1A" is A minor, which Traktor calls 8A.
BASE = "1A"

# (name, tracks, bpm at the start, bpm at the end, extra weight per feeling)
PHASES = [
    ("Príchod",     4, 108, 115, {"orient": .35, "sensual": .30}),
    ("Prebúdzanie", 5, 116, 120, {"orient": .30, "playful": .20, "driving": .10}),
    ("Rozbeh",      5, 120, 124, {"driving": .30, "playful": .25}),
    ("Vrchol",      6, 124, 128, {"driving": .40, "playful": .35}),
    ("Uvoľnenie",   4, 126, 121, {"sensual": .40, "orient": .25}),
    ("Pristátie",   3, 120, 112, {"orient": .40, "sensual": .30}),
]
# How many tracks may sit at each harmonic distance. The base key must dominate.
KEY_QUOTA = {"presná": 18, "+2": 3, "-2": 3, "+7": 2, "-7": 1}
BPM_TOLERANCE = 3.5          # how far a record may sit from its slot's tempo
BPM_PENALTY = 0.055          # fit lost per BPM away from the slot
# WHAT THE MIX ACTUALLY FEELS: the jump from the PREVIOUS record, not the
# distance from an abstract target. Two records four BPM apart mix; the same two
# with a third at the wrong tempo between them do not.
BPM_STEP_FREE = 2.0          # a step this small costs nothing
BPM_STEP_PENALTY = 0.045     # fit lost per BPM beyond that
BPM_MAX_STEP = 6.0           # never ask the deck for more than this
ARTIST_MAX = 2               # times one LEAD artist may appear in the whole set
ARTIST_GAP = 6               # slots that must pass before that artist returns
# A label or collective is not one artist — "Cafe De Anatolia" is credited on
# tracks by ten different producers — but ten of them still makes a one-label
# night instead of the promised range of genres. This caps any single NAME
# anywhere in the credits. TWEAK: lower for more variety, raise to lean harder
# on one collective.
COLLECTIVE_MAX = 9

_SPLIT = re.compile(r"\s*[,/&]\s*|\s+(?:feat|ft|x)\.?\s+", re.I)


def credits(t: dict) -> list[str]:
    """Every name in the credit line, lower-cased.

    CREDIT STRINGS IN THIS LIBRARY ARE NOT CONSISTENT: some are comma-separated
    ("KÖNI, Cafe De Anatolia"), others simply run together ("HVMZA Gaz Mawete
    Cafe De Anatolia"). Splitting on punctuation alone missed the collective in
    the second form and the cap leaked. So the known names are also looked for
    as whole words inside the raw string."""
    raw = (t.get("artist") or "")
    names = [n.strip().lower() for n in _SPLIT.split(raw) if n.strip()]
    low = raw.lower()
    for known in ORIENT_ARTISTS:
        if " " in known and re.search(r"\b" + re.escape(known), low) and known not in names:
            names.append(known)
    return names

_STRIP = re.compile(r"\s*[\(\[-].*$|\s+(feat|ft)\.?\s.*$", re.I)


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def dedupe_keys(t: dict) -> tuple[str, str]:
    """TWO keys, because one is not enough to recognise the same record.

    The first treats "Sete", "Sete (Raffa Fl Remix)" and "Sete - Extended" as one
    tune — the opposite of what track MATCHING wants, and exactly right here.

    The second exists because the same recording appears in this library under
    different artist strings: "Love" was in the set twice, once credited to
    "Tebra, Cafe De Anatolia" and once to "Cafe De Anatolia" — two files, two
    ids, identical audio. Same title and same length to the second is the same
    record, whatever the credits say."""
    title = _STRIP.sub("", (t["title"] or "").lower()).strip()
    artist = (t["artist"] or "").split(",")[0].strip().lower()
    length = round(float(t.get("seconds") or 0) / 2)
    return _plain(f"{artist}|{title}"), _plain(f"{title}#{length}")


def relation(camelot_pos: str, base: str = BASE) -> str | None:
    a, sa = int(base[:-1]), base[-1]
    b, sb = int(camelot_pos[:-1]), camelot_pos[-1]
    if sa != sb:
        return None                       # minor never mixes to major here
    return {0: "presná", 2: "+2", 10: "-2", 7: "+7", 5: "-7"}.get((b - a) % 12)


def build(tracks: list[dict], total: int, base: str = BASE) -> list[dict]:
    pool, seen = [], set()
    for t in sorted(tracks, key=lambda t: -t["fit"]):
        rel = relation(t["camelot"], base)
        if rel is None:
            continue
        # THE THEME IS A GATE, NOT A PREFERENCE. Without this, records that
        # merely score high on mood walked into the set — a Eurodance pop single
        # made the first build purely on "sensual" and "danceable".
        if t.get("core", 0) < CORE_FLOOR:
            continue
        if t.get("banned"):
            continue
        # sexy OR playful — the night needs one of them from every record.
        if max(t["p_sensual"], t["p_playful"]) < FLAVOUR_FLOOR:
            continue
        k1, k2 = dedupe_keys(t)
        if k1 in seen or k2 in seen:
            continue
        seen.update((k1, k2))
        t["rel"] = rel
        pool.append(t)

    quota = dict(KEY_QUOTA)
    scale = total / sum(KEY_QUOTA.values())
    if scale != 1:
        quota = {k: max(0, round(v * scale)) for k, v in quota.items()}

    chosen, used_artist, used_name, taken, unfilled = [], {}, {}, set(), []
    slot = 0
    slots = [(name, bias, lo + (hi - lo) * (i / max(1, n - 1)))
             for name, n, lo, hi, bias in PHASES for i in range(n)]
    slots = slots[:total]

    prev_bpm = None
    for name, bias, target in slots:
        best, best_score, tolerance = None, -9e9, BPM_TOLERANCE
        while best is None and tolerance <= 8:
            for t in pool:
                if id(t) in taken:
                    continue
                if quota.get(t["rel"], 0) <= 0:
                    continue
                if abs(t["bpm"] - target) > tolerance:
                    continue
                if prev_bpm is not None and abs(t["bpm"] - prev_bpm) > BPM_MAX_STEP:
                    continue
                who = (t["artist"] or "").split(",")[0].strip().lower()
                if used_artist.get(who, {}).get("n", 0) >= ARTIST_MAX:
                    continue
                if slot - used_artist.get(who, {}).get("last", -99) < ARTIST_GAP:
                    continue
                if any(used_name.get(n, 0) >= COLLECTIVE_MAX for n in credits(t)):
                    continue
                step = 0.0 if prev_bpm is None else max(0.0, abs(t["bpm"] - prev_bpm) - BPM_STEP_FREE)
                score = (t["fit"]
                         + sum(w * t["p_" + f] for f, w in bias.items())
                         - BPM_PENALTY * abs(t["bpm"] - target)
                         - BPM_STEP_PENALTY * step)
                if score > best_score:
                    best, best_score = t, score
            tolerance += 3.5
        if best is None:
            # NEVER SHORTEN THE SET IN SILENCE. An unfilled slot means the
            # filters left nothing at this tempo, and the DJ has to know which
            # one to loosen — a set that is quietly four tracks shorter looks
            # like a working set right up until the night.
            unfilled.append((name, round(target)))
            continue
        who = (best["artist"] or "").split(",")[0].strip().lower()
        used_artist.setdefault(who, {"n": 0})
        used_artist[who]["n"] += 1
        used_artist[who]["last"] = slot
        for n in credits(best):
            used_name[n] = used_name.get(n, 0) + 1
        quota[best["rel"]] -= 1
        taken.add(id(best))
        best["phase"] = name
        chosen.append(best)
        prev_bpm = best["bpm"]
        slot += 1
    if unfilled:
        print(f"\n!! {len(unfilled)} slotov sa nepodarilo naplniť: "
              + ", ".join(f"{n} @{b} BPM" for n, b in unfilled))
        print("   Uvoľni niečo: COLLECTIVE_MAX, FLAVOUR_FLOOR, CORE_FLOOR alebo BPM_MAX_STEP.\n")
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", type=int, default=27)
    ap.add_argument("--out", default=str(Path.home() / "Desktop" / "Ecstatic Masquerade.nml"))
    ap.add_argument("--cache", default="/tmp/ecstatic_ranked.json")
    ap.add_argument("--base", default=BASE, help="základná tónina (číslovanie enginu)")
    args = ap.parse_args()

    cache = Path(args.cache)
    if cache.exists():
        tracks = json.loads(cache.read_text())
    else:
        from ecstatic_rank import rank
        tracks = rank()
        cache.write_text(json.dumps(tracks))

    picked = build(tracks, args.tracks, args.base)
    total = sum(t["seconds"] for t in picked)
    print(f"{len(picked)} trackov · {int(total//3600)}h {int(total%3600//60)}min\n")
    print(f"{'#':>3} {'fáza':<12}{'bpm':>5} {'tónina':<9}{'vzťah':<8}{'or se pl dr':<12} interpret — názov")
    phase = None
    for i, t in enumerate(picked, 1):
        if t["phase"] != phase:
            phase = t["phase"]
            print(f"   -- {phase} " + "-" * 60)
        flav = f"{t['p_orient']:.1f} {t['p_sensual']:.1f} {t['p_playful']:.1f} {t['p_driving']:.1f}"
        print(f"{i:>3} {t['phase']:<12}{t['bpm']:>5.0f} {t['key']:<9}{t['rel']:<8}{flav:<12} "
              f"{t['artist'][:28]} — {t['title'][:36]}")
    from collections import Counter
    print("\nrozloženie tónin:", dict(Counter(t["rel"] for t in picked)))
    out = nml_write.write(picked, args.out, "Ecstatic Masquerade")
    print(f"NML: {out}")

    # A READABLE SET LIST NEXT TO IT. The .nml is for Traktor; this is for the
    # person standing behind the decks, who needs to see the shape at a glance.
    lines = [f"# Ecstatic Masquerade — {len(picked)} skladieb · "
             f"{int(total//3600)}h {int(total%3600//60)}min",
             "",
             f"Základná tónina **{picked[0]['key'] if picked else '?'}**"
             f" — 18 skladieb v nej, ostatné ±2 a ±7 na Camelot kruhu.", ""]
    phase = None
    for i, t in enumerate(picked, 1):
        if t["phase"] != phase:
            phase = t["phase"]
            lines += ["", f"## {phase}", ""]
        lines.append(f"{i:>2}. **{t['artist']} — {t['title']}**  "
                     f"· {t['bpm']:.0f} BPM · {t['key']} ({t['rel']})")
    txt = Path(args.out).with_suffix(".md")
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"setlist: {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

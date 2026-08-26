#!/usr/bin/env python3
"""Turn the scored pool into ONE ranking, and say which key to build the set in.

WHY PERCENTILES AND NOT THE RAW SCORES: the four feelings are wildly different
in how common they are — 23,795 tracks read as "driving", only 202 as "sensual".
Adding those numbers together would let the common signal drown the rare one.
A percentile answers the question that actually matters: "how oriental is this
record COMPARED TO THE REST OF THIS LIBRARY".

HOW TO TWEAK: WEIGHTS decides what the night is about. Raise "orient" for more
theme, raise "driving" for a harder floor. DRIVING_FLOOR is a gate, not a
weight — below it a record is dropped however lovely it is, because the owner
asked for a set that moves.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict

from ecstatic_pool import load
from similarity_engine import camelot

WEIGHTS = {"orient": 0.40, "scene": 0.12, "sensual": 0.16,
           "playful": 0.14, "driving": 0.18}
WRONG_PENALTY = 0.40
DRIVING_FLOOR = 0.45          # percentile; below this it is not a dance record
CAMELOT_NAME = {"m": "A", "d": "B"}     # minor -> A side, major -> B side


def percentiles(values: list[float]) -> list[float]:
    """Rank each value 0..1 against all the others (ties share a rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j) / 2 / max(1, len(order) - 1)
        for k in range(i, j + 1):
            out[order[k]] = rank
        i = j + 1
    return out


def rank(verbose: bool = True) -> list[dict]:
    tracks = load(verbose=verbose)["tracks"]
    for name in list(WEIGHTS) + ["wrong"]:
        for t, p in zip(tracks, percentiles([t[name] for t in tracks])):
            t["p_" + name] = p
    for t in tracks:
        t["fit"] = (sum(w * t["p_" + n] for n, w in WEIGHTS.items())
                    - WRONG_PENALTY * t["p_wrong"])
        c = camelot(t["key"])
        t["camelot"] = f"{c[0]}{CAMELOT_NAME[c[1]]}" if c else None
    tracks = [t for t in tracks if t["camelot"] and t["p_driving"] >= DRIVING_FLOOR]
    tracks.sort(key=lambda t: -t["fit"])
    if verbose:
        print(f"po bráne 'driving' ostáva: {len(tracks):,}\n")
    return tracks


if __name__ == "__main__":
    tracks = rank()
    top = tracks[:600]
    print("=== 30 najlepších ===")
    print(f"{'#':>3} {'fit':>5} {'or':>4}{'se':>4}{'pl':>4}{'dr':>4}  {'key':<4}{'bpm':>5}  interpret — názov")
    for i, t in enumerate(top[:30], 1):
        print(f"{i:>3} {t['fit']:.3f} {t['p_orient']:.2f}{t['p_sensual']:.2f}"
              f"{t['p_playful']:.2f}{t['p_driving']:.2f}  {t['camelot']:<4}{t['bpm']:>5.0f}  "
              f"{t['artist'][:26]} — {t['title'][:34]}")

    print("\n=== zásoba podľa tóniny (v top 600) ===")
    per = Counter(t["camelot"] for t in top)
    tot = defaultdict(float)
    for t in top:
        tot[t["camelot"]] += t["fit"]
    for k, n in sorted(per.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {k:<4} {n:>4} trackov · súčet fit {tot[k]:>6.1f}")

#!/usr/bin/env python3
"""Which key to build the set in — decided by what the library can actually supply.

THE RULE THE OWNER ASKED FOR: everything in ONE key, plus +-2 and +-7 around it
on the Camelot wheel, but PRIMARILY in that one key. On the wheel those are
deltas 0, 2/10 and 7/5, always the same side (minor stays minor).

So the base key is not a taste decision, it is an inventory question: which key
has enough genuinely good records IN IT, with the neighbours only there to give
the set room to breathe. A key with a beautiful top record but nothing behind it
makes an impossible set.

HOW TO TWEAK: PRIMARY_SHARE is how much of the set must sit in the base key.
NEIGHBOUR_CREDIT is how much a +-2/+-7 track counts when comparing keys — it is
deliberately low, because a set that leans on its neighbours is not "primarily
in one key" any more.
"""
from __future__ import annotations

from ecstatic_rank import rank

PRIMARY_SHARE = 0.65
NEIGHBOUR_CREDIT = 0.35
CONSIDER_TOP = 2500          # only records good enough to actually play


def allowed_deltas() -> dict[int, str]:
    """Wheel offsets the owner allows, and what to call them."""
    return {0: "presná", 2: "+2", 10: "-2", 7: "+7", 5: "-7"}


def supply(tracks: list[dict]) -> list[tuple]:
    pool = tracks[:CONSIDER_TOP]
    by_pos: dict[tuple, list] = {}
    for t in pool:
        num = int(t["camelot"][:-1]); side = t["camelot"][-1]
        by_pos.setdefault((num, side), []).append(t)

    out = []
    for side in ("A", "B"):
        for base in range(1, 13):
            exact = by_pos.get((base, side), [])
            neigh = []
            for d in (2, 10, 7, 5):
                neigh += by_pos.get(((base - 1 + d) % 12 + 1, side), [])
            if len(exact) < 12:          # cannot carry the majority of a set
                continue
            score = sum(t["fit"] for t in exact) + NEIGHBOUR_CREDIT * sum(t["fit"] for t in neigh)
            out.append((score, f"{base}{side}", len(exact), len(neigh),
                        sum(t["fit"] for t in exact[:20]) / 20))
    out.sort(reverse=True)
    return out


if __name__ == "__main__":
    tracks = rank()
    print(f"{'kľúč':<6}{'v tónine':>9}{'susedia':>9}{'sila':>8}   {'top20 priemer':>13}")
    for score, key, n_exact, n_neigh, avg in supply(tracks)[:14]:
        print(f"{key:<6}{n_exact:>9}{n_neigh:>9}{score:>8.1f}   {avg:>13.3f}")

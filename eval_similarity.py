#!/usr/bin/env python3
"""Measure which signals actually carry "this is the same track" information.

THE GROUND TRUTH: the library holds the radio edit, the extended mix and the
remix of the same song as separate tracks. Those pairs ARE the same music, which
is exactly the target the owner described. So for each track that has a sibling
version, we ask every signal on its own: where does it rank that sibling?

METRICS
  recall@100  how often the sibling lands in the top 100 (what the app shows)
  MRR         mean of 1/rank — rewards putting it FIRST, not merely in the list

WHY THIS IS NOT CIRCULAR: the signals never see the title, the artist or the
song identity. They see audio embeddings, tags and numbers.

THE CAVEAT, STATED UP FRONT: a few tag types identify the RELEASE rather than
the sound — label, version, remixer, country. They will score well here because
siblings share a release, not because they hear anything. They are flagged in
the output and must not be read as "good at similarity".

USAGE
  ./.venv/bin/python eval_similarity.py --queries 150
"""
from __future__ import annotations

import argparse
import collections
import sqlite3

import numpy as np

import similarity_engine as engine
import similarity_features as feat

RELEASE_TAGS = {"label", "version", "remixer", "country", "format", "onetagger"}


def sibling_groups(lib) -> dict[str, list[str]]:
    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    groups: dict[str, list[str]] = collections.defaultdict(list)
    marks = ",".join("?" * 900)
    ids = list(lib.pos)
    for start in range(0, len(ids), 900):
        chunk = ids[start:start + 900]
        rows = db.execute(
            f"SELECT spotify_id,title,artist_names FROM tracks WHERE spotify_id IN ({','.join('?'*len(chunk))})",
            chunk).fetchall()
        for r in rows:
            groups[engine.song_key(r["title"], r["artist_names"])].append(r["spotify_id"])
    db.close()
    return {k: v for k, v in groups.items() if len(v) > 1 and k.strip(" |")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=int, default=150)
    args = ap.parse_args()
    print("loading …", flush=True)
    engine.warm()
    lib = engine._state["lib"]
    catalogue = engine.signals()

    groups = sibling_groups(lib)
    pairs = [(members[0], set(members[1:])) for members in groups.values()]
    rng = np.random.default_rng(7)
    rng.shuffle(pairs)
    pairs = pairs[:args.queries]
    print(f"{len(groups):,} songs have more than one version; testing {len(pairs)} of them\n")

    n = len(lib.ids)
    stats: dict[str, list] = collections.defaultdict(list)
    for ref, siblings in pairs:
        row = lib.pos[ref]
        sib_rows = [lib.pos[s] for s in siblings if s in lib.pos]
        if not sib_rows:
            continue
        for signal in catalogue:
            got = engine._signal_vector(lib, signal["id"], ref, row, n)
            if got is None:
                continue
            values, mask = got
            z = engine._z(values, mask)
            z[row] = -1e9                      # never rank the query itself
            order = np.argsort(-z)
            place = {int(r): i for i, r in enumerate(order[:2000])}
            best = min((place.get(r, 10**6) for r in sib_rows), default=10**6)
            stats[signal["id"]].append(best + 1)

    rows = []
    for sid, ranks in stats.items():
        info = next(s for s in catalogue if s["id"] == sid)
        arr = np.array(ranks, dtype=float)
        rows.append({"id": sid, "label": info["label"], "group": info["group"],
                     "n": len(arr), "recall100": float((arr <= 100).mean()),
                     "mrr": float((1.0 / arr).mean())})
    rows.sort(key=lambda r: -r["mrr"])
    print(f"{'signal':34} {'group':9} {'recall@100':>10} {'MRR':>7}   note")
    for r in rows:
        flag = "  <- identifies the RELEASE, not the sound" \
            if r["label"] in RELEASE_TAGS else ""
        print(f"{r['label'][:32]:34} {r['group']:9} {r['recall100']*100:9.0f}% {r['mrr']:7.3f}{flag}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Measure how much of a track we must analyse to keep the same answer.

WHY: GPU cost scales with the number of model windows per track, and the
rhythm/MAEST/CLAP stages currently tile the WHOLE track. If a subset of
evenly spaced windows reproduces the full-track verdict, the rest is money
spent for no information. This replays already-paid results — the per-window
timelines stored in each shard's results.jsonl — so the study itself costs
nothing and needs no GPU.

WHAT IT REPORTS: for each candidate window budget, how often the summary a
DJ actually reads (rhythm pattern, beat presence, BPM within tolerance)
matches the full-track answer, plus how much GPU work that budget saves.

HOW TO TWEAK: BUDGETS lists the candidate window counts; BPM_TOLERANCE is
how far a BPM may drift and still count as agreeing.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median
import jsonl_io

ROOT = Path(__file__).resolve().parent
SHARDS = ROOT / "data" / "cloud_full_shards"
BUDGETS = (3, 4, 5, 6, 8)
BPM_TOLERANCE = 0.5  # BPM; anything under this is inaudible for beatmatching


def evenly_spaced(items: list, count: int) -> list:
    """Pick `count` windows spread across the track (never just the middle)."""
    if count >= len(items):
        return items
    step = (len(items) - 1) / (count - 1) if count > 1 else 0
    return [items[round(i * step)] for i in range(count)]


def summarize(timeline: list) -> dict:
    """Reproduce run_rhythm's aggregation exactly, for a given window set."""
    patterns = Counter(w["rhythm_pattern"] for w in timeline)
    dominant, hits = patterns.most_common(1)[0]
    coverage = hits / len(timeline)
    if coverage < 0.60:
        dominant = "mixed_or_variable"
    bpms = [float(w["bpm"]) for w in timeline if w.get("bpm")]
    return {
        "rhythm_pattern": dominant,
        "beat_presence": Counter(w["beat_presence"] for w in timeline).most_common(1)[0][0],
        "bpm": float(median(bpms)) if bpms else None,
    }


def main() -> None:
    tracks = []
    for results in sorted(SHARDS.glob("shard-*/results.jsonl*")):
        with jsonl_io.open_jsonl(results) as handle:
          for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("stage") != "rhythm_full" or row.get("status") != "success":
                continue
            timeline = (row.get("result") or {}).get("timeline") or []
            if len(timeline) >= max(BUDGETS):      # only tracks long enough to subsample
                tracks.append(sorted(timeline, key=lambda w: w["index"]))
        if len(tracks) >= 4000:
            break

    print(f"tracks studied: {len(tracks):,} (only those with >= {max(BUDGETS)} windows)")
    avg_windows = sum(len(t) for t in tracks) / max(len(tracks), 1)
    print(f"average windows per track: {avg_windows:.1f}\n")
    print(f"{'budget':>7}{'pattern':>10}{'presence':>10}{'BPM':>8}{'all 3':>8}{'GPU saved':>11}")
    for budget in BUDGETS:
        pattern = presence = bpm_ok = both = 0
        for timeline in tracks:
            truth = summarize(timeline)
            got = summarize(evenly_spaced(timeline, budget))
            p = got["rhythm_pattern"] == truth["rhythm_pattern"]
            b = got["beat_presence"] == truth["beat_presence"]
            m = (truth["bpm"] is None and got["bpm"] is None) or (
                truth["bpm"] is not None and got["bpm"] is not None
                and abs(got["bpm"] - truth["bpm"]) <= BPM_TOLERANCE)
            pattern += p; presence += b; bpm_ok += m; both += (p and b and m)
        n = len(tracks)
        saved = 100 * (1 - sum(min(budget, len(t)) for t in tracks) / sum(len(t) for t in tracks))
        print(f"{budget:>7}{100*pattern/n:>9.1f}%{100*presence/n:>9.1f}%"
              f"{100*bpm_ok/n:>7.1f}%{100*both/n:>7.1f}%{saved:>10.0f}%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rank the library against one track, using whichever signals you switch on.

EVERY comparable thing in the database is a separate, tickable signal:

  audio      3 embedding models — how the track actually sounds
  tags       all 40 tag types, each compared on its own (genre apart from mood,
             apart from label, apart from instrument …)
  numbers    every musical number — energy, valence, syncopation, loudness,
             tempo stability … — scored by how CLOSE the value is
  musical    bpm distance and Camelot key compatibility

TWO RULES MAKE THE MIX FAIR

1. Each signal is standardised across the candidates before it is weighted. The
   signals live on different scales — a cosine sits near 0.9, a tag overlap near
   0.05, a bpm penalty is negative. Added raw, whichever had the widest spread
   would quietly decide everything and the weights would be decoration.

2. A GROUP's weight is shared among the signals ticked inside it. Ticking all 40
   tag types therefore does not drown the audio; it just makes the tag opinion
   better informed. Without this, "use everything" would always mean "tags win".

MISSING DATA NEVER PUNISHES: a track we lack a number for scores exactly average
on that signal rather than sinking to the bottom for a gap in our data.

HOW TO TWEAK: GROUP_WEIGHTS is the balance between the four families; the app
sends its own per-search, so this is only the default.
"""
from __future__ import annotations

import sqlite3
import threading

import numpy as np

import similarity_features as feat

# The group weight multiplies the SUM of its signals, so it must account for how
# many there usually are. A default selection ticks 3 audio, ~16 tags, ~17
# numbers and 2 musical, so equal-looking numbers here would let tags outweigh
# audio five to one. These keep the measured balance (audio decides, tags and
# numbers inform) while leaving both dials in the owner's hands.
#   audio    3 x 1.0  x 1.00  = 3.0
#   tags    16 x ~0.9 x 0.15  = 2.2
#   numbers 17 x ~0.8 x 0.12  = 1.6
#   musical  2 x 1.0  x 0.30  = 0.6
GROUP_WEIGHTS = {"audio": 1.0, "tags": 0.15, "numbers": 0.12, "musical": 0.3}
CHUNK = 8192

_NOTE = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5,
         "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}
_MIN = {9: 1, 4: 2, 11: 3, 6: 4, 1: 5, 8: 6, 3: 7, 10: 8, 5: 9, 0: 10, 7: 11, 2: 12}
_MAJ = {0: 1, 7: 2, 2: 3, 9: 4, 4: 5, 11: 6, 6: 7, 1: 8, 8: 9, 3: 10, 10: 11, 5: 12}


# Default weight per signal, taken from the measurement in
# docs/similarity-signal-evaluation.txt rather than from taste. These are only
# STARTING values — every one is editable per signal in the app, and a saved
# profile keeps whatever the owner set.
#   MRR measured against songs that exist as more than one mix:
#   Essentia 0.56 · CLAP 0.43 · MAEST 0.39 · onset_rate 0.34 ·
#   average_loudness 0.33 · dynamic_complexity 0.29 · genre 0.27 ·
#   subgenre 0.18 · style 0.14 · BPM 0.001 · key 0.002
SIGNAL_WEIGHT_HINTS = {
    "genre": 1.5, "subgenre": 1.2, "style": 1.0, "audio_style_candidate": 0.9,
    "genre_audio_candidate": 0.7, "mood": 0.7, "mood_candidate": 0.8,
    "instrument": 0.5, "voice": 0.4, "label": 0.6,
    "onset_rate": 1.5, "average_loudness": 1.4, "dynamic_complexity": 1.3,
    "duration_ms": 1.0, "energy": 0.8, "speechiness": 0.7,
    "instrumentalness": 0.7, "danceability": 0.6, "valence": 0.6,
    "acousticness": 0.5, "liveness": 0.5, "loudness": 0.5,
}

_lock = threading.Lock()
_state: dict = {"lib": None, "ready": False, "loading": False, "error": None}


def camelot(value):
    if not value:
        return None
    text = str(value).strip().lower().replace(" ", "-")
    mode = "m" if "min" in text else ("d" if "maj" in text else None)
    note = _NOTE.get(text.split("-")[0].strip())
    if mode is None or note is None:
        return None
    return (_MIN if mode == "m" else _MAJ)[note], mode


def key_score(a, b) -> float:
    """1.0 same key · 0.6 mixable (wheel neighbour or relative) · 0.0 clashes."""
    ka, kb = camelot(a), camelot(b)
    if not ka or not kb:
        return np.nan
    if ka == kb:
        return 1.0
    if ka[1] == kb[1] and min(abs(ka[0] - kb[0]), 12 - abs(ka[0] - kb[0])) == 1:
        return 0.6
    if ka[0] == kb[0] and ka[1] != kb[1]:
        return 0.6
    return 0.0



# --- harmonic filtering (Mixed In Key / Camelot) ------------------------------
# The wheel is laid out in fifths, so the DISTANCE between two positions says
# what the relationship is. Everything here is a filter, never a score: the
# measurement in D-074 showed key ranks near-last of 77 signals for deciding
# similarity, but it is exactly what decides whether two records can be played
# together.
#
#   delta = (candidate - reference) mod 12, same letter unless stated
#     0        the same key
#     1 or 11  one step around the wheel — the classic harmonic mix
#     2 or 10  two steps
#     7 or 5   what you get by transposing ONE SEMITONE (a semitone is seven
#              fifths, so +1 semitone = +7 on the wheel and -1 = -7 = +5)
#   relative   same number, other letter — minor <-> its relative major
KEY_RULES = {
    "exact":    lambda d, same_mode: d == 0 and same_mode,
    "relative": lambda d, same_mode: d == 0 and not same_mode,
    "step1":    lambda d, same_mode: d in (1, 11) and same_mode,
    "step2":    lambda d, same_mode: d in (2, 10) and same_mode,
    "semitone": lambda d, same_mode: d in (7, 5) and same_mode,
}


def key_allowed(ref_key, cand_key, rules) -> bool:
    """Does the candidate satisfy ANY of the selected harmonic relationships?"""
    if not rules:
        return True
    a, b = camelot(ref_key), camelot(cand_key)
    if not a or not b:
        return False          # unknown key cannot be proven mixable
    delta = (b[0] - a[0]) % 12
    same_mode = a[1] == b[1]
    return any(KEY_RULES[r](delta, same_mode) for r in rules if r in KEY_RULES)


def status() -> dict:
    lib = _state["lib"]
    return {"ready": _state["ready"], "loading": _state["loading"],
            "error": _state["error"], "tracks": len(lib.ids) if lib else 0}


def warm() -> None:
    with _lock:
        if _state["ready"] or _state["loading"]:
            return
        _state["loading"] = True
    try:
        lib = feat.Library()
        lib.load()
        _state.update(lib=lib, ready=True, loading=False, error=None)
    except Exception as exc:
        _state.update(loading=False, ready=False, error=f"{type(exc).__name__}: {exc}")


def signals() -> list[dict]:
    """Everything that CAN be compared — the checkbox list the app draws."""
    if not _state["ready"]:
        warm()
    lib = _state["lib"]
    out: list[dict] = []
    for model, (_, label, note) in feat.MODELS.items():
        if model in lib.models:
            out.append({"id": f"emb:{model}", "group": "audio", "label": label,
                        "note": note, "coverage": len(lib.models[model]["index"]),
                        "default": True, "weight": 1.0})
    for ttype, index in sorted(lib.tag_index.items()):
        out.append({"id": f"tag:{ttype}", "group": "tags", "label": ttype,
                    "note": f"{len(index):,} rôznych hodnôt",
                    "coverage": int((lib.tag_sum[ttype] > 0).sum()),
                    "default": ttype in feat.TAG_DEFAULT_ON,
                    "weight": SIGNAL_WEIGHT_HINTS.get(ttype, 1.0)})
    for name in sorted(lib.numbers):
        mean, std = lib.number_stats.get(name, (0.0, 1.0))
        # The panel needs REAL units to pre-fill a tolerance the owner
        # recognises: "BPM ±5", not "±0.25 standard deviations".
        # These columns are ANOTHER provider's tempo/key and disagree with the
        # BPM and key shown in the table on most of the library. Saying so in
        # the label is what stops "BPM = 90" from returning 125 BPM tracks.
        rival = {"bpm": "bpm (iný zdroj!)", "tempo": "tempo (iný zdroj!)",
                 "track.bpm": "bpm (Spotify)", "key": "key (iný zdroj!)",
                 "key_int": "key_int (iný zdroj!)"}
        out.append({"id": f"num:{name}", "group": "numbers",
                    "label": rival.get(name, name),
                    "note": ("nesúhlasí s BPM/tóninou v tabuľke — cieľ nastav "
                             "radšej na BPM v sekcii Hudobné"
                             if name in rival else "najbližšia hodnota"),
                    "coverage": int(lib.number_present[name].sum()),
                    "default": name in feat.NUMBER_DEFAULT_ON,
                    "weight": SIGNAL_WEIGHT_HINTS.get(name, 1.0),
                    "mean": round(float(mean), 4), "std": round(float(std), 4),
                    "tol": round(float(std) / 4.0, 4)})
    out.append({"id": "bpm", "group": "musical", "label": "BPM",
                "note": "to isté BPM, aké je v tabuľke", "weight": 1.0,
                "mean": 0.0, "std": 1.0, "tol": 3.0,
                "coverage": int(np.isfinite(lib.bpm).sum()), "default": True})
    out.append({"id": "key", "group": "musical", "label": "Tónina",
                "note": "Camelot — rovnaká 1.0, mixovateľná 0.6", "weight": 1.0,
                "coverage": int(sum(1 for k in lib.key if k)), "default": True})
    return out


def _z(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values, dtype=np.float32)
    use = mask & np.isfinite(values)
    if use.sum() < 2:
        return out
    mean, std = values[use].mean(), values[use].std() or 1.0
    out[use] = (values[use] - mean) / std
    return out


def _signal_vector(lib, sid: str, ref: str, row: int, n: int, target=None):
    """One signal's raw opinion, plus the mask of tracks it can speak about."""
    if sid.startswith("emb:"):
        model = lib.models.get(sid[4:])
        if not model or ref not in model["index"]:
            return None
        matrix, rows = model["matrix"], model["rows"]
        query = matrix[model["index"][ref]].astype(np.float32)
        cos = np.empty(matrix.shape[0], dtype=np.float32)
        for start in range(0, matrix.shape[0], CHUNK):
            cos[start:start + CHUNK] = matrix[start:start + CHUNK].astype(np.float32) @ query
        values = np.full(n, np.nan, dtype=np.float32)
        values[rows] = cos
        mask = np.zeros(n, dtype=bool)
        mask[rows] = True
        return values, mask

    if sid.startswith("tag:"):
        ttype = sid[4:]
        index, sums = lib.tag_index.get(ttype), lib.tag_sum.get(ttype)
        if index is None:
            return None
        mine = lib.tag_of.get(ttype, {}).get(ref)
        if not mine:
            return None                       # reference has no tag of this kind
        shared = np.zeros(n, dtype=np.float32)
        for tag in mine:
            entry = index.get(tag)
            if entry is not None:
                shared[entry[0]] += entry[1]
        union = sums[row] + sums - shared
        union[union <= 0] = 1.0
        return (shared / union).astype(np.float32), sums > 0

    if sid.startswith("num:"):
        name = sid[4:]
        values, present = lib.numbers.get(name), lib.number_present.get(name)
        if values is None:
            return None
        if target is not None:
            # AIM AT A VALUE instead of at the reference. The owner types it in
            # real units ("energy 0.8"), so it is converted onto the same
            # standardised scale the column lives on.
            mean, std = lib.number_stats.get(name, (0.0, 1.0))
            wanted = (float(target) - mean) / (std or 1.0)
            return -np.abs(values - wanted), present.copy()
        if not present[row]:
            return None
        return -np.abs(values - values[row]), present.copy()

    if sid == "bpm":
        # Aim at a named tempo, or at the reference's own. This is the SAME
        # number the results table prints — deliberately, because the separate
        # `num:bpm` column comes from another provider and disagrees with it on
        # roughly two thirds of the library.
        aim = float(target) if target is not None else lib.bpm[row]
        if not np.isfinite(aim) or aim <= 0:
            return None
        return -np.abs(lib.bpm - aim) / aim, np.isfinite(lib.bpm)

    if sid == "key":
        if not lib.key[row]:
            return None
        values = np.array([key_score(lib.key[row], k) for k in lib.key], dtype=np.float32)
        return values, np.isfinite(values)
    return None


def _name_of(cache: dict, sid: str) -> str:
    """Artist — title for a message, looked up once per call."""
    return cache.get(sid) or sid


def _seed_list(ref, refs) -> list[str]:
    """One reference or many — the rest of the engine does not care which."""
    if refs:
        return [str(r) for r in refs if r]
    if isinstance(ref, (list, tuple)):
        return [str(r) for r in ref if r]
    return [str(ref)] if ref else []


def common_ground(lib, seeds: list[str], min_share: float = 0.5) -> list[dict]:
    """What the chosen tracks actually share — shown so the owner can see WHY.

    A tag counts as common when at least `min_share` of the seeds carry it, so
    with three seeds a tag on two of them still counts, but a tag on only one
    does not. This is a REPORT, not part of the score: the score gets its
    agreement for free (see `similar`).
    """
    if len(seeds) < 2:
        return []
    need = max(2, int(round(min_share * len(seeds))))
    out = []
    for ttype, per_track in lib.tag_of.items():
        counts: dict[str, int] = {}
        for s in seeds:
            for tag in (per_track.get(s) or ()):
                counts[tag] = counts.get(tag, 0) + 1
        shared = sorted((t for t, c in counts.items() if c >= need),
                        key=lambda t: -counts[t])[:6]
        if shared:
            out.append({"type": ttype, "tags": shared,
                        "of": len(seeds), "hits": [counts[t] for t in shared]})
    out.sort(key=lambda d: -max(d["hits"]))
    return out[:8]


def similar(ref: str = "", limit: int = 100, spotify_only: bool = True,
            bpm_window: float = 0.0, bpm_tol: float = 0.0,
            same_key: bool = False, dedupe: bool = True,
            key_rules: list[str] | None = None,
            base_key: str | None = None,
            enabled: list[str] | None = None,
            group_weights: dict | None = None,
            signal_weights: dict | None = None,
            signal_modes: dict | None = None,
            tag_rules: list | None = None,
            refs: list[str] | None = None) -> dict:
    """Rank the library against ONE seed track or against SEVERAL at once.

    MANY SEEDS, and why it works the way it does. Each seed gets its own opinion
    per signal, that opinion is standardised (z-scored) so the signals are on a
    common scale, and the seeds' z-scores are then AVERAGED — deliberately
    without re-normalising afterwards. That single choice is the whole feature:

      * where the seeds agree, their z-scores point the same way and the average
        keeps its full size, so that signal stays strong;
      * where they disagree, the z-scores point opposite ways and cancel toward
        zero, so that signal quietly stops mattering.

    So "what the tracks have most in common" drives the result automatically —
    no hand-tuned consensus rule, and nothing to configure. Re-normalising the
    average would undo exactly this, which is why it is not done.

    HOW TO TWEAK: pass more seeds to be more specific. Two seeds that share a
    groove but differ in key will rank groove highly and ignore key on their
    own. If you want a signal to survive disagreement anyway, raise its weight
    in the panel.
    """
    if not _state["ready"]:
        warm()
    if _state["error"]:
        raise RuntimeError(_state["error"])
    lib = _state["lib"]

    seeds = _seed_list(ref, refs)
    missing = [s for s in seeds if s not in lib.pos]
    seeds = [s for s in seeds if s in lib.pos]
    if not seeds:
        raise RuntimeError("tieto tracky ešte nemajú audio analýzu, nedá sa porovnať")
    rows = [lib.pos[s] for s in seeds]
    n = len(lib.ids)

    if enabled is None:
        enabled = [s["id"] for s in signals() if s["default"]]
    weights = {**GROUP_WEIGHTS, **(group_weights or {})}
    per_signal = signal_weights or {}
    catalogue = signals()
    group_of = {s["id"]: s["group"] for s in catalogue}
    labels = {s["id"]: s["label"] for s in catalogue}

    # TWO LEVELS OF WEIGHT, exactly as the owner asked for:
    #
    #     score = SUM over groups of  group_weight * SUM( signal_weight * z )
    #
    # Each signal carries its own weight, those are ADDED inside the group, and
    # the group weight multiplies that sum. Weighting the MEAN instead would
    # quietly mean that adding a 40th tag made each of the other 39 count less.
    # This does not: ticking more signals in a group genuinely gives that group
    # more say, which is the point of choosing them. The trade-off is real and
    # it is the owner's — with 40 tags ticked at weight 1.0 the tag group
    # contributes roughly forty times one signal, so it will dominate audio
    # unless its group weight is lowered. That is why the panel shows both.
    #
    # PER-SIGNAL INTENT. "same" is the default; "diff" flips the sign so the
    # signal rewards CONTRAST instead of likeness, and "target" aims a number at
    # a value the owner names. This is what lets a set move: hold the groove and
    # the key, but ask for different energy or a different mood, so the next
    # record belongs without repeating the last one.
    modes = signal_modes or {}
    collected: dict[str, list] = {}
    agreement: dict[str, float] = {}

    # A TARGET IS A CONSTRAINT, NOT A HINT. Asking for "BPM = 90" used to be a
    # scoring preference worth about a fifteenth of one embedding, so the answer
    # came back full of 125 BPM tracks — measured: 20 of 20 outside 85-95. When
    # a tolerance comes with the target the number now FILTERS: anything outside
    # target ± tolerance cannot appear at all, and closeness still orders what
    # remains. Leaving the tolerance empty keeps the old soft behaviour.
    # FILTERS ON A NUMBER: aim at a value (→), or demand more/less than one
    # (> <). All three are hard — they decide what may appear at all, while the
    # ranking stays whatever the enabled signals say.
    # "≠" IS A DEMAND, NOT A NUDGE. Flipping one signal's sign was worth
    # 0.15 x one tag against audio's 1.0 x three embeddings, so asking for a
    # different genre changed nothing at all — measured: 20 of 20 results still
    # shared a genre with the seed, 16 of them the very same tracks. On a TAG it
    # now excludes anything sharing a value with the seed; on a NUMBER anything
    # within the tolerance of the seed's value. The ranking stays similarity —
    # "a different genre, but otherwise as close as possible", which is what
    # building a set actually needs.
    #
    # Embeddings keep the sign flip: a continuous distance has nothing to
    # exclude, and there the flip is visible anyway because audio carries the
    # heaviest weight.
    diff_gates: list[np.ndarray] = []
    notes: list[str] = []
    missing_fields: list[dict] = []
    skipped: list[dict] = []
    for sid, spec in modes.items():
        if (spec or {}).get("mode") != "diff":
            continue
        if sid.startswith("tag:"):
            ttype = sid[4:]
            per_track = lib.tag_of.get(ttype) or {}
            mine: set = set()
            for sd in seeds:
                mine |= (per_track.get(sd) or set())
            if not mine:
                # Nothing to be different FROM. Silence here reads as a broken
                # filter, so the app is told why it changed nothing.
                notes.append(f"„{ttype} ≠“ nemá čo vylúčiť — zvolený track nemá "
                             f"žiadnu hodnotu typu {ttype}.")
                continue
            index = lib.tag_index.get(ttype) or {}
            shared = np.zeros(n, dtype=bool)
            for tag, (idxs, _w, _a) in index.items():
                if tag in mine:
                    shared[idxs] = True
            diff_gates.append(~shared)
        elif sid == "bpm" or sid.startswith("num:"):
            if sid == "bpm":
                raw, present = lib.bpm, np.isfinite(lib.bpm)
                mine_vals = [lib.bpm[r] for r in rows]
                dtol = float(spec.get("tol") or 3.0)
            else:
                name = sid[4:]
                values, present = lib.numbers.get(name), lib.number_present.get(name)
                if values is None:
                    continue
                mean, std = lib.number_stats.get(name, (0.0, 1.0))
                raw = values * (std or 1.0) + mean
                mine_vals = [raw[r] for r in rows if present[r]]
                dtol = float(spec.get("tol") or (std or 1.0) / 4.0)
                if not mine_vals:
                    notes.append(f"„{name} ≠“ nemá čo vylúčiť — zvolený track "
                                 f"nemá hodnotu {name}.")
                    continue
            near = np.zeros(n, dtype=bool)
            for v in mine_vals:
                if np.isfinite(v):
                    with np.errstate(invalid="ignore"):
                        near |= np.abs(raw - v) <= abs(dtol)
            diff_gates.append(present & ~near)

    number_gates: list[np.ndarray] = []
    for sid, spec in modes.items():
        spec = spec or {}
        op = spec.get("mode")
        if op not in ("target", "gt", "lt", "gte", "lte"):
            continue
        if spec.get("target") in (None, ""):
            continue
        tol = spec.get("tol")
        if sid == "bpm":
            raw, present = lib.bpm, np.isfinite(lib.bpm)
            default_tol = 3.0
        elif sid.startswith("num:"):
            name = sid[4:]
            values, present = lib.numbers.get(name), lib.number_present.get(name)
            if values is None:
                continue
            mean, std = lib.number_stats.get(name, (0.0, 1.0))
            raw = values * (std or 1.0) + mean       # back to real units
            default_tol = (std or 1.0) / 4.0
        else:
            continue
        # NAMING A VALUE IS A DEMAND, NOT A HINT. If no tolerance came with it,
        # a sensible one is used rather than falling back to a soft preference —
        # a preference is worth a fraction of one embedding and simply loses.
        if tol in (None, "", 0):
            tol = default_tol
        want = float(spec["target"])
        with np.errstate(invalid="ignore"):
            if op == "target":
                ok = present & (np.abs(raw - want) <= abs(float(tol)))
            elif op == "gt":
                ok = present & (raw > want)
            elif op == "gte":
                ok = present & (raw >= want)
            elif op == "lt":
                ok = present & (raw < want)
            else:
                ok = present & (raw <= want)
        number_gates.append(ok)

    for sid in enabled:
        spec = modes.get(sid) or {}
        mode = spec.get("mode", "same")
        target = spec.get("target") if mode == "target" else None
        if mode in ("gt", "lt", "gte", "lte"):
            mode = "same"      # they filter; the ranking stays similarity-based
        per_seed = []
        for seed, row in zip(seeds, rows):
            result = _signal_vector(lib, sid, seed, row, n, target=target)
            if result is None:
                continue                       # this seed cannot speak here
            values, mask = result
            if mode == "diff":
                values = -values
            per_seed.append(_z(values, mask))
        if not per_seed:
            # SILENTLY DROPPING A TICKED SIGNAL IS EXACTLY WHAT MUST NOT HAPPEN.
            # A data-poor seed can lose most of the comparison this way — one
            # track lost 27 of 45 — and the app used to report only how many
            # signals were used, never how many were asked for and could not be.
            skipped.append({"id": sid, "label": labels.get(sid, sid),
                            "group": group_of.get(sid, "other")})
            continue
        z = per_seed[0] if len(per_seed) == 1 else np.mean(per_seed, axis=0)
        # How much the seeds agreed, purely for display: the length of the
        # average against the average length. 1.0 = they said the same thing,
        # near 0 = they cancelled each other out.
        if len(per_seed) > 1:
            sizes = float(np.mean([float(np.linalg.norm(v)) for v in per_seed])) or 1.0
            agreement[sid] = round(float(np.linalg.norm(z)) / sizes, 3)
        collected.setdefault(group_of.get(sid, "other"), []).append((sid, z))

    score = np.zeros(n, dtype=np.float32)
    used: dict[str, int] = {}
    contributions: dict[str, np.ndarray] = {}
    for group, items in collected.items():
        gw = weights.get(group, 0.5)
        used[group] = len(items)
        for sid, z in items:
            sw = float(per_signal.get(sid, 1.0))
            score += gw * sw * z
            contributions[sid] = sw * z

    # Against MANY seeds a candidate is judged by its BEST match among them:
    # in a set it only has to sit next to one of the records, not all of them.
    # HARMONY AGAINST A KEY YOU CHOOSE. Normally the reference is the seed's own
    # key, but a set is often built in a key the seed is not in — so `base_key`
    # replaces it, and everything harmonic (the filter, the match score and the
    # relation shown in the table) is measured from there instead.
    if base_key:
        key_cols = [np.array([key_score(base_key, k) for k in lib.key], dtype=np.float32)]
    else:
        key_cols = [np.array([key_score(lib.key[r], k) for k in lib.key], dtype=np.float32)
                    for r in rows]
    keys = key_cols[0] if len(key_cols) == 1 else np.max(np.stack(key_cols), axis=0)
    bpm_cols, bpm_abs_cols = [], []
    for r in rows:
        rb = lib.bpm[r]
        good = np.isfinite(rb) and rb > 0
        bpm_cols.append((np.abs(lib.bpm - rb) / rb) if good
                        else np.full(n, np.nan, dtype=np.float32))
        # Absolute distance too, because "± 3 BPM from what I picked" is what a
        # DJ actually means — a percentage moves with the tempo and 3 % is a
        # different thing at 90 than at 174.
        bpm_abs_cols.append(np.abs(lib.bpm - rb) if good
                            else np.full(n, np.nan, dtype=np.float32))
    if len(bpm_abs_cols) == 1:
        bpm_abs = bpm_abs_cols[0]
    else:
        st = np.stack(bpm_abs_cols)
        bpm_abs = np.full(n, np.nan, dtype=np.float32)
        any_a = np.isfinite(st).any(axis=0)
        if any_a.any():
            bpm_abs[any_a] = np.nanmin(st[:, any_a], axis=0)
    if len(bpm_cols) == 1:
        bpm_rel = bpm_cols[0]
    else:
        # nanmin warns (and is meaningless) on a row where NO seed has a BPM.
        stack = np.stack(bpm_cols)
        bpm_rel = np.full(n, np.nan, dtype=np.float32)
        any_bpm = np.isfinite(stack).any(axis=0)
        if any_bpm.any():
            bpm_rel[any_bpm] = np.nanmin(stack[:, any_bpm], axis=0)
    seed_set = set(seeds)

    # EVERY hard filter as one mask. The ranking is untouched by it — the loop
    # below still walks the library in score order and simply skips whatever the
    # mask forbids, so what comes back is always the BEST of what survived.
    allowed = np.ones(n, dtype=bool)
    if tag_rules:
        allowed &= tag_rule_mask(lib, tag_rules, n)
    for ok in number_gates:
        allowed &= ok
    for ok in diff_gates:
        allowed &= ok
    if bpm_window:
        allowed &= ~(np.isfinite(bpm_rel) & (bpm_rel * 100 > bpm_window))
    if bpm_tol:
        allowed &= np.isfinite(bpm_abs) & (bpm_abs <= bpm_tol)
    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    db_names = {}
    for sd in seeds:
        row = db.execute("SELECT title, artist_names FROM tracks WHERE spotify_id=?", (sd,)).fetchone()
        if row:
            db_names[sd] = f"{row['artist_names']} — {row['title']}"

    # A FILTER THAT CANNOT BE ANSWERED MUST SAY SO. The seed that started this
    # had no detected key at all, so every key-filtered profile came back empty
    # with no explanation. Each of these records WHICH value is missing and on
    # WHICH track, so the app can offer to fill it in instead of shrugging.
    if (same_key or key_rules) and not base_key and not any(lib.key[r] for r in rows):
        missing_fields.append({"field": "key", "label": "tónina",
                        "tracks": [{"id": sd, "name": _name_of(db_names, sd)} for sd in seeds],
                        "why": "Filter na tóninu sa nedá vyhodnotiť — zvolený track "
                               "nemá rozpoznanú tóninu."})
    if (bpm_tol or bpm_window) and not any(np.isfinite(lib.bpm[r]) and lib.bpm[r] > 0 for r in rows):
        missing_fields.append({"field": "bpm", "label": "BPM",
                        "tracks": [{"id": sd, "name": _name_of(db_names, sd)} for sd in seeds],
                        "why": "Tempové okno sa nedá vyhodnotiť — zvolený track "
                               "nemá rozpoznané BPM."})
    if same_key:
        allowed &= keys >= 1.0
    if key_rules:
        bases = [base_key] if base_key else [lib.key[r] for r in rows]
        allowed &= np.array([any(key_allowed(b, k, key_rules) for b in bases)
                             for k in lib.key], dtype=bool)

    order = np.argsort(-score)
    rank_of = np.empty(n, dtype=np.int32)
    rank_of[order] = np.arange(n, dtype=np.int32)
    # How good could this query possibly be, ignoring the filters? Showing the
    # match against THAT instead of against the filtered winner is what makes a
    # narrowed result look narrowed rather than look wrong.
    ceiling = float(score[order[0]]) if n else 0.0
    pool = int(allowed.sum() - sum(1 for sd in seeds if allowed[lib.pos[sd]]))

    out, seen = [], set()
    for idx in order:
        sid = lib.ids[idx]
        if sid in seed_set:
            continue
        # A length check is NOT enough: a local id looks like
        # "local_c1e89649e0ddf452" — exactly 22 characters, same as a real one.
        if spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        if not allowed[idx]:
            continue
        info = db.execute("""SELECT t.title, t.artist_names,
                                (SELECT comment FROM track_comment c
                                 WHERE c.spotify_id=t.spotify_id AND c.comment IS NOT NULL
                                 LIMIT 1) comment,
                                (SELECT energy FROM track_comment c
                                 WHERE c.spotify_id=t.spotify_id AND c.energy IS NOT NULL
                                 LIMIT 1) energy,
                                (SELECT path FROM audio_files f WHERE f.spotify_id=t.spotify_id
                                 AND f.path IS NOT NULL LIMIT 1) path,
                                (SELECT value_text FROM track_attributes a
                                 WHERE a.spotify_id=t.spotify_id AND a.attribute='track.preview'
                                 AND a.value_text LIKE 'http%' LIMIT 1) preview
                             FROM tracks t WHERE t.spotify_id=?""", (sid,)).fetchone()
        title, artist = (info["title"] if info else ""), (info["artist_names"] if info else "")
        if dedupe:
            song = song_key(title, artist)
            if song in seen:
                continue
            seen.add(song)
        # Short names: a signal id like
        # "emb:laion/larger_clap_music@clap-taxonomy-v1.1.0/full-aggregate"
        # is unreadable in a table, and splitting on ":" alone leaves the path.
        top = sorted(((labels.get(s, s), float(v[idx])) for s, v in contributions.items()),
                     key=lambda kv: -kv[1])[:4]
        best_row = max(rows, key=lambda r: key_score(lib.key[r], lib.key[idx]))
        shown_base = base_key or lib.key[best_row]
        out.append({"spotify_id": sid, "title": title, "artist": artist,
                    "has_file": bool(info and info["path"]),
                    # The real file path travels with the row so the native app
                    # can arm a Finder-style drag the instant the mouse goes
                    # down — fetching it on mousedown would be a race.
                    "path": (info["path"] if info else None),
                    # A 30-second preview plays in OUR audio element, which means
                    # one click and — the part that matters live — it goes to the
                    # headphones like everything else. The Spotify iframe needed a
                    # second click inside it and ignored the output device.
                    "preview": (info["preview"] if info else None),
                    "score": round(float(score[idx]), 3),
                    "bpm": round(float(lib.bpm[idx]), 1) if np.isfinite(lib.bpm[idx]) else None,
                    "key": lib.key[idx],
                    # The owner's own energy rating, kept in Traktor's Comment.
                    # It is the one human judgement in the whole library.
                    "comment": (info["comment"] if info else None),
                    "energy_rating": (info["energy"] if info else None),
                    "bpm_diff": None if not np.isfinite(bpm_rel[idx]) else round(float(bpm_rel[idx] * 100), 1),
                    "key_match": None if not np.isfinite(keys[idx]) else float(keys[idx]),
                    "key_rel": key_relation(shown_base, lib.key[idx]),
                    "rank": int(rank_of[idx]) + 1,
                    "why": [name for name, v in top if v > 0.5]})
        if len(out) >= limit:
            break
    # THE SEED ITSELF, FIRST. It was invisible in its own result list, so there
    # was no way to click it — to play it, to edit its values, or to send it for
    # analysis. It is marked so the table can show it as the reference rather
    # than as a match.
    head = []
    for sd in seeds:
        i = lib.pos.get(sd)
        if i is None:
            continue
        row = db.execute("""SELECT t.title, t.artist_names,
                               (SELECT path FROM audio_files f WHERE f.spotify_id=t.spotify_id
                                AND f.path IS NOT NULL LIMIT 1) path,
                               (SELECT comment FROM track_comment c
                                WHERE c.spotify_id=t.spotify_id AND c.comment IS NOT NULL
                                LIMIT 1) comment,
                               (SELECT energy FROM track_comment c
                                WHERE c.spotify_id=t.spotify_id AND c.energy IS NOT NULL
                                LIMIT 1) energy,
                               (SELECT value_text FROM track_attributes a
                                WHERE a.spotify_id=t.spotify_id AND a.attribute='track.preview'
                                AND a.value_text LIKE 'http%' LIMIT 1) preview
                            FROM tracks t WHERE t.spotify_id=?""", (sd,)).fetchone()
        head.append({"spotify_id": sd, "seed": True,
                     "title": row["title"] if row else "", "artist": row["artist_names"] if row else "",
                     "has_file": bool(row and row["path"]), "path": (row["path"] if row else None),
                     "preview": (row["preview"] if row else None),
                     "comment": (row["comment"] if row else None),
                     "energy_rating": (row["energy"] if row else None),
                     "score": None, "rank": None,
                     "bpm": round(float(lib.bpm[i]), 1) if np.isfinite(lib.bpm[i]) else None,
                     "key": lib.key[i], "bpm_diff": None, "key_match": None,
                     "key_rel": None, "why": []})

    db.close()
    return {"results": head + out, "signals_used": used, "seeds": seeds,
            "ceiling": round(ceiling, 3), "pool": pool, "library": n,
            "notes": notes, "missing": missing_fields, "skipped": skipped,
            "asked": len(enabled),
            "seeds_missing": missing, "agreement": agreement,
            "common": common_ground(lib, seeds)}


def key_relation(ref_key, cand_key) -> str | None:
    """A short human label for how two keys relate — shown in the results."""
    a, b = camelot(ref_key), camelot(cand_key)
    if not a or not b:
        return None
    delta = (b[0] - a[0]) % 12
    same_mode = a[1] == b[1]
    if delta == 0:
        return "rovnaká" if same_mode else "relatívna"
    if not same_mode:
        return None
    return {1: "+1", 11: "-1", 2: "+2", 10: "-2",
            7: "+7 (poltón hore)", 5: "-7 (poltón dole)"}.get(delta)


def tag_values(limit_per_type: int = 400) -> dict[str, list[str]]:
    """Every tag VALUE the owner can build a rule on, per tag type.

    The contrast panel needs real choices ("drum and bass", "afro house"), not a
    free-text box that silently matches nothing when a word is spelled slightly
    differently.
    """
    if not _state["ready"]:
        warm()
    lib = _state["lib"]
    out = {}
    for ttype, index in lib.tag_index.items():
        values = sorted(index, key=lambda t: -len(index[t][0]))[:limit_per_type]
        out[ttype] = values
    return out


# ---------------------------------------------------------------------------
# MACROS — one click for a whole mood, energy or genre.
#
# A macro is nothing more than a saved tag rule, but the wording is the work:
# a mood is never one word. "Cheerful" lives in `mood` as happy and in
# `mood_candidate` as uplifting, so every macro names SEVERAL tag types and
# SEVERAL values, and matches when any pairing hits (see passes_tag_rules).
#
# Macros are NOT combined with each other here on purpose — they are meant to be
# stacked by hand. Two macros are two rules, and rules AND together, so picking
# "Veselé" and "Vysoká energia" gives cheerful AND high-energy.
#
# WHY `mood_candidate` IS NOT USED HERE, even though it has the widest coverage
# and the more evocative words: EVERY track carries it, several values each, so
# a macro built on it matches almost the whole library. Measured — "happy" from
# mood+mood_candidate hit 99.5 % of records and filtered nothing. The macros
# therefore stand on the CONFIRMED tags, where the shares are 8-60 % and the
# filter actually means something. mood_candidate remains available as a
# similarity signal, which is what it is good at.
#
# HOW TO TWEAK: add an entry below. `value` is matched as a SUBSTRING, so avoid
# words that are prefixes of something else — "electro" would match every
# "electronic" record, which is why there is no such macro. Then check the share
# it reports: above roughly 60 % it is not really a filter.
from similarity_macros import MACROS, MACRO_MIN_CONF, GROUP_MIN_CONF

# Counting every macro walks the whole tag index, so it is done once per warm.
_macro_cache: dict = {}


def macros() -> list[dict]:
    """The macro list, each with how many tracks it actually matches.

    The count is the honest part: a macro nobody can use because three records
    carry the tag should say so rather than look like an option.
    """
    if not _state["ready"]:
        warm()
    if _macro_cache:
        return _macro_cache["out"]
    lib = _state["lib"]
    out = []
    for group in MACROS:
        items = []
        for m in group["items"]:
            # Counted the SAME way the filter matches — exactly. Counting
            # loosely and filtering strictly would put a number on the chip that
            # the result could never reach.
            want = {v.strip() for v in m["value"].split("|") if v.strip()}
            conf = float(m.get("min_conf",
                                GROUP_MIN_CONF.get(group["group"], MACRO_MIN_CONF)))
            rows, present = set(), set()
            for ttype in m["type"].split("|"):
                index = lib.tag_index.get(ttype.strip())
                if not index:
                    continue
                for tag, (idxs, weights, artist) in index.items():
                    if tag in want:
                        present.add(tag)
                        keep = (weights >= conf) & ~artist
                        rows.update(idxs[keep].tolist())
            items.append({**m, "match": "exact", "track_only": True,
                          "min_conf": conf,
                          "count": len(rows),
                          # Which of the listed values actually exist. A value
                          # that matches nothing is a typo waiting to be found.
                          "dead": sorted(want - present),
                          "pct": round(100.0 * len(rows) / max(1, len(lib.ids)), 1)})
        out.append({"group": group["group"], "items": items})
    _macro_cache["out"] = out
    return out


def tag_rule_mask(lib, rules: list[dict], n: int) -> np.ndarray:
    """The same yes/no as passes_tag_rules, for the whole library at once.

    Answering it in one pass is what lets the app say HOW MANY tracks survived a
    filter. Without that number a narrowed result looks like the ranking was
    thrown away, when in truth it was the best of a small pool.
    """
    mask = np.ones(n, dtype=bool)
    for rule in rules or []:
        ttype = (rule.get("type") or "").strip()
        value = (rule.get("value") or "").strip().lower()
        if not ttype or not value:
            continue
        types = [t.strip() for t in ttype.split("|") if t.strip()]
        values = [v.strip() for v in value.split("|") if v.strip()]
        # EXACT means the tag must BE one of these, not merely contain one.
        # Substring matching both missed and over-matched: it never found the
        # 1,206 tracks tagged plain `dnb` while asking for "drum n bass", and it
        # pulled `liquid funk` — drum'n'bass — into a disco/funk filter. Macros
        # always ask for exact; a rule typed by hand stays forgiving.
        exact = rule.get("match") == "exact"
        want = set(values)
        # A MINIMUM CONFIDENCE, and it is what makes a genre filter mean
        # anything. A track carries a MEDIAN OF 26 genre tags from a dozen
        # sources, most of them artist-level guesses at 0.15 — so "has the tag
        # ambient" was true of almost every electronic record. Measured at 0.8:
        # ambient's beat presence falls 0.569 -> 0.461 and its four-on-the-floor
        # share 36 % -> 23 %; drum'n'bass's median tempo rises 158 -> 176 BPM.
        # TWEAK: macros pass 0.8 (similarity_macros.py); a hand-typed rule
        # passes nothing and stays permissive.
        min_conf = float(rule.get("min_conf") or 0)
        # Ignore tags that describe the artist rather than this recording.
        track_only = bool(rule.get("track_only"))
        hit = np.zeros(n, dtype=bool)
        for t in types:
            for tag, (rows, weights, artist) in (lib.tag_index.get(t) or {}).items():
                if not ((tag in want) if exact else any(v in tag for v in values)):
                    continue
                keep = np.ones(len(rows), dtype=bool)
                if min_conf:
                    keep &= weights >= min_conf
                if track_only:
                    keep &= ~artist
                hit[rows[keep]] = True
        mask &= hit if rule.get("mode", "must") == "must" else ~hit
    return mask


def passes_tag_rules(lib, idx: int, rules: list[dict]) -> bool:
    """Hard yes/no on tag VALUES — the "must contain / must not contain" filter.

    Separate from the similarity score on purpose: "it has to be drum and bass"
    is not a preference to be outweighed by a strong match elsewhere, it is a
    condition. Scoring it would let a very similar house record outrank the
    requirement and quietly ignore what was asked.
    """
    sid = lib.ids[idx]
    for rule in rules or []:
        ttype = (rule.get("type") or "").strip()
        value = (rule.get("value") or "").strip().lower()
        mode = rule.get("mode", "must")
        if not ttype or not value:
            continue
        # BOTH SIDES ACCEPT ALTERNATIVES, separated by "|". A mood is rarely one
        # word — "cheerful" lives in `mood` as happy and in `mood_candidate` as
        # uplifting — so a single rule can name several tag types and several
        # values, and matches when ANY pairing hits. Separate rules still AND
        # together, which is what lets two macros be combined.
        types = [t.strip() for t in ttype.split("|") if t.strip()]
        values = [v.strip() for v in value.split("|") if v.strip()]
        have: set[str] = set()
        for t in types:
            have |= (lib.tag_of.get(t, {}).get(sid) or set())
        # Same rule as tag_rule_mask: exact for macros, forgiving for a rule
        # typed by hand, where "drum" finding "drum and bass" is a convenience.
        if rule.get("match") == "exact":
            # NOTE: `tag_of` carries no confidence, so this per-track twin
            # ignores min_conf. It is only used for one-off checks; every real
            # query goes through tag_rule_mask above, which honours it.
            hit = bool(have & set(values))
        else:
            hit = any(v in tag for tag in have for v in values)
        if mode == "must" and not hit:
            return False
        if mode == "must_not" and hit:
            return False
    return True

def song_key(title: str, artist: str) -> str:
    """Identity of a SONG, ignoring which mix it is — radio edit, extended and
    remix cluster together and would eat a playlist's variety."""
    base = (title or "").lower()
    for cut in (" - ", " (", " ["):
        if cut in base:
            base = base.split(cut)[0]
    return f"{base.strip()}|{(artist or '').split(',')[0].strip().lower()}"


def search(query: str, limit: int = 25) -> list[dict]:
    if not query.strip():
        return []
    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    words = query.split()
    sql = ("SELECT spotify_id, title, artist_names FROM tracks WHERE "
           + " AND ".join(["(title LIKE ? OR artist_names LIKE ?)"] * len(words)) + " LIMIT 400")
    rows = db.execute(sql, [x for w in words for x in (f"%{w}%", f"%{w}%")]).fetchall()
    db.close()
    lib = _state["lib"]
    out = [{"spotify_id": r["spotify_id"], "title": r["title"], "artist": r["artist_names"],
            "analysed": (r["spotify_id"] in lib.pos) if lib else None} for r in rows]
    out.sort(key=lambda r: (not r["analysed"], len(r["title"] or "")))
    return out[:limit]


# ---------------------------------------------------------------- presets
# Five ready-made selections. Every one of them is justified by
# docs/similarity-signal-evaluation.txt, which measured each signal against a
# ground truth the library provides for free: songs that exist here as more than
# one mix (radio edit / extended / remix). Those pairs ARE the same music, so
# "where does this signal rank the other version?" is a fair test of how much
# same-track information it carries. 2,876 such songs; 120 sampled.
#
# WHAT THE MEASUREMENT SAID (MRR = how often it puts the sibling FIRST):
#   Essentia 0.56 · CLAP 0.43 · MAEST 0.39   the embeddings win outright
#   onset_rate 0.34 · average_loudness 0.33 · dynamic_complexity 0.29
#   genre 0.27 · subgenre 0.18 · style 0.14
#   BPM 0.001 · key 0.002                    near USELESS for ranking
#
# The last line is the surprise and it shapes these presets: thousands of tracks
# share a key and a tempo, so neither can single out the right one. They belong
# in the FILTERS, narrowing what may appear — never in the score.
#
# `label` reached the highest recall of any tag (81%) but it identifies the
# RELEASE, not the sound; it is used only where "more from this scene" is the
# actual goal, and never in the sound-only presets.
PRESETS = [
    {
        "id": "same_track",
        "label": "Ten istý track",
        "note": "Najvyššia celková podobnosť — všetko, čo v meraní obstálo.",
        "why": "Spája tri embeddingy (MRR 0.56/0.43/0.39) so žánrovými tagmi "
               "(genre 0.27, subgenre 0.18, style 0.14) a s číslami, ktoré "
               "merateľne nesú informáciu (onset_rate 0.34, average_loudness "
               "0.33, dynamic_complexity 0.29). Vynecháva pásmové tagy typu "
               "energy_band, ktoré majú 2-3 hodnoty a v meraní vyšli na nulu.",
        "groups": {"audio": 1.0, "tags": 0.15, "numbers": 0.12, "musical": 0.2},
        "tags": ["genre", "subgenre", "style", "audio_style_candidate",
                 "genre_audio_candidate", "mood", "mood_candidate", "instrument"],
        "numbers": ["onset_rate", "average_loudness", "dynamic_complexity",
                    "energy", "danceability", "valence", "speechiness",
                    "instrumentalness", "acousticness", "loudness", "duration_ms"],
        "embeddings": "all", "musical": ["bpm", "key"],
    },
    {
        "id": "pure_sound",
        "label": "Čistý zvuk",
        "note": "Len to, ako to znie. Ignoruje každý štítok.",
        "why": "Tri embeddingy samé sú najsilnejší signál v celom meraní. "
               "Keďže nevidia žáner ani label, nájdu track, ktorý znie rovnako, "
               "aj keď ho niekto zaradil inam — na objavovanie naprieč scénami.",
        "groups": {"audio": 1.0, "tags": 0.0, "numbers": 0.0, "musical": 0.0},
        "tags": [], "numbers": [], "embeddings": "all", "musical": [],
    },
    {
        "id": "dj_mix",
        "label": "Do mixu",
        "note": "Podobné A ZÁROVEŇ mixovateľné — tónina a tempo ako tvrdý filter.",
        "why": "Práve preto, že tónina (MRR 0.002) a BPM (0.001) sú na "
               "zoradenie takmer bezcenné — zdieľajú ich tisíce trackov — sa tu "
               "používajú ako SITO, nie ako skóre. Poradie určí zvuk a rytmus, "
               "ale prejdú len tracky do 3 % tempa a v mixovateľnej tónine.",
        "groups": {"audio": 1.0, "tags": 0.25, "numbers": 0.15, "musical": 0.0},
        "tags": ["genre", "subgenre", "style"],
        "numbers": ["onset_rate", "average_loudness", "dynamic_complexity",
                    "four_on_floor_score", "broken_beat_score",
                    "syncopation_score", "tempo_stability", "rhythm_regularity"],
        "embeddings": "all", "musical": [],
        "filters": {"bpm_window": 3.0, "same_key": True},
    },
    {
        "id": "mood",
        "label": "Nálada a energia",
        "note": "Rovnaký pocit, aj keď je to iný žáner.",
        "why": "CLAP je model natrénovaný na dvojice zvuk-text, čiže na náladu a "
               "textúru, a v meraní skončil druhý (0.43). Dopĺňajú ho mood tagy "
               "(mood_candidate 0.114, nad väčšinou tagov) a čísla o energii a "
               "valencii. Žánrové tagy sú zámerne von — inak by ti to vracalo "
               "ten istý žáner namiesto tej istej nálady.",
        "groups": {"audio": 1.2, "tags": 0.3, "numbers": 0.2, "musical": 0.0},
        "tags": ["mood", "mood_candidate", "theme", "vocal_character", "voice"],
        "numbers": ["energy", "valence", "danceability", "average_loudness",
                    "dynamic_complexity", "acousticness"],
        "embeddings": ["CLAP"], "musical": [],
    },
    {
        "id": "scene",
        "label": "Žáner a scéna",
        "note": "Viac z tej istej scény — vrátane vydavateľstva.",
        "why": "MAEST je žánrový model (0.39) a žánrové tagy tu majú najvyššie "
               "pokrytie (genre 61 %, style 60 %, subgenre 56 % v top 100). "
               "Pridáva aj label, ktorý mal vôbec najvyšší recall zo všetkých "
               "tagov (81 %) — ale POZOR, ten neidentifikuje zvuk, len to, že "
               "vyšli u toho istého vydavateľa. Preto je len tu.",
        "groups": {"audio": 1.2, "tags": 0.25, "numbers": 0.3, "musical": 0.0},
        "tags": ["genre", "subgenre", "style", "audio_style_candidate",
                 "genre_audio_candidate", "label", "country", "production_style"],
        "numbers": ["onset_rate", "dynamic_complexity"],
        "embeddings": ["MAEST"], "musical": [],
    },
    {
        "id": "mood_in_scene",
        "label": "Nálada v scéne",
        "note": "Presne tá nálada a energia — ale v tom istom žánri a scéne.",
        "why": "Spojenie dvoch predošlých režimov, a spojenie zámerne "
               "nerovnomerné. 'Nálada a energia' zámerne vyhadzuje žánrové "
               "tagy, aby našla ten istý pocit inde; 'Žáner a scéna' zase "
               "nepozerá na náladu. Tu bežia obidva modely naraz — CLAP nesie "
               "náladu a textúru (MRR 0.43), MAEST žáner (0.39) — a tagy sú "
               "oboje: mood spolu s genre, subgenre a style. Label je VON, "
               "hoci má najvyšší recall: vydavateľstvo je znak scény, nie "
               "nálady, a v tomto režime by ťa stiahol späť ku katalógu jednej "
               "firmy namiesto k tomu pocitu. Použi to, keď vieš presne, akú "
               "náladu chceš, ale nechceš, aby ti to vyskočilo zo žánru — "
               "typicky uprostred setu, keď držíš scénu a hýbeš energiou.",
        "groups": {"audio": 1.2, "tags": 0.3, "numbers": 0.25, "musical": 0.0},
        "tags": ["mood", "mood_candidate", "theme", "vocal_character", "voice",
                 "genre", "subgenre", "style", "audio_style_candidate",
                 "genre_audio_candidate", "production_style"],
        "numbers": ["energy", "valence", "danceability", "average_loudness",
                    "dynamic_complexity", "acousticness", "onset_rate"],
        "embeddings": ["CLAP", "MAEST"], "musical": [],
    },
]


def apply_override(track_id: str, field: str, value) -> bool:
    """Put a corrected value into the loaded library immediately.

    Without this the correction would only take effect after a restart, and the
    owner would type the key, see nothing change, and reasonably conclude it did
    not work.
    """
    if not _state["ready"]:
        return False
    lib = _state["lib"]
    i = lib.pos.get(track_id)
    if i is None:
        return False
    if field == "key":
        lib.key[i] = str(value) if value else None
    elif field == "bpm":
        lib.bpm[i] = float(value) if value else np.nan
    return True


def explain(sid: str) -> dict:
    """Everything the ⓘ button shows for one signal.

    The prose comes from similarity_help.py; the numbers and value lists are
    read from the library itself, so the help can never describe data that is
    not there. TWEAK the wording in similarity_help.py, never here.
    """
    import similarity_help as helptext
    if not _state["ready"]:
        warm()
    lib = _state["lib"]
    item = next((s for s in signals() if s["id"] == sid), None)
    if not item:
        return {"error": "taký signál neexistuje"}
    out = {"id": sid, "label": item["label"], "group": item["group"],
           "coverage": item["coverage"], "library": len(lib.ids),
           "default": item["default"]}
    key = sid.split(":", 1)[1] if ":" in sid else sid
    what, how = helptext.prose(item["group"], item["label"] if item["group"] == "audio" else key)

    if item["group"] == "tags":
        index = lib.tag_index.get(key) or {}
        top = sorted(((tag, len(rows)) for tag, (rows, *_r) in index.items()),
                     key=lambda kv: -kv[1])[:18]
        out["values"] = [{"value": t, "count": c} for t, c in top]
        out["distinct"] = len(index)
        if not what:
            what = f"Typ štítku s {len(index):,} rôznymi hodnotami."
            how = "Vlastného popisu zatiaľ nemá — pozri najčastejšie hodnoty nižšie."
        out["usage"] = ("V paneli „Čo posunúť“ sa dá použiť ako tvrdé pravidlo: "
                        "musí / nesmie obsahovať jednu z hodnôt nižšie.")
    elif item["group"] in ("numbers", "musical"):
        if item["group"] == "musical":
            raw = lib.bpm[np.isfinite(lib.bpm)]
        else:
            values, present = lib.numbers.get(key), lib.number_present.get(key)
            mean, std = lib.number_stats.get(key, (0.0, 1.0))
            raw = (values * (std or 1.0) + mean)[present]
        if raw.size:
            qs = np.percentile(raw, [5, 25, 50, 75, 95])
            out["range"] = {"min": round(float(raw.min()), 3), "max": round(float(raw.max()), 3),
                            "mean": round(float(raw.mean()), 3),
                            "p5": round(float(qs[0]), 3), "p25": round(float(qs[1]), 3),
                            "median": round(float(qs[2]), 3), "p75": round(float(qs[3]), 3),
                            "p95": round(float(qs[4]), 3)}
            out["suggest"] = {"nízke": round(float(qs[1]), 2), "stredné": round(float(qs[2]), 2),
                              "vysoké": round(float(qs[3]), 2), "extrém": round(float(qs[4]), 2)}
        out["tol"] = item.get("tol")
        if not what:
            what = "Číselná vlastnosť skladby."
            how = "Vlastného popisu zatiaľ nemá — orientuj sa podľa rozsahu nižšie."
        out["usage"] = ("Porovnáva sa vzdialenosťou: čím bližšie k hodnote zvoleného tracku, "
                        "tým vyššie skóre. V paneli „Čo posunúť“ sa dá namieriť na hodnotu (→) "
                        "alebo obmedziť operátormi > a <.")
    else:
        out["usage"] = ("Embedding — porovnáva sa kosínusovou podobnosťou celých odtlačkov zvuku. "
                        "Nedá sa naň nastaviť cieľová hodnota, len zapnúť a zvážiť.")
    out["what"], out["how"] = what, how
    return out


def presets() -> list[dict]:
    """The built-in selections, resolved against the signals this library
    actually has — so a preset never asks for a tag type or number that is
    missing. Adding one means adding an entry to PRESETS above; nothing else
    in the app needs to know about it."""
    catalogue = signals()
    by_group: dict[str, list[dict]] = {}
    for item in catalogue:
        by_group.setdefault(item["group"], []).append(item)
    out = []
    for preset in PRESETS:
        enabled: list[str] = []
        want_emb = preset["embeddings"]
        for item in by_group.get("audio", []):
            if want_emb == "all" or item["label"] in want_emb:
                enabled.append(item["id"])
        for item in by_group.get("tags", []):
            if item["label"] in preset["tags"]:
                enabled.append(item["id"])
        for item in by_group.get("numbers", []):
            if item["label"] in preset["numbers"]:
                enabled.append(item["id"])
        for item in by_group.get("musical", []):
            if item["id"] in preset.get("musical", []):
                enabled.append(item["id"])
        out.append({**{k: v for k, v in preset.items()
                       if k not in ("tags", "numbers", "embeddings", "musical")},
                    "enabled": enabled, "group_weights": preset["groups"]})
    return out

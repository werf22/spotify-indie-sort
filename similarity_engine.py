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
        out.append({"id": f"num:{name}", "group": "numbers", "label": name,
                    "note": "najbližšia hodnota",
                    "coverage": int(lib.number_present[name].sum()),
                    "default": name in feat.NUMBER_DEFAULT_ON,
                    "weight": SIGNAL_WEIGHT_HINTS.get(name, 1.0)})
    out.append({"id": "bpm", "group": "musical", "label": "BPM",
                "note": "vzdialenosť tempa", "weight": 1.0,
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
        ref_bpm = lib.bpm[row]
        if not np.isfinite(ref_bpm) or ref_bpm <= 0:
            return None
        return -np.abs(lib.bpm - ref_bpm) / ref_bpm, np.isfinite(lib.bpm)

    if sid == "key":
        if not lib.key[row]:
            return None
        values = np.array([key_score(lib.key[row], k) for k in lib.key], dtype=np.float32)
        return values, np.isfinite(values)
    return None


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
            bpm_window: float = 0.0, same_key: bool = False, dedupe: bool = True,
            key_rules: list[str] | None = None,
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
    for sid in enabled:
        spec = modes.get(sid) or {}
        mode = spec.get("mode", "same")
        target = spec.get("target") if mode == "target" else None
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
    key_cols = [np.array([key_score(lib.key[r], k) for k in lib.key], dtype=np.float32)
                for r in rows]
    keys = key_cols[0] if len(key_cols) == 1 else np.max(np.stack(key_cols), axis=0)
    bpm_cols = []
    for r in rows:
        rb = lib.bpm[r]
        bpm_cols.append((np.abs(lib.bpm - rb) / rb) if np.isfinite(rb) and rb > 0
                        else np.full(n, np.nan, dtype=np.float32))
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

    db = sqlite3.connect(feat.DB, timeout=120)
    db.row_factory = sqlite3.Row
    out, seen = [], set()
    for idx in np.argsort(-score):
        sid = lib.ids[idx]
        if sid in seed_set:
            continue
        # A length check is NOT enough: a local id looks like
        # "local_c1e89649e0ddf452" — exactly 22 characters, same as a real one.
        if spotify_only and (len(sid) != 22 or sid.startswith("local_")):
            continue
        if bpm_window and np.isfinite(bpm_rel[idx]) and bpm_rel[idx] * 100 > bpm_window:
            continue
        if same_key and not keys[idx] >= 1.0:
            continue
        if key_rules and not any(key_allowed(lib.key[r], lib.key[idx], key_rules) for r in rows):
            continue
        if tag_rules and not passes_tag_rules(lib, idx, tag_rules):
            continue
        info = db.execute("""SELECT t.title, t.artist_names,
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
                    "bpm_diff": None if not np.isfinite(bpm_rel[idx]) else round(float(bpm_rel[idx] * 100), 1),
                    "key_match": None if not np.isfinite(keys[idx]) else float(keys[idx]),
                    "key_rel": key_relation(lib.key[best_row], lib.key[idx]),
                    "why": [name for name, v in top if v > 0.5]})
        if len(out) >= limit:
            break
    db.close()
    return {"results": out, "signals_used": used, "seeds": seeds,
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


def passes_tag_rules(lib, idx: int, rules: list[dict]) -> bool:
    """Hard yes/no on tag VALUES — the "must contain / must not contain" filter.

    Separate from the similarity score on purpose: "it has to be drum and bass"
    is not a preference to be outweighed by a strong match elsewhere, it is a
    condition. Scoring it would let a very similar house record outrank the
    requirement and quietly ignore what was asked.
    """
    for rule in rules or []:
        ttype = rule.get("type")
        value = (rule.get("value") or "").strip().lower()
        mode = rule.get("mode", "must")
        if not ttype or not value:
            continue
        have = lib.tag_of.get(ttype, {}).get(lib.ids[idx]) or set()
        # substring match, so "drum" finds "drum and bass" without exact spelling
        hit = any(value in tag for tag in have)
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
]


def presets() -> list[dict]:
    """The five selections, resolved against the signals this library actually
    has — so a preset never asks for a tag type or number that is missing."""
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

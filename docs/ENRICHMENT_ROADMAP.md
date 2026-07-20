# Enrichment roadmap — researched options, costs, recommendations

Researched 2026-07-20. Goal: maximum genre/mood/beat-type/instrument data per
track WITHOUT listening, at minimum cost, without diluting the existing
quality tiers (provenance + confidence stay per D-001/D-009).

## The structural fact driving everything

Audio-derived data (beat type, temporal moods, instruments heard, energy
curves) currently reaches only the **5,394 locally matched tracks** — the
full-track pipeline finishing now. The other ~62,700 tracks have **no audio
source at all**, so their data can only come from (a) metadata providers or
(b) legally streamable 30-second previews. That is the frontier.

## Option A — Deezer 30-second preview analysis tier  ⭐ biggest data win

**What:** For the ~55,500 tracks with an exact Deezer ISRC match, fetch the
public 30-s preview stream, run the SAME local models (MAEST genre, CLAP
mood/instrument candidates, Essentia heads, Beat This rhythm → beat type),
store results as a separate low-confidence tier (`audio-preview:*` sources),
delete the audio immediately — only derived features are kept.

**Wins:** beat type (regular/four-on-floor/broken/beatless) + audio-genre +
audio-mood for ~10× more tracks than today. Exactly the "know the track
without hearing it" ask.

**Quality guard:** previews stay a strictly lower tier than full-track
analysis (D-008 unaffected); canonical tags still require consensus.
30 s from the track's middle typically misses intros/outros — fine for
candidates, never promoted alone.

**Cost:** ~27 GB transient bandwidth; compute either (a) laptop overnight
(free, but warms the laptop — D-020 tension) or (b) one bounded RunPod CPU
or 3090 batch, crude estimate $8–15 total. No new subscriptions.

**Legal note (owner must accept):** Deezer's developer terms allow
non-commercial use and serve 30-s extracts precisely for preview purposes,
but forbid storing full audio content offline; this design stores no audio,
only derived features, and stays personal/non-commercial. Still an owner
call under repo rule 8 — not started without explicit approval.

## Option B — Direct Discogs API enricher  ⭐ best free metadata win

**What:** Replace/augment the slow OneTagger bridge (4,900 successes,
43,000 untouched, ~100/batch) with a direct Discogs database-search enricher
using the documented free API (personal token, ~60 req/min). Conservative
identity matching per D-006 (artist+title+year window; barcode/catno via
MusicBrainz/Deezer where present).

**Wins:** Discogs *styles* are the canonical DJ subgenre vocabulary —
deepest genre granularity available anywhere, free. Also fills label +
release-date gaps (currently 43%/47%).

**Cost:** $0. ~68k lookups ≈ 19 API-hours spread over ~2–3 days inside the
existing daemon. Effort: one enricher script in the established pattern.

## Option C — Skip list (researched, rejected)

- **Cyanite / Bridge.audio / Soundcharts / Musiio:** commercial AI-tagging
  APIs; Cyanite free tier = 5 tracks/month — useless at 68k. Paid plans
  violate "minimum money" with no quality edge over our own MAEST+Essentia.
- **Spotify 30-s previews:** deprecated Nov 2024; `preview_url` mostly null
  for newer apps — unreliable foundation; Deezer covers the same need.
- **Beatport:** no public API (partner-only); OneTagger's scraper already
  broken by their redesign.
- **GetSongBPM & similar BPM databases:** we already have BPM ~90%; the
  missing tail is underground material these registries lack too.
- **AcousticBrainz:** frozen archive, already integrated (43 matches).
- **Lyrics/Genius sentiment as mood:** weak signal vs. audio models; slow at
  68k scale. Backlog-only.

## Option D — Smaller free fills (do opportunistically)

1. **MusicBrainz genre tags via existing MBIDs** — we now have 23,557 MBIDs
   (34.6%) but only ~3,500 MB-tagged tracks; a second pass pulling
   genre/tag lists for known MBIDs is nearly free at 1 req/s.
2. **FreqBlog `needs_review` queue (2,414)** — `validate_freqblog.py`
   exists; a supervised fuzzy-acceptance pass could convert a chunk to
   successes without new API calls.
3. **Deezer untouched (10,696)** — already draining in the daemon.

## Recommended order

1. **B (Discogs direct)** — free, zero risk, deepest genre/style gain.
2. **A (preview tier)** — after owner sign-off; transforms beat/mood
   coverage. Run as bounded batches with the same ledger/watchdog discipline
   as the full-track pipeline.
3. **D1 (MBID genre pass)** — trivial addition to the daemon.
4. Re-run coverage + conflict reports, then the planned stratified audit
   calibrates all new tiers together.

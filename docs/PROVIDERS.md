# Providers, matching and costs

All provider values coexist with provenance. Matching preference is exact ID,
then ISRC, then conservative artist/title/album identity. Fuzzy matches must be
flagged for review rather than silently accepted.

## Active sources

| Source | Cost/status | Contribution | Match |
|---|---|---|---|
| Spotify API/account export | Existing account; normal API | Library, playlists, saved tracks, IDs, catalog metadata, artist genres | Spotify ID |
| Spotify Extended Streaming History | Free user export | Real play events and local lifetime statistics | URI/ID then resolver |
| ReccoBeats | Free public API | Spotify-style BPM/key/mode/loudness/energy/danceability/valence/etc. | Exact Spotify ID, batches |
| Spotify 114k public dataset | Free | Legacy Spotify audio features and genre where IDs overlap | Exact Spotify ID |
| FreqBlog Starter | **EUR 39/month**, 150k requests/month | 42+ fields, BPM/key/Camelot, perceptual features, metadata, genre/mood | ISRC first, artist/title fallback |
| Last.fm | Free personal API | Community artist/track genres, scenes, moods, instruments, vocals | Artist/title |
| MusicBrainz | Free, 1 request/s etiquette | MBIDs, ISRC links, dates, release/label identity, community tags | ISRC then exact metadata |
| Deezer | Free public API | ISRC validation, album/label/date/genre/rank, occasional BPM | ISRC |
| TheAudioDB | Free key | Broad genre/mood/style, IDs and descriptions | Exact artist/title |
| OneTagger SQL + Discogs/Bandcamp | Free/open source | Release genre/style, label, country, format, year | Normalized release identity |
| AcousticBrainz historical | Free/frozen | Historical high/low-level descriptors where MBID overlaps | MusicBrainz recording ID |
| Beat This + DSP | Free/open source, local | Beat presence/type, BPM, regularity, syncopation, kick placement | Local matched audio |
| MAEST Discogs400 | Free/open model, RunPod | Specialist genres/styles and embeddings | Full local audio |
| Essentia supervised stack | Free/open models, local | Mood/theme, genre, instrument, voice, danceability and other heads | Full local audio |
| LAION larger-CLAP-music | Free/open model, RunPod | Open-ended semantic mood vocabulary and embeddings | Full local audio |

## FreqBlog decision

The user first tested the Free key, then purchased Starter for EUR 39/month.
The active key is stored only in `.env`.

Two evaluations produced apparently different results:

- initial bulk validation: 3/200 immediately resolved;
- individual lookup probe: 40/40, including Tebra and underground controls,
  with 100% coverage for core audio fields among found records.

This indicated server-side/on-demand resolution behavior rather than a useless
catalog. The paid worker therefore uses `/bulk` for throughput and a two-phase
lookup/polling model where needed. Cache and state prevent duplicate paid calls.
FreqBlog is trusted strongly for BPM, key and catalog breadth; its heuristic
perceptual fields are retained but do not override stronger exact measurements.

## FreqBlog vs SoundNet

The explicit decision is **FreqBlog without SoundNet**:

- ReccoBeats already provides a strong free exact-Spotify-ID measurement layer.
- FreqBlog provides the paid broad fallback and long-tail catalog behavior.
- SoundNet would substantially overlap these outputs and add another plan/API
  without enough demonstrated incremental coverage.
- `enrich_soundnet.py` is retained for future experiments but
  `SOUNDNET_ENABLED=0` and no plan should be purchased automatically.

## OneTagger decision

The user wanted OneTagger enrichment without requiring local audio. The project
therefore has three complementary paths:

1. Python `onetagger_db_bridge.py` feeds SQLite rows to Discogs matching and
   persists provider results without audio files.
2. Standalone Rust `onetagger-db` runs database-fed sources; its Bandcamp source
   is active in the daemon.
3. The fork in `vendor/onetagger` contains an experimental workspace crate for
   a deeper upstream-style integration.

Beatport's redesigned site and Traxsource/Juno smoke failures are currently
disabled. Do not burn CPU repeatedly on known broken scrapers without a new test.

## Sources evaluated but not selected

- Soundcharts: enterprise/sales-led analytics, not efficient for this personal
  68k catalog.
- Bridge.audio: useful AI tagging via upload/webhooks but paid credits duplicate
  much of the open local stack. Could be used only to audit a small sample.
- Gracenote and TiVo: commercial/partner access; public developer offerings do
  not provide the desired low-cost arbitrary music bulk enrichment.
- Music Story: potentially useful but sales-led; no cost-effective 68k route
  demonstrated.
- OneMusicAPI: aggregates open databases already queried directly, reducing
  control over provenance.
- melod.ie: detailed metadata for its own production-music catalog, not an
  arbitrary Spotify-recording enrichment service.
- Cyanite/stats.fm: useful product references. Cyanite-like semantic retrieval
  is implemented locally; stats.fm-like play counts come from Spotify history.
- Spotify Audio Features/Analysis: deprecated/restricted for new applications;
  do not assume access will be granted. A future extended-quota application can
  be investigated, but the system does not depend on it.

## Cloud compute

RunPod was funded manually by the user with USD 10. The system must never add
funds. The current default is RTX 3090, followed by RTX 4090 and RTX A4000 only
when availability and the USD 0.40/hour ceiling allow it. Production selected
an RTX 3090 at USD 0.22/hour; an attempted 4090 benchmark found no community
capacity and created no pod.

The quality-first cloud scope is Beat This + MAEST + Essentia + CLAP for 5,394
local tracks. All heavy inference is cloud-only: Essentia runs on pod CPU
concurrently with the GPU lane, while the laptop performs only one
background-priority FFmpeg preparation task.

## Matching and confidence rules

- Exact Spotify ID and ISRC are authoritative identity joins.
- Artist/title lookup responses must pass normalized identity checks.
- MusicBrainz is throttled and exact-first.
- Deezer is queried only when ISRC exists.
- Provider no-match is a state, not a permanent global conclusion; another
  provider can still succeed.
- Inferred playlist/semantic tags have lower confidence and never masquerade as
  audio measurements.
- Every provider's raw response should remain available for audits and future
  schema extraction.

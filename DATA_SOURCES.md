# Data sources and operating plan

> The expanded current provider/cost/matching record is
> [docs/PROVIDERS.md](docs/PROVIDERS.md). The binding trust and full-track
> decisions are in [docs/DATA_MODEL.md](docs/DATA_MODEL.md) and
> [docs/DECISIONS.md](docs/DECISIONS.md).

The database is intentionally multi-source. Every tag, feature, and generic
attribute retains its provider and confidence; raw provider payloads are kept
for later audits and schema upgrades.

## Active sources

| Source | Cost | What it contributes | Matching |
|---|---:|---|---|
| Spotify account export/API | free | identity, library/playlists, play history, ISRC, album, label, release date, duration, popularity, legacy artist genres | Spotify ID |
| Last.fm artist + track APIs | free personal use | fine-grained community genres, scenes, moods, instruments and vocal tags | artist/title |
| MusicBrainz | free non-commercial, 1 call/s | MBIDs, ISRC cross-links, recording identity, dates, community tags | ISRC first, then exact artist/title |
| Deezer | free public API | exact ISRC cross-check, album label/date, broad genre, rank and occasional BPM | ISRC |
| TheAudioDB | free public key (`123`) | broad genre/mood/style, MBID, artwork/video/description and catalog IDs | exact artist/title |
| OneTagger SQL bridge / Discogs | free/open source | release genre/style, label, country, format and year without requiring local audio files | normalized artist/release identity |
| FreqBlog Starter | €39/month, 150k requests | 42+ fields including BPM, key/Camelot, perceptual features, metadata and provider payload | ISRC first, exact artist/title fallback |
| ReccoBeats | free public API | Spotify-style audio features: BPM, key, mode, loudness, energy, danceability, valence, acousticness, instrumentalness, speechiness and liveness | exact Spotify ID, batches of 40 |
| Spotify Tracks 114k public dataset | free/BSD-3-Clause | historical Spotify audio features and track genre for exact catalog overlaps | exact Spotify ID |
| Beat This + local DSP | free/open source | audible beat presence, beatless/steady four-on-the-floor/broken beat, BPM, regularity, syncopation, tempo stability and kick placement | local audio matched by Spotify ID/ISRC/metadata |
| MAEST Discogs400 | free/open model | 400-way specialist genre/style predictions plus reusable audio embeddings | local audio |
| LAION larger-CLAP-music | free/open model | rich zero-shot mood vocabulary and reusable semantic audio embeddings; instrument/voice outputs are retained as candidates | local audio |
| Essentia Discogs-EffNet supervised heads | free/open models | full-track mood/theme, genre, instrument, voice, danceability, production and tonal predictions plus temporal embeddings | local audio |

The active quality-first pass covers every complete track with model-native
windows. It does not use only one 45-second excerpt.

All workers run continuously. FreqBlog is enabled by `FREQBLOG_ENABLED=1` and
its key in `.env`; ReccoBeats requires no key. Provider-specific status tables,
retry timestamps, and local identity caches make every job resumable.

## Quality policy

- ReccoBeats and exact matches from the historical Spotify dataset are the
  primary Spotify-style audio measurements.
- FreqBlog is primary for BPM, key, Camelot, metadata breadth, and long-tail
  coverage. Its perceptual estimates remain available but receive lower field-
  specific weights in similarity scoring.
- Every provider response remains queryable in `audio_features`, `tags`, and
  `track_attributes`; conflicting values are retained instead of overwritten.
- `source_field_policy` determines which source is used for each comparison.

## Evaluated but not selected for the 64k bulk run

- SoundNet/RapidAPI was evaluated but deliberately not purchased or activated.
  ReccoBeats gives a stronger exact-Spotify-ID measurement layer at no added
  cost, while FreqBlog provides the broader fallback.
- Soundcharts aggregates many commercial sources, but its API is sales-led and
  aimed at enterprise analytics rather than a sub-€500 personal catalog run.
- Bridge.audio requires uploading audio assets and commercial credits. Local
  open models now cover the same core use case without per-track fees; it
  remains an optional audit layer for a statistically chosen sample.
- Gracenote/TiVo's public developer portal is for TV, video, and sports; music
  metadata access is commercial/partner-led.
- Music Story offers useful metadata and audio processing, but commercial API
  access is sales-led; its free account is a small evaluation quota.
- OneMusicAPI aggregates MusicBrainz, Discogs, AcoustID and Wikipedia. The same
  open sources are queried directly here with full provenance and no aggregator
  lock-in.
- melod.ie exposes richly tagged tracks from its own production-music catalog;
  it is not an arbitrary Spotify-recording enrichment API.
- AcousticBrainz's live API is no longer dependable. The full historical dump
  is tens of millions of submissions and requires recording identifiers or
  fingerprints; it remains an optional later layer rather than a blind bulk
  download for this Spotify-ID-first catalog.

## Reliability

`com.jakub.local-dj-enrichment` is a macOS LaunchAgent with `RunAtLoad` and
`KeepAlive`. It starts on login/reboot and survives individual worker crashes.
Online workers wait for connectivity; local audio workers continue without the
internet once their models are cached. SQLite uses WAL mode and every worker
checkpoints per track, so completed items are never redone and transient
failures are retried after the connection returns.

Current coverage:

```bash
./.venv/bin/python coverage_report.py
```

Nearest-track search after the audio layer is populated:

```bash
./.venv/bin/python find_similar.py "SPOTIFY_TRACK_URL" --limit 30
```

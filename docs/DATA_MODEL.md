# Data model and trust policy

The database is `/Users/jakub/Appky Claude/spotify-indie-sort/data/music.db`.
SQLite was chosen for portability, local ownership and zero service cost. WAL
mode supports concurrent readers/writers; every connection uses a long busy
timeout because many enrichment workers are active.

## Design principles

1. A track has one canonical Spotify identity, but many observations.
2. Provider disagreement is retained, not overwritten.
3. Every derived value records `source`, `confidence` and usually raw JSON.
4. Fixed provider priority is field-specific; no provider is globally best.
5. Candidate/open-vocabulary labels are separated from canonical labels.
6. Raw full-audio artifacts and temporal matrices are retained so aggregation
   and thresholds can be improved without re-running expensive inference.

## Main entities

### Identity and catalog

- `tracks`: canonical Spotify ID/URI, title, album, artists, ISRC, MBID,
  duration, date, label, popularity, original Spotify genres and library source.
- `stream_events`: deduplicated Spotify history events.
- `track_play_stats` view: event count, qualified plays, total listening time,
  first and last play. A qualified play currently means at least 30 seconds and
  not marked skipped.

Spotify itself does not expose the user's lifetime per-track play count via the
normal Web API. The count comes from imported Extended Streaming History.

### Multi-source observations

- `audio_features`: one row per track/provider for BPM, key, mode,
  time-signature, danceability, energy, valence, acousticness,
  instrumentalness, speechiness, liveness and loudness.
- `tags`: many genre, subgenre, mood, instrument, voice, rhythm and candidate
  tags per track/source.
- `track_attributes`: flexible text/numeric/JSON values such as Camelot,
  beat-section coverage, production style and provider-specific metadata.
- `source_field_policy`: reliability, similarity weight, usage and notes per
  provider/field.

### Local files and acquisition state

- `audio_files`: path, identity match, file metadata and analysis state.
- `audio_verification`: deep FFprobe/file verification and optional checksum.
- `traktor_entries`: parsed NML rows, missing-manifest membership and Spotify
  match.
- `acquisition_queue`: present/locate/verify/needs-source lifecycle. This is an
  inventory queue, not proof that a downloader exists.
- `sync_control`, `sync_runs`: global pause, disk floor and run status.

### Audio intelligence

- `local_audio_analysis`: beat/rhythm aggregate summaries.
- `audio_embeddings`: compressed aggregate vectors by exact model version.
- `audio_temporal_features`: compressed frame/window matrices, dimensions and
  hop size.
- `audio_analysis_artifacts`: compressed complete per-stage result payloads.
- `audio_model_jobs`: resumable older per-file/model job state.

### Spotify exports created by the project

- `spotify_export_playlists`: purpose/part -> playlist ID/URL and item counts.
- `spotify_export_items`: exact track membership for resumable playlist writes.

## Views

### `track_profile`

Chooses one preferred value per common field while retaining all raw rows.
Current priority examples:

- BPM/key: ReccoBeats -> legacy Spotify dataset -> FreqBlog -> OneTagger ->
  AcousticBrainz/Deezer;
- energy: ReccoBeats -> legacy Spotify -> OneTagger -> AcousticBrainz -> other
  measured sources -> FreqBlog -> playlist inference;
- danceability/valence: ReccoBeats -> legacy Spotify -> AcousticBrainz ->
  other measured sources -> FreqBlog -> playlist inference.

It also aggregates canonical genre, mood, instrument and voice tags.

### `dj_track_profile`

Extends `track_profile` with subgenres, beat presence, rhythm pattern and their
best confidence.

### `audio_feature_comparison`

Compares FreqBlog and ReccoBeats for disagreement auditing, including
half/double-tempo-aware BPM delta.

## Full-audio stages

The canonical stage names are:

| Stage | Primary outputs | Trust |
|---|---|---|
| `rhythm_full` | Beat presence, BPM, regularity, syncopation, four-on-floor/broken/mixed timeline | Audio-measured primary |
| `maest_full` | Discogs400 genre/style probabilities and timeline | Specialist supervised candidate/primary with catalog agreement |
| `essentia_full` | EffNet embeddings and 19 supervised mood/genre/instrument/voice/dance heads | Supervised primary, thresholded |
| `clap_full` | Semantic embeddings and open-ended mood/instrument/voice labels | Candidate-only unless independently confirmed |

Each successful stage stores the complete compressed result in
`audio_analysis_artifacts`. Important temporal tensors go to
`audio_temporal_features`; aggregate vectors go to `audio_embeddings`.

## Essentia supervised heads

One shared Discogs-EffNet embedding is reused by:

- MTG-Jamendo mood/theme, genre, instruments and top-50 tags;
- electronic genre taxonomy;
- aggressive, happy, party, relaxed, sad, acoustic and electronic binary heads;
- danceability, approachability and engagement;
- voice/instrumental, voice gender, timbre and tonal/atonal heads.

The import stores mean, p90, section coverage and full temporal predictions.
Binary moods require strong probability and support from the broader Jamendo
head. Acoustic/electronic are production styles, not moods.

## Consensus rules

- CLAP candidate mood + exact Essentia canonical mood -> consensus mood.
- Genre/style is promoted only when MAEST/Essentia and another independent
  source agree, except very strong supervised broad-genre cases.
- MAEST style probabilities that lack catalog agreement remain
  `audio_style_candidate` at conservative confidence.
- CLAP instruments/voices never become canonical from CLAP alone.
- Raw provider tags are never deleted merely because they conflict.

## Similarity model

`find_similar.py` dynamically loads the best field observation according to
`source_field_policy`. Current relative emphasis:

- CLAP embedding 2.60; MAEST embedding 1.55;
- subgenre overlap 2.80; genre 1.80; mood 1.20;
- BPM 1.65; rhythm pattern 1.35; energy 1.30;
- danceability 1.05; beat presence 0.90; valence 0.80;
- instruments 0.80; voice 0.50; harmonic key 0.55.

Tag overlap uses confidence and inverse document frequency, so a niche shared
subgenre matters more than a ubiquitous `electronic` tag. Candidates with
fewer than three comparable signals are not ranked.

## Backup guidance

Do not copy `music.db` alone while WAL writers are active. Use Python/SQLite's
backup API or safely pause workers, checkpoint WAL, copy the DB and then resume.
Never run destructive schema or vacuum operations while the pipeline is live.

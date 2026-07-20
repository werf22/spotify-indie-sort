"""Local DJ music intelligence database.

SQLite keeps the first version portable and dependency-free.  Every enriched
field has a source and confidence so later providers can be added without
overwriting provenance.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "music.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS tracks (
  spotify_id TEXT PRIMARY KEY,
  uri TEXT NOT NULL,
  title TEXT NOT NULL,
  album TEXT,
  album_id TEXT,
  label TEXT,
  duration_ms INTEGER,
  release_date TEXT,
  musicbrainz_id TEXT,
  isrc TEXT,
  spotify_url TEXT,
  popularity INTEGER,
  explicit INTEGER,
  artist_names TEXT NOT NULL,
  artist_ids TEXT NOT NULL,
  genres TEXT NOT NULL,
  library_sources TEXT NOT NULL,
  first_seen_at TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audio_features (
  spotify_id TEXT NOT NULL,
  source TEXT NOT NULL,
  source_id TEXT,
  bpm REAL,
  key TEXT,
  mode TEXT,
  time_signature INTEGER,
  danceability REAL,
  energy REAL,
  valence REAL,
  acousticness REAL,
  instrumentalness REAL,
  speechiness REAL,
  liveness REAL,
  loudness REAL,
  confidence REAL,
  raw_json TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id, source),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE TABLE IF NOT EXISTS tags (
  spotify_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  tag_type TEXT NOT NULL,
  source TEXT NOT NULL,
  confidence REAL,
  PRIMARY KEY (spotify_id, tag, tag_type, source),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE TABLE IF NOT EXISTS track_attributes (
  spotify_id TEXT NOT NULL,
  attribute TEXT NOT NULL,
  source TEXT NOT NULL,
  value_text TEXT,
  value_num REAL,
  value_json TEXT,
  confidence REAL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id, attribute, source),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_track_attributes_name_num
ON track_attributes(attribute, value_num);
CREATE INDEX IF NOT EXISTS idx_tags_type_tag ON tags(tag_type, tag);
CREATE INDEX IF NOT EXISTS idx_audio_features_source_track ON audio_features(source,spotify_id);
CREATE INDEX IF NOT EXISTS idx_tags_track_type ON tags(spotify_id,tag_type,source);
CREATE TABLE IF NOT EXISTS audio_files (
  path TEXT PRIMARY KEY,
  spotify_id TEXT,
  isrc TEXT,
  title TEXT,
  artist_names TEXT,
  album TEXT,
  duration_seconds REAL,
  file_size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  codec TEXT,
  match_method TEXT,
  match_confidence REAL,
  scan_status TEXT NOT NULL DEFAULT 'indexed',
  analysis_status TEXT NOT NULL DEFAULT 'queued',
  analysis_version TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_audio_files_track ON audio_files(spotify_id);
CREATE INDEX IF NOT EXISTS idx_audio_files_analysis ON audio_files(analysis_status,spotify_id);
CREATE INDEX IF NOT EXISTS idx_audio_files_isrc ON audio_files(isrc);
CREATE TABLE IF NOT EXISTS local_audio_analysis (
  spotify_id TEXT NOT NULL,
  path TEXT NOT NULL,
  analyzer TEXT NOT NULL,
  analyzer_version TEXT NOT NULL,
  segment_start REAL,
  segment_duration REAL,
  beat_presence_score REAL,
  beat_confidence REAL,
  rhythm_pattern TEXT,
  rhythm_pattern_confidence REAL,
  four_on_floor_score REAL,
  broken_beat_score REAL,
  syncopation_score REAL,
  rhythm_regularity REAL,
  tempo_stability REAL,
  kick_on_quarter_ratio REAL,
  offbeat_kick_ratio REAL,
  bpm REAL,
  raw_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id,path,analyzer_version),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_local_audio_analysis_track
ON local_audio_analysis(spotify_id,analyzer_version);
CREATE TABLE IF NOT EXISTS audio_embeddings (
  spotify_id TEXT NOT NULL,
  path TEXT NOT NULL,
  model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  dtype TEXT NOT NULL,
  vector BLOB NOT NULL,
  segment_start REAL,
  segment_duration REAL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id,path,model),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE TABLE IF NOT EXISTS audio_temporal_features (
  spotify_id TEXT NOT NULL,
  path TEXT NOT NULL,
  model TEXT NOT NULL,
  feature_set TEXT NOT NULL,
  frames INTEGER NOT NULL,
  dimensions INTEGER NOT NULL,
  hop_seconds REAL,
  dtype TEXT NOT NULL,
  values_blob BLOB NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id,path,model,feature_set),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_audio_temporal_features_track
ON audio_temporal_features(spotify_id,model);
CREATE TABLE IF NOT EXISTS audio_analysis_artifacts (
  spotify_id TEXT NOT NULL,
  path TEXT NOT NULL,
  stage TEXT NOT NULL,
  model TEXT NOT NULL,
  coverage_mode TEXT,
  payload_codec TEXT NOT NULL,
  payload_blob BLOB NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (spotify_id,path,stage,model),
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_audio_analysis_artifacts_track
ON audio_analysis_artifacts(spotify_id,stage);
CREATE TABLE IF NOT EXISTS audio_model_jobs (
  path TEXT NOT NULL,
  model TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (path,model,version)
);
CREATE INDEX IF NOT EXISTS idx_audio_model_jobs_status
ON audio_model_jobs(model,version,status);
CREATE TABLE IF NOT EXISTS source_field_policy (
  source TEXT NOT NULL,
  field TEXT NOT NULL,
  reliability REAL NOT NULL,
  similarity_weight REAL NOT NULL,
  usage TEXT NOT NULL,
  notes TEXT,
  PRIMARY KEY(source,field)
);
CREATE VIEW IF NOT EXISTS track_profile AS
SELECT t.*,
  (SELECT a.bpm FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.bpm IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 3 WHEN 'onetagger' THEN 4 WHEN 'acousticbrainz' THEN 5 WHEN 'deezer' THEN 6 ELSE 9 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS bpm,
  (SELECT a.source FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.bpm IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 3 WHEN 'onetagger' THEN 4 WHEN 'acousticbrainz' THEN 5 WHEN 'deezer' THEN 6 ELSE 9 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS bpm_source,
  (SELECT a.key FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.key IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 3 WHEN 'onetagger' THEN 4 WHEN 'acousticbrainz' THEN 5 ELSE 9 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS musical_key,
  (SELECT a.source FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.key IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 3 WHEN 'onetagger' THEN 4 WHEN 'acousticbrainz' THEN 5 ELSE 9 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS key_source,
  (SELECT a.mode FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.mode IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 3 WHEN 'onetagger' THEN 4 ELSE 9 END LIMIT 1) AS mode,
  (SELECT a.energy FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.energy IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'onetagger' THEN 3
                         WHEN 'acousticbrainz' THEN 4 WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS energy,
  (SELECT a.source FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.energy IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'onetagger' THEN 3
                         WHEN 'acousticbrainz' THEN 4 WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS energy_source,
  (SELECT a.danceability FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.danceability IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 4
                         WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS danceability,
  (SELECT a.source FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.danceability IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 4
                         WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS danceability_source,
  (SELECT a.valence FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.valence IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 4
                         WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS valence,
  (SELECT a.source FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.valence IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 4
                         WHEN 'freqblog' THEN 7 WHEN 'spotify:playlist-inference' THEN 9 ELSE 6 END,
            COALESCE(a.confidence,0) DESC LIMIT 1) AS valence_source,
  (SELECT a.acousticness FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.acousticness IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 3 WHEN 'freqblog' THEN 8 ELSE 6 END LIMIT 1) AS acousticness,
  (SELECT a.instrumentalness FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.instrumentalness IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 3 WHEN 'freqblog' THEN 8 ELSE 6 END LIMIT 1) AS instrumentalness,
  (SELECT a.speechiness FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.speechiness IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 3 WHEN 'freqblog' THEN 8 ELSE 6 END LIMIT 1) AS speechiness,
  (SELECT a.liveness FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.liveness IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'acousticbrainz' THEN 3 WHEN 'freqblog' THEN 8 ELSE 6 END LIMIT 1) AS liveness,
  (SELECT a.loudness FROM audio_features a WHERE a.spotify_id=t.spotify_id AND a.loudness IS NOT NULL
   ORDER BY CASE a.source WHEN 'reccobeats' THEN 1 WHEN 'spotify_legacy_dataset' THEN 2 WHEN 'freqblog' THEN 7 ELSE 6 END LIMIT 1) AS loudness,
  (SELECT group_concat(tag, ' | ') FROM
     (SELECT DISTINCT tag FROM tags x WHERE x.spotify_id=t.spotify_id AND x.tag_type='genre' ORDER BY tag)
  ) AS all_genres,
  (SELECT group_concat(tag, ' | ') FROM
     (SELECT DISTINCT tag FROM tags x WHERE x.spotify_id=t.spotify_id AND x.tag_type='mood' ORDER BY tag)
  ) AS moods,
  (SELECT group_concat(tag, ' | ') FROM
     (SELECT DISTINCT tag FROM tags x WHERE x.spotify_id=t.spotify_id AND x.tag_type='instrument' ORDER BY tag)
  ) AS instruments,
  (SELECT group_concat(tag, ' | ') FROM
     (SELECT DISTINCT tag FROM tags x WHERE x.spotify_id=t.spotify_id AND x.tag_type='voice' ORDER BY tag)
  ) AS voice_tags
FROM tracks t;
CREATE VIEW IF NOT EXISTS dj_track_profile AS
SELECT p.*,
  (SELECT group_concat(tag, ' | ') FROM
     (SELECT DISTINCT tag FROM tags x WHERE x.spotify_id=p.spotify_id AND x.tag_type='subgenre' ORDER BY tag)
  ) AS subgenres,
  (SELECT value_text FROM track_attributes x
     WHERE x.spotify_id=p.spotify_id AND x.attribute='beat_presence'
     ORDER BY COALESCE(confidence,0) DESC LIMIT 1) AS beat_presence,
  (SELECT confidence FROM track_attributes x
     WHERE x.spotify_id=p.spotify_id AND x.attribute='beat_presence'
     ORDER BY COALESCE(confidence,0) DESC LIMIT 1) AS beat_presence_confidence,
  (SELECT value_text FROM track_attributes x
     WHERE x.spotify_id=p.spotify_id AND x.attribute='rhythm_pattern'
     ORDER BY COALESCE(confidence,0) DESC LIMIT 1) AS rhythm_pattern,
  (SELECT confidence FROM track_attributes x
     WHERE x.spotify_id=p.spotify_id AND x.attribute='rhythm_pattern'
     ORDER BY COALESCE(confidence,0) DESC LIMIT 1) AS rhythm_pattern_confidence
FROM track_profile p;
CREATE VIEW IF NOT EXISTS audio_feature_comparison AS
SELECT f.spotify_id,
       f.bpm AS freqblog_bpm, r.bpm AS reccobeats_bpm,
       min(abs(f.bpm-r.bpm),abs(f.bpm*2-r.bpm),abs(f.bpm-r.bpm*2)) AS bpm_delta,
       f.key AS freqblog_key,r.key AS reccobeats_key,
       CASE WHEN lower(f.key)=lower(r.key) THEN 1 ELSE 0 END AS key_agrees,
       f.energy AS freqblog_energy,r.energy AS reccobeats_energy,abs(f.energy-r.energy) AS energy_delta,
       f.danceability AS freqblog_danceability,r.danceability AS reccobeats_danceability,
       abs(f.danceability-r.danceability) AS danceability_delta,
       f.valence AS freqblog_valence,r.valence AS reccobeats_valence,abs(f.valence-r.valence) AS valence_delta,
       CASE WHEN min(abs(f.bpm-r.bpm),abs(f.bpm*2-r.bpm),abs(f.bpm-r.bpm*2))>5
                  OR (f.key IS NOT NULL AND r.key IS NOT NULL AND lower(f.key)<>lower(r.key))
                  OR abs(f.energy-r.energy)>0.25 THEN 1 ELSE 0 END AS needs_review
FROM audio_features f JOIN audio_features r USING(spotify_id)
WHERE f.source='freqblog' AND r.source='reccobeats';
CREATE TABLE IF NOT EXISTS stream_events (
  id INTEGER PRIMARY KEY,
  event_hash TEXT UNIQUE,
  played_at TEXT NOT NULL,
  spotify_id TEXT,
  title TEXT,
  artist_names TEXT,
  ms_played INTEGER,
  skipped INTEGER,
  offline INTEGER,
  shuffle INTEGER,
  platform TEXT,
  raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_stream_events_track ON stream_events(spotify_id);
CREATE VIEW IF NOT EXISTS track_play_stats AS
SELECT spotify_id,
       COUNT(*) AS event_count,
       SUM(CASE WHEN COALESCE(ms_played,0) >= 30000 AND COALESCE(skipped,0)=0 THEN 1 ELSE 0 END) AS qualified_plays,
       SUM(COALESCE(ms_played,0)) AS total_ms_played,
       MIN(played_at) AS first_played_at,
       MAX(played_at) AS last_played_at
FROM stream_events WHERE spotify_id IS NOT NULL GROUP BY spotify_id;
CREATE TABLE IF NOT EXISTS source_runs (
  source TEXT PRIMARY KEY,
  imported_at TEXT NOT NULL,
  item_count INTEGER NOT NULL,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS traktor_entries (
  entry_id TEXT PRIMARY KEY,
  source_nml TEXT NOT NULL,
  path TEXT NOT NULL,
  title TEXT,
  artist_names TEXT,
  album TEXT,
  duration_seconds REAL,
  bitrate INTEGER,
  missing_manifest INTEGER NOT NULL DEFAULT 0,
  path_exists INTEGER NOT NULL DEFAULT 0,
  resolved_path TEXT,
  spotify_id TEXT,
  match_method TEXT,
  match_confidence REAL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_traktor_entries_track ON traktor_entries(spotify_id);
CREATE INDEX IF NOT EXISTS idx_traktor_entries_missing ON traktor_entries(missing_manifest,path_exists);
CREATE TABLE IF NOT EXISTS audio_verification (
  path TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  duration_seconds REAL,
  codec TEXT,
  bitrate INTEGER,
  sample_rate INTEGER,
  channels INTEGER,
  file_size INTEGER,
  mtime_ns INTEGER,
  sha256 TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audio_verification_status ON audio_verification(status);
CREATE TABLE IF NOT EXISTS acquisition_queue (
  spotify_id TEXT PRIMARY KEY,
  local_state TEXT NOT NULL,
  acquisition_state TEXT NOT NULL,
  reason TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 100,
  preferred_provider TEXT,
  provider_item_id TEXT,
  provider_url TEXT,
  target_path TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT,
  last_error TEXT,
  verified_path TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (spotify_id) REFERENCES tracks(spotify_id)
);
CREATE INDEX IF NOT EXISTS idx_acquisition_queue_state
ON acquisition_queue(acquisition_state,priority,next_retry_at);
CREATE TABLE IF NOT EXISTS sync_control (
  id INTEGER PRIMARY KEY CHECK(id=1),
  paused INTEGER NOT NULL DEFAULT 0,
  pause_reason TEXT,
  min_free_gib REAL NOT NULL DEFAULT 50.0,
  output_root TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  phase TEXT NOT NULL,
  status TEXT NOT NULL,
  processed INTEGER NOT NULL DEFAULT 0,
  succeeded INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS spotify_export_playlists (
  purpose TEXT NOT NULL,
  part INTEGER NOT NULL,
  playlist_id TEXT NOT NULL,
  playlist_url TEXT,
  name TEXT NOT NULL,
  expected_items INTEGER NOT NULL,
  added_items INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (purpose,part)
);
CREATE TABLE IF NOT EXISTS spotify_export_items (
  purpose TEXT NOT NULL,
  spotify_id TEXT NOT NULL,
  playlist_id TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY (purpose,spotify_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS track_search USING fts5(
  spotify_id UNINDEXED, title, artist_names, album, genres, library_sources,
  content='tracks', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
  INSERT INTO track_search(rowid, spotify_id, title, artist_names, album, genres, library_sources)
  VALUES (new.rowid, new.spotify_id, new.title, new.artist_names, new.album, new.genres, new.library_sources);
END;
CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
  INSERT INTO track_search(track_search, rowid, spotify_id, title, artist_names, album, genres, library_sources)
  VALUES ('delete', old.rowid, old.spotify_id, old.title, old.artist_names, old.album, old.genres, old.library_sources);
  INSERT INTO track_search(rowid, spotify_id, title, artist_names, album, genres, library_sources)
  VALUES (new.rowid, new.spotify_id, new.title, new.artist_names, new.album, new.genres, new.library_sources);
END;
"""


def connect_readonly(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the database strictly read-only for status/monitoring queries.

    WHAT/WHY: the full ``connect()`` below always runs schema DDL, which takes a
    write lock. Monitoring loops (orchestrator counters, status dashboards) were
    colliding with long importer transactions and dying with "database is
    locked". Read-only mode never competes for the write lock.
    HOW TO TWEAK: busy_timeout is how long a reader waits (ms) when WAL
    checkpointing briefly blocks readers; 30s is generous.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=90)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=90000")
    # One-time view migration: older databases ranked FreqBlog/SoundNet first.
    # Recreate only when needed so concurrent workers do not churn the schema.
    profile = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name='track_profile'"
    ).fetchone()
    comparison = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name='audio_feature_comparison'"
    ).fetchone()
    if profile and "reccobeats" not in (profile[0] or "").lower():
        conn.execute("DROP VIEW IF EXISTS track_profile")
    if comparison and "reccobeats" not in (comparison[0] or "").lower():
        conn.execute("DROP VIEW IF EXISTS audio_feature_comparison")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(stream_events)")}
    if "event_hash" not in cols:
        conn.execute("ALTER TABLE stream_events ADD COLUMN event_hash TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stream_events_hash ON stream_events(event_hash)")
    track_cols = {r[1] for r in conn.execute("PRAGMA table_info(tracks)")}
    if "musicbrainz_id" not in track_cols:
        conn.execute("ALTER TABLE tracks ADD COLUMN musicbrainz_id TEXT")
    if "album_id" not in track_cols:
        conn.execute("ALTER TABLE tracks ADD COLUMN album_id TEXT")
    if "label" not in track_cols:
        conn.execute("ALTER TABLE tracks ADD COLUMN label TEXT")
    conn.execute(
        """INSERT OR IGNORE INTO sync_control
           (id,paused,pause_reason,min_free_gib,output_root,updated_at)
           VALUES(1,0,NULL,50.0,?,datetime('now'))""",
        (str(Path.home() / "Music" / "Spotify Library Sync"),),
    )
    policies = [
        ("freqblog", "bpm", 0.90, 1.00, "primary", "Essentia tempo; handle half/double time"),
        ("freqblog", "key", 0.88, 0.85, "primary", "Essentia key plus Camelot/Open Key"),
        ("freqblog", "loudness", 0.62, 0.45, "relative", "30-second dBFS; compare relatively"),
        ("freqblog", "energy", 0.45, 0.38, "relative", "RMS-derived; useful mainly within genre"),
        ("freqblog", "danceability", 0.35, 0.28, "relative", "Heuristic with elevated distribution"),
        ("freqblog", "valence", 0.12, 0.08, "weak", "DSP proxy; not semantic happiness"),
        ("freqblog", "acousticness", 0.08, 0.03, "avoid", "Tonal/noise proxy; saturates near one"),
        ("freqblog", "instrumentalness", 0.08, 0.04, "avoid", "MFCC-shape proxy, not vocal classifier"),
        ("freqblog", "speechiness", 0.12, 0.05, "weak", "Shifted scale; only coarse ranking"),
        ("freqblog", "liveness", 0.04, 0.01, "avoid", "Saturated for compressed masters"),
        ("onetagger", "bpm", 0.82, 0.85, "primary", "Provider-dependent consensus"),
        ("onetagger", "key", 0.78, 0.72, "primary", "Provider-dependent consensus"),
        ("onetagger", "energy", 0.55, 0.48, "relative", "Normalize source scale before use"),
        ("acousticbrainz", "bpm", 0.78, 0.75, "primary", "Historical Essentia analysis"),
        ("acousticbrainz", "key", 0.72, 0.65, "primary", "Historical Essentia analysis"),
        ("acousticbrainz", "energy", 0.65, 0.58, "relative", "Historical low-level analysis"),
        ("acousticbrainz", "danceability", 0.58, 0.50, "relative", "Historical classifier"),
        ("spotify_legacy_dataset", "bpm", 0.97, 1.00, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "key", 0.95, 0.96, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "loudness", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "energy", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "danceability", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "valence", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "acousticness", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "instrumentalness", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "speechiness", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("spotify_legacy_dataset", "liveness", 0.97, 0.95, "primary", "Exact Spotify ID; historical Spotify API"),
        ("reccobeats", "bpm", 0.98, 1.00, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "key", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "loudness", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "energy", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "danceability", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "valence", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "acousticness", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "instrumentalness", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "speechiness", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("reccobeats", "liveness", 0.98, 0.98, "primary", "Exact Spotify ID mapping; Spotify-style feature"),
        ("spotify:playlist-inference", "energy", 0.20, 0.15, "fallback", "Inferred from playlist context"),
        ("spotify:playlist-inference", "danceability", 0.20, 0.15, "fallback", "Inferred from playlist context"),
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO source_field_policy
           (source,field,reliability,similarity_weight,usage,notes)
           VALUES(?,?,?,?,?,?)""",
        policies,
    )
    conn.commit()
    return conn

def record_source_run(conn: sqlite3.Connection, source: str, imported_at: str, item_count: int, notes: str) -> None:
    for attempt in range(12):
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO source_runs VALUES (?,?,?,?)", (source, imported_at, item_count, notes))
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or attempt == 11:
                raise
            time.sleep(min(2 ** attempt, 30))

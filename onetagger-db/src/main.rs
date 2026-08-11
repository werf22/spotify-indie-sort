use anyhow::{Context, Result};
use clap::Parser;
use onetagger_platforms::{
    bandcamp::BandcampBuilder,
    beatport::BeatportBuilder,
    itunes::ITunesBuilder,
    junodownload::JunoDownloadBuilder,
    musicbrainz::MusicBrainz,
    traxsource::TraxsourceBuilder,
};
use onetagger_tag::AudioFileFormat;
use onetagger_tagger::{
    AudioFileInfo, AutotaggerSource, AutotaggerSourceBuilder, FileTaggedStatus, TaggerConfig,
};
use rusqlite::{params, Connection};
use std::time::Duration;
use std::{collections::HashMap, path::PathBuf};

#[derive(Parser, Debug)]
struct Args {
    #[arg(long, default_value = "data/music.db")]
    db: PathBuf,
    #[arg(long, default_value = "musicbrainz")]
    source: String,
    #[arg(long, default_value_t = 100)]
    limit: usize,
}

fn main() -> Result<()> {
    env_logger::init();
    let a = Args::parse();
    let mut db = Connection::open(&a.db).context("opening music.db")?;
    // The daemon, orchestrator and shard importer all write to this SQLite file;
    // without a busy timeout a batch aborts with "database is locked" and leaves
    // its current track stranded in 'processing'.
    db.busy_timeout(std::time::Duration::from_secs(30))?;
    db.execute_batch("CREATE TABLE IF NOT EXISTS onetagger_enrichment_status(spotify_id TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(spotify_id,source)); CREATE INDEX IF NOT EXISTS idx_ot_status ON onetagger_enrichment_status(source,status);")?;
    let mut cfg = TaggerConfig::default();
    let mut platform: Box<dyn AutotaggerSource> = match a.source.as_str() {
        "musicbrainz" => Box::new(MusicBrainz::new()),
        "beatport" => {
            let mut b = BeatportBuilder::new();
            cfg.custom.0.insert(
                "beatport".to_string(),
                b.info().custom_options.get_defaults(),
            );
            b.get_source(&cfg)?
        }
        "traxsource" => {
            let mut b = TraxsourceBuilder::new();
            b.get_source(&cfg)?
        }
        "junodownload" => {
            let mut b = JunoDownloadBuilder::new();
            b.get_source(&cfg)?
        }
        "bandcamp" => {
            let mut b = BandcampBuilder::new();
            cfg.custom.0.insert(
                "bandcamp".to_string(),
                b.info().custom_options.get_defaults(),
            );
            b.get_source(&cfg)?
        }
        "itunes" => {
            let mut b = ITunesBuilder::new();
            cfg.custom.0.insert(
                "itunes".to_string(),
                b.info().custom_options.get_defaults(),
            );
            b.get_source(&cfg)?
        }
        x => anyhow::bail!("unsupported source: {x}"),
    };
    let rows = {
        // Also reclaim rows abandoned in 'processing': a run that dies between
        // marking a track and resolving it used to orphan that track forever,
        // because this selector only ever looked at missing-or-failed rows.
        // 603 bandcamp tracks sat unreachable from 2026-07-18 that way, and the
        // lane reported "ok=0, failed=0" every cycle as if it had finished.
        // HOW TO TWEAK: '-1 hour' is the age at which a processing row is
        // considered abandoned; keep it well above the slowest single lookup.
        let mut s=db.prepare("SELECT t.spotify_id,t.title,t.artist_names,t.isrc,t.duration_ms FROM tracks t LEFT JOIN onetagger_enrichment_status s ON s.spotify_id=t.spotify_id AND s.source=?1 WHERE s.spotify_id IS NULL OR (s.status='failed' AND s.attempts<3) OR (s.status='processing' AND s.updated_at < datetime('now','-1 hour')) ORDER BY t.spotify_id LIMIT ?2")?;
        let mapped = s.query_map(params![&a.source, a.limit as i64], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, Option<String>>(3)?,
                r.get::<_, Option<i64>>(4)?,
            ))
        })?;
        mapped.collect::<rusqlite::Result<Vec<_>>>()?
    };
    let mut ok = 0;
    let mut failed = 0;
    for (id, title, artists, isrc, dur) in rows {
        db.execute("INSERT INTO onetagger_enrichment_status(spotify_id,source,status,attempts,updated_at) VALUES(?1,?2,'processing',1,CURRENT_TIMESTAMP) ON CONFLICT(spotify_id,source) DO UPDATE SET status='processing',attempts=attempts+1,updated_at=CURRENT_TIMESTAMP",params![id,a.source])?;
        let mut ft = HashMap::new();
        if let Some(x) = isrc.clone() {
            ft.insert("ISRC".to_string(), vec![x]);
        }
        let info = AudioFileInfo {
            title: Some(title),
            artists: artists
                .split(',')
                .map(|x| x.trim().to_string())
                .filter(|x| !x.is_empty())
                .collect(),
            format: AudioFileFormat::MP4,
            path: PathBuf::from(format!("spotify-db://{id}")),
            isrc,
            duration: dur.map(|x| Duration::from_millis(x as u64)),
            track_number: None,
            tagged: FileTaggedStatus::Untagged,
            tags: ft,
        };
        match platform.match_track(&info, &cfg).and_then(|mut ms| {
            let mut m = ms.drain(..).next().context("no match")?;
            platform.extend_track(&mut m.track, &cfg)?;
            Ok(m)
        }) {
            Ok(m) => {
                persist(&mut db, &id, &a.source, &m.track, m.accuracy)?;
                ok += 1;
            }
            Err(e) => {
                let message = e.to_string();
                let status = if message.to_lowercase().contains("no match") {
                    "no_match"
                } else {
                    "failed"
                };
                db.execute("UPDATE onetagger_enrichment_status SET status=?3,last_error=?4,updated_at=CURRENT_TIMESTAMP WHERE spotify_id=?1 AND source=?2",params![id,a.source,status,message])?;
                failed += 1;
            }
        }
    }
    println!("OneTagger DB {}: ok={}, failed={}", a.source, ok, failed);
    Ok(())
}
fn persist(
    db: &mut Connection,
    id: &str,
    source: &str,
    t: &onetagger_tagger::Track,
    accuracy: f64,
) -> Result<()> {
    // BEGIN IMMEDIATE, not the default deferred transaction. A deferred tx
    // takes a read lock first and then tries to upgrade to write; if any other
    // process wrote in between, SQLite returns BUSY_SNAPSHOT *immediately* and
    // busy_timeout does not retry it. With four writers on this database that
    // aborted almost every batch after one track, leaving it in 'processing'.
    let tx = db.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let raw = serde_json::to_string(t)?;
    tx.execute("UPDATE tracks SET album=COALESCE(?1,album),release_date=COALESCE(?2,release_date),isrc=COALESCE(?3,isrc),updated_at=CURRENT_TIMESTAMP WHERE spotify_id=?4",params![t.album,t.release_date.map(|x|x.to_string()),t.isrc,id])?;
    if t.bpm.is_some() || t.key.is_some() {
        tx.execute("INSERT OR REPLACE INTO audio_features(spotify_id,source,source_id,bpm,key,raw_json,confidence,updated_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",params![id,format!("onetagger:{source}"),t.track_id,t.bpm.map(|x|x as f64),t.key,raw,accuracy])?;
    }
    for (kind, vals) in [("genre", &t.genres), ("style", &t.styles)] {
        for v in vals {
            tx.execute("INSERT OR IGNORE INTO tags(spotify_id,tag,tag_type,source,confidence) VALUES(?,?,?,?,?)",params![id,v.to_lowercase(),kind,format!("onetagger:{source}"),accuracy])?;
        }
    }
    if let Some(m) = &t.mood {
        tx.execute(
            "INSERT OR IGNORE INTO tags VALUES(?,?,?,?,?)",
            params![
                id,
                m.to_lowercase(),
                "mood",
                format!("onetagger:{source}"),
                accuracy
            ],
        )?;
    }
    tx.execute("INSERT INTO onetagger_enrichment_status(spotify_id,source,status,attempts,updated_at) VALUES(?1,?2,'success',1,CURRENT_TIMESTAMP) ON CONFLICT(spotify_id,source) DO UPDATE SET status='success',last_error=NULL,updated_at=CURRENT_TIMESTAMP",params![id,source])?;
    tx.commit()?;
    Ok(())
}

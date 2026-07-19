# Lokálna DJ databáza

> Aktuálny cold-start handoff a prevádzkový stav sú v
> [HANDOFF.md](HANDOFF.md) a [docs/README.md](docs/README.md). Starší
> sekvenčný audio pipeline nižšie ostáva podporovaný, ale hlavný quality-first
> beh dnes používa plné tracky, lokálnu Essentiu/Beat This a bounded RunPod
> MAEST/CLAP shardy.

Databáza používa SQLite a je pripravená pre celú Spotify knižnicu. Prvý import:

```bash
./.venv/bin/python build_music_db.py
./.venv/bin/python query_music.py "indie folk"
```

Po doručení Spotify Extended Streaming History ZIP:

```bash
./.venv/bin/python import_streaming_history.py ~/Downloads/spotify-data.zip
```

Pre každý track držíme samostatnú provenienciu: Spotify identitu, žánre a zdroje knižnice, audio features, tagy a stream events. Prehrávania sa deduplikujú hashom; view `track_play_stats` poskytuje kvalifikované prehratia, celkový čas a prvé/posledné prehratie.

## Plán enrichmentu

1. Spotify export + Extended History: identita, playlisty, saved tracks a reálne počúvanie.
2. MusicBrainz: ISRC, recording/release/artist IDs, label, dátumy a lokálne tagy. Core dáta sú CC0; API má limit 1 request/s.
3. ReccoBeats: presný Spotify-ID batch po 40 skladbách. Je to hlavný cloudový zdroj Spotify-style BPM, key, mode, energy, danceability, valence, acousticness, instrumentalness, speechiness, liveness a loudness.
4. Verejný historický Spotify dataset: presné Spotify-ID prieniky pridávajú pôvodné legacy audio-features bez fuzzy matchingu.
5. AcousticBrainz: bezplatný doplnok audio-deskriptorov z MusicBrainz recording ID; dataset je historický, preto sa používa ako fallback.
6. FreqBlog: cloudový enrichment cez ISRC + názov + interpreta. Dopĺňa BPM, key/Camelot/Open Key, perceptual features, genre, mood a desiatky metadát. Starter plán má 150k requestov mesačne; lokálna identity cache a dvojfázové polling stavy obmedzujú opakované platené dotazy.
7. Full-track audio analýza je aktívna. `Beat This` + DSP rozlišujú počuteľný beat,
   beatless hudbu, pravidelný four-on-the-floor a broken beat. MAEST (Discogs400)
   dopĺňa žánre/subžánre a CLAP bohaté mood tagy plus kandidátov nástrojov a
   hlasov. Essentia a rytmus bežia lokálne; MAEST a CLAP v checksumovaných,
   resumable RunPod shardoch. Všetky modely pokrývajú celý track cez natívne
   časové okná a ukladajú aj temporal profile, nie iba jeden priemer.

## Lokálne audio

Jednorazová inštalácia a manuálny cyklus:

```bash
./install_audio_enrichment.sh
./.audio-venv/bin/python run_local_audio_pipeline.py
```

Predvolene sa skenujú `~/Music` a `~/Downloads`. Indexer najskôr používa
Spotify ID v názve súboru a ISRC v tagoch, potom konzervatívne porovná názov,
interpreta a dĺžku. Každý výsledok sa uloží po jednej skladbe; prerušenie siete,
uspatie ani reštart počítača nestratia hotovú prácu. LaunchAgent následne
pokračuje automaticky.

Stav lokálneho spracovania:

```bash
./.venv/bin/python audio_enrichment_status.py
```

## OneTagger database mode

The source fork in `vendor/onetagger` contains a new `onetagger-db` crate. It feeds OneTagger's MusicBrainz/Beatport matching pipeline with database rows through synthetic `spotify-db://...` identities and persists matches into SQLite, without creating audio files. The Python `onetagger_db_bridge.py` is the immediate resilient fallback for Discogs while the Rust binary is compiled.

Každý atribút má `source`, `confidence`, `updated_at` a raw payload, aby sa dali výsledky porovnávať a opravovať bez straty pôvodu. Tabuľka `source_field_policy` určuje spoľahlivosť osobitne pre každé pole; napríklad FreqBlog BPM/key majú vysokú váhu, ale jeho perceptual odhady neprebijú presný ReccoBeats profil.

Aktuálne zdroje, dôvody výberu a prevádzkový plán sú v `DATA_SOURCES.md`.
Jednotný SQL view `track_profile` skladá pre každý atribút najlepší dostupný
zdroj; `coverage_report.py` meria pokrytie a `find_similar.py` vyhľadáva
najbližšie tracky pre DJ set podľa audio vlastností, tagov, nálady, BPM, key,
rytmu a lokálnych CLAP/MAEST audio embeddingov.

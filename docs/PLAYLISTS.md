# Spotify playlists and playlist tooling

Playlist facts below were verified through persisted local state and, where
noted, a read-only Spotify API lookup on 2026-07-18.

## Created and verified

| Playlist | Tracks | Purpose | URL |
|---|---:|---|---|
| Indie Sort | 1,805 | Narrow Indie/adjacent music, excluding afro/organic/shamanic/ecstatic functional dance material | [Spotify](https://open.spotify.com/playlist/7pufsPzBuGoxOZnAn3A4pM) |
| Indie Sort – Obľúbené skladby | 500 | Same taste boundary, only from Liked Songs | [Spotify](https://open.spotify.com/playlist/2o80p5DW9YMMMqorQiFuYG) |
| Local Library Blindspots 01/04 | 8,000 | Spotify-only tracks absent from local/Traktor/Missing Tracks scope | [Spotify](https://open.spotify.com/playlist/0bTKh3ds3WktMM4kCRintp) |
| Local Library Blindspots 02/04 | 8,000 | Continuation | [Spotify](https://open.spotify.com/playlist/59cXG4ZD8PUyBkLtbElWUY) |
| Local Library Blindspots 03/04 | 8,000 | Continuation | [Spotify](https://open.spotify.com/playlist/4PjDJsHt9LWVRnynLMn44m) |
| Local Library Blindspots 04/04 | 2,142 | Continuation | [Spotify](https://open.spotify.com/playlist/0NSuCyIWEvbmpUtS52YQnE) |

The Spotify lookup reported these playlists as public at verification time,
even though the original Indie script requested `public=False`. Spotify/user
settings may have changed after creation; do not assume privacy from source code.

## Blindspot selection rule

`build_blindspot_playlists.py` selects tracks whose acquisition reason is
`spotify_only` and state is `needs_source`, then excludes:

- anything represented in the pre-existing Missing Tracks Spotify map;
- anything matching any Traktor entry;
- duplicate recordings/URIs;
- anything already exported for the same purpose.

Membership and playlist IDs are persisted in `spotify_export_playlists` and
`spotify_export_items`, making writes resumable.

## Implemented but not durably verified

### Made of Gold — Sensual 200

`build_sensual_playlist.py` ranks 200 tracks around seed
`5mPD9BQWOOglxSOV9S9htW` using sensual/related playlist context, audio features,
tags, artist diversity and duplicate-recording prevention. No local playlist ID
or URL was found. Query Spotify before claiming it exists; if absent, rerun only
after reviewing the current DB and avoiding duplicate creation.

### September 2024–January 2026 “return to depth” playlist

Requested from the user's second-brain repository and listening history to
reconnect with a period of spiritual/poetic depth. No verifiable result exists
in this repository. A future implementation should combine:

- tracks played/saved/playlist-added during the target period;
- second-brain themes and dated notes;
- mood/semantic embeddings and lyrics-safe metadata where available;
- manual narrative arc rather than merely top play count.

## Original classification artifacts

- `data/library_export.json`: 63,213 deduplicated classified source tracks.
- `data/classification.json`: final keep/exclude decisions.
- `data/state.json`: Indie Sort playlist ID and added IDs.
- `data/run_log.json`: final count and URL.
- `genre_line.py`: positive references and negative boundary.

The original `Indie Sort` request must not be reinterpreted as “everything that
is not ecstatic dance.” The user explicitly rejected that broad 43k result.

## Safe playlist-writing rules

- Search persisted state and Spotify before creating a new playlist.
- Record playlist ID, purpose, expected and actual count.
- Add in Spotify-safe batches and back off on 429.
- Deduplicate exact URI and same recording/version where appropriate.
- Do not delete or replace user playlists unless explicitly requested.
- Separate technical/acquisition playlists from taste evidence.

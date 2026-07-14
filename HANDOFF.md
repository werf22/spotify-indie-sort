# HANDOFF

## Snapshot (2026-07-14, ~10:15, mid-morning update)

**Blocked on a Spotify rate-limit ban until ~14:57 Bratislava time today.**
Root cause: the overnight duplicate-process bug (see below) hammered the
Spotify API hard enough that it returned `429` with `Retry-After: 17421`
(4.8 hours) on a plain `GET /me/playlists` call — confirmed via a direct
curl test with verbose output, not a guess. This isn't normal throttling,
it's an extended ban on the app/token used by `dj-set-spotify` /
`spotify-tidal-sync` / this project (they share one Client ID).

What I did about it:
- Confirmed via `ps aux` that no process is currently running or sleeping
  against the API (nothing will silently retry and extend the ban).
- Fixed `spotify_client.py` to fail loudly instead of sleeping through long
  `Retry-After` values (`MAX_AUTO_RETRY_WAIT_SECONDS = 120` — beyond that it
  raises immediately with the exact clear time, instead of blocking silently
  for hours like it just did twice).
- **DO NOT run `export.py`, `classify.py`, `build_playlist.py`, or anything
  else that hits `api.spotify.com` / `accounts.spotify.com` before
  ~14:57 Bratislava time (2026-07-14).** Re-check with a plain curl first
  (see README or just retry `GET /v1/me` with a fresh token) before running
  the real pipeline again, in case the ban extended further somehow.

## Snapshot (2026-07-14, ~00:50, overnight autonomous run)

Owner said: don't ask anything more tonight, work autonomously, want the
whole "Indie Sort" playlist done by morning. This file is the entry point if
this session dies and a fresh one needs to pick up cold.

## State of the world

- Spotify MCP server (`../spotify-mcp-server`) built, registered with Claude
  Code at user scope (`claude mcp add spotify -s user`), OAuth completed —
  real access+refresh tokens sitting in `../spotify-mcp-server/spotify-config.json`.
  Won't show up as live tools in *this* session (Claude Code needs a restart
  to pick up newly-registered MCP servers) but will work from the next
  session onward, and works fine.
- This project (`spotify-indie-sort`) scaffolded: `.env`/token seeded
  (credentials copied from `dj-set-spotify`, refresh token copied from the
  MCP server's auth, both value-blind — never displayed in chat).
  `spotify_client.py`, `export.py`, `classify.py`, `build_playlist.py`,
  `run.sh`, `genre_line.py` (the taste calibration, see there for the actual
  keep/exclude boundary + the 8 reference tracks) all written.
- Real library scale, confirmed via API: **1,305 owned playlists**, 2,853
  Liked Songs.
- **Found and stopped a problem before it burned an hour on garbage data:**
  a chunk of those 1,305 playlists are NOT taste playlists — they're
  leftovers from the unrelated Traktor-to-Spotify matching project from
  2026-07-09 (see `missing_tracks_traktor_2026-07-09.csv` in the parent
  dir). One single playlist, "Traktor missing tracks 2026-07-09 (part 2)",
  has **9,500 tracks** in it. Pulling those into the taste sort would be
  wrong (they're not curated listening choices, they're a technical
  matching artifact) and would have ~doubled the runtime for no reason.
  First export.py run was killed after playlist 56/1305 for this reason.

## DO-THIS-NOW (next action)

1. A cheap name-only scan of all 1,305 owned playlists is running/just
   finished — check `data/_owned_playlists_raw.json` and the scan output.
2. Add a name-pattern exclusion list to `export.py` (skip playlists matching
   utility patterns — "missing track" confirmed so far, check the scan for
   others) before running the real export. Log what got excluded and why —
   don't silently drop things.
3. Run `export.py` for real (background, will take a while — ~1,300
   playlists to page through even after excluding junk).
4. Classify: **no `ANTHROPIC_API_KEY` is available in this environment**, so
   `classify.py` (which calls the Anthropic API directly) can't run
   standalone tonight. Instead, do the classification live in-session using
   Agent subagents, batching ~150-250 tracks per agent call, each given
   `genre_line.py`'s boundary + the 8 reference tracks + its batch of
   {id, name, artists, genres}. Merge all results into
   `data/classification.json` in the exact shape `classify.py` would have
   produced ([{id, decision, reason}]), so `build_playlist.py` doesn't care
   which path produced it.
5. Run `build_playlist.py` for real (owner explicitly said don't wait for
   review — write directly). Target playlist name: "Indie Sort" (owner never
   gave a name; picked this as a clear, obvious, trivially-renameable
   default since they said not to ask).
6. Update this file + `DONE.md`-equivalent (just log in this file for now,
   single-project scope) with final counts and the playlist URL.

## Decisions made without asking (owner said not to ask tonight)

- Playlist name: **"Indie Sort"**, private, description explaining what it is.
- Excluding Traktor-matching utility playlists from the source scope (not
  "your music library" in any real sense) — see above.
- Batch-classification failures default to **keep**, not exclude (a wrongly
  included track is a 2-second manual removal; a wrongly excluded track is
  invisible and never gets noticed).
- Classification done live via Agent subagents tonight (no API key
  available for the standalone script path); `classify.py` is still fully
  written and works whenever `ANTHROPIC_API_KEY` gets added to `.env` for
  future unattended re-runs via `./run.sh`.

## If this session dies before finishing

Check `data/library_export.json`, `data/classification.json`,
`data/state.json`, `data/run_log.json` for how far it got — each pipeline
step's output persists to disk, so resume from whichever file is missing
rather than restarting from scratch.

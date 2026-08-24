# DONE — <project-name>

<!-- Append-only completion log. NEVER edit or delete past entries — newest entry on top.
     One entry per completed task, written at the moment the task's box gets checked in
     the task file. "Verified by" must name real external signal (test run, manual flow,
     log output) — "looked correct" does not count (core §2 VERIFIER). -->

## <YYYY-MM-DD> — <task-id>

- **What changed:** <one or two lines, user-visible outcome first>
- **Files touched:** <paths, comma-separated>
- **Verified by:** <e.g. test suite green (<n> tests) + manual run of <user flow> + <log/screenshot evidence>>

## 2026-08-24 — D-071: similarity app UI (panels, presets, profiles) + analysis funding check

**Changed**
- `music_app/similar.js` — the three panels open on load, fold independently and
  remember what was folded. They were an accordion that started closed, so the
  owner saw nothing until they clicked. Spotify embed fallback restored.
- `music_app/similar_panels.js` — system presets unpinnable and restorable;
  pinned user profiles render as chips on the same bar; profiles render as a
  real treeview (folders split on `/`, expand/collapse persisted).
- `music_app/similar.html` — `#pins` row, chip wrapper, treeview CSS.
- `runpod_pilot.py` — SSH wait 180 → 330 s. `analyze_now.py` — 3 pod attempts.
- `HANDOFF.md` — rewritten around the funding constraint.

**Verified** (browser, real data): presets 5 → 4 on unpin, restore → 5; one
pinned profile chip; folder collapses; 77 compare + 75 shift signals visible on
load; no horizontal overflow; a Spotify-only track played through the
fresh-preview proxy.

**Measured** RunPod: 54,666 / 66,833 done, $75.25 over 344 pod-hours →
$0.00138/track. $5.89 left covers ~4,276 of the 12,167 remaining (~35 %).
One pod live at $0.17/h, no orphans.


## 2026-08-24 — D-072 · the similarity app became a native macOS application

**Why.** The owner pointed out that building it as a localhost web app was
pointless and was exactly what broke drag-and-drop into Traktor. He was right:
the browser sandbox forbids handing a filesystem path to another application.

**Changed**
- `native/SimilarTracksApp.swift`, `native/build.sh` — new AppKit app hosting
  the existing UI in a WKWebView; starts/keeps its own engine, menu with ⌘Q/⌘R,
  and a real `NSDraggingSession` for file drags.
- `Similar Tracks.command` — now builds the app if missing and opens it.
- `traktor_drag/` — deleted; the separate drag puck is obsolete.
- `similarity_engine.py` — `similar()` accepts many seeds (z-score average
  without re-normalising), returns `agreement`, `common`, `seeds`; result rows
  now carry the real `path`; NaN guard on the multi-seed BPM column.
- `music_app/server.py` — `IDLE_EXIT_MINUTES = 45` self-retirement, request
  timestamping; `/api/similar` accepts `ids`.
- `music_app/similar.js` / `.html` — seed chips, add-seed button, seed from
  selection, shared-tag line, full-width Spotify player row, native drag
  arming, seed restore gated on `window.signalsReady`.
- `music_app/similar_panels.js` — boot published as `window.signalsReady`.
- `music_app/traktor_bridge.py` — drag-shuttle endpoints removed again.

**Verified**
- Synthetic CGEvent drag on a result row → `app.log`: `armDrag: 1 file(s),
  first=/Users/jakub/Music/…` then `startDrag: 1 file(s) — natívna session
  spustená`. A drag across the checkbox column produced no `armDrag`, so
  drag-select still works.
- `setSinkId=true` and `enumerateDevices=true` reported from inside the
  WKWebView — CUE routing intact.
- Cold start 164 s; ⌘Q leaves the engine running; reopen 0 s.
- Multi-seed: Lila + Camo & Krooked → all drum'n'bass, 0/5 overlap with either
  seed alone; three seeds also fine; BPM window applies against the nearest
  seed with no NaN warnings.
- Panels render 77 compare + 75 shift signals in the app after the race fix.

**NOT verified:** the actual drop into Traktor. The drag session starts with a
real file URL — the same AppKit call Finder uses — but Traktor was not running
and launching it on the owner's machine mid-work was not appropriate. One real
drag by the owner settles it.

**Measured** RunPod: 55,267 / 66,833 done. One pod live at $0.22/h, no orphans.


## 2026-08-24 — D-073 · Spotify scrubbing, Finder-style selection, analysis queue, media keys

**Changed**
- `music_app/similar.js` — one transport, two backends. The footer's buttons,
  long seek bar and clock now drive either the app's own `<audio>` or Spotify's
  embedded player through the official iFrame API
  (`open.spotify.com/embed/iframe-api/v1`; `seek()` takes SECONDS,
  `playback_update` reports MILLISECONDS). Position is interpolated between
  updates so the bar moves smoothly.
- `music_app/similar.js` — selection is decided on MOUSE-DOWN, like Finder. It
  used to happen on click, i.e. on mouse-up, so any pointer movement let the
  drag swallow the gesture and nothing got selected. Clicking an already
  selected row still unselects on release, and only if no drag happened, so a
  selected row stays draggable.
- `music_app/analyze_jobs.py` — a single worker drains a FIFO queue. Every job
  used to spawn its own process, so a second track while the first was running
  created a SECOND pod. The worker also takes everything waiting in one go:
  three tracks queued during a pod boot are analysed by one pod, not three.
- `music_app/similar_panels.js` — the UI shows the queued state and position.
- `native/SimilarTracksApp.swift` — MediaPlayer framework: remote commands for
  play/pause/next/previous, and now-playing info published from the page so
  macOS routes the keyboard's media keys to the app. Re-published when the app
  becomes active, to take the keys back from other media apps.

**Verified**
- Spotify backend: 13 `playback_update` events, position advanced 0 → 6.8 s,
  the app's own bar tracked it, and `T.seekTo(60 % of duration)` landed at 0:20
  of 0:29 with the clock and bar agreeing. (Duration is 30 s because Spotify is
  not logged in; logging in from the embed plays the whole track.)
- Selection: a synthetic click WITH 8 px of movement — the case that used to
  fail — selected row 5 and showed "1 označených", and the same gesture still
  started a real file drag (`startDrag` in `native/app.log`).
- Queue: three requests, A ran alone immediately, B and C waited and merged
  into a single run (`ids = AAA`, then `ids = BBB,CCC`).
- Media keys: `media command from macOS: next` and `: prev` reached the app.

**NOT working, and why:** the play/pause key does not reach the app while the
Spotify desktop client is running — Spotify holds that key globally and also
steals next/previous once it grabs it. next/previous work when Spotify is not
contending. Quitting Spotify's desktop app (or turning off its media-key
setting) is the only fix; the spacebar always works inside the app.


## 2026-08-24 — D-074 · Mixed in Key switch, sixth preset, full Spotify playback, the manual

**Changed**
- `music_app/similar.html` / `similar.js` — a "Mixed in Key" switch beside "len
  zo Spotify". It sits ABOVE profiles: while on it forces the four mixable key
  relationships (exact, ±1, ±2, ±7 semitone) whatever profile is loaded, greys
  out the panel's own boxes, and gives the profile its rules back untouched
  when switched off. Its state lives in the browser, never in a profile.
  "relative" is deliberately excluded — it was not among the four asked for.
- `similarity_engine.py` — sixth preset "Nálada v scéne": CLAP and MAEST
  together, mood tags AND genre/subgenre/style, label deliberately left out.
- `spotify_authorize.py` (new) — one-off re-authorisation adding the
  `streaming` permission, which the stored token lacks. Backs up the old token,
  prints nothing secret.
- `music_app/similar_api.py` / `server.py` — `/api/spotify/token` (short-lived
  access token for the page, refresh token never leaves the server) and
  `/api/spotify/play` (start a track on the page's SDK device).
- `music_app/similar.js` — Spotify now has TWO backends. The Web Playback SDK
  plays the WHOLE track through an audio element in our own page, which is what
  finally makes CUE routing possible for Spotify; the iFrame embed stays as the
  fallback (30 s, no CUE) when `streaming` is not granted. `applySink()` routes
  both.
- `docs/prirucka.html` (new) — the manual: every signal, preset and switch,
  what it measures and when to use it. Published as an artifact.

**Verified**
- Presets endpoint returns six, "Nálada v scéne" resolving to 20 signals.
- Key filter: without it 6 of 40 results had no harmonic relation to the seed;
  with the four rules, 0 violations in 40.
- The switch: profile rule `relative` → switch on → the four forced rules →
  switch off → `relative` back, boxes unlocked. (First attempt got this wrong
  and left the forced set in place; fixed and re-tested.)
- `/api/spotify/token` returns a token and correctly reports
  `streaming: false`, so the app falls back to the embed and says why.

**BLOCKED on one owner action:** full-track Spotify playback and its CUE
routing need the `streaming` permission. Add `http://127.0.0.1:8899/callback`
to the app's Redirect URIs at developer.spotify.com/dashboard, then run
`python3 spotify_authorize.py` once. The account is Premium, which the SDK
requires, and every other permission is already granted.

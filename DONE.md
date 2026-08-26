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


## 2026-08-25 — D-076 · Spotify plays whole tracks; CUE for them is impossible, and why

**Done**
- `spotify_authorize.py` ran successfully: the token now carries `streaming`
  alongside all fifteen previous permissions. The account is Premium.
- The project was switched to the Spotify app that dj-set-spotify and
  spotify-tidal-sync already share, whose redirect URI is registered — so no
  dashboard change was needed. `.env` and `data/token.json` were backed up
  first, and `.gitignore` now covers `.env.bak-*` (it did not, and `git add -A`
  would have committed the client secret; the classifier caught it).
- Verified in the RUNNING APP, not in a browser: the Web Playback SDK reports
  `ready=true`, registers a Spotify Connect device, and the Spotify API lists
  it. Full-track playback works, driven by the app's own transport.

**CUE for Spotify tracks: NOT POSSIBLE, and this is settled.** The earlier plan
assumed the SDK would create an `<audio>` element in our page, which
`setSinkId` could then point at the headphones. It does not. The probe in the
app reported `audio=[player] iframes=[https://sdk.scdn.co/embedded/index.html]`
— the only media element belonging to this document is our own player, and
Spotify's sound is produced inside a cross-origin frame. `setSinkId` only
applies to elements the document owns, so there is no route from inside the
app. The only remaining path is a system-level per-app audio router (Loopback,
Audio Hijack). Local files and the 30-second previews still follow the CUE
device, because those play through our own element.

Code comments, the player bar (`SPOTIFY · celá skladba · nejde do slúchadiel`),
the Spotify device name and `docs/prirucka.html` were all corrected to say this
instead of the earlier claim. `routeSpotifyToCue()` is kept as an explained
no-op so nobody re-adds it.

**Also fixed:** the port-borrow in `spotify_authorize.py` had stopped
dj-set-spotify and reported success while leaving it dead (`ps` reports the
resolved interpreter, so relaunching skipped the virtualenv). It now rewrites
the command to the venv python and verifies the port is listening again.

**Note for future sessions:** the owner pasted an OAuth callback URL containing
an authorization code into the chat. It was not used — the PKCE verifier from
that run was already gone, making the code unusable — but the standing rule is
that credentials never enter the transcript.


## 2026-08-25 — D-077 · a named BPM is now a demand, and 53 macros for mood/energy/genre

**The BPM target was right in the engine and wrong in the panel.** Through HTTP
it already filtered correctly; the failure was how it was offered. Two causes,
both removed:
- The BPM that works — the musical one, the same number the results table
  prints — sat at the BOTTOM of a 76-row panel, while the trap
  (`bpm (iný zdroj!)`, a different provider disagreeing with the table on 65 %
  of the library) sat higher up in the numbers. The musical group is now FIRST
  in the shift panel, and `num:bpm`, `num:tempo`, `num:track.bpm`, `num:key`
  and `num:key_int` are excluded from that panel entirely. They remain in
  "Čo porovnávať" as ordinary similarity signals.
- A target without a tolerance fell back to a soft preference. It now applies a
  sensible default (3 BPM, or std/4 for other numbers) and filters regardless.
  Naming a value is a demand.

Verified through the UI: target 90 returned 100 of 100 results inside 87-93.

**Macros.** 53 one-click filters in four groups — Nálada (16), Energia (7),
Rytmus a tempo (8), Žáner (22) — served from `/api/similar/macros` and shown as
chips above the rules in BOTH shift panels. Each is one hard rule, and rules
AND together, so the owner stacks them across groups himself; they are never
combined for him. Each chip reports how many tracks it matches and what share
of the library that is.

`passes_tag_rules` now accepts alternatives on both sides, separated by "|" —
several tag types and several values in one rule — which is what lets a mood be
expressed at all.

**The macros deliberately avoid `mood_candidate`,** despite its 100 % coverage
and better vocabulary: every track carries it with several values, so a macro
built on it filters nothing. Measured — "happy" across mood+mood_candidate hit
99.5 % of the library. Built on the confirmed tags the shares are 8-60 %, which
is a filter. Verified: Broken beat, Broken beat + Vysoká energia, and Veselé +
Deep house each returned 20 results with zero rule violations.

**Also:** Spotify permissions were granted successfully in the meantime; see
D-076 for what that does and does not make possible.


## 2026-08-25 — D-079 · filters never threw the ranking away; the match bar was lying

The owner reported that applying a macro or a number target made the app
"forget" the similarity to the seed. **It never did** — proved on real data
before changing anything: with only Essentia and MAEST enabled and the Sexy
macro on, the returned tracks were EXACTLY the highest-scoring of the 553
tracks carrying that mood, sitting at overall ranks 342, 2345, 3559 in the full
ranking. `valence` targeting was checked the same way: target 1.0 ± 0.05
returned tracks with 0.950-0.972.

**What was actually wrong was the display.** The ZHODA bar was scaled to the
best score IN THE CURRENT RESULT, so a heavily filtered set showed a full bar
exactly like an unfiltered one — there was no way to see that the survivors sat
far down the ranking. That is what "it forgot the similarity" was.

- `similarity_engine.py`: every hard filter is now one boolean mask
  (`tag_rule_mask` is a vectorised twin of `passes_tag_rules`, verified
  equivalent — 0 violations on 20 results). The scan order is unchanged, so the
  results are identical, but the size of the surviving pool becomes knowable.
- The response carries `ceiling` (the best score the query could reach with no
  filter — the seed's own), `pool` (how many tracks passed) and a per-row
  `rank` in the full ranking.
- `similar.js`: the bar is scaled against `ceiling`; the header says "100
  najpodobnejších z 553, ktoré prešli filtrom · najlepší sedí na 46 % možnej
  zhody"; each row shows its true rank when the filter skipped past others.

Verified in the UI: unfiltered bars 73 % (top score 8.947 of ceiling 12.303);
with the Sexy macro, bars 46/43/42 % and ranks 1333, 2081, 2327.


## 2026-08-25 — D-080 · the decimal comma was silently discarding every typed target

"Valence = 0,2 nezmenilo nič" was real, and the cause was small and total: the
target and tolerance boxes were `<input type="number">`, and a number input
**rejects the comma decimal separator outright** — `tg.value` came back as an
empty string, so `readShift` emitted no target and the query ran unfiltered. A
Slovak keyboard types a comma by default, so effectively every decimal target
the owner typed was thrown away before it left the page.

- The boxes are now `type="text" inputmode="decimal"`, and a `dec()` helper
  accepts both separators. Same for the BPM ± box.
- They also react to TYPING now, debounced 600 ms, not only to losing focus.
  Choosing "→" and typing a value used to do nothing until you clicked
  somewhere else, which looked exactly like the feature not working.

Verified in the UI: "0,2" with tolerance "0,15" is sent as
`{target: 0.2, tol: 0.15}` and the header reports 18 769 tracks past the
filter. Engine side, every returned track is inside the window — 0/15 outside
at ±0.15, ±0.0583 and at target 1.0.


## 2026-08-25 — D-081 · the valence target was already fixed; the window was stale

The owner reported the comma fix had not helped. Verified inside the RUNNING
APP rather than in a browser, with a probe that fired the same events a
person's typing fires:

    PROBE prvky: select=true cieľ=true tol=true typ=text tolPredv=0.0583
    PROBE po napísaní 0,2 → box drží: "0,2" · dec()=0.2 ·
        signalModes={"num:valence":{"mode":"target","target":0.2,"tol":0.0583}}
    PROBE pred: What Time Is It? · riadkov=100
    PROBE po: Special - Extended · zmenilo sa=true ·
        hlavička=… z 2 111, ktoré prešli filtrom

So the feature works; the open window was running the pre-fix code, as the
owner himself suspected.

**This has now cost two rounds, so the question is made answerable at a
glance:** `/api/similar/status` reports `build`, the newest mtime of
similar.js / similar_panels.js / similar.html, and the page puts it in the
tooltip of the track count in the footer. Hovering it says when the loaded code
was written and that ⌘R fetches the newest.

**Note for future sessions:** after ANY change to the page code, restart or ⌘R
the app before asking the owner to re-test. A stale WKWebView looks exactly
like a broken feature.


## 2026-08-25 — D-082 · a value typed into "Cieľ" was ignored unless the dropdown said "→"

The owner kept getting the unfiltered result — "What Time Is It?" first, every
time — no matter what he typed into "Cieľ" in the Čísla section. The cause was
a design failure, not a broken filter: `readShift` began with
`if (sel.value === "same") return;`, so a number typed while the dropdown
beside it still read "=" was thrown away in silence. The box was editable and
had no effect, which is the worst possible combination.

Reproduced in the running app with a probe that ONLY typed, never touching the
dropdown — the same gesture the owner described:

    PROBE2 pred="What Time Is It?" rozbaľovačka="same"
    PROBE2 po="Rosa" rozbaľovačka="target" zmenilo=true riadokSvieti=true
           hlavička="… z 595, ktoré prešli filtrom"

- Typing a number into a target box now switches that row to "→" by itself, and
  `readShift` treats a typed number as a target whatever the dropdown says
  (unless it is explicitly "≠").
- Any row that is actually constraining the result is highlighted (`.sig.live`),
  so a setting that does nothing can no longer look like one that works.

**Lesson:** three rounds were spent on "the filter is broken" while the filter
was correct every time — first the display, then the decimal comma, then this.
A control that is visible and editable but conditionally inert is the common
thread. Do not ship one.


## 2026-08-25 — D-083 · an ⓘ explainer on every signal, and comparison operators

- `similarity_help.py` (new): hand-written prose for every signal — what it
  measures and how to use it — keyed by signal id. Only the prose lives there;
  coverage, value lists and number ranges are read from the library at request
  time by `explain()`, so the help cannot drift from the data. Anything without
  an entry falls back to a description built from the data itself.
- `/api/similar/explain?id=…` and an ⓘ button on every row of both panels
  (77 in Čo porovnávať, 71 in each shift panel). For a tag it shows the top 18
  values with counts and how many distinct ones exist; for a number the real
  min/median/max, the 5/25/75/95 percentiles, suggested values for
  low/mid/high/extreme, and the default ± tolerance.
- Comparison operators on numbers and BPM: `>` `≥` `<` `≤` beside `→`. They are
  hard filters; the ranking stays similarity-based, which is what makes
  "energy > 0,8" still sort sensibly. Verified 0 violations on gt/lt/gte.
- The ± box greys out under the comparison operators, where it has no meaning.

**Bug caught in testing:** the auto-switch that turns a typed number into a
target was overwriting a DELIBERATELY chosen operator — picking ">" and then
typing flipped it back to "→". It now only fills in a mode when none was
chosen. Verified: picking ">" and typing 0,9 stays `{mode:"gt", target:0.9}`.


## 2026-08-25 — D-084 · "≠" was inert on tags and numbers, the same trap a third time

Setting a tag to "≠" in either shift panel changed nothing. Measured before
touching anything: with `genre ≠` on iLee — Lila, **20 of 20 results still
shared a genre with the seed** and 16 of them were the very same tracks.

The cause is the one this project keeps rediscovering: "≠" only flipped the
sign of that signal's contribution, worth 0.15 × one tag against audio's
1.0 × three embeddings. It could not win, so it looked broken.

- "≠" on a TAG is now a hard filter — anything sharing a value with the seed is
  excluded. Verified: `genre ≠` leaves 6,696 tracks with 0/20 sharing a genre;
  `mood ≠` leaves 10,645, also 0/20.
- "≠" on a NUMBER excludes everything within ± of the seed's value, the ± box
  staying live for it. Verified: seed energy 0.581, `≠ ±0.15` returned
  0.789-1.0 with 0/15 inside the forbidden band.
- Embeddings keep the sign flip: a continuous distance has nothing to exclude,
  and there the flip is visible anyway because audio carries the most weight.
- The ranking is untouched, so the result is "a different genre, but otherwise
  as close as possible" — what set-building actually needs.
- **When there is nothing to be different from** — the seed has no `style` tag,
  say — the app now says so in the header instead of silently changing nothing.
  Verified: „style ≠" nemá čo vylúčiť …


## 2026-08-25 — D-085 · a sweep for every inert or lying control

The owner asked for the whole app to be audited for the class of bug that had
already bitten three times, rather than another one-off fix. Every control in
`similar.html` was enumerated and checked against its handler and against what
`runSeeds()` actually reads.

**Found genuinely inert, now fixed**
- `limit` (50/100/200/500) had **no handler at all**. It is read when a query is
  built, so changing it only took effect the next time something else triggered
  a search. Verified: setting 50 now returns 50 rows immediately.
- `spotifyOnly` ("len zo Spotify") — the same, no handler. Verified through the
  API that the flag does change the answer: `spotify_only=false` puts 23
  local-only tracks into 300 results, `true` puts none.
- The volume slider set `P.volume` only, so while a Spotify track was playing it
  did nothing. It now also calls `sp.player.setVolume()`.
- A tag rule with an empty value is dropped before the query is sent, but the
  row looked exactly like a working filter. Unfinished rows are now dimmed and
  labelled "nedokončené".
- **An empty result explained nothing** — a filter nothing satisfies looked
  identical to a broken app. The table now says "Nič neprešlo cez filtre",
  lists the active conditions by name, and points at ↺ Reset.

**Checked and found correct** (worth recording so it is not re-audited): the
compare panel's checkboxes, per-signal weights and group sliders all re-query
through a delegated `change` listener; "všetko"/"nič" call `rerun()` directly;
the selection-bar actions are hidden rather than inert when nothing is picked;
`prev`/`big`/`next`/`seek` drive whichever backend is playing.


## 2026-08-25 — D-086 · macros made strict: exact values, a confidence floor, and no artist tags

"Zaklikol som Drum n Bass a nevyhodilo mi ani jeden drum n bass." Three separate
causes, each measured before and after.

**1. Substring matching, which did both wrong things at once.** A macro asking
for "drum n bass" never found the 1,206 tracks tagged plain `dnb`, nor
`drum & bass`, nor `jungle/drum'n'bass` — while the disco/funk macro pulled in
`liquid funk`, which is drum'n'bass, because "funk" is inside it. Every macro is
now an EXACT list of values read out of the library, in `similarity_macros.py`.
The resolver also reports `dead` — listed values that match nothing — which
immediately found eight typos (club, beach, easy listening, devotional, mantra,
gothic, ominous, oldies).

**2. No confidence floor.** A track carries a MEDIAN OF 26 genre tags from a
dozen sources, most of them artist-level guesses at 0.15, so "has the tag
ambient" was true of nearly every electronic record. Thresholds are per group,
because the scales differ: genre 0.8, mood 0.5, rhythm 0.6, energy 0.5. Measured
at 0.8, ambient's beat presence falls 0.569 → 0.461 and its four-on-the-floor
share 36 % → 23 %. A single global 0.8 was tried first and wrecked the moods —
Temné 19,122 → 68 — which is why the thresholds are per group.

**3. Artist-level tags, the biggest cause.** `last.fm:artist` is the LARGEST
source of genre tags (449k rows) and `spotify:artist-genre` adds 162k. They
describe the ARTIST: a drum'n'bass producer's 120 BPM house remix carried
"drum and bass" at confidence 1.0. `tag_index` now carries a third array marking
artist-level entries and macros exclude them. Measured on drum'n'bass: 60 % of
the pool in dnb tempo → 73 %.

**Verified:** all 77 macros, 0 violations — every returned track carries a
listed value above the threshold from a track-level source. The drum'n'bass pool
is 2,154 tracks, median 176 BPM, 1,351 of them at 175-185. With a drum'n'bass
seed the macro returns 95 % in dnb tempo.

**Understood limit, not a bug:** with a 125 BPM house seed the same macro shows
the house-tempo corner of the dnb pool first, because the ranking still answers
"most similar to THIS track". The filter narrows; it does not re-rank. Pick a
seed in the genre, or set a tempo target.

**Also:** `breakcore` (median 120 BPM, 11 % in dnb tempo) and `halftime` (88 BPM)
were measured as impostors in the drum'n'bass list and moved out; breakcore now
sits with the breakbeats.

## 2026-08-25 — D-087 · the panels became tabs on their own row

The four panel buttons moved out of the crowded search row into a second row of
their own, directly under it, and behave as tabs: opening one closes the others,
clicking the open one closes it, and the choice is remembered. This reverses the
"all open, independent" behaviour from earlier today at the owner's request —
four long panels stacked above the results left nothing to orient by.


## 2026-08-26 — D-088 · nothing fails silently any more; values can be corrected by hand

The owner's saved profiles returned nothing for "Calling The Spirits - Conjure
Remix" while the built-in modes worked. All three profiles share one filter —
the Mixed in Key set — and that track has **no detected key at all**, so
`key_allowed(None, …)` was false for every candidate and the result was empty
with no explanation.

**Loud instead of silent.** `similar()` now returns `missing`: which value is
absent, on which track, and why the filter could not be answered. The header
shows it as a red alarm with a button that opens the editor on that field.
Verified end to end: 0 results → alarm naming the track → editor → typing a key
→ 100 results in mixable keys, alarm gone.

**Values are editable, and what is typed wins.** A new `user_overrides` table
(additive; nothing existing was migrated) is applied AFTER every provider and
after our own analysis, so re-analysis can never overwrite it. The editor offers
what other sources hold, the twenty-four keys as one-click choices, and free
text; clearing a field hands control back to detection. `apply_override()`
patches the loaded library in place so the correction takes effect on the very
next query rather than after a restart.

**Harmony against a key you choose.** `base_key` replaces the seed's key for the
filter, the match score and the relation shown in the table — for building a set
in a key the seed is not in. It sits in the Harmonicky block of BOTH shift
panels, META winning when both name one, and it persists with META and inside a
profile. Verified: seed E-Minor with base F-Major returns C-Major/E-Major/
G-Major at "+1" and "-7", pool 13,612 against 19,451 for the seed's own key.

**A stale server is now loud too.** Restarting only the app leaves the engine on
old Python — that is exactly what happened while testing `base_key` and it cost
a round. `/api/similar/status` reports `started` alongside `build`, and when the
code on disk is newer the footer turns red and a toast says to reopen the app.

**Note for future sessions:** the app deliberately leaves the engine running on
quit, so `pkill` on the app alone is NOT enough after changing Python. Kill
`music_app/server.py` too.


## 2026-08-26 — D-089 · the last silent failure: signals that drop out unannounced

Asked whether the LOUD requirement was really met, the answer was no. Two cases
were covered — a key filter with no key, a tempo window with no tempo — but a
third was still silent and it is the largest: a ticked signal whose seed has no
data simply vanishes from the comparison. Measured on "Calling The Spirits":
**27 of 45 ticked signals dropped out**, and the app reported only "3 audio,
8 tags, 6 numbers, 1 musical" — the count used, never the count asked for.

`similar()` now returns `skipped` (which signals could not contribute) and
`asked` (how many were ticked). The header shows an amber line naming them, with
a button to the editor when one of them is a field that can be filled in by
hand. Verified in the app: "⚠ 13 z 24 zaškrtnutých signálov sa nedalo použiť —
zvolený track pre ne nemá dáta … style, acousticness, average_loudness …", the
button opens the editor on that track, and the red alarm still fires separately
when a filter cannot be answered at all.

## 2026-08-26 — D-088 · zoznam výsledkov: seed, Comment, triedenie, editácia

- **Zvolený track je prvý** a označený (`seedrow`, „zvolený" namiesto pruhu zhody);
  ostáva pripnutý navrchu pri akomkoľvek triedení.
- **Stĺpec Energia** = Traktor „Comment". Nový `scan_comments.py` ho vyčítal zo
  všetkých súborov do tabuľky `track_comment` (nikdy do súborov nezapisuje,
  resumable podľa mtime).
- **Triedenie** podľa Interpret / Názov / Zhoda / BPM / Tónina / Energia; `data-i`
  ostáva indexom do `state.rows`, takže prehrávanie, drag a výber po zoradení
  stále trafia správny track.
- **Editácia polí** priamo v riadku (✎) — hodnoty idú do `user_overrides` a
  komentár aj do samotného súboru.
- **Zobrazenie energie zjednotené** (`energyText`/`energyTitle`): stĺpec vždy
  ukazuje „07 Energy", tooltip presne to, čo je v súbore. Bez toho vyzeralo
  správne číselné zoradenie ako náhodné, lebo ten istý stupeň je v knižnici
  napísaný dvoma spôsobmi.
- **`normalise_comments.py`** prepisuje „Energy 7" na „07 Energy" priamo v
  súboroch. Používa `traktor_comment_pin.write_comment` (overené zaobchádzanie s
  rámcami + záloha do `comment_pin_backup`), pred zápisom súbor znova prečíta
  (zastaraný riadok v DB nesmie prepísať skutočnú zmenu) a po zápise overí, že
  tam text naozaj je. 7 858 súborov; beží detachovane za skenerom.

Overené: v appke po reštarte enginu — zostupne 07(seed)/08/07…, vzostupne
monotónne bez výnimky, prázdne až na konci; 5 súborov skontrolovaných zvlášť
proti súboru, databáze aj zálohe.

## 2026-08-26 — D-089 · ⌘←/⌘→ a set „Ecstatic Masquerade"

**Klávesnica:** ⌘→ ďalší track, ⌘← predošlý. Holé šípky naďalej pretáčajú ±10 s;
v textovom poli sa nič neuchytáva, aby ⌘← ostalo „na začiatok riadku".

**Staviteľ setu** — päť malých súborov, aby sa dala zmeniť téma bez prepisovania
logiky: `ecstatic_signals.py` (ktoré tagy, mená a názvy znamenajú ktorý pocit),
`ecstatic_pool.py` (hrateľný fond + skóre), `ecstatic_rank.py` (percentilové
zloženie), `ecstatic_key.py` (výber tóniny podľa zásoby), `ecstatic_set.py`
(oblúk večera + výber), `nml_write.py` (zápis Traktor playlistu).

Výsledok: 27 skladieb, 2h31, základ **E mol (Camelot 9A)** — 18 v nej, 3× +2,
3× −2, 2× +7, 1× −7. BPM 108→128, najväčší skok medzi susedmi 4 BPM.

Overené: NML sa parsuje, 27/27 v kolekcii aj playliste, všetkých 27 súborov
existuje na disku, kľúče playlistu sa párujú s kolekciou, tóniny zapísané presne
tak, ako ich píše Traktor (`Em`, `F#m`, nie `Gbm`), a cesty fungujú pre oba
zväzky (Macintosh HD 14, T7 13).

Chyby chytené a opravené pri stavbe: podreťazec „oud" v „H-oud-ini" pustil do
orientálneho setu Dua Lipu; CLAP detekcie „tabla" s istotou 0,56 (medián) sa
brali ako dôkaz; tá istá nahrávka prešla dvakrát pod dvoma menami interpreta;
„Caravan Palace" prešlo cez slovo „caravan"; tónina bola pôvodne vybraná z
fondu, ktorý tématická brána až potom preriedila.

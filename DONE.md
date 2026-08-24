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

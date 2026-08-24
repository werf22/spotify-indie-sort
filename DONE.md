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

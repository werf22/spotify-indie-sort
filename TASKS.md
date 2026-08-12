# TASKS — <project-name>

<!-- Single source of truth for ordered work. Work strictly top-down within the current phase.
     Tasks are VERTICAL SLICES: each one is end-to-end usable (UI → logic → data → test),
     never layer-by-layer. Check a box ONLY when the DoD is met and tests are green —
     an unchecked box with honest status beats a checked lie (core §4, §5 NEVER). -->

<!-- Task format:
     - [ ] T<phase>-<n> — <description> · DoD: <observable outcome>
     Example:
     - [ ] T1-2 — <user can submit <form> and see saved result> · DoD: <submitting valid input persists the record and the new entry renders on reload; invalid input shows a clear error> -->

## Phase 0 — Foundations

- [ ] T0-1 — <repo, environment, run/test commands working> · DoD: <fresh clone runs with one command>
- [ ] T0-2 — <skeleton: app boots, health endpoint / blank screen renders> · DoD: <observable outcome>
- [ ] T0-3 — <deploy pipeline to a live URL or distributable> · DoD: <a trivial change reaches the live target>

## Phase 1 — MVP

- [ ] T1-1 — <first vertical slice of the core user action> · DoD: <observable outcome>
- [ ] T1-2 — <description> · DoD: <observable outcome>
- [ ] T1-3 — <description> · DoD: <observable outcome>

## Backlog

<!-- Unordered. Ideas and later-phase work. Nothing here gets built until promoted
     into a phase above — promoting is a human decision, not an agent one. -->

- <idea / future task>
- <idea / future task>

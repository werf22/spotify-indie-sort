# LESSONS — <project-name>

<!-- Project-level lessons learned. Auto-imported every session via the @LESSONS.md line
     in this project's CLAUDE.md — if you rename this file, update that import line too.
     Same format as global learned rules. Saved via the learning protocol (core §6):
     a correction, a stated preference, or a repeated mistake → one-line save question → here.
     When a lesson repeats ACROSS projects, promote it to global via the learn skill —
     it moves to ~/.claude/rules/learned-rules.md and gets removed from here. -->

<!-- Format: - [YYYY-MM-DD] lesson — why
     Store every lesson in English, regardless of the language it was stated in — translate,
     and optionally keep the original phrase in the why. One storage language keeps
     grep-based dedupe working.
     Example shape (kept in this comment so it never loads as a real entry — replace with
     the first real lesson, don't append after it):
     - [<YYYY-MM-DD>] <lesson, imperative: "always X in this project" / "never Y here"> — <why: what broke or what it prevents> -->
- [2026-08-14] Tags in this database are English, always — never translated, never localised. Deezer localises genre names to the account locale and had written 113,319 non-English tags (57,386 "elektronická", 33,323 "tanečná"); enrich_deezer.py now sends Accept-Language: en-US and music_app/derive.py refuses to surface a non-English value. The existing 113,319 rows are still there — cleaning them is a data migration and needs the owner's approval.

- [2026-08-25] A control that is visible and editable but conditionally inert is the worst thing to ship — three separate rounds of "the filter is broken" were all this. The target box in „Čo posunúť" was ignored unless a dropdown beside it already said "→"; before that a decimal comma was silently discarded by `input type=number`; before that the match bar was scaled to the filtered winner so a narrowed result looked identical to an unfiltered one. In every case the engine was correct and the UI lied. Rules that came out of it: a typed value IS the intent (fill in the mode rather than ignoring the value), accept both decimal separators, grey out anything that has no effect right now, and mark every control that is actually constraining the result.
- [2026-08-25] Verify page changes IN THE APP, not in a browser tab — and restart or ⌘R it before asking the owner to re-test. A stale WKWebView is indistinguishable from a broken feature and cost a full round. `/api/similar/status` now reports `build` (newest mtime of the page code) and the footer's track count carries it in its tooltip.

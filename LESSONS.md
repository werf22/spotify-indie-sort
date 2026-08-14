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

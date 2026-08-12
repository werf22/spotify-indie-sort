# DOCUMENTATION — <project-name>

<!-- Living map of the codebase, written for a NON-CODER owner. Updated after every task
     that adds, removes, or rewires modules (rules/documentation-protocol.md). This is a
     tour, not an API reference: after reading it, someone who cannot code knows what
     exists, what talks to what, and where to look when something misbehaves.
     Plain language — every jargon term costs a reader. -->

## Overview

<what the app does and for whom — 3 lines max, plain language>

## Modules

<!-- One row per meaningful file or directory. "Talks to" names the modules/services it
     calls or is called by — that column is what makes this a map and not a list. -->

| File / Dir | Purpose | Talks to |
|---|---|---|
| `<path>` | <one line — what it is for> | `<module>`, `<service>` |
| `<path>` | <one line> | `<module>` |

## Data flows

<!-- One bullet per MAIN user action, walked end-to-end. Follow the data; name the
     modules from the table above at each hop. -->

- **<User action, e.g. "save a note">:** <UI element> → `<module>` → `<module>` → <storage> → <what the user sees>
- **<User action>:** <walkthrough>

## External services

| Service | Used for | Where configured |
|---|---|---|
| `<service>` | <one line> | `<env var(s) / config file>` |

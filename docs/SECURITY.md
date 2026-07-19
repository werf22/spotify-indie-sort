# Security, credentials and spend controls

## Secret locations

Credentials may exist in:

- `.env` (Spotify client, FreqBlog, Last.fm, RunPod and optional API settings);
- `data/token.json` (Spotify refresh token);
- sibling Spotify MCP configuration;
- `~/.runpod/` and RunPod CLI configuration;
- macOS/browser authenticated sessions.

`.env` and `data/` are gitignored. Documentation contains names and policies,
never values.

The current `.env`, Spotify token, Spotify MCP config, RunPod config and Tidal
token are permission-restricted to the owner. Validate handoff access with
`verify_handoff_access.py --live`; do not duplicate keys into another document.

## Keys disclosed during project work

The owner supplied Last.fm, MusicBrainz OAuth, FreqBlog Free/Starter and other
credentials during the conversation. Treat any credential pasted into chat as
sensitive. The active FreqBlog Starter key and required API credentials are in
local secret storage; do not copy them into source, logs, commits or handoffs.

After the long-running enrichment completes, recommend rotating exposed keys
where providers support rotation, then update `.env` without printing values.
Do not rotate an active key autonomously because that would interrupt work and
may require owner authorization.

## Billing authority

The owner explicitly requires:

- only the owner can add funds or approve a payment;
- the agent may warn about low balance;
- no automatic top-up, billing API, subscription upgrade or plan purchase;
- no FreqBlog/SoundNet/RunPod upgrade without a new explicit instruction.

Current code enforces RunPod controls:

- account must already have at least USD 1.00;
- unexpected current hourly spend blocks new pods;
- selected pod must be at most USD 0.40/hour;
- server-side stop/terminate deadlines are configured;
- pod deletion is attempted even when analysis/download fails.

The user's RunPod account-level spend limit is not a project budget. The local
USD 0.40/hour and USD 1 balance guards are the binding project controls.

## Data sensitivity

The DB contains private listening history, playlist membership and local file
paths. Treat `data/music.db`, account exports, streaming history, Traktor NML
and manifests as private personal data. Do not upload the database or history
to third parties. Cloud audio analysis uploads only the selected analysis audio
copies and necessary IDs/state to the user's paid RunPod pod.

## Source control hygiene

- Never run `git clean`, destructive reset or checkout over the dirty tree.
- Never commit `.env`, token files, data, model caches, environments or audio.
- Before any future commit, inspect staged diff for credentials and absolute
  private paths.
- Generated handoff documents intentionally include project paths and Spotify
  playlist URLs, but not API secrets.
- The OneTagger vendor fork has uncommitted modifications; preserve them.

## Model supply-chain control

MAEST uses Hugging Face remote model code. It is pinned to commit
`d298f3a38365aa566b6a4417560423061ed82380` in
`analyze_local_genres.py`, so a model-repository update cannot silently change
production behavior. Preserve or deliberately review this pin when upgrading.

Essentia models are downloaded official model artifacts under
`vendor/essentia-models`. CLAP uses the configured LAION model. Record exact
revisions for any future model replacement and rerun the quality gate.

## Audio rights

The owner states that missing tracks are purchased/licensed. Nevertheless,
automation must not assume arbitrary streaming tracks may be downloaded. Any
future Tidal/Spotify acquisition adapter must:

- operate only within the user's lawful entitlement;
- avoid DRM circumvention or redistribution;
- deduplicate against verified local files;
- verify complete files and quality;
- retain provider/order provenance;
- remain separately pausable and rate-limited.

The current repository intentionally stops at inventory, blindspot playlists
and verification; no bulk downloader is claimed as complete.

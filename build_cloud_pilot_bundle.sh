#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}"
OUT="$ROOT/data/cloud_pilot/cloud-audio-pilot.tar"
cd "$ROOT"

# FLAC excerpts are already compressed; plain tar is faster and the exact
# bundle can be retried after an interrupted upload.
tar -cf "$OUT.partial" \
  cloud_audio_pilot.py \
  analyze_local_rhythm.py \
  analyze_local_genres.py \
  analyze_local_semantics.py \
  audio_taxonomy.py \
  musicdb.py \
  requirements-cloud-audio.txt \
  data/cloud_pilot/manifest.csv \
  data/cloud_pilot/clips
mv "$OUT.partial" "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
ls -lh "$OUT" "$OUT.sha256"

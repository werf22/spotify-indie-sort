#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}"
OUT="$ROOT/data/cloud_full_smoke/cloud-full-smoke.tar"
cd "$ROOT"

tar -cf "$OUT.partial" \
  cloud_audio_full.py \
  analyze_essentia_full.py \
  analyze_local_rhythm.py \
  analyze_local_genres.py \
  analyze_local_semantics.py \
  audio_taxonomy.py \
  musicdb.py \
  requirements-cloud-audio.txt \
  vendor/essentia-models \
  data/cloud_full_smoke/manifest.csv \
  data/cloud_full_smoke/clips
mv "$OUT.partial" "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
ls -lh "$OUT" "$OUT.sha256"

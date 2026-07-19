#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}"
PYTHON="${AUDIO_PYTHON:-$(command -v python3.12 || true)}"

if [[ -z "$PYTHON" ]]; then
  echo "Python 3.12 is required. Install it with: brew install python@3.12" >&2
  exit 1
fi

if [[ ! -x "$ROOT/.audio-venv/bin/python" ]]; then
  "$PYTHON" -m venv "$ROOT/.audio-venv"
fi

"$ROOT/.audio-venv/bin/python" -m pip install --upgrade pip
"$ROOT/.audio-venv/bin/python" -m pip install -r "$ROOT/requirements-audio.txt"
"$ROOT/.audio-venv/bin/python" - <<'PY'
import torch
import librosa
import transformers
from beat_this.inference import File2Beats
print("Audio environment ready; MPS:", torch.backends.mps.is_available())
PY

echo "Installed local audio enrichment environment"

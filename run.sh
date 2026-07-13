#!/usr/bin/env bash
# Re-run this any time to pull in newly liked/playlisted tracks.
# First run needs data/token.json seeded — see README "Token bootstrap".
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

python export.py
python classify.py
python build_playlist.py

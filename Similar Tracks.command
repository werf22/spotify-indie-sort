#!/bin/bash
# Opens the Similar Tracks app. This exists only so the project folder still has
# a double-clickable entry point; the real application is "Similar Tracks.app"
# next to it, which can be dragged to the Dock or to /Applications.
#
# The app starts its own engine, so nothing else has to be running first.
cd "$(dirname "$0")"

if [ ! -x "Similar Tracks.app/Contents/MacOS/SimilarTracks" ]; then
  echo "Prvé spustenie — zostavujem aplikáciu…"
  ./native/build.sh || { echo "Zostavenie zlyhalo. Chýbajú Xcode Command Line Tools? Spusti: xcode-select --install"; exit 1; }
fi

open "Similar Tracks.app"
echo "Similar Tracks beží. Toto okno môžeš zavrieť."

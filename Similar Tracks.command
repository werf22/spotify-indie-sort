#!/bin/bash
# Double-click this file in Finder to open the "find similar tracks" app.
#
# It starts the same small local server the database browser uses and opens the
# similarity screen. The first search waits about a minute while the audio
# fingerprints load; the screen says so while it happens.
# Closing this Terminal window stops the app.
cd "$(dirname "$0")"

# Reuse the server if it is already running (e.g. the database browser is open),
# otherwise start it. Either way, open the similarity page.
if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8765/api/similar/status; then
  open "http://127.0.0.1:8765/similar"
  echo "App already running — opened http://127.0.0.1:8765/similar"
  echo "This window can be closed."
else
  ( sleep 2; open "http://127.0.0.1:8765/similar" ) &
  exec ./.venv/bin/python music_app/server.py
fi

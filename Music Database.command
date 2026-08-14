#!/bin/bash
# Double-click this file in Finder to open the music database browser.
# It starts a small local server and opens your browser at it.
# Closing this Terminal window stops the app.
cd "$(dirname "$0")"
exec ./.venv/bin/python music_app/server.py

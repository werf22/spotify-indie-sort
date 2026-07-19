#!/bin/zsh
set -e
ROOT="/Users/jakub/Appky Claude/spotify-indie-sort"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS"
cp "$ROOT/com.jakub.local-dj-enrichment.plist" "$AGENTS/com.jakub.local-dj-enrichment.plist"
launchctl bootout "gui/$(id -u)/com.jakub.local-dj-enrichment" 2>/dev/null || true
for attempt in 1 2 3 4 5; do
  if launchctl bootstrap "gui/$(id -u)" "$AGENTS/com.jakub.local-dj-enrichment.plist"; then
    break
  fi
  if [[ "$attempt" == 5 ]]; then
    echo "Could not bootstrap LaunchAgent after 5 attempts" >&2
    exit 1
  fi
  sleep 1
done
launchctl kickstart -k "gui/$(id -u)/com.jakub.local-dj-enrichment"
echo "Installed and started LaunchAgent"

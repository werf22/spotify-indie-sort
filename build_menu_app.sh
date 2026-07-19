#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}"
BUILD="$ROOT/dist/Music Library Sync.app"
INSTALL="$HOME/Applications/Music Library Sync.app"
PLIST="$HOME/Library/LaunchAgents/com.jakub.music-library-sync-menu.plist"

mkdir -p "$BUILD/Contents/MacOS" "$HOME/Applications" "$HOME/Library/LaunchAgents"
swiftc -parse-as-library -O \
  -target arm64-apple-macosx13.0 \
  -framework SwiftUI -framework AppKit \
  "$ROOT/menu_app/MusicSyncMenu.swift" \
  -o "$BUILD/Contents/MacOS/MusicLibrarySync"
cp "$ROOT/menu_app/Info.plist" "$BUILD/Contents/Info.plist"
codesign --force --deep --sign - "$BUILD" >/dev/null
rm -rf "$INSTALL"
cp -R "$BUILD" "$INSTALL"
cp "$ROOT/menu_app/com.jakub.music-library-sync-menu.plist" "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed: $INSTALL"

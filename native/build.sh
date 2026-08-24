#!/bin/bash
# Builds "Similar Tracks.app" into the project folder. Needs only the Xcode
# Command Line Tools (swiftc); macOS installs them with `xcode-select --install`.
set -e
cd "$(dirname "$0")/.."
APP="Similar Tracks.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Similar Tracks</string>
  <key>CFBundleDisplayName</key><string>Similar Tracks</string>
  <key>CFBundleExecutable</key><string>SimilarTracks</string>
  <key>CFBundleIdentifier</key><string>com.jakub.similar-tracks</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSMicrophoneUsageDescription</key><string>Potrebné iba na to, aby macOS ukázal názvy zvukových výstupov pre CUE.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PLIST
swiftc -O -o "$APP/Contents/MacOS/SimilarTracks" \
  native/SimilarTracksApp.swift -framework AppKit -framework WebKit -framework MediaPlayer
# Ad-hoc signature: without it macOS refuses the microphone prompt and the
# window can be killed on launch.
codesign --force --deep --sign - "$APP" 2>/dev/null || true
echo "built: $APP"

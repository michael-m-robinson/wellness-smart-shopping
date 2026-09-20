#!/bin/bash
# Build a drag-to-Applications disk image.
#
#   ./make_dmg.sh                    -> dist/Wellness Smart Shopping.dmg
#   ./make_dmg.sh "My Shopping App"  -> under your own name
#
# The app inside is self-contained: the control panel ships in its Resources,
# so there is no folder to keep beside it. macOS only.
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="${1:-Wellness Smart Shopping}"
APP="build/$APP_NAME.app"
DIST="dist"
DMG="$DIST/$APP_NAME.dmg"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

./build.sh "$APP_NAME"

echo
echo "Packaging $APP_NAME"
[ -d "$APP" ] || { echo "  ! $APP was not built" >&2; exit 1; }

mkdir -p "$DIST"
rm -f "$DMG"

echo "  staging ..."
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

cat > "$STAGE/Read Me.txt" <<TXT
$APP_NAME

To install: drag the app onto the Applications folder shown beside it.

To use it:
  1. Open $APP_NAME from Applications.
  2. Press "Scan with Claude...", then "Start Control Panel".
     The panel opens in your browser. It is inside the app; there is no
     other folder to keep.
  3. Pick a store, sign in to it, and give Claude the instruction shown.
  4. Import the sales file it writes.

Your settings, scans and sales files are kept in:
  ~/Library/Application Support/$APP_NAME

Needs: macOS 13+, Python 3 (included with macOS), Google Chrome or another
Chromium browser, and the Claude for Chrome extension with a Claude
subscription -- scanning reads store pages you are signed in to.

To uninstall: drag the app to the Trash, and delete the folder above.
TXT

echo "  building the image ..."
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO \
    -quiet "$DMG"

SIZE=$(du -h "$DMG" | cut -f1 | tr -d ' ')
echo
echo "Built: $DMG  ($SIZE)"
echo "Open it with:  open \"$DMG\""

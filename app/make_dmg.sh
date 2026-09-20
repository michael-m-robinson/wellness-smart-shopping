#!/bin/bash
# Build the install disk image.
#
#   ./make_dmg.sh                    -> dist/Wellness Smart Shopping.dmg
#   ./make_dmg.sh "My Shopping App"  -> under your own name
#
# Double-click the image and it opens the familiar window: the app on the left,
# the Applications folder on the right, drag across, done. The app is
# self-contained -- the control panel ships inside it -- so nothing else has to
# be installed and no folder has to stay beside it.
#
# macOS only. Needs the Swift toolchain (xcode-select --install).
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="${1:-Wellness Smart Shopping}"
APP="build/$APP_NAME.app"
DIST="dist"
DMG="$DIST/$APP_NAME.dmg"
VOLUME="$APP_NAME"
STAGE="$(mktemp -d)"
RW_DMG="$(mktemp -u).dmg"
ICON_SIZE=128          # the icons the user drags; Apple's own images use 128
WINDOW_W=700
WINDOW_H=460

cleanup() {
  [ -n "${MOUNTED:-}" ] && hdiutil detach "$MOUNTED" -force -quiet 2>/dev/null || true
  rm -rf "$STAGE" "$RW_DMG"
}
trap cleanup EXIT

./build.sh "$APP_NAME"
[ -d "$APP" ] || { echo "  ! $APP was not built" >&2; exit 1; }

echo
echo "Packaging $APP_NAME"

# --- what goes in the window ------------------------------------------------
echo "  staging ..."
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

mkdir -p "$STAGE/.background"
python3 ../tools/make_dmg_art.py "$STAGE/.background/background.png" >/dev/null
cp Resources/AppIcon.icns "$STAGE/.VolumeIcon.icns"

# --- a writable image we can arrange ----------------------------------------
echo "  creating the image ..."
SIZE_KB=$(( $(du -sk "$STAGE" | cut -f1) + 20000 ))
hdiutil create -srcfolder "$STAGE" -volname "$VOLUME" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW -size "${SIZE_KB}k" \
    -quiet "$RW_DMG"

MOUNTED="/Volumes/$VOLUME"
hdiutil attach "$RW_DMG" -readwrite -noverify -noautoopen -quiet
sleep 2

# --- lay the window out ------------------------------------------------------
echo "  arranging the window ..."
if ! osascript <<APPLESCRIPT
tell application "Finder"
  tell disk "$VOLUME"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 140, $((200 + WINDOW_W)), $((140 + WINDOW_H))}
    set opts to the icon view options of container window
    set arrangement of opts to not arranged
    set icon size of opts to $ICON_SIZE
    set text size of opts to 13
    set background picture of opts to file ".background:background.png"
    set position of item "$APP_NAME.app" of container window to {186, 196}
    set position of item "Applications" of container window to {512, 196}
    delay 1
    close
  end tell
end tell
APPLESCRIPT
then
  echo "  ! could not arrange the window; the image still installs" >&2
fi

# The volume icon only takes effect once the file is flagged as one.
if command -v SetFile >/dev/null 2>&1; then
  SetFile -a C "$MOUNTED" 2>/dev/null || echo "  (volume icon needs SetFile; skipped)"
fi

sync
hdiutil detach "$MOUNTED" -quiet
MOUNTED=""

# --- compress ---------------------------------------------------------------
echo "  compressing ..."
mkdir -p "$DIST"
rm -f "$DMG"
hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -quiet -o "$DMG"

SIZE=$(du -h "$DMG" | cut -f1 | tr -d ' ')
echo
echo "Built: $DMG  ($SIZE)"
echo "Try it: open \"$DMG\""

#!/bin/bash
# Build the Wellness Smart Shopping desktop app.
#
#   ./build.sh                     -> build/Wellness Smart Shopping.app
#   ./build.sh "My Shopping App"   -> build it under your own name
#
# Needs the Swift toolchain that ships with Xcode command line tools
# (xcode-select --install). macOS only.
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="${1:-Wellness Smart Shopping}"
SLUG=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')
BUNDLE_ID="org.wellnesssmartshopping.${SLUG:-app}"
OUT="build/$APP_NAME.app"

echo "Building $APP_NAME"
rm -rf "$OUT"
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"

echo "  compiling main.swift ..."
swiftc -O -o "$OUT/Contents/MacOS/SmartShoppingList" main.swift

echo "  bundling ..."
cp Info.plist "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName $APP_NAME" \
                        -c "Set :CFBundleIdentifier $BUNDLE_ID" \
                        "$OUT/Contents/Info.plist" >/dev/null
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string $APP_NAME" \
                        "$OUT/Contents/Info.plist" >/dev/null 2>&1 || \
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName $APP_NAME" \
                        "$OUT/Contents/Info.plist" >/dev/null
# Regenerate the icon from the artwork so the two cannot drift apart.
if [ -f art/icon-source.png ]; then
  python3 ../tools/make_icon.py art/icon-source.png Resources/AppIcon.icns >/dev/null 2>&1 || true
fi
cp Resources/AppIcon.icns "$OUT/Contents/Resources/" 2>/dev/null || true

# The closing picture: prefer a theme chosen in the control panel.
THEME=$(python3 -c "import json,sys;print(json.load(open('../branding.json')).get('theme',''))" 2>/dev/null || true)
[ -z "$THEME" ] && THEME=$(python3 -c "import json;print(json.load(open('../branding.example.json')).get('theme',''))" 2>/dev/null || true)
SRC=""
for ext in png jpg jpeg; do
  [ -f "../themes/$THEME.$ext" ] && SRC="../themes/$THEME.$ext" && break
done
if [ -n "$SRC" ]; then
  echo "  theme image: $THEME"
  sips -s format png "$SRC" --out "$OUT/Contents/Resources/theme.png" >/dev/null 2>&1 \
    || cp "$SRC" "$OUT/Contents/Resources/theme.png"
elif [ -f Resources/theme.png ]; then
  cp Resources/theme.png "$OUT/Contents/Resources/theme.png"
fi

# Ship the control panel inside the app so a drag-to-Applications install is
# self-contained: no folder to find, nothing to keep next to it.
echo "  bundling the control panel ..."
PANEL="$OUT/Contents/Resources/panel"
mkdir -p "$PANEL"
for item in panel.py crawl.py dealcrawler themes browser examples extension \
            config.example.json branding.example.json; do
  [ -e "../$item" ] && cp -R "../$item" "$PANEL/"
done
# Caches and anyone's personal files must not travel inside the bundle.
find "$PANEL" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
rm -f "$PANEL/config.json" "$PANEL/branding.json" "$PANEL/profile.json"
rm -rf "$PANEL/harvest" "$PANEL/out"

echo "  signing (ad-hoc) ..."
codesign --force --deep --sign - "$OUT" >/dev/null 2>&1 || \
  echo "  ! could not sign; run: codesign --force --deep --sign - \"$OUT\""

echo
echo "Built: $OUT"
echo "Run it:  open \"$OUT\""

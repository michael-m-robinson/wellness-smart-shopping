#!/usr/bin/env python3
"""Rename and re-skin the macOS shopping app bundle.

The desktop app ships as a compiled bundle, so its built-in text cannot be
changed from here -- but its *name* and its *picture* can, because the app
loads that picture from its own Resources folder by filename. Swapping the file
swaps what the app shows.

    python3 personalize.py --list
    python3 personalize.py --app "/Applications/Smart Shopping List.app" \
                           --name "Wellness Smart Shopping" --theme farm-market

A timestamped backup is taken before anything is touched, and the bundle is
re-signed afterwards so macOS will still launch it.
"""

import argparse
import os
import plistlib
import re
import shutil
import subprocess
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dealcrawler import branding

# The compiled app loads its picture from its own Resources folder by a fixed
# filename, so we keep that filename and change only the file's contents. The
# default below is the legacy name used by the original build; pass
# --image-resource if your bundle uses a different one.
DEFAULT_IMAGE_RESOURCE = "betty-1950s.png"


def find_app(explicit=None):
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    candidates = []
    for root in (os.path.dirname(HERE), "/Applications",
                 os.path.expanduser("~/Applications"),
                 os.path.expanduser("~/Downloads")):
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            if entry.endswith(".app") and os.path.isfile(
                    os.path.join(root, entry, "Contents", "Info.plist")):
                info = read_plist(os.path.join(root, entry, "Contents", "Info.plist"))
                ident = (info or {}).get("CFBundleIdentifier", "")
                if "smartshoppinglist" in ident.lower():
                    candidates.append(os.path.join(root, entry))
    return candidates[0] if candidates else None


def read_plist(path):
    try:
        with open(path, "rb") as fh:
            return plistlib.load(fh)
    except Exception:
        return None


def make_icns(src_png, dest_icns):
    """Build an .icns from a PNG using the macOS tools that ship with the OS."""
    iconset = dest_icns.replace(".icns", ".iconset")
    if os.path.isdir(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset)
    try:
        for size in (16, 32, 64, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                px = size * scale
                out = os.path.join(iconset, f"icon_{size}x{size}{suffix}.png")
                # -Z fits the longest side, -c pads to a square canvas
                subprocess.run(["sips", "-s", "format", "png", "-Z", str(px),
                                src_png, "--out", out],
                               check=True, capture_output=True)
                subprocess.run(["sips", "-c", str(px), str(px), out],
                               check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", dest_icns],
                       check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ! could not rebuild the icon ({exc}); leaving the old one")
        return False
    finally:
        shutil.rmtree(iconset, ignore_errors=True)


def resign(app):
    """Editing a bundle breaks its signature; ad-hoc re-sign so it still opens."""
    try:
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app],
                       check=True, capture_output=True)
        print("  re-signed the bundle (ad-hoc)")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ! could not re-sign ({exc}). If macOS refuses to open the app, run:")
        print(f'      codesign --force --deep --sign - "{app}"')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", help="path to the .app bundle (auto-detected if omitted)")
    ap.add_argument("--name", help="new display name for the app")
    ap.add_argument("--theme", help="theme image to show inside the app")
    ap.add_argument("--icon", action="store_true", help="also rebuild the app icon")
    ap.add_argument("--list", action="store_true", help="list available themes")
    ap.add_argument("--image-resource", default=DEFAULT_IMAGE_RESOURCE,
                    help="filename of the picture inside the bundle's Resources")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        print("Available themes:")
        for t in branding.themes():
            print(f"  {t['name']:14} {t['description']}")
        return 0

    app = find_app(args.app)
    if not app:
        print("Could not find the shopping app bundle. Pass --app /path/to/App.app",
              file=sys.stderr)
        return 1
    print(f"App: {app}")

    if not args.no_backup:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{app.rstrip('/')}.{stamp}.backup"
        shutil.copytree(app, backup, symlinks=True)
        print(f"  backed up to {backup}")

    contents = os.path.join(app, "Contents")
    changed = False

    # --- picture -----------------------------------------------------------
    if args.theme:
        src = os.path.join(branding.THEME_DIR, f"{args.theme}.png")
        if not os.path.isfile(src):
            print(f"  ! no theme called {args.theme!r}; try --list", file=sys.stderr)
            return 1
        dest = os.path.join(contents, "Resources", args.image_resource)
        if not os.path.isfile(dest):
            print(f"  ! this bundle has no {args.image_resource} to replace")
        else:
            shutil.copyfile(src, dest)
            print(f"  image  -> {args.theme}")
            changed = True
        if args.icon:
            icns = os.path.join(contents, "Resources", "AppIcon.icns")
            if os.path.isfile(icns) and make_icns(src, icns):
                print(f"  icon   -> {args.theme}")
                changed = True

    # --- name --------------------------------------------------------------
    if args.name:
        plist_path = os.path.join(contents, "Info.plist")
        info = read_plist(plist_path) or {}
        info["CFBundleName"] = args.name
        info["CFBundleDisplayName"] = args.name
        slug = re.sub(r"[^a-z0-9]+", "", args.name.lower()) or "app"
        info["CFBundleIdentifier"] = f"org.wellnesssmartshopping.{slug}"
        with open(plist_path, "wb") as fh:
            plistlib.dump(info, fh)
        print(f"  name   -> {args.name}")
        changed = True

        new_path = os.path.join(os.path.dirname(app.rstrip("/")), f"{args.name}.app")
        if os.path.abspath(new_path) != os.path.abspath(app):
            if os.path.exists(new_path):
                print(f"  ! {new_path} already exists; leaving the folder name alone")
            else:
                os.rename(app, new_path)
                app = new_path
                print(f"  bundle -> {new_path}")

    if changed:
        resign(app)
        print("\nDone. If the app was open, quit and reopen it to see the change.")
    else:
        print("\nNothing to change. Pass --name and/or --theme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

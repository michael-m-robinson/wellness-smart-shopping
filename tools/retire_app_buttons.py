#!/usr/bin/env python3
"""Retire the desktop app's obsolete built-in coupon controls.

The bundled app predates this project and carries its own "Find Official
Offers" / coupon-import panel. That flow is superseded by the control panel,
but the app ships as a compiled binary with no source, so the button cannot be
deleted -- deleting it means changing code, and there is no code to change.

What *can* be done safely is relabelling it in place. Swift keeps a string
literal's length as an immediate in the instruction stream and the bytes in
__TEXT,__cstring, so a replacement of exactly the same byte length is a safe,
layout-preserving edit: the worst case is odd-looking text, never a crash.
Replacements shorter than the original are padded with spaces to match.

    python3 tools/retire_app_buttons.py --app "/Applications/Your App.app"
    python3 tools/retire_app_buttons.py --app ... --restore

A timestamped backup is taken first and the bundle is re-signed afterwards.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys

# original -> replacement. Replacements must not exceed the original length;
# they are space-padded to match it exactly.
RETIREMENTS = [
    (b"Find Official Offers",
     b"Use Control Panel"),
    (b"Scans accessible official offers and applies strong item matches to the "
     b"estimate. For BJ's or ShopRite, Connect opens the official sign-in page "
     b"and keeps its session cookie; this app never reads or stores the "
     b"password. Found-offer quantity limits are honored; manual values apply "
     b"per package.",
     b"Retired. Run 'python3 panel.py' and press How to Scan for step-by-step, "
     b"per-store directions on reading a store's coupon list from your "
     b"signed-in browser, then Import Sales XML here."),
    (b"Import coupon text copied from the selected official store page",
     b"Retired - use the control panel, then Import Sales XML"),
    (b"Sign in on the official page, open its coupon list, then Scan All Offers "
     b"(it auto-scrolls the whole list). Passwords stay inside the retailer page.",
     b"Retired. The control panel's How to Scan explains this per store, and "
     b"writes a file you import below."),
]


def exe_path(app: str):
    macos = os.path.join(app, "Contents", "MacOS")
    if not os.path.isdir(macos):
        return None
    for entry in os.listdir(macos):
        full = os.path.join(macos, entry)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def resign(app: str):
    try:
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app],
                       check=True, capture_output=True)
        print("  re-signed the bundle (ad-hoc)")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ! could not re-sign ({exc}). Run this yourself:")
        print(f'      codesign --force --deep --sign - "{app}"')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True, help="path to the .app bundle")
    ap.add_argument("--restore", metavar="BACKUP",
                    help="restore the binary from a backup taken earlier")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    exe = exe_path(args.app)
    if not exe:
        print(f"No executable found inside {args.app}", file=sys.stderr)
        return 1

    if args.restore:
        if not os.path.isfile(args.restore):
            print(f"No such backup: {args.restore}", file=sys.stderr)
            return 1
        shutil.copyfile(args.restore, exe)
        print(f"Restored {exe} from {args.restore}")
        resign(args.app)
        return 0

    data = bytearray(open(exe, "rb").read())
    changes, missing = [], []

    for original, replacement in RETIREMENTS:
        if len(replacement) > len(original):
            print(f"  ! replacement longer than original, skipping: "
                  f"{replacement[:40]!r}", file=sys.stderr)
            continue
        idx = data.find(original)
        if idx < 0:
            # Already patched, or a build that never had this string.
            missing.append(original[:46].decode(errors="replace"))
            continue
        if data.count(original) != 1:
            print(f"  ! {original[:40]!r} appears more than once; skipping")
            continue
        padded = replacement + b" " * (len(original) - len(replacement))
        assert len(padded) == len(original)
        changes.append((idx, original, padded))

    for text in missing:
        print(f"  - not found (already retired?): {text}...")

    if not changes:
        print("\nNothing to change.")
        return 0

    print(f"\n{len(changes)} string(s) to retire in {os.path.basename(exe)}:")
    for idx, original, padded in changes:
        print(f"  0x{idx:06x}  {original[:44].decode(errors='replace')}...")
        print(f"         -> {padded.strip().decode(errors='replace')[:44]}...")

    if args.dry_run:
        print("\nDry run; nothing written.")
        return 0

    # Keep the backup OUTSIDE the bundle: anything left inside gets swept into
    # the code signature and bloats the app.
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(
        os.path.dirname(os.path.abspath(args.app.rstrip("/"))),
        f"{os.path.basename(args.app.rstrip('/'))}.binary.{stamp}.bak")
    shutil.copyfile(exe, backup)
    print(f"\n  backed up binary to {backup}")

    for idx, original, padded in changes:
        data[idx:idx + len(original)] = padded

    mode = os.stat(exe).st_mode
    with open(exe, "wb") as fh:
        fh.write(bytes(data))
    os.chmod(exe, mode)
    print(f"  patched {len(changes)} string(s)")
    resign(args.app)
    print("\nDone. Quit and reopen the app to see the change.")
    print(f"To undo:  python3 tools/retire_app_buttons.py --app \"{args.app}\" "
          f"--restore \"{backup}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

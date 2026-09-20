#!/usr/bin/env python3
"""Retire the desktop app's obsolete built-in coupon controls.

The bundled app predates this project and carries its own "Find Official
Offers" / coupon-import panel. That flow is superseded by the control panel,
but the app ships as a compiled binary with no source, so the button cannot be
deleted -- deleting it means changing code, and there is no code to change.

Two things can be done safely from outside the binary.

Relabelling it in place: Swift keeps a string literal's length as an immediate
in the instruction stream and the bytes in __TEXT,__cstring, so a replacement of
exactly the same byte length is a layout-preserving edit -- the worst case is
odd-looking text, never a crash. Shorter replacements are space-padded to match.

Neutering it: relabelling alone leaves the coupon engine running, so a button
reading "Scan with Claude" still fetched and scraped store pages. Pointing its
scrape targets at about:blank makes the retired feature genuinely inert rather
than misleadingly alive. Pass --keep-scraper to relabel without this.

    python3 tools/retire_app_buttons.py --app "/Applications/Your App.app"
    python3 tools/retire_app_buttons.py --app ... --restore

A timestamped backup is taken first and the bundle is re-signed afterwards.
"""

import argparse
import datetime
import re
import os
import shutil
import subprocess
import sys

# --- exact replacements -----------------------------------------------------
# original -> replacement. Replacements must not exceed the original length;
# they are space-padded to match it exactly.
RETIREMENTS = [
    (b"Find & Apply Coupons...", b"Scan with Claude..."),
    (b"Find Official Offers", b"Use Control Panel"),
    (b", use Find & Apply Coupons ", b", use Scan with Claude "),
    (b"Import coupon text copied from the selected official store page",
     b"Retired - use the control panel, then Import Sales XML"),
    (b"Sign in on the official page, open its coupon list, then Scan All Offers "
     b"(it auto-scrolls the whole list). Passwords stay inside the retailer page.",
     b"Retired. The control panel's How to Scan explains this per store, and "
     b"writes a file you import below."),
    (b"Scans accessible official offers and applies strong item matches to the "
     b"estimate. For BJ's or ShopRite, Connect opens the official sign-in page "
     b"and keeps its session cookie; this app never reads or stores the "
     b"password. Found-offer quantity limits are honored; manual values apply "
     b"per package.",
     b"Retired. Run 'python3 panel.py' and press How to Scan for step-by-step, "
     b"per-store directions on reading a store's coupon list from your "
     b"signed-in browser, then Import Sales XML here."),
    (b"Scanned the full page but found no strong shopping-list matches. Open the "
     b"coupon list (not the store home page), then scan again.",
     b"Retired. Use the control panel: 'python3 panel.py' > How to Scan, then "
     b"Import Sales XML here."),
    (b"Apply ShopRite web-circular sales?", b"Retired - scan with Claude"),
    (b"ShopRite Weekly Sales - public circular", b"Retired - scan with Claude"),
    (b"Matched from this week's public ShopRite circular. These are advertised "
     b"sale prices (savings estimated vs. the app's normal price), not card-clip "
     b"digital coupons ",
     b"Retired. Scan the store with Claude for its own numbers, then use Import "
     b"Sales XML. "),
]

# --- prefix rules -----------------------------------------------------------
# Some strings embed the town the original build was made for. Matching them by
# a neutral prefix means this file never has to carry anybody's address, and the
# rule still works on a build personalised for somewhere else.
PREFIX_RULES = [
    (b"Local Coupon Finder & Applier - ",
     b"Deals are scanned from your signed-in browser"),
    (b"Ready to check ",
     b"Run 'python3 panel.py' and press How to Scan. Claude reads the coupon "
     b"list from the store page you are signed in to."),
    (b"Read this week's ShopRite circular from a public deals site",
     b"Retired. Deals no longer come from third-party coupon sites. Scan your "
     b"store with Claude instead, then use Import Sales XML below."),
]

# --- neutering --------------------------------------------------------------
# Relabelling alone leaves the coupon engine running: the buttons still fetch
# store pages and scrape them. Pointing its scrape targets at about:blank makes
# the retired feature genuinely inert instead of misleadingly alive. The item
# source links in the price book are deliberately left alone.
SCRAPE_URLS = [
    b"https://www.bjs.com/deals",
    b"https://www.costco.com/o/-/warehouse-savings",
    b"https://stewleonards.com/stews-flyer/",
    b"https://www.shoprite.com/",
]
BLANK = b"about:blank"

# Status text from the scraper, so a dead feature reads as dead.
SCRAPER_TEXT = [
    (b"Check ShopRite Web Sales", b"Retired"),
    (b"Finding this week's ShopRite deals page...",
     b"Retired - use the control panel"),
    (b"Scanned the ShopRite deals page but nothing mapped to your shopping list "
     b"this week.",
     b"Retired. Run 'python3 panel.py' and press Scan with Claude."),
    (b"No items mapped to your list on this page. Scroll to the deals section, "
     b"then Scan Sales again.",
     b"Retired. Scanning now happens in the control panel: python3 panel.py"),
    (b"This week's public ShopRite deals. Once it finishes loading, choose Scan "
     b"Sales to read the advertised prices (not card-clip coupons).",
     b"Retired. This page no longer loads. Run 'python3 panel.py', press Scan "
     b"with Claude, and import the file it writes."),
]

# --- pattern rules ----------------------------------------------------------
# Store pickers in the original build are labelled with real branch addresses.
# Anyone handed the app would be reading a stranger's neighbourhood, so these
# are matched structurally and replaced with a neutral label.
LOCATION_PATTERNS = [
    (re.compile(rb"^[A-Z][A-Za-z.'\- ]{2,30} - store \d{1,6}$"), b"Your store"),
    (re.compile(rb"^[A-Z][A-Za-z.'\- ]{2,30} - \d{1,6} [A-Za-z.'\- ]{2,28}"
                rb"(?:Rd|Road|St|Street|Ave|Avenue|Blvd|Hwy|Pike|Way|Ln|Dr)$"),
     b"Your local branch"),
]

# A store link pinned to one branch is likewise personal; keep the chain only.
URL_PATTERNS = [
    (re.compile(rb"^https://www\.shoprite\.com/sm/planning/rsid/\d+/[^\s]*$"),
     b"https://www.shoprite.com/"),
    # Stop the app reaching third-party coupon blogs at all.
    (re.compile(rb"^https://(?:www\.)?livingrichwithcoupons\.com/[^\s]*$"),
     b"https://www.shoprite.com/"),
]


def _printable_strings(data: bytes):
    """Every printable, NUL-terminated run in the binary, with its offset."""
    for m in re.finditer(rb"[\x20-\x7e]{6,400}", data):
        yield m.start(), m.group(0)


def build_rules(data: bytes, neuter: bool = True):
    """Exact rules, plus any prefix/pattern matches found in this binary."""
    rules = list(RETIREMENTS)
    if neuter:
        rules.extend(SCRAPER_TEXT)
        for url in SCRAPE_URLS:
            rules.append((url, BLANK))
    for prefix, replacement in PREFIX_RULES:
        idx = data.find(prefix)
        if idx < 0:
            continue
        end = idx
        while end < len(data) and 0x20 <= data[end] <= 0x7E:
            end += 1
        rules.append((data[idx:end], replacement))
    for off, text in _printable_strings(data):
        for pattern, replacement in LOCATION_PATTERNS + URL_PATTERNS:
            if pattern.match(text):
                rules.append((text, replacement))
                break
    # Longest first so a rule can never be shadowed by a substring of itself.
    seen, ordered = set(), []
    for original, replacement in sorted(rules, key=lambda r: -len(r[0])):
        if original in seen:
            continue
        seen.add(original)
        ordered.append((original, replacement))
    return ordered


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
    ap.add_argument("--keep-scraper", action="store_true",
                    help="relabel only; leave the old coupon scraper working")
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

    for original, replacement in build_rules(bytes(data), neuter=not args.keep_scraper):
        if len(replacement) > len(original):
            print(f"  ! replacement longer than original, skipping: "
                  f"{replacement[:40]!r}", file=sys.stderr)
            continue
        idx = data.find(original)
        if idx < 0:
            # Already patched, or a build that never had this string.
            missing.append(original[:46].decode(errors="replace"))
            continue
        padded = replacement + b" " * (len(original) - len(replacement))
        assert len(padded) == len(original)
        start = 0
        while True:
            at = data.find(original, start)
            if at < 0:
                break
            changes.append((at, original, padded))
            start = at + len(original)

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

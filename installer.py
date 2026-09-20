#!/usr/bin/env python3
"""Wellness Smart Shopping - setup wizard.

Checks what this machine already has, offers to set up what is missing, builds
the desktop app, and leaves you with a working control panel.

    python3 installer.py            # the wizard
    python3 installer.py --check    # report only, change nothing
    python3 installer.py --yes      # accept every prompt (skips nothing risky)

Nothing is installed without asking, nothing needs sudo, and every step can be
declined -- a declined step only removes the feature it belongs to.
"""

import argparse
import json
import plistlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
EXTENSION_ID = "fcoeoabgfenejglbffodgkkbkcdhcgfn"
EXTENSION_URL = f"https://chromewebstore.google.com/detail/{EXTENSION_ID}"
CHROME_URL = "https://www.google.com/chrome/"
MIN_PY = (3, 9)

TTY = sys.stdout.isatty()
def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if TTY else text
BOLD = lambda t: _c("1", t)
DIM = lambda t: _c("2", t)
GREEN = lambda t: _c("32", t)
YELLOW = lambda t: _c("33", t)
RED = lambda t: _c("31", t)

OK, WARN, BAD = GREEN("ok"), YELLOW("--"), RED("!!")

state = {"steps": [], "assume_yes": False, "check_only": False}


# ----------------------------------------------------------------- utilities
def heading(step, total, title):
    print()
    print(BOLD(f"  Step {step}/{total}  {title}"))
    print(DIM("  " + "-" * (len(title) + 14)))


def report(mark, label, detail=""):
    print(f"    [{mark}] {label}" + (DIM(f"  {detail}") if detail else ""))


def ask(question, default=True):
    if state["check_only"]:
        return False
    if state["assume_yes"]:
        print(f"    {question} {DIM('[auto-yes]')}")
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"    {question} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer.startswith("y")


def run(cmd, **kw):
    # PYTHONDONTWRITEBYTECODE: --check promises to change nothing, and stray
    # __pycache__ directories are still a change.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.update(kw.pop("env", {}))
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                              env=env, **kw)
    except (OSError, subprocess.SubprocessError):
        return None


def which(name):
    return shutil.which(name)


def open_url(url):
    subprocess.run(["open", url], capture_output=True)


# -------------------------------------------------------------------- checks
def check_macos():
    mac = platform.mac_ver()[0]
    if not mac:
        report(BAD, "macOS", f"this is {platform.system()}; the desktop app is macOS only")
        return False, mac
    major = int(mac.split(".")[0])
    good = major >= 13
    report(OK if good else WARN, f"macOS {mac}",
           "" if good else "the desktop app wants 13 or newer")
    return good, mac


def check_python():
    version = sys.version_info
    good = (version.major, version.minor) >= MIN_PY
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    report(OK if good else BAD, label,
           sys.executable if good else f"need {MIN_PY[0]}.{MIN_PY[1]} or newer")
    return good, f"{version.major}.{version.minor}.{version.micro}"


def check_swift():
    path = which("swiftc")
    if not path:
        report(WARN, "Swift toolchain", "missing - only needed to build the app")
        return False, ""
    result = run(["swiftc", "--version"])
    version = ""
    if result and result.returncode == 0:
        first = result.stdout.splitlines()[0] if result.stdout else ""
        version = first.strip()
    report(OK, "Swift toolchain", version)
    return True, version


# The extension runs in any Chromium-family browser, so accepting only Google
# Chrome reports a false alarm for anyone using Edge, Brave or Arc.
CHROMIUM_BROWSERS = [
    ("Google Chrome", "Google Chrome.app"),
    ("Microsoft Edge", "Microsoft Edge.app"),
    ("Brave", "Brave Browser.app"),
    ("Arc", "Arc.app"),
    ("Chromium", "Chromium.app"),
]


def check_chrome():
    found = []
    for label, bundle in CHROMIUM_BROWSERS:
        for root in ("/Applications", os.path.expanduser("~/Applications")):
            path = os.path.join(root, bundle)
            if not os.path.isdir(path):
                continue
            plist = os.path.join(path, "Contents", "Info.plist")
            result = run(["/usr/libexec/PlistBuddy", "-c",
                          "Print :CFBundleShortVersionString", plist])
            version = result.stdout.strip() if result and result.returncode == 0 else ""
            found.append(f"{label} {version}".strip())
            break
    if found:
        report(OK, "Chromium browser", ", ".join(found))
        return True, ", ".join(found)
    report(WARN, "Chromium browser", "none found - needed only for scanning")
    return False, ""


def check_extension():
    """Look for the extension in the Chromium-family profiles on this machine."""
    roots = [
        "~/Library/Application Support/Google/Chrome",
        "~/Library/Application Support/Chromium",
        "~/Library/Application Support/BraveSoftware/Brave-Browser",
        "~/Library/Application Support/Microsoft Edge",
        "~/Library/Application Support/Arc",
    ]
    for root in roots:
        base = os.path.expanduser(root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, _ in os.walk(base):
            if dirpath.count(os.sep) - base.count(os.sep) > 3:
                dirnames[:] = []
                continue
            if EXTENSION_ID in dirnames:
                report(OK, "Claude for Chrome", os.path.basename(root))
                return True, os.path.basename(root)
    report(WARN, "Claude for Chrome", "not detected - needed for scanning")
    return False, ""


# ------------------------------------------------------------- one copy only
# Two installed copies of the same app is a real trap: you open one, it is the
# old build, and nothing you changed appears. The identifier is matched rather
# than the name so a bundle renamed with build.sh is still recognised.
OUR_IDENTIFIER_PREFIX = "org.wellnesssmartshopping."
LEGACY_IDENTIFIERS = ("local.codex.smartshoppinglist",)
CANONICAL_DIR = os.path.expanduser("~/Applications")

SEARCH_ROOTS = ["/Applications", "~/Applications", "~/Desktop", "~/Downloads",
                "~/dev", "~/Documents"]


LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks"
              "/LaunchServices.framework/Support/lsregister")


def unregister(app):
    """Drop it from LaunchServices too, or macOS keeps offering the ghost in
    Launchpad, Spotlight and Open With long after the files are gone."""
    if os.path.exists(LSREGISTER):
        subprocess.run([LSREGISTER, "-u", app], capture_output=True)


def bundle_identifier(app):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as fh:
            return str(plistlib.load(fh).get("CFBundleIdentifier", ""))
    except Exception:
        return ""


def find_installed_copies():
    """Every copy on this machine: (path, identifier, is_ours).

    The staging copy under app/build counts. It was excluded once on the
    grounds that it is only what we install *from* -- but macOS indexes it like
    any other app, so it showed up as a second entry in Launchpad. If it is on
    disk, it is a copy.
    """
    found = {}
    roots = [os.path.expanduser(r) for r in SEARCH_ROOTS]
    roots.append(os.path.dirname(HERE))
    roots.append(os.path.join(HERE, "app", "build"))
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, _ in os.walk(root):
            if dirpath.count(os.sep) - root.count(os.sep) > 2:
                dirnames[:] = []
                continue
            for name in list(dirnames):
                if not name.endswith(".app"):
                    continue
                path = os.path.realpath(os.path.join(dirpath, name))
                ident = bundle_identifier(path)
                if ident.startswith(OUR_IDENTIFIER_PREFIX):
                    found[path] = (ident, True)
                elif ident in LEGACY_IDENTIFIERS:
                    found[path] = (ident, False)
            dirnames[:] = [d for d in dirnames if not d.endswith(".app")]
    return [(p, i, ours) for p, (i, ours) in sorted(found.items())]


def step_one_copy(step, total):
    heading(step, total, "Making sure there is only one copy")
    copies = find_installed_copies()
    ours = [p for p, _, mine in copies if mine]
    legacy = [(p, i) for p, i, mine in copies if not mine]

    if not ours:
        report(WARN, "installed app", "none yet - build and install it above")
    canonical = os.path.join(CANONICAL_DIR, "Wellness Smart Shopping.app")
    for path in ours:
        if os.path.realpath(path) == os.path.realpath(canonical):
            report(OK, "kept", path)
        else:
            report(WARN, "duplicate", path)

    extras = [p for p in ours if os.path.realpath(p) != os.path.realpath(canonical)]
    if extras and os.path.isdir(canonical):
        if state["check_only"]:
            report(WARN, "duplicates", f"{len(extras)} would be removed")
        elif ask(f"Remove {len(extras)} duplicate cop{'y' if len(extras) == 1 else 'ies'}? "
                 f"(the one in Applications is kept)", default=True):
            for path in extras:
                unregister(path)
                shutil.rmtree(path, ignore_errors=True)
                report(OK, "removed", path)
    elif extras:
        report(WARN, "duplicates", "keeping them: nothing is installed in Applications yet")

    if legacy:
        print()
        print("    Older builds of the original app are also on this machine.")
        print("    They are a different app, and yours to keep or remove:")
        for path, ident in legacy:
            report(WARN, "older build", path)
        if not state["check_only"] and ask("Remove those too?", default=False):
            for path, _ in legacy:
                unregister(path)
                shutil.rmtree(path, ignore_errors=True)
                report(OK, "removed", path)
    return True


# --------------------------------------------------------------------- steps
def step_prerequisites(step, total):
    heading(step, total, "Checking what you already have")
    mac_ok, mac = check_macos()
    py_ok, py = check_python()
    swift_ok, swift = check_swift()
    chrome_ok, chrome = check_chrome()
    ext_ok, ext = check_extension()
    state["detected"] = {"macOS": mac, "python": py, "swift": swift,
                         "chrome": chrome, "extension": ext}

    if not py_ok:
        print()
        print(RED("    Python 3.9+ is required and this interpreter is older."))
        print("    Install the Xcode command line tools (which include python3):")
        print(BOLD("      xcode-select --install"))
        return False

    if not swift_ok:
        print()
        print("    The Swift toolchain builds the desktop app. Without it you can")
        print("    still run the control panel and produce a sales file.")
        if ask("Run 'xcode-select --install' now? (opens Apple's installer)", default=True):
            subprocess.run(["xcode-select", "--install"], capture_output=True)
            print(YELLOW("    Apple's installer is opening. Finish it, then run this again."))
            return False

    if not chrome_ok and ask("Open the Chrome download page?", default=True):
        open_url(CHROME_URL)
    if not ext_ok and ask("Open the Claude for Chrome extension page?", default=True):
        open_url(EXTENSION_URL)
    return True


def step_config(step, total):
    heading(step, total, "Setting up your files")
    # Only config.json is seeded. branding.json is deliberately NOT created:
    # copying every default into it would shadow future defaults, which is a
    # bug this project already had once. The panel writes it on first Save,
    # containing only what you actually changed.
    made = []
    for example, real in (("config.example.json", "config.json"),):
        src, dst = os.path.join(HERE, example), os.path.join(HERE, real)
        if os.path.exists(dst):
            report(OK, real, "already yours - left alone")
            continue
        if not os.path.exists(src):
            report(WARN, real, f"no {example} to copy")
            continue
        if state["check_only"]:
            report(WARN, real, "would be created")
            continue
        shutil.copyfile(src, dst)
        made.append(real)
        report(OK, real, f"created from {example}")

    report(OK, "branding.json", "left to the control panel - it saves only your changes")

    for folder in ("harvest", "out"):
        path = os.path.join(HERE, folder)
        if os.path.isdir(path):
            report(OK, f"{folder}/", "exists")
        elif state["check_only"]:
            report(WARN, f"{folder}/", "would be created")
        else:
            os.makedirs(path, exist_ok=True)
            report(OK, f"{folder}/", "created")
    return True


def step_build(step, total):
    heading(step, total, "Building the desktop app")
    build = os.path.join(HERE, "app", "build.sh")
    if not os.path.isfile(build):
        report(WARN, "app/build.sh", "not present - skipping")
        return True
    if not which("swiftc"):
        report(WARN, "Swift toolchain", "missing - skipping the build")
        return True
    if state["check_only"]:
        report(WARN, "desktop app", "would be built")
        return True
    if not ask("Build the desktop app now? (about a minute)", default=True):
        report(WARN, "desktop app", "skipped")
        return True

    print(DIM("    compiling, this takes a moment ..."))
    result = subprocess.run([build], capture_output=True, text=True, cwd=os.path.dirname(build))
    if result.returncode != 0:
        report(BAD, "build failed")
        print(DIM((result.stderr or result.stdout or "").strip()[-600:]))
        return True
    app = os.path.join(HERE, "app", "build", "Wellness Smart Shopping.app")
    report(OK, "built", app)
    state["built_app"] = app

    if ask("Install it to your Applications folder?", default=True):
        target_dir = CANONICAL_DIR
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, os.path.basename(app))
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(app, target, symlinks=True)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", target],
                       capture_output=True)
        report(OK, "installed", target)
        state["installed_app"] = target
        # The build output is only a staging copy; leaving it behind is how
        # you end up with two apps and no idea which one you just opened.
        unregister(app)
        shutil.rmtree(app, ignore_errors=True)
        report(OK, "build output cleared", "so only the installed copy remains")
    return True


def step_verify(step, total):
    heading(step, total, "Checking it works")
    tests = os.path.join(HERE, "test_crawler.py")
    if not os.path.isfile(tests):
        report(WARN, "tests", "not present")
        return True
    # The suite exercises this wizard, so running it from here would recurse.
    if os.environ.get("WSS_SKIP_TESTS"):
        report(OK, "test suite", "skipped - already running inside it")
        return True
    result = run([sys.executable, tests], cwd=HERE)
    if result is None:
        report(WARN, "tests", "could not run")
        return True
    tail = (result.stderr or "").strip().splitlines()
    summary = next((line for line in reversed(tail) if line.startswith("Ran ")), "")
    if result.returncode == 0:
        report(OK, "test suite", summary or "passed")
    else:
        report(BAD, "test suite", summary or "failed")

    # Fall back to the installed copy, so skipping the build still verifies
    # the app that is actually on this machine.
    app = state.get("installed_app") or state.get("built_app")
    if not app or not os.path.isdir(app):
        app = os.path.join(CANONICAL_DIR, "Wellness Smart Shopping.app")
    if not os.path.isdir(app):
        installed = [p for p, _, ours in find_installed_copies() if ours]
        app = installed[0] if installed else None
    if app:
        binary = os.path.join(app, "Contents", "MacOS", "SmartShoppingList")
        if os.path.isfile(binary):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                pdfs = [os.path.join(tmp, f"{n}.pdf") for n in "abc"]
                result = run([binary, "--self-test", *pdfs])
                ok = result is not None and result.returncode == 0
                report(OK if ok else BAD, "app self-test",
                       "planner, recipes, PDFs and XML import" if ok else "failed")
    return True


def step_finish(step, total):
    heading(step, total, "Ready")
    detected = state.get("detected", {})
    if not state["check_only"]:
        path = os.path.join(HERE, "requirements", "detected.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("Detected on this machine\n========================\n\n")
            for key, value in detected.items():
                fh.write(f"{key:12} {value or '(not found)'}\n")
            fh.write("\nPython packages required: none (standard library only)\n")
        report(OK, "requirements/detected.txt", "written")

    print()
    print(BOLD("    You're set up. From here:"))
    print()
    print("      1. Start the control panel:")
    print(BOLD("         python3 panel.py") + DIM("   (or double-click Start Panel.command)"))
    print("      2. Press " + BOLD("Scan with Claude") + ", pick a store, and follow the steps.")
    print("      3. Import the file it writes into the desktop app.")
    print()
    if state.get("installed_app"):
        print(DIM(f"      The app is at {state['installed_app']}"))
        print(DIM("      Its Scan with Claude button can start the panel for you."))
    print()

    if not state["check_only"] and ask("Start the control panel now?", default=True):
        panel = os.path.join(HERE, "panel.py")
        if os.path.isfile(panel):
            subprocess.Popen([sys.executable, panel], cwd=HERE)
            print(GREEN("    Started. It will open in your browser."))
    return True


# ---------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--yes", action="store_true", help="accept every prompt")
    args = ap.parse_args(argv)
    state["check_only"] = args.check
    state["assume_yes"] = args.yes and not args.check

    print()
    print(BOLD("  Wellness Smart Shopping - setup"))
    print(DIM("  Eat well on what's actually on sale this week."))
    print()
    print("  No Python packages are needed: everything here is standard library.")
    print("  This wizard checks the few tools that are, and sets the rest up.")
    if args.check:
        print(YELLOW("  Check only - nothing will be changed."))

    steps = [step_prerequisites, step_config, step_build, step_one_copy,
             step_verify, step_finish]
    total = len(steps)
    for index, step in enumerate(steps, start=1):
        try:
            if not step(index, total):
                print()
                print(YELLOW("  Stopped. Fix the item above and run this again."))
                return 1
        except KeyboardInterrupt:
            print()
            print(YELLOW("  Cancelled. Nothing further was changed."))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

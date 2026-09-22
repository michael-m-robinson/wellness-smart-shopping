"""Where the code lives, and where your files live.

These are the same directory when you run from a clone, and different when the
app is installed: everything inside `Wellness Smart Shopping.app` is read-only
and code-signed, so writing your config, scans and sales files in there would
either fail or break the signature.

  SOURCE_DIR  the code and the things that ship with it (themes, examples)
  DATA_DIR    your files: config.json, branding.json, profile.json,
              harvest/ and out/
  DEALS_DIR   the sales files a scan produces: ~/Documents/Deals, where
              they are easy to find and import

Set WSS_DATA_DIR to put your files anywhere you like. Sales files always go
to ~/Documents/Deals unless WSS_DEALS_DIR says otherwise.
"""

import os

SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_SUPPORT = os.path.expanduser("~/Library/Application Support/Wellness Smart Shopping")


def enclosing_app_bundle(path):
    """The .app this path sits inside, if any."""
    current = os.path.abspath(path)
    while current != os.path.dirname(current):
        if current.endswith(".app"):
            return current
        current = os.path.dirname(current)
    return None


def _resolve_data_dir():
    override = os.environ.get("WSS_DATA_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    # Installed: the bundle is read-only, so your files go to Application Support.
    if enclosing_app_bundle(SOURCE_DIR):
        return APP_SUPPORT
    # A clone you can write to: keep everything together, as before.
    return SOURCE_DIR


DATA_DIR = _resolve_data_dir()
IS_BUNDLED = enclosing_app_bundle(SOURCE_DIR) is not None


DOCUMENTS_DEALS = os.path.expanduser("~/Documents/Deals")


def _resolve_deals_dir():
    # Always Documents > Deals -- even when the desktop app starts the panel
    # with its own WSS_DATA_DIR -- unless WSS_DEALS_DIR says otherwise.
    override = os.environ.get("WSS_DEALS_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return DOCUMENTS_DEALS


DEALS_DIR = _resolve_deals_dir()


def friendly(path):
    """~/Documents/Deals -> "Documents > Deals"; anything else as a ~ path."""
    home = os.path.expanduser("~")
    path = os.path.abspath(path)
    if path.startswith(home + os.sep):
        rel = path[len(home) + 1:]
        return " > ".join(rel.split(os.sep)) if rel.startswith("Documents") else "~/" + rel
    return path


def data(*parts):
    return os.path.join(DATA_DIR, *parts)


def source(*parts):
    return os.path.join(SOURCE_DIR, *parts)


def ensure_data_dir():
    """Create DATA_DIR and seed it from what shipped, the first time."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for folder in ("harvest", "out", "themes"):
        os.makedirs(data(folder), exist_ok=True)
    seed = source("config.example.json")
    target = data("config.json")
    if os.path.isfile(seed) and not os.path.exists(target):
        import shutil
        shutil.copyfile(seed, target)
    return DATA_DIR

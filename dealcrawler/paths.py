"""Where the code lives, and where your files live.

These are the same directory when you run from a clone, and different when the
app is installed: everything inside `Wellness Smart Shopping.app` is read-only
and code-signed, so writing your config, scans and sales files in there would
either fail or break the signature.

  SOURCE_DIR  the code and the things that ship with it (themes, examples)
  DATA_DIR    your files: config.json, branding.json, profile.json,
              harvest/ and out/

Set WSS_DATA_DIR to put your files anywhere you like.
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

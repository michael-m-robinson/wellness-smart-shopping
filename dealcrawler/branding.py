"""Branding: every piece of user-facing text and imagery, in one place.

Nothing in the product is hard-coded to one household, one name or one picture.
`branding.json` (git-ignored, yours) overrides `branding.example.json`, and any
key you leave out falls back to the default below. Add your own image to
`themes/` and it shows up in the picker automatically.
"""

import json
import os
from typing import Dict, List

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_DIR = os.path.join(HERE, "themes")
USER_FILE = os.path.join(HERE, "branding.json")
EXAMPLE_FILE = os.path.join(HERE, "branding.example.json")

# Every string the control panel can show. Override any of them in branding.json.
DEFAULTS: Dict[str, str] = {
    "app_name": "Wellness Smart Shopping",
    "tagline": "Eat well on what's actually on sale this week",
    "greeting": "Let's shop well this week",
    "greeting_morning": "Good morning - let's shop well",
    "greeting_afternoon": "Good afternoon - let's shop well",
    "greeting_evening": "Good evening - let's plan the week",
    "use_time_greeting": True,

    "deals_header": "This week's deals, matched to your list",
    "deals_empty": "No deals matched your staples yet. Try Refresh Deals.",
    "signin_header": "These stores need you signed in",
    "signin_body": ("Grocers show their coupons only to a signed-in session. "
                    "Open the store, sign in, then refresh."),
    "themes_header": "Choose a look",
    "output_header": "Files ready to import",

    "refresh_button": "Refresh Deals",
    "refresh_working": "Checking stores...",
    "import_button": "How to Import",
    "save_button": "Save",

    "import_title": "Importing into your shopping app",
    "import_steps": [
        "Open the Wellness Smart Shopping desktop app.",
        "Choose Import Sales XML... from the menu.",
        "Pick the newest file from the out/ folder listed below.",
        "The app re-prices your list and re-ranks recipes around the deals.",
        "Clip any store-account coupons in your store account - the file tells "
        "the app what a deal is worth, it cannot clip it for you.",
    ],
    "import_note": "Advertised prices change. Always check your receipt.",

    "footer": "Free and open source. Bring your own stores and accounts.",
    "theme": "farm-market",
}


def _read(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load() -> dict:
    """Defaults <- branding.example.json <- branding.json."""
    merged = dict(DEFAULTS)
    merged.update(_read(EXAMPLE_FILE))
    merged.update(_read(USER_FILE))
    return merged


def save(updates: dict) -> dict:
    """Persist overrides to branding.json, keeping anything already there."""
    current = _read(USER_FILE)
    for key, value in updates.items():
        if key in DEFAULTS and value is not None:
            current[key] = value
    with open(USER_FILE, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return load()


def greeting(brand: dict, hour: int) -> str:
    """Time-aware greeting, unless the user pinned a fixed one."""
    if not brand.get("use_time_greeting", True):
        return brand.get("greeting", DEFAULTS["greeting"])
    if hour < 12:
        key = "greeting_morning"
    elif hour < 17:
        key = "greeting_afternoon"
    else:
        key = "greeting_evening"
    return brand.get(key) or brand.get("greeting", DEFAULTS["greeting"])


def themes() -> List[dict]:
    """Every image in themes/ -- bundled or one the user dropped in."""
    described = {}
    meta = os.path.join(THEME_DIR, "THEMES.json")
    if os.path.exists(meta):
        try:
            with open(meta) as fh:
                described = json.load(fh)
        except (OSError, ValueError):
            described = {}
    out = []
    if os.path.isdir(THEME_DIR):
        for fname in sorted(os.listdir(THEME_DIR)):
            stem, ext = os.path.splitext(fname)
            if ext.lower() not in (".png", ".jpg", ".jpeg"):
                continue
            out.append({
                "name": stem,
                "file": fname,
                "description": described.get(stem, "Your own image"),
                "bundled": stem in described,
            })
    return out

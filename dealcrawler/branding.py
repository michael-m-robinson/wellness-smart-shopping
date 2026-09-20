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

    # Shown above the shopping list. Pick one of the presets or write your own.
    "list_message": "Good food, brighter days.",
    "list_message_presets": [
        "Good food, brighter days.",
        "Stronger, healthier, happier you.",
        "Progress looks good on you.",
        "Eat well. Spend less. Feel better.",
        "Small choices, every week.",
        "Real food, real savings.",
        "This week's plan, sized to you.",
    ],

    "deals_header": "This week's deals, matched to your list",
    "deals_empty": "No deals matched your staples yet. Try Refresh Deals.",
    "signin_header": "These stores need you signed in",
    "signin_body": ("Grocers show their coupons only to a signed-in session. "
                    "Open the store, sign in, then refresh."),
    "themes_header": "Choose a look",
    "output_header": "Files ready to import",

    "targets_header": "Your daily target",
    "targets_note": ("Calories use the Mifflin-St Jeor equation with your "
                     "activity level. Planning guidance only - it cannot account "
                     "for medication, health history or body composition. If you "
                     "have medical needs, use your clinician's numbers."),
    "targets_note_partial": ("Add your age for a target based on the Mifflin-St "
                             "Jeor equation. Showing a size-only estimate."),
    "profile_title": "Set your daily targets",
    "profile_intro": ("A couple of details set your calorie and macro targets, "
                      "so the shopping list is sized to you. Saved on this "
                      "machine only, and you can change it whenever you like."),
    "profile_edit_button": "Edit",
    "profile_save_button": "Save targets",
    "scan_button": "How to Scan",
    "refresh_button": "Refresh Deals",
    "refresh_working": "Checking stores...",
    "import_button": "How to Import",
    "save_button": "Save",

    "scan_title": "Scanning a store for deals",
    "scan_intro": ("Every deal comes from a store page you are signed in to - "
                   "this app never contacts a store itself. Scanning reads the "
                   "visible coupon list from the tab you already have open, so "
                   "no password ever leaves the store site."),
    "scan_steps": [
        "Sign in to the store in Chrome.",
        "Open its weekly ad or digital coupon list and scroll once so every "
        "offer loads.",
        "Ask Claude, with the Claude for Chrome extension enabled: "
        "\"run browser/harvest.js on this tab\".",
        "Claude scrolls the whole list and prints one offer per line. Save that "
        "as harvest/<store>.txt - the exact path is shown per store below.",
        "Press Refresh Deals. The scan is turned into XML you import.",
    ],
    "scan_note": ("If a page says you are signed out, sign in and open the "
                  "coupon list again - harvest.js will tell you rather than "
                  "return an empty list."),

    "import_title": "Importing into your shopping app",
    "import_steps": [
        "Open the Wellness Smart Shopping desktop app.",
        "Choose Import Sales XML... from the menu.",
        "Pick the newest file from the out/ folder listed below.",
        "The app re-prices your list and re-ranks recipes around the deals.",
        "Store-account coupons still need clipping in your store account - "
        "the file tells the app what a deal is worth, it cannot clip it.",
    ],
    "import_note": "Advertised prices change. Always check your receipt.",

    "footer": "Free and open source. Bring your own stores and accounts.",
    "theme": "50s-1",
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
            if os.path.isdir(os.path.join(THEME_DIR, fname)):
                continue
            stem, ext = os.path.splitext(fname)
            if ext.lower() not in (".png", ".jpg", ".jpeg"):
                continue
            thumb = os.path.join(THEME_DIR, "thumbs", f"{stem}.jpg")
            out.append({
                "name": stem,
                "file": fname,
                "thumb": f"thumbs/{stem}.jpg" if os.path.isfile(thumb) else fname,
                "description": described.get(stem, "Your own image"),
                "bundled": stem in described,
            })
    return out

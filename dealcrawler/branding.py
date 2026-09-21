"""Branding: every piece of user-facing text and imagery, in one place.

Nothing in the product is hard-coded to one household, one name or one picture.
`branding.json` (git-ignored, yours) overrides `branding.example.json`, and any
key you leave out falls back to the default below. Add your own image to
`themes/` and it shows up in the picker automatically.
"""

import json
import os
from typing import Dict, List

from . import paths

HERE = paths.SOURCE_DIR
THEME_DIR = paths.source("themes")
# Your own images live beside your other files, not inside the app bundle.
USER_THEME_DIR = paths.data("themes")
USER_FILE = paths.data("branding.json")
EXAMPLE_FILE = paths.source("branding.example.json")

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
    # Claude for Chrome. A page cannot reliably detect an extension -- the
    # resources it exposes are content-hashed and change on every release -- so
    # this informs rather than claims, and can be dismissed for good.
    "extension_id": "fcoeoabgfenejglbffodgkkbkcdhcgfn",
    "extension_url": ("https://chromewebstore.google.com/detail/"
                      "fcoeoabgfenejglbffodgkkbkcdhcgfn"),
    "extension_title": "Scanning needs the Claude for Chrome extension",
    "extension_body": ("Scan with Claude reads deals from the store page you "
                       "are signed in to, which the Claude for Chrome extension "
                       "makes possible. Everything else here works without it."),
    "extension_wrong_browser": ("This browser cannot run the Claude for Chrome "
                                "extension. Open the panel in Google Chrome to "
                                "use Scan with Claude."),
    "extension_install": "Get the extension",
    "extension_have": "I already have it",

    "scan_button": "Scan with Claude",
    "scan_help_button": "How to Scan",

    # The wizard. {store} and {path} are filled in for the chosen store.
    "scan_pick_title": "Which store shall I scan?",
    "scan_pick_intro": ("Pick a store, sign in to it, and Claude will read this "
                        "week's deals straight off the page."),
    "scan_wait_title": "Scanning {store}",
    "scan_prompt": ("Run browser/harvest.js on this page to scan it for deals. "
                    "It sends the result to my control panel on its own."),
    "scan_wait_body": ("Open the store below and sign in, then give Claude this "
                       "instruction. The scan comes straight back here - there "
                       "is no file to save."),
    "scan_waiting": "Waiting for the scan to finish...",
    "scan_paste_label": "Claude printed the offers instead? Paste them here",
    "scan_paste_button": "Use these offers",
    "scan_done_title": "{store}: {count} deals found",
    "scan_done_body": "Your sales file is ready. Import it now?",
    "scan_none_title": "{store}: nothing matched",
    "scan_none_body": ("The scan came through, but none of the offers matched "
                       "the staples on your list. That just means a quiet week "
                       "at this store."),
    "scan_import_now": "Import deals now",
    "scan_import_later": "Not now",
    "scan_later_title": "Saved for later",
    "scan_later_body": ("No problem - your deals are saved and will keep. When "
                        "you're ready, open the app, choose Import Sales XML..., "
                        "and pick this file:"),
    "scan_imported_body": ("Opened the app and revealed the file in Finder. "
                           "Choose Import Sales XML... and pick:"),
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
        "Claude scrolls the whole list and sends the offers straight to this "
        "panel. If it cannot reach it, it prints them instead - paste those "
        "into the box in the Scan window.",
        "The panel picks them up and turns them into a file you import.",
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
    """Defaults <- branding.json.

    branding.example.json is a copy-me template, deliberately NOT part of this
    chain: when it was, a stale checked-in copy silently shadowed newly added
    defaults, so the app showed old wording that no longer existed in the code.
    """
    merged = dict(DEFAULTS)
    merged.update(_read(USER_FILE))
    return merged


def write_example() -> str:
    """Regenerate the template from DEFAULTS so the two cannot drift."""
    payload = {"_comment": "Copy this to branding.json and change anything. "
                           "Every string here is yours to edit.",
               **DEFAULTS}
    with open(EXAMPLE_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return EXAMPLE_FILE


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
    """Every image on offer: the ones that shipped, plus any you added.

    Yours win on a name clash, so dropping in `farm-market.jpg` replaces the
    bundled one rather than showing twice.
    """
    described = {}
    meta = os.path.join(THEME_DIR, "THEMES.json")
    if os.path.exists(meta):
        try:
            with open(meta) as fh:
                described = json.load(fh)
        except (OSError, ValueError):
            described = {}

    out, seen = [], set()
    for folder, is_users in ((USER_THEME_DIR, True), (THEME_DIR, False)):
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if os.path.isdir(os.path.join(folder, fname)):
                continue
            stem, ext = os.path.splitext(fname)
            if ext.lower() not in (".png", ".jpg", ".jpeg") or stem in seen:
                continue
            seen.add(stem)
            thumb = os.path.join(folder, "thumbs", f"{stem}.jpg")
            # THEMES.json entries are {description, focus}; older files held
            # just the description string, so accept both.
            entry = described.get(stem)
            if isinstance(entry, dict):
                description = entry.get("description", "Your own image")
                focus = entry.get("focus", 50)
            else:
                description = entry or "Your own image"
                focus = 50
            out.append({
                "name": stem,
                "file": fname,
                "thumb": f"thumbs/{stem}.jpg" if os.path.isfile(thumb) else fname,
                "dir": folder,
                "mine": is_users,
                "description": description,
                "focus": focus,
                "bundled": stem in described and not is_users,
            })
    return sorted(out, key=lambda t: t["name"])

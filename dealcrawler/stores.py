"""Store definitions.

Deals are read from your signed-in browser by the Claude for Chrome extension,
never fetched by this program. That means a store needs no code here -- only a
name and the pages worth scanning. Add any grocer to `config.json` and it works.

Each store's scan lands in `harvest/<key>.txt`, which is what the crawler reads.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List

from . import paths

HERE = paths.SOURCE_DIR
HARVEST_DIR = paths.data("harvest")

# Sensible starting points. Everything here is overridable in config.json, and
# `store_id` is templated into the URLs so you point at your own branch.
# A store can carry its own instruction. Where a site needs particular handling
# -- a widget in a cross-origin frame, an infinite scroll that has to be driven
# -- a generic "read the page" prompt quietly returns a fraction of the offers,
# so the specifics are written down per store. {submit} is filled in with the
# panel's own address. Stores without one get GENERIC_PROMPT.
SHOPRITE_PROMPT = """Scan the ShopRite digital coupons page for offers.

Don't scroll this page - the coupons sit in a cross-origin iframe that blocks
JS, the accessibility tree and the network log. Instead open the widget
standalone at https://shop-rite-web-prod.azurewebsites.net/ (it keeps my store
context), then drive its infinite scroll by setting .scrollable-container
scrollTop to scrollHeight repeatedly until .card.coupon-item stops growing.

Read the DOM: .coupon-savings, .coupon-desc (the full text is there; the
ellipsis is CSS only) and .coupon-badge for "Limit N".

Emit one line per offer:  product name | $X.XX off | limit
- price is the discount amount
- limit is the "Limit N" badge, or "no limit" if the page says none
- for the product name, drop the leading "Save $X.XX on/when you buy ONE (1)"
  and cut at "(excludes", "*Redeem", or a repeated "Save $" tail
- sanity check: your line count and your "Limit" count must match the page's
  own "All Coupons (N)" and its "Limit" count

Then POST the lines as plain text to {submit}
Probe that endpoint first. If it is not reachable, say so and show me the list
rather than dropping it."""

GENERIC_PROMPT = """Scan this page for grocery deals.

Load every offer first - if the list scrolls or pages, keep going until it
stops growing. Then emit one line per offer:  product name | price | limit
- price is the sale price, or the discount if that is what is shown
- limit is the purchase cap if the page gives one, otherwise "no limit"
- keep the product name as written, minus any "Save $X.XX on" preamble
- sanity check your count against any total the page states

Then POST the lines as plain text to {submit}
Probe that endpoint first. If it is not reachable, say so and show me the list
rather than dropping it."""

DEFAULT_STORES: Dict[str, dict] = {
    "shoprite": {
        "name": "ShopRite",
        "store_id": "000",
        "prompt": SHOPRITE_PROMPT,
        "urls": [
            {"label": "Open the digital coupon list",
             "url": "https://www.shoprite.com/sm/planning/rsid/{store_id}/digital-coupon"},
        ],
    },
    "stews": {
        "name": "Stew Leonard's",
        "urls": [{"label": "Open the weekly flyer",
                  "url": "https://stewleonards.com/stews-flyer/"}],
    },
    "costco": {
        "name": "Costco",
        "urls": [{"label": "Open warehouse savings",
                  "url": "https://www.costco.com/o/-/warehouse-savings"}],
    },
}


@dataclass
class Store:
    key: str
    name: str
    urls: List[dict] = field(default_factory=list)
    enabled: bool = True
    prompt: str = ""

    def instruction(self, submit: str, script: str = "", override: str = "") -> str:
        """What to give Claude, with the panel's address filled in.

        `override` is branding.json's scan_prompt: when set it is used for
        every store. Otherwise the store's own prompt is used -- a generic
        "read this page" instruction quietly returns a fraction of the offers
        on a site like ShopRite, whose coupons sit in a cross-origin iframe --
        and GENERIC_PROMPT covers stores that define none.

        Substitution is plain replacement, not str.format -- a prompt naming a
        CSS selector or a snippet of JS is full of braces.
        """
        template = override or self.prompt or GENERIC_PROMPT
        for token, value in (("{submit}", submit), ("{script}", script),
                             ("{store}", self.name),
                             ("{path}", self.harvest_path)):
            template = template.replace(token, value)
        return template

    @property
    def harvest_path(self) -> str:
        return os.path.join(HARVEST_DIR, f"{self.key}.txt")

    @property
    def scanned(self) -> bool:
        return os.path.isfile(self.harvest_path)

    @property
    def scanned_at(self):
        if not self.scanned:
            return None
        import datetime
        return datetime.datetime.fromtimestamp(os.path.getmtime(self.harvest_path))

    @property
    def scan_age_hours(self):
        at = self.scanned_at
        if at is None:
            return None
        import datetime
        return (datetime.datetime.now() - at).total_seconds() / 3600.0

    @property
    def command(self) -> str:
        return f"python3 crawl.py --harvest {self.key}=<your scan file>"


def load(config: dict = None) -> List[Store]:
    """Stores from config, falling back to the defaults for anything omitted."""
    config = config or {}
    configured = config.get("stores") or {}
    keys = list(dict.fromkeys(list(DEFAULT_STORES) + list(configured)))

    out = []
    for key in keys:
        base = dict(DEFAULT_STORES.get(key, {}))
        base.update({k: v for k, v in (configured.get(key) or {}).items()
                     if not k.startswith("_")})
        if not base.get("enabled", True):
            continue
        store_id = str(base.get("store_id", ""))
        urls = []
        for entry in base.get("urls", []):
            if isinstance(entry, str):
                entry = {"label": "Open the store", "url": entry}
            url = str(entry.get("url", ""))
            if "{store_id}" in url:
                if not store_id or store_id == "000":
                    # Unconfigured branch: still show it, but say so.
                    url = url.replace("{store_id}", store_id or "000")
                else:
                    url = url.replace("{store_id}", store_id)
            urls.append({"label": entry.get("label", "Open the store"), "url": url})
        out.append(Store(key=key, name=base.get("name", key.title()), urls=urls,
                         prompt=str(base.get("prompt", "") or "")))
    return out


def get(key: str, config: dict = None):
    for store in load(config):
        if store.key == key:
            return store
    return None

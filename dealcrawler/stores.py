"""Store definitions.

Deals are read from your signed-in browser by the Scanner extension (or Claude),
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

STEWS_PROMPT = """Scan Stew Leonard's weekly specials.

Don't use the flyer on stewleonards.com - it and its print view are page
images with no text. The same specials are listed as products in Stew's online
shop. Open https://shopnow.stewleonards.com/store/stew-leonards/storefront and
follow its "This Week's Specials" link (.../collections/rc-weekly-specials-...;
the address changes every week). No sign-in is needed.

Scroll the window to the bottom, wait about 1.5s, and repeat until the number of
product cards ([role="group"][aria-label="Product"]) stops growing - about 120.

For each card read the image alt text (the product name), a size line such as
"16 oz" if there is one, and the two screen-reader lines: "Current price: $2.49
per pound" and, on most cards, "Original Price: $3.99 per pound". Ignore the
rounded "Save $1" badge.

Emit one line per product:  name, size | $X.XX/lb, was $Y.YY/lb | no limit
- write /lb for "per pound", "each" for "each (estimated)"; leave out ", was"
  when there is no original price
- Stew's shows no purchase limits, so the limit is always "no limit"

Then POST the lines as plain text to {submit}
Probe that endpoint first. If it is not reachable, say so and show me the list
rather than dropping it."""

COSTCO_PROMPT = """Scan Costco's warehouse savings.

Open https://www.costco.com/o/-/warehouse-savings - it is public, no sign-in.
Offers are grouped by department ([data-testid^="coupon-set-"]); scroll once
to the bottom so every group renders.

Each offer card holds: the name, often a size ("14 oz"), "Item 1244454",
"Limit 5.", and a price in one of two forms:
- "Save $6.80"                    -> write "Save $6.80"
- "$15.99" then "After $6 OFF"    -> write "$15.99 after $6.00 off"
A few cards show their price only in the picture; skip those and say how many.

Emit one line per offer:  name, size | price as above | Limit N
- limit is the "Limit N" in the card, or "no limit" if it states none

Then POST the lines as plain text to {submit}
Probe that endpoint first. If it is not reachable, say so and show me the list
rather than dropping it."""

# What a shopper needs to know or do for a store's deals to count at the
# register. Shown after a scan (panel and toolbar popup), in the app's import
# preview and on the shopping list PDF; the app keeps matching wording in
# redeemNotice() in app/main.swift.
#   level      "action" (do something first) or "info" (good to know)
#   signed_in  the wording once the Scanner can see you are logged in
SHOPRITE_REDEEM = {
    "level": "action",
    "title": "Almost there! Log in to ShopRite to use these coupons",
    "body": ("You must be logged in to ShopRite, because it's the only way you "
             "can load coupons to your account. Once you're in, open Digital "
             "Coupons and tap Load to Card on each coupon below. We only read "
             "the list, so the loading is yours to do - and any coupon you skip "
             "rings up at the regular price."),
    "signed_in": {
        "title": "You're logged in - nice! Now load your coupons",
        "body": ("Open ShopRite's Digital Coupons and tap Load to Card on each "
                 "coupon below. A coupon only comes off at the register once "
                 "it's on your account."),
    },
    "link": {"label": "Open my ShopRite coupons",
             "url": "https://www.shoprite.com/sm/planning/rsid/{store_id}/digital-coupon"},
}

# From Costco's own terms on the savings page: "instant savings", "Active
# Costco membership required for warehouse purchases", per-household limits,
# some promotions online only.
COSTCO_REDEEM = {
    "level": "info",
    "title": "Good news - no clipping at Costco",
    "body": ("Costco calls these instant savings: there are no coupons to clip "
             "or load. You just need an active Costco membership when you shop "
             "in the warehouse. Limits are per household, and a few deals are "
             "online only, so give each one a quick look before you go."),
}

# Stew's weekly specials are the week's prices. The online specials list the
# scan reads carries every discounted item in the printed flyer except a
# handful (checked 2026-09-21: 3 of the flyer's sale items were missing, none
# of them staples), so it is where to send people. Flyer "APP DEAL" items are
# app-only, and the flyer says how they apply: "Scan your Member ID or enter
# your phone number at checkout and these offers will automatically be applied!"
STEWS_REDEEM = {
    "level": "info",
    "title": "Good news - no coupons to clip at Stew's",
    "body": ("These are simply this week's sale prices, and you'll find them all "
             "in one place on Stew's website. For anything marked APP DEAL, just "
             "scan your Member ID in the free Stew Leonard's app (or give your "
             "phone number) at checkout and the deal is applied for you."),
    # "scanned": link to the exact page the Scanner read, when there is one.
    "link": {"label": "See this week's specials",
             "url": "https://shopnow.stewleonards.com/store/stew-leonards/storefront",
             "scanned": True},
}

DEFAULT_STORES: Dict[str, dict] = {
    "shoprite": {
        "name": "ShopRite",
        "store_id": "000",
        "prompt": SHOPRITE_PROMPT,
        # The Scanner extension's site file (extension/sites/<adapter>.js).
        # A store without one is read by the generic site.
        "adapter": "shoprite",
        "redeem": SHOPRITE_REDEEM,
        "urls": [
            {"label": "Open the digital coupon list",
             "url": "https://www.shoprite.com/sm/planning/rsid/{store_id}/digital-coupon"},
        ],
    },
    "stews": {
        "name": "Stew Leonard's",
        "prompt": STEWS_PROMPT,
        "adapter": "stews",
        "redeem": STEWS_REDEEM,
        # The flyer on stewleonards.com is images; the shop lists the same
        # specials as text.
        "urls": [{"label": "Open this week's specials",
                  "url": "https://shopnow.stewleonards.com/store/stew-leonards/storefront"}],
    },
    "costco": {
        "name": "Costco",
        "prompt": COSTCO_PROMPT,
        "adapter": "costco",
        "redeem": COSTCO_REDEEM,
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
    adapter: str = ""
    redeem: dict = field(default_factory=dict)

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
                         prompt=str(base.get("prompt", "") or ""),
                         adapter=str(base.get("adapter", "") or ""),
                         redeem=_redeem(base.get("redeem"), store_id)))
    return out


def _redeem(value, store_id: str) -> dict:
    """A store's redeem notice, cleaned, with links pointed at the configured branch."""
    if not isinstance(value, dict) or not value.get("title"):
        return {}
    out = {"level": "action" if value.get("level") == "action" else "info",
           "title": str(value["title"]), "body": str(value.get("body", ""))}
    link = value.get("link")
    if isinstance(link, dict) and link.get("url"):
        out["link"] = {"label": str(link.get("label", "Open")),
                       "url": str(link["url"]).replace("{store_id}", store_id or "000")}
        if link.get("scanned"):
            out["link"]["scanned"] = True
    for part, keys in (("signed_in", ("title", "body")),):
        sub = value.get(part)
        if isinstance(sub, dict) and sub.get("title"):
            out[part] = {k: str(sub.get(k, "")) for k in keys}
    return out


def get(key: str, config: dict = None):
    for store in load(config):
        if store.key == key:
            return store
    return None

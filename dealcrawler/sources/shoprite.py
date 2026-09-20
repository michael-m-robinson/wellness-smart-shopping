"""ShopRite weekly circular and digital coupons.

shoprite.com serves its circular and coupon list only to a signed-in,
JavaScript-rendered session and blocks plain HTTP clients, so there are two
paths:

  1. A public weekly-ad summary, which needs no account and is what the
     free/offline mode uses.
  2. browser/harvest.js run against your signed-in ShopRite coupon page, which
     is the only way to see account-clipped digital coupons.
"""

import html as _html
import re
from typing import List

from .. import fetch
from ..matcher import match
from ..offers import Offer, extract

STORE = "ShopRite"
# Public weekly-ad roundup; no account required.
PUBLIC_URL = "https://www.livingrichwithcoupons.com/category/stores/shoprite"
CACHE = "shoprite-lrwc.html"
# Your own store's coupon page. store_id comes from config.json.
COUPON_URL = ("https://www.shoprite.com/sm/planning/rsid/{store_id}"
              "/digital-coupon?cfrom=homenavigation")
CIRCULAR_URL = "https://www.shoprite.com/sm/planning/rsid/{store_id}/weekly-ad"

RE_TAG = re.compile(r"(?i)</?(div|li|article|section|p|br|h[1-6]|tr|td|span)[^>]*>")
RE_ANY_TAG = re.compile(r"<[^>]+>")


def _text_blocks(html: str) -> List[str]:
    text = RE_TAG.sub("\n", html)
    text = RE_ANY_TAG.sub(" ", text)
    text = _html.unescape(text).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", b).strip() for b in text.split("\n")]


# Roundup blurbs pack several products into one line ("Eggo Waffles just $2.49
# + Free 6 ct Eggs"). Splitting on these separators keeps each price attached to
# the product it actually belongs to instead of the next product along.
RE_PHRASE_SPLIT = re.compile(r"\s*(?:[+,;]|\band\b|\bplus\b|\bwith\b)\s*", re.I)


def parse_public(html: str, per_weight: str = "convert") -> List[Offer]:
    offers: List[Offer] = []
    for block in _text_blocks(html):
        # A usable circular line needs a product and a price on the same line.
        if not (6 < len(block) < 400) or "$" not in block:
            continue
        for phrase in RE_PHRASE_SPLIT.split(block):
            phrase = phrase.strip()
            # The price has to sit in the same phrase as the product name.
            if not (6 < len(phrase) < 180) or "$" not in phrase:
                continue
            # "Free X" gives no usable per-package number for X.
            if re.search(r"(?i)\bfree\b", phrase):
                continue
            item_id = match(phrase)
            if not item_id:
                continue
            offer = extract(item_id, STORE, phrase, phrase,
                            source_url=PUBLIC_URL, per_weight=per_weight)
            if offer:
                offers.append(offer)
    return offers


def crawl(refresh: bool = False, per_weight: str = "convert") -> List[Offer]:
    page = fetch.get(PUBLIC_URL, CACHE, store=STORE, refresh=refresh)
    return parse_public(page.html, per_weight=per_weight)


def signin_urls(store_id: str) -> List[str]:
    return [COUPON_URL.format(store_id=store_id), CIRCULAR_URL.format(store_id=store_id)]

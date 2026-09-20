"""Costco warehouse savings.

Costco publishes the current warehouse/instant-savings book as escaped JSON
embedded in the public page, so this source works over plain HTTP. Member-only
pricing still requires a signed-in browser; see browser/harvest.js for that.
"""

import json
import re
from typing import List

from .. import fetch
from ..matcher import match
from ..offers import Offer, extract

STORE = "Costco"
URL = "https://www.costco.com/o/-/warehouse-savings"
CACHE = "costco-warehouse-savings.html"

# The embedded JSON lists one object per offer; we slice on the title key and
# read each offer's fields out of its own chunk, which survives the key order
# changing between Costco page builds.
RE_TITLE = re.compile(r'"cardDescription":"([^"]{3,200})"')
RE_VALUE = re.compile(r'"value":\["?([0-9]+(?:\.[0-9]{1,2})?)"?\]')
RE_HAS_OFF = re.compile(r'"has_off":(true|false)')
RE_DETAILS = re.compile(r'"offerDetails":"([^"]{0,120})"')
RE_DATES = re.compile(r'"validDatesOverride":"([^"]{0,160})"')
RE_APPLIC = re.compile(r'"applicability":"([^"]{0,40})"')


def _unescape(html: str) -> str:
    """The offer JSON is embedded backslash-escaped inside a script tag."""
    return html.replace('\\"', '"').replace("\\\\", "\\").replace("\\/", "/")


def parse(html: str, per_weight: str = "convert") -> List[Offer]:
    text = _unescape(html)
    marks = [m for m in RE_TITLE.finditer(text)]
    offers: List[Offer] = []
    for i, m in enumerate(marks):
        title = m.group(1)
        chunk = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else m.end() + 6000]

        # Skip online-only offers: the app plans an in-store trip.
        applic = RE_APPLIC.search(chunk)
        if applic and applic.group(1) == "online_only":
            continue

        item_id = match(title)
        if not item_id:
            continue

        val = RE_VALUE.search(chunk)
        if not val:
            continue
        amount = val.group(1)
        has_off = RE_HAS_OFF.search(chunk)
        is_discount = bool(has_off and has_off.group(1) == "true")

        details = RE_DETAILS.search(chunk)
        dates = RE_DATES.search(chunk)
        detail = " ".join(b.group(1) for b in (details, dates) if b and b.group(1))

        # Feed the number back through the shared extractor so Costco offers get
        # the same sanity caps and limit parsing as every other source.
        synth = f"${amount} off {title}" if is_discount else f"{title} ${amount}"
        offer = extract(item_id, STORE, title, f"{synth} {detail}",
                        source_url=URL, per_weight=per_weight)
        if offer:
            offer.note = title
            offers.append(offer)
    return offers


def crawl(refresh: bool = False, per_weight: str = "convert") -> List[Offer]:
    page = fetch.get(URL, CACHE, store=STORE, refresh=refresh)
    return parse(page.html, per_weight=per_weight)

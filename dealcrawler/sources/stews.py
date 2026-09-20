"""Stew Leonard's weekly flyer.

stewleonards.com returns HTTP 403 to plain HTTP clients and renders its flyer
in JavaScript, so this store is browser-harvest only: run browser/harvest.js on
the flyer page in your signed-in browser and feed the result back in with
`--harvest stews=<file>`.
"""

from typing import List

from .. import fetch
from ..offers import Offer

STORE = "Stew Leonard's"
FLYER_URL = "https://stewleonards.com/stews-flyer/"
CACHE = "stews-flyer.html"


def crawl(refresh: bool = False, per_weight: str = "convert") -> List[Offer]:
    # Attempt the public page anyway: if Stew Leonard's ever serves it to plain
    # clients this starts working with no code change. Otherwise fetch raises
    # NeedsSignIn and the CLI prints the browser-harvest instructions.
    page = fetch.get(FLYER_URL, CACHE, store=STORE, refresh=refresh)
    from .shoprite import parse_public
    offers = parse_public(page.html, per_weight=per_weight)
    for o in offers:
        o.store = STORE
        o.source_url = FLYER_URL
    return offers


def signin_urls(store_id: str = "") -> List[str]:
    return [FLYER_URL]

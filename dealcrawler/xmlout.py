"""Write sales XML in exactly the dialect Smart Shopping List imports.

The app does not use a real XML parser; it scans the text for <offer .../>
elements and pulls attributes out by hand. So this writer deliberately mirrors
the app's own built-in self-test fixture, byte pattern included:

    <shopriteSales store="ShopRite" date="2026-09-20">
      <offer itemId="turkey" savings="2.00" limit="4" note="93% lean ground turkey"/>
      <offer itemId="eggs" salePrice="2.49" limit="6" note="Large eggs 18ct"/>
    </shopriteSales>

One offer per line, attributes in that order, double quotes, self-closing.
Anything fancier risks the hand-rolled parser silently skipping an offer.
"""

import re
from datetime import date
from typing import Iterable, List

from .offers import Offer

# A hand-rolled attribute scanner has no chance against raw &, <, > or quotes,
# so note text is reduced to a safe ASCII subset rather than entity-escaped.
_UNSAFE = re.compile(r'[^A-Za-z0-9 ,.%/()+\-]')


def safe_note(text: str, limit: int = 90) -> str:
    text = (text or "").replace("&", "and").replace('"', "").replace("'", "")
    text = _UNSAFE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _root_for(store: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]", "", store).lower()
    return f"{slug or 'store'}Sales"


def render(store: str, offers: Iterable[Offer], on: date = None) -> str:
    on = on or date.today()
    offers = list(offers)
    root = _root_for(store)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<{root} store="{safe_note(store, 40)}" date="{on.isoformat()}">']
    for o in offers:
        attrs = [f'itemId="{o.item_id}"']
        if o.savings is not None:
            attrs.append(f'savings="{o.savings:.2f}"')
        elif o.sale_price is not None:
            attrs.append(f'salePrice="{o.sale_price:.2f}"')
        else:
            continue
        if o.limit:
            attrs.append(f'limit="{o.limit}"')
        if o.expires:
            attrs.append(f'expires="{o.expires}"')
        note = safe_note(o.note or o.title)
        if note:
            attrs.append(f'note="{note}"')
        lines.append("  <offer " + " ".join(attrs) + "/>")
    lines.append(f"</{root}>")
    return "\n".join(lines) + "\n"


def validate(xml: str) -> List[str]:
    """Re-read our own output the way the app would. Returns a list of problems."""
    from .catalog import VALID_IDS

    problems = []
    offers = re.findall(r"<offer\s([^>]*?)/>", xml)
    if not offers:
        problems.append("no <offer> elements found")
    for raw in offers:
        ident = re.search(r'itemId="([^"]*)"', raw)
        if not ident:
            problems.append(f"offer without itemId: {raw}")
            continue
        if ident.group(1) not in VALID_IDS:
            problems.append(f"itemId not in app catalog: {ident.group(1)}")
        has_sav = re.search(r'savings="([0-9.]+)"', raw)
        has_price = re.search(r'salePrice="([0-9.]+)"', raw)
        if not has_sav and not has_price:
            problems.append(f"offer has neither savings nor salePrice: {raw}")
        if has_sav and has_price:
            problems.append(f"offer has both savings and salePrice: {raw}")
    return problems

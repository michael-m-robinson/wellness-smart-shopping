"""Parse offer text harvested from a signed-in browser session.

Stores that hide their deals behind a login (ShopRite digital coupons, Stew
Leonard's flyer, Costco member pricing) cannot be read over plain HTTP. The
supported path is browser/harvest.js, which the Claude for Chrome extension
runs inside the page you are already signed in to. It writes one offer per
line; this module turns those lines into Offers.

Accepted line formats (whichever the page yields):
    Boneless Skinless Chicken Breast | $1.99/lb | Limit 4
    Nature's Own Bread | $1.00 off | Limit 4 | ends 2026-09-26
    Save $2.00 on 93% Lean Ground Turkey
    Large Eggs 18 ct $2.49
"""

import json
import re
import os
from typing import List

from ..matcher import match
from ..offers import Offer, extract


ENDS = re.compile(r"^\s*ends\s+(\d{4}-\d{2}-\d{2})\s*$", re.I)


def parse_lines(lines, store: str, per_weight: str = "convert") -> List[Offer]:
    offers: List[Offer] = []
    for raw in lines:
        line = (raw or "").strip()
        if len(line) < 6:
            continue
        # "| ends 2026-09-26": when the deal ends. Taken out before the price
        # is read, so a date can never be mistaken for a price or a limit.
        expires = ""
        if "|" in line:
            fields = [f for f in line.split("|")]
            kept = []
            for f in fields:
                m = ENDS.match(f)
                if m:
                    expires = m.group(1)
                else:
                    kept.append(f)
            line = "|".join(kept).strip()
        # "Title | price | limit" -> title is the first field, rest is detail.
        if "|" in line:
            head, _, rest = line.partition("|")
            title, detail = head.strip(), rest.replace("|", " ").strip()
        else:
            title, detail = line, line
        item_id = match(title) or match(line)
        if not item_id:
            continue
        offer = extract(item_id, store, title, detail, per_weight=per_weight)
        if offer:
            offer.expires = expires
            offers.append(offer)
    return offers


def parse_file(path: str, store: str, per_weight: str = "convert") -> List[Offer]:
    """Read a harvest file. Accepts plain text (one offer per line) or JSON."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        body = fh.read()

    body_strip = body.lstrip()
    if body_strip.startswith("[") or body_strip.startswith("{"):
        data = json.loads(body)
        if isinstance(data, dict):
            store = data.get("store", store)
            data = data.get("offers", [])
        lines = []
        for entry in data:
            if isinstance(entry, str):
                lines.append(entry)
            elif isinstance(entry, dict):
                lines.append(" | ".join(
                    str(entry.get(k, "")) for k in ("title", "price", "limit")
                    if entry.get(k)))
        return parse_lines(lines, store, per_weight)

    return parse_lines(body.splitlines(), store, per_weight)

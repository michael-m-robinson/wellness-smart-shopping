"""Map free-text store offer titles onto Smart Shopping List catalog IDs."""

import re
from typing import List, Optional

from .catalog import ITEMS, GLOBAL_EXCLUDE, TWIN_ONLY

_WS = re.compile(r"\s+")
_GLOBAL = [re.compile(p, re.I) for p in GLOBAL_EXCLUDE]

# Pre-compile per item so a full circular scan stays cheap.
_COMPILED = [
    (
        item,
        [re.compile(p, re.I) for p in item.require],
        [re.compile(p, re.I) for p in item.exclude],
    )
    for item in ITEMS
    if item.id not in TWIN_ONLY and item.require
]


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    return _WS.sub(" ", text).strip()


def match(text: str) -> Optional[str]:
    """Return the best catalog ID for an offer title, or None.

    Bias is deliberately toward None: an unmatched offer costs nothing, while a
    wrong match quietly corrupts the user's budget in the app.
    """
    if not text:
        return None
    t = normalize(text)
    if any(g.search(t) for g in _GLOBAL):
        return None

    best = None
    best_score = 0.0
    for item, requires, excludes in _COMPILED:
        if any(x.search(t) for x in excludes):
            continue
        hits = [r for r in requires if r.search(t)]
        if not hits:
            continue
        # Longer, more specific patterns win over generic single words.
        score = max(len(r.pattern) for r in hits) + (len(hits) - 1)
        if score > best_score:
            best, best_score = item.id, score
    return best


def match_all(text: str) -> List[str]:
    """Primary match plus any twin line items the same sale applies to."""
    from .catalog import BY_ID

    primary = match(text)
    if not primary:
        return []
    return [primary] + list(BY_ID[primary].twins)

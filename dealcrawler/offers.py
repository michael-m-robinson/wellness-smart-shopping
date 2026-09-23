"""Offer model: parsing advertised prices and turning them into app numbers."""

import re
from dataclasses import dataclass
from typing import List, Optional

from .catalog import BY_ID

# These mirror the regexes the Smart Shopping List app itself uses, so the
# crawler and the app agree on what a "$X off" or "limit N" looks like.
RE_LIMIT = re.compile(r"(?i)limit\s+([0-9]+)")
RE_OFF = re.compile(r"(?i)\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*off")
RE_SAVE = re.compile(r"(?i)save\s*\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
RE_AFTER = re.compile(r"(?i)after\s*\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:off|instant savings)")
RE_INSTANT = re.compile(
    r"(?i)\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*"
    r"(?:instant savings|digital coupon|coupon|manufacturer)"
)
RE_PRICE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
RE_PER_WEIGHT = re.compile(
    r"(?i)\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*/?\s*(?:per\s*)?(lb|lbs|pound|pounds|oz|ounce|ounces)\b"
)
# Coupon shorthand "$1/1" or "$2/2" = that many dollars off that many packages.
RE_COUPON_OFF = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*/\s*([0-9]{1,2})\b")
# "2 for $5" / "10 for $10"
RE_MULTI = re.compile(r"(?i)\b([0-9]{1,2})\s*(?:for|/)\s*\$\s*([0-9]+(?:\.[0-9]{1,2})?)")


@dataclass
class Offer:
    item_id: str
    store: str
    title: str
    savings: Optional[float] = None
    sale_price: Optional[float] = None
    limit: Optional[int] = None
    note: str = ""
    source_url: str = ""
    # why this number is what it is -- surfaced in --report, never in the XML
    basis: str = ""
    # last day the deal is good for, "YYYY-MM-DD" ("" when the page gave none)
    expires: str = ""

    @property
    def value(self) -> float:
        """Approximate per-package benefit, used only for ranking/dedupe."""
        if self.savings is not None:
            return self.savings
        item = BY_ID.get(self.item_id)
        if item and self.sale_price is not None:
            return max(0.0, item.price - self.sale_price)
        return 0.0


def parse_limit(text: str) -> Optional[int]:
    m = RE_LIMIT.search(text or "")
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:
        return None
    return n if 1 <= n <= 99 else None


def _package_units(item, unit: str) -> Optional[float]:
    """How many advertised units (lb/oz) are in one catalog package."""
    unit = unit.lower()
    if unit.startswith("lb") or unit.startswith("pound"):
        if item.lbs:
            return item.lbs
        if item.oz:
            return item.oz / 16.0
    if unit.startswith("oz") or unit.startswith("ounce"):
        if item.oz:
            return item.oz
        if item.lbs:
            return item.lbs * 16.0
    return None


def extract(item_id: str, store: str, title: str, detail: str = "",
            source_url: str = "", per_weight: str = "convert") -> Optional[Offer]:
    """Build an Offer from advertised text, or None if no usable number."""
    item = BY_ID.get(item_id)
    if item is None:
        return None
    blob = f"{title} {detail}".strip()
    limit = parse_limit(blob)

    def mk(**kw):
        return Offer(item_id=item_id, store=store, title=title.strip(),
                     limit=limit, note=_note(title, detail),
                     source_url=source_url, **kw)

    # 1. An explicit discount amount is the most reliable signal.
    for rx, why in ((RE_AFTER, "after $X off"), (RE_SAVE, "save $X"),
                    (RE_OFF, "$X off"), (RE_INSTANT, "instant savings")):
        m = rx.search(blob)
        if m:
            amt = float(m.group(1))
            if 0 < amt <= item.price * 0.95:
                return mk(savings=round(amt, 2), basis=why)
            if 0 < amt:
                # Discount exceeds the app's normal price -- almost always a
                # bulk/multi-pack offer. Cap rather than emit a bogus number.
                return mk(savings=round(item.price * 0.5, 2),
                          basis=f"{why} ${amt:.2f} capped at 50% of normal price")

    # 2. Per-weight advertised price -> per-package sale price.
    m = RE_PER_WEIGHT.search(blob)
    if m:
        if per_weight == "skip":
            return None
        units = _package_units(item, m.group(2))
        if not units:
            return None
        pkg = float(m.group(1)) * units
        if pkg >= item.price:
            return None
        return mk(sale_price=round(pkg, 2),
                  basis=f"${float(m.group(1)):.2f}/{m.group(2)} x {units:g} = ${pkg:.2f}/pkg")

    # 3. Coupon shorthand: "$1/1" -> $1.00 off one package.
    m = RE_COUPON_OFF.search(blob)
    if m:
        amt, qty = float(m.group(1)), int(m.group(2))
        if qty > 0:
            per = amt / qty
            if 0 < per <= item.price * 0.95:
                return mk(savings=round(per, 2),
                          basis=f"coupon ${amt:.2f}/{qty} = ${per:.2f} per package")

    # 4. "2 for $5" -> unit price.
    m = RE_MULTI.search(blob)
    if m:
        qty, total = int(m.group(1)), float(m.group(2))
        if qty > 0:
            unit_price = total / qty
            if unit_price < item.price:
                return mk(sale_price=round(unit_price, 2),
                          basis=f"{qty} for ${total:.2f} = ${unit_price:.2f} each")
            return None

    # 5. A bare price is a sale price only if it beats the app's normal price.
    m = RE_PRICE.search(blob)
    if m:
        price = float(m.group(1))
        if 0 < price < item.price:
            return mk(sale_price=round(price, 2), basis=f"advertised ${price:.2f}")
    return None


def _note(title: str, detail: str) -> str:
    note = title.strip()
    if detail and detail.strip() and detail.strip().lower() not in note.lower():
        note = f"{note} ({detail.strip()})"
    return note


def dedupe(offers: List[Offer]) -> List[Offer]:
    """Keep the single best offer per (item, store)."""
    best = {}
    for o in offers:
        key = (o.item_id, o.store)
        if key not in best or o.value > best[key].value:
            best[key] = o
    return sorted(best.values(), key=lambda o: (o.store, -o.value, o.item_id))


def mirror_twins(offers: List[Offer]) -> List[Offer]:
    """Apply a parent item's offer to its snack twin line items."""
    out = list(offers)
    seen = {(o.item_id, o.store) for o in offers}
    for o in offers:
        for twin in BY_ID[o.item_id].twins:
            if (twin, o.store) in seen:
                continue
            out.append(Offer(item_id=twin, store=o.store, title=o.title,
                             savings=o.savings, sale_price=o.sale_price,
                             limit=o.limit, note=o.note, source_url=o.source_url,
                             basis=f"mirrored from {o.item_id}", expires=o.expires))
            seen.add((twin, o.store))
    return out

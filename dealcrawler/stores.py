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
DEFAULT_STORES: Dict[str, dict] = {
    "shoprite": {
        "name": "ShopRite",
        "store_id": "000",
        "urls": [
            {"label": "Open the digital coupon list",
             "url": "https://www.shoprite.com/sm/planning/rsid/{store_id}/digital-coupon"},
            {"label": "Open the weekly ad",
             "url": "https://www.shoprite.com/sm/planning/rsid/{store_id}/weekly-ad"},
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
        out.append(Store(key=key, name=base.get("name", key.title()), urls=urls))
    return out


def get(key: str, config: dict = None):
    for store in load(config):
        if store.key == key:
            return store
    return None

"""HTTP fetching with caching and sign-in detection."""

import gzip
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")

# Signals that a page came back as a sign-in wall or a bot block rather than deals.
LOGIN_HINTS = [
    r"(?i)\bsign in\b", r"(?i)\blog ?in\b", r"(?i)create an account",
    r"(?i)access denied", r"(?i)are you a human", r"(?i)unusual traffic",
    r"(?i)enable javascript", r"(?i)pardon our interruption",
]


class NeedsSignIn(Exception):
    """Raised when a source can only be read from a signed-in browser session."""

    def __init__(self, store: str, url: str, reason: str):
        self.store, self.url, self.reason = store, url, reason
        super().__init__(f"{store}: {reason}")


@dataclass
class Page:
    url: str
    html: str
    from_cache: bool


def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name)


def get(url: str, cache_as: str, store: str = "", max_age_hours: float = 12.0,
        refresh: bool = False, timeout: int = 30) -> Page:
    """Fetch a URL, falling back to a cached copy; raise NeedsSignIn on a wall."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(cache_as)

    if not refresh and os.path.exists(path):
        age = (time.time() - os.path.getmtime(path)) / 3600.0
        if age <= max_age_hours:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return Page(url, fh.read(), True)

    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            html = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return Page(url, fh.read(), True)
        raise NeedsSignIn(
            store or url, url,
            f"the site returned HTTP {exc.code}; its deals are behind a sign-in "
            "or bot check and must be read from your signed-in browser",
        ) from exc
    except Exception as exc:  # network down, DNS, timeout
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return Page(url, fh.read(), True)
        raise NeedsSignIn(store or url, url, f"could not be reached ({exc})") from exc

    if len(html) < 20000 and any(re.search(p, html) for p in LOGIN_HINTS):
        raise NeedsSignIn(
            store or url, url,
            "the page came back as a sign-in / verification wall instead of deals",
        )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return Page(url, html, False)


def load_cached(cache_as: str) -> Optional[str]:
    path = _cache_path(cache_as)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()

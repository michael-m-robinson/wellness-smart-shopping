#!/usr/bin/env python3
"""Wellness Smart Shopping - control panel.

A small local web app: refresh this week's deals, see what matched, pick the
look, edit every greeting and header, and get step-by-step import help.

    python3 panel.py            # opens http://127.0.0.1:8765 in your browser
    python3 panel.py --port 9000 --no-open

Everything runs on your machine. Nothing is uploaded anywhere.
"""

import argparse
import datetime
import html
import json
import mimetypes
import os
import plistlib
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dealcrawler import (branding, offers as offers_mod, paths, profile as profile_mod,
                         stores as stores_mod, xmlout)
from dealcrawler.sources import harvest

OUT_DIR = paths.data("out")
paths.ensure_data_dir()

_state = {"running": False, "last": None}
_lock = threading.Lock()

# The panel should not outlive the window it serves. Each open panel page holds
# a live connection to /api/live; closing the tab or navigating away drops it,
# and the panel stops once none are left. There is no heartbeat: nothing is
# sent on a timer by the page. Nothing happens until the first page connects,
# so a panel started by the desktop app before any browser opens is left alone.
_alive = {"pages": 0, "seen": False, "empty_since": 0.0,
          # A scan happens in another tab, and the user may well close this
          # one to get at it. Shutting down mid-scan would throw the offers
          # away when the store page posts them back, so a scan in progress
          # holds the panel open.
          "scanning_since": 0.0}
_alive_lock = threading.Lock()
SCAN_HOLD_MAX = 45 * 60.0   # a scan left open forever should not pin it
# Filled in once the server binds, so the prompt carries the real port rather
# than an assumed one.
_base = {"url": "http://127.0.0.1:8765"}
CLOSE_GRACE = 3.0      # after the last page goes, this long for a reload to return
LIVE_PROBE = 1.0       # how often the server checks a live connection is still there


def _page_opened():
    with _alive_lock:
        _alive["pages"] += 1
        _alive["seen"] = True
        _alive["empty_since"] = 0.0


def _page_closed():
    with _alive_lock:
        _alive["pages"] = max(0, _alive["pages"] - 1)
        if _alive["pages"] == 0:
            _alive["empty_since"] = time.monotonic()


# ---- accepting scans -------------------------------------------------------
# What the switch on the panel reflects. This is written to disk rather than
# held in memory because the panel shuts itself down when its window closes:
# an in-memory flag would quietly flip back to "active" on the next launch,
# which is the opposite of what someone who paused it asked for.
_ACTIVE_FILE = "panel_state.json"


def scanning_active() -> bool:
    """True when the panel is accepting scans."""
    try:
        with open(paths.data(_ACTIVE_FILE)) as fh:
            return bool(json.load(fh).get("active", True))
    except (OSError, ValueError):
        return True          # absent or unreadable: active, as on first run


def set_scanning_active(value: bool) -> bool:
    value = bool(value)
    path = paths.data(_ACTIVE_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"active": value}, fh)
    except OSError:
        pass                 # a read-only data dir should not break the toggle
    return value


def _watchdog(server, close_grace):
    if close_grace <= 0:
        return
    while True:
        time.sleep(0.5)
        with _alive_lock:
            seen, pages, since = (_alive["seen"], _alive["pages"],
                                  _alive["empty_since"])
        if not seen or pages or not since:
            continue
        # Hold while a scan is open, however the window behaves.
        started = _alive["scanning_since"]
        if started and time.monotonic() - started < SCAN_HOLD_MAX:
            continue
        if time.monotonic() - since > close_grace:
            print("\nStopping: the panel page was closed.")
            try:
                server.shutdown()
            except Exception:
                pass
            os._exit(0)


def load_config() -> dict:
    for path in (paths.data("config.json"), paths.source("config.example.json")):
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                pass
    return {}


def run_refresh() -> dict:
    """Re-read every store's scan and rewrite the XML.

    Nothing here touches the network: a store's deals arrive only from a scan
    of your signed-in browser, saved into harvest/.
    """
    cfg = load_config()
    per_weight = cfg.get("per_weight", "convert")
    use_twins = cfg.get("snack_twins", True)

    scanned, unscanned, written = [], [], []
    for store in stores_mod.load(cfg):
        if not store.scanned:
            unscanned.append({"key": store.key, "store": store.name,
                              "urls": store.urls, "path": store.harvest_path})
            continue
        try:
            found = harvest.parse_file(store.harvest_path, store.name, per_weight)
        except (OSError, ValueError) as exc:
            unscanned.append({"key": store.key, "store": store.name,
                              "urls": store.urls, "path": store.harvest_path,
                              "error": f"could not read the scan ({exc})"})
            continue

        found = offers_mod.dedupe(found)
        if use_twins:
            found = offers_mod.dedupe(offers_mod.mirror_twins(found))

        path = ""
        if found:
            os.makedirs(OUT_DIR, exist_ok=True)
            xml = xmlout.render(store.name, found)
            if not xmlout.validate(xml):
                today = datetime.date.today()
                path = os.path.join(OUT_DIR, f"{store.key}-sales-{today:%Y-%m-%d}.xml")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(xml)
                written.append(path)

        age = store.scan_age_hours
        scanned.append({
            "key": store.key, "store": store.name, "count": len(found),
            "file": path,
            "age": (f"scanned {age:.0f}h ago" if age and age >= 1
                    else "scanned just now"),
            "offers": [{
                "item": o.item_id,
                "amount": (f"save ${o.savings:.2f}" if o.savings is not None
                           else f"${o.sale_price:.2f}"),
                "limit": o.limit, "title": o.title, "basis": o.basis,
            } for o in found],
        })

    return {"stores": scanned, "unscanned": unscanned, "written": written,
            "when": datetime.datetime.now().strftime("%a %d %b, %H:%M")}


def find_app() -> str:
    """Locate the desktop app so the panel can hand the file over to it."""
    cfg = load_config()
    configured = cfg.get("app_path")
    if configured and os.path.isdir(configured):
        return configured
    roots = [os.path.dirname(HERE), "/Applications",
             os.path.expanduser("~/Applications")]
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            if not entry.endswith(".app"):
                continue
            plist = os.path.join(root, entry, "Contents", "Info.plist")
            if not os.path.isfile(plist):
                continue
            try:
                with open(plist, "rb") as fh:
                    info = plistlib.load(fh)
            except Exception:
                continue
            ident = str(info.get("CFBundleIdentifier", "")).lower()
            if "smartshopping" in ident or "shoppinglist" in ident:
                return os.path.join(root, entry)
    return ""


def build_for(store) -> dict:
    """Parse a store's scan and write its XML. Returns what was found."""
    cfg = load_config()
    per_weight = cfg.get("per_weight", "convert")
    use_twins = cfg.get("snack_twins", True)

    if not store.scanned:
        return {"found": False}
    try:
        offers = harvest.parse_file(store.harvest_path, store.name, per_weight)
    except (OSError, ValueError) as exc:
        return {"found": True, "error": str(exc), "count": 0, "xml": ""}

    offers = offers_mod.dedupe(offers)
    if use_twins:
        offers = offers_mod.dedupe(offers_mod.mirror_twins(offers))

    xml_path = ""
    if offers:
        os.makedirs(OUT_DIR, exist_ok=True)
        xml = xmlout.render(store.name, offers)
        if not xmlout.validate(xml):
            today = datetime.date.today()
            xml_path = os.path.join(OUT_DIR, f"{store.key}-sales-{today:%Y-%m-%d}.xml")
            with open(xml_path, "w", encoding="utf-8") as fh:
                fh.write(xml)
    # The offers themselves, once per product (a snack twin repeats its
    # parent's), so the scan result can list what to load to an account.
    listed, seen = [], set()
    for o in offers:
        if o.title in seen:
            continue
        seen.add(o.title)
        listed.append({"title": o.title, "savings": o.savings,
                       "sale_price": o.sale_price, "limit": o.limit})
    return {"found": True, "count": len(offers), "xml": xml_path,
            "offers": listed, "mtime": os.path.getmtime(store.harvest_path)}


def scan_help() -> list:
    """Per-store scanning directions, built from the configured stores."""
    out = []
    for store in stores_mod.load(load_config()):
        out.append({
            "key": store.key,
            "store": store.name,
            "urls": store.urls,
            "scanned": store.scanned,
            "path": store.harvest_path,
            "note": ("Every store is read the same way: from the page you are "
                     "signed in to. Nothing is fetched behind your back."),
            "command": f"python3 crawl.py --stores {store.key}",
        })
    return out



# ---------------------------------------------------------------- how to scan
# A page cannot open a browser extension or type into it -- extensions are
# isolated from page scripts and expose no API for it. So the steps are drawn
# instead, because "ask Claude to run the script" means nothing to someone who
# has never opened the side panel.
STEP_ART = {
    "store": """
<svg viewBox="0 0 170 116" role="img" aria-label="A browser window showing a store page with a sign-in button">
  <rect x="4" y="8" width="162" height="100" rx="8" fill="var(--card)" stroke="var(--line)" stroke-width="2"/>
  <path d="M4 26h162" stroke="var(--line)" stroke-width="2" fill="none"/>
  <circle cx="16" cy="17" r="3" fill="var(--line)"/><circle cx="26" cy="17" r="3" fill="var(--line)"/>
  <circle cx="36" cy="17" r="3" fill="var(--line)"/>
  <rect x="48" y="12" width="110" height="10" rx="5" fill="var(--bg)"/>
  <rect x="18" y="38" width="64" height="8" rx="4" fill="var(--line)"/>
  <rect x="18" y="54" width="92" height="6" rx="3" fill="var(--bg)"/>
  <rect x="18" y="66" width="76" height="6" rx="3" fill="var(--bg)"/>
  <rect x="18" y="84" width="62" height="16" rx="8" fill="var(--accent)"/>
  <text x="49" y="95" text-anchor="middle" font-size="9" font-weight="700"
        fill="var(--accent-ink)" font-family="sans-serif">Sign in</text>
</svg>""",
    "icon": """
<svg viewBox="0 0 170 116" role="img" aria-label="Clicking the Claude icon in the browser toolbar opens a panel at the side">
  <rect x="4" y="8" width="162" height="100" rx="8" fill="var(--card)" stroke="var(--line)" stroke-width="2"/>
  <path d="M4 26h162" stroke="var(--line)" stroke-width="2" fill="none"/>
  <rect x="14" y="12" width="96" height="10" rx="5" fill="var(--bg)"/>
  <circle cx="132" cy="17" r="9" fill="var(--accent)"/>
  <path d="M128 17h8M132 13v8" stroke="var(--accent-ink)" stroke-width="2" stroke-linecap="round"/>
  <circle cx="132" cy="17" r="13" fill="none" stroke="var(--accent)" stroke-width="2" opacity="0.45"/>
  <rect x="112" y="32" width="50" height="72" rx="6" fill="var(--bg)" stroke="var(--accent)" stroke-width="2"/>
  <rect x="120" y="42" width="34" height="5" rx="2.5" fill="var(--line)"/>
  <rect x="120" y="52" width="26" height="5" rx="2.5" fill="var(--line)"/>
  <path d="M138 26l-4 8h8z" fill="var(--accent)"/>
  <path d="M142 24l9 9-4 1-1 4z" fill="var(--ink)"/>
</svg>""",
    "paste": """
<svg viewBox="0 0 170 116" role="img" aria-label="Pasting the instruction into the panel and pressing return">
  <rect x="26" y="8" width="118" height="100" rx="8" fill="var(--card)" stroke="var(--line)" stroke-width="2"/>
  <rect x="38" y="22" width="56" height="6" rx="3" fill="var(--line)"/>
  <rect x="38" y="40" width="94" height="40" rx="6" fill="var(--bg)" stroke="var(--accent)" stroke-width="2"/>
  <rect x="46" y="49" width="70" height="5" rx="2.5" fill="var(--line)"/>
  <rect x="46" y="59" width="58" height="5" rx="2.5" fill="var(--line)"/>
  <rect x="46" y="69" width="40" height="5" rx="2.5" fill="var(--line)"/>
  <circle cx="122" cy="90" r="11" fill="var(--accent)"/>
  <path d="M117 90l4 4 7-8" stroke="var(--accent-ink)" stroke-width="2.5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
}


def how_to_steps(store_name: str) -> str:
    steps = [
        ("store", "Open the store",
         f"Click the link above. Sign in to {store_name} the way you normally would."),
        ("icon", "Open Claude",
         "Click the Claude button in your browser's toolbar, at the top right. "
         "A panel slides in from the side."),
        ("paste", "Paste and press return",
         "Press Copy below, paste it into that panel, and press return. "
         "Claude reads the page and sends the deals straight back here."),
    ]
    out = []
    for index, (art, title, body) in enumerate(steps, start=1):
        out.append(
            f'<li class="howto"><div class="art">{STEP_ART[art]}</div>'
            f'<div class="howtext"><b>{index}. {html.escape(title)}</b>'
            f'<span>{html.escape(body)}</span></div></li>')
    return "".join(out)


# ------------------------------------------------------------------ page
def page() -> str:
    brand = branding.load()
    hour = datetime.datetime.now().hour
    g = lambda k: html.escape(str(brand.get(k, "")))
    # For values embedded in JavaScript: JSON-encode (quotes included) rather
    # than HTML-escape, which would leak entities into textContent.
    # JSON-encode, then neutralise the sequences that would end the <script>
    # block early: json.dumps escapes quotes but leaves "</script>" intact, so
    # a single "<" in any branded string would otherwise break every script
    # below it.
    j = lambda k: (json.dumps(str(brand.get(k, "")))
                   .replace("<", "\\u003c").replace(">", "\\u003e")
                   .replace("&", "\\u0026"))
    theme = brand.get("theme") or "50s-1"
    # Rendered server-side from the real state, so the card does not flash
    # "active" and then correct itself once /api/state comes back.
    active_now = scanning_active()
    active_cls = "" if active_now else " paused"
    active_aria = "true" if active_now else "false"
    active_title = g('panel_active_title') if active_now else g('panel_paused_title')
    active_body = g('panel_active_body') if active_now else g('panel_paused_body')
    active_lbl = g('panel_switch_on') if active_now else g('panel_switch_off')
    scan_dis = "" if active_now else " disabled"
    theme_files = {t["name"]: t["file"] for t in branding.themes()}
    theme_focus = {t["name"]: t["focus"] for t in branding.themes()}
    banner_file = theme_files.get(theme) or next(iter(theme_files.values()), "")
    banner_focus = theme_focus.get(theme, 50)
    steps = brand.get("import_steps") or []
    steps_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in steps)
    prof = profile_mod.load()
    tgt = profile_mod.target(prof)
    first_run = not profile_mod.exists()
    presets = brand.get("list_message_presets") or []
    msg_opts = "".join(
        f'<option value="{html.escape(str(m))}">{html.escape(str(m))}</option>'
        for m in presets)
    # Stores whose deals need you signed in (ShopRite coupons): the panel asks
    # the Scanner whether you are, and shows the login bar if not.
    account_json = json.dumps([
        {"key": st.key, "site": st.adapter or st.key, "name": st.name,
         "login": st.redeem["login"],
         "url": (st.redeem.get("link") or {}).get("url", "")}
        for st in stores_mod.load(load_config()) if st.redeem.get("login")])
    pick_html = "".join(
        f'<button class="picker" data-store="{html.escape(st["key"])}">'
        f'<b>{html.escape(st["store"])}</b>'
        f'<span>{"scanned" if st["scanned"] else "not scanned yet"}</span>'
        f'</button>' for st in scan_help())
    meals_all = ["Breakfast", "Lunch", "Dinner", "Snacks"]
    meals_html = "".join(
        f'<label class="chk"><input type="checkbox" value="{m}"'
        f'{" checked" if m in (prof.meals or []) else ""}> {m}</label>'
        for m in meals_all)
    sex_opts = "".join(
        f'<option value="{k}"{" selected" if prof.sex == k else ""}>'
        f'{html.escape(v[0])}</option>' for k, v in profile_mod.SEXES.items())
    activity_opts = "".join(
        f'<option value="{k}"{" selected" if prof.activity == k else ""}>'
        f'{html.escape(v[0])}</option>' for k, v in profile_mod.ACTIVITY.items())
    goal_opts = "".join(
        f'<option value="{k}"{" selected" if prof.goal == k else ""}>'
        f'{html.escape(v[0])}</option>' for k, v in profile_mod.GOALS.items())
    scan_steps = brand.get("scan_steps") or []
    scan_steps_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in scan_steps)
    stores_html = ""
    for st in scan_help():
        links = "".join(
            f'<p><a href="{html.escape(u["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(u["label"])}</a></p>' for u in st["urls"])
        badge = ('<span class="pill auto">scanned</span>' if st["scanned"]
                 else '<span class="pill need">not scanned yet</span>')
        stores_html += (
            f'<div class="store-help"><div class="sh-head"><strong>'
            f'{html.escape(st["store"])}</strong>{badge}</div>{links}'
            f'<p class="muted" style="margin:6px 0 0">Save the scan as:</p>'
            f'<code>{html.escape(st["path"])}</code></div>')
    themes_html = "".join(
        f'<button class="theme{" on" if t["name"] == theme else ""}" '
        f'data-theme="{html.escape(t["name"])}" data-file="{html.escape(t["file"])}" '
        f'data-focus="{t["focus"]}" title="{html.escape(t["description"])}">'
        f'<img src="/themes/{html.escape(t["thumb"])}" loading="lazy" '
        f'alt="{html.escape(t["name"])}">'
        f'<span>{html.escape(t["name"].replace("-", " "))}</span></button>'
        for t in branding.themes())

    first_run_js = "true" if first_run else "false"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="wss-panel" content="1">
<title>{g('app_name')}</title>
<style>
  :root {{
    --bg:#f7f6f3; --card:#fff; --ink:#1c1b19; --muted:#6b6862;
    --line:#e5e2dc; --accent:#3f7d4f; --accent-ink:#fff;
    --good:#2f7a45; --warn:#9a6212; --warn-bg:#fdf5e6;
    --warm-1:#fff6ec; --warm-2:#ffe8d4; --warm-line:#f2c29a; --warm-ink:#5b3415;
    --warm-btn:#d8661f; --warm-btn-ink:#fff; --warm-icon:#ffd9b8;
    --fresh-1:#f1faf3; --fresh-2:#e1f3e6; --fresh-line:#a9d8b6; --fresh-ink:#1f4a2c;
    --fresh-icon:#c9ebd3;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#16181a; --card:#1e2124; --ink:#eceae6; --muted:#a3a09a;
      --line:#2e3236; --accent:#6fae7d; --accent-ink:#10231a;
      --good:#7cc08e; --warn:#e0b070; --warn-bg:#2a2317;
      --warm-1:#3a2617; --warm-2:#2f1f13; --warm-line:#6e4524; --warm-ink:#ffe2c6;
      --warm-btn:#f29a5c; --warm-btn-ink:#2a1508; --warm-icon:#57371e;
      --fresh-1:#17281c; --fresh-2:#132219; --fresh-line:#2f5a3b; --fresh-ink:#cdeed6;
      --fresh-icon:#24432e;
    }}
  }}
  /* Friendly notices: warm peach when there is something to do first,
     fresh mint when it is good news. Prominent, never alarming. */
  .note{{display:flex;gap:14px;align-items:flex-start;border-radius:16px;
    padding:16px 18px;border:1.5px solid var(--warm-line);color:var(--warm-ink);
    background:linear-gradient(135deg,var(--warm-1),var(--warm-2));
    box-shadow:0 8px 22px -14px rgba(120,60,10,.45)}}
  /* display rules above would otherwise override the hidden attribute */
  .note[hidden],.note [hidden]{{display:none !important}}
  .note.fresh{{border-color:var(--fresh-line);color:var(--fresh-ink);
    background:linear-gradient(135deg,var(--fresh-1),var(--fresh-2));
    box-shadow:0 8px 22px -14px rgba(20,90,40,.4)}}
  .note .ico{{flex:0 0 42px;height:42px;border-radius:50%;display:grid;place-items:center;
    background:var(--warm-icon)}}
  .note.fresh .ico{{background:var(--fresh-icon)}}
  .note .ico svg{{width:22px;height:22px}}
  .note .txt{{flex:1;min-width:0}}
  .note h3{{margin:1px 0 5px;font-size:1.1rem;font-weight:750;line-height:1.3}}
  .note p{{margin:0;line-height:1.5}}
  .note .acts{{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-top:12px}}
  .note .go{{display:inline-block;padding:9px 16px;border-radius:999px;font-weight:700;
    text-decoration:none;background:var(--warm-btn);color:var(--warm-btn-ink)}}
  .note.fresh .go{{background:var(--accent);color:var(--accent-ink)}}
  .note .go:hover{{filter:brightness(1.05)}}
  .note .later{{background:none;border:0;padding:4px 2px;color:inherit;
    text-decoration:underline;text-underline-offset:3px;font-size:.92rem}}
  .note .x{{flex:0 0 auto;background:none;border:0;padding:2px 6px;margin:-4px -6px 0 0;
    color:inherit;font-size:1.3rem;line-height:1;opacity:.6}}
  .note .x:hover{{opacity:1}}
  #loginbar{{margin:16px 0}}
  #w-redeem{{margin:0 0 18px}}
  .redeem-items{{list-style:none;margin:14px 0 0;padding:0}}
  .redeem-items li{{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;
    padding:10px 12px;margin:0 0 8px;border-radius:12px;
    background:color-mix(in srgb,var(--card) 72%,transparent)}}
  .redeem-items .what{{flex:1 1 200px;min-width:0}}
  .redeem-items .what b{{display:block;font-weight:650}}
  .redeem-items .what span{{font-size:.88rem;opacity:.85}}
  .redeem-items button{{padding:5px 12px;font-size:.82rem;border-radius:999px}}
  .redeem-items a{{font-weight:650;font-size:.88rem;color:inherit}}
  .redeem-items .redeem-hint{{background:none;padding:0 2px;margin:0 0 6px;font-size:.92rem}}
  @media (max-width:520px){{.note{{padding:14px}} .note .ico{{display:none}}}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
  .wrap{{max-width:860px;margin:0 auto;padding:0 16px 56px}}
  header{{position:relative;border-radius:0 0 18px 18px;overflow:hidden;
    margin:0 -16px 26px;min-height:190px;display:flex;align-items:flex-end}}
  header img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
  header .veil{{position:absolute;inset:0;
    background:linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.62))}}
  header .txt{{position:relative;padding:20px 22px;color:#fff}}
  header h1{{margin:0;font-size:1.05rem;font-weight:600;opacity:.92;
    letter-spacing:.02em}}
  header p{{margin:.2rem 0 0;font-size:1.65rem;font-weight:700;line-height:1.2}}
  header .tag{{margin:.35rem 0 0;font-size:.95rem;opacity:.9;font-weight:400}}
  .row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}}
  button{{font:inherit;cursor:pointer;border-radius:10px;border:1px solid var(--line);
    background:var(--card);color:var(--ink);padding:11px 17px;font-weight:600}}
  button:hover{{border-color:var(--accent)}}
  button.primary{{background:var(--accent);color:var(--accent-ink);border-color:transparent}}
  button[disabled]{{opacity:.6;cursor:progress}}
  #activecard{{padding:15px 20px}}
  #activecard h2{{margin:0;display:flex;align-items:center;gap:9px}}
  #activecard p{{margin:3px 0 0}}
  .switchrow{{display:flex;align-items:center;justify-content:space-between;gap:16px}}
  .dot{{width:10px;height:10px;border-radius:50%;background:var(--good);flex:none}}
  #activecard.paused .dot{{background:transparent;border:2px solid var(--muted)}}
  button.switch{{display:inline-flex;align-items:center;gap:6px;flex:none;
    width:88px;padding:5px;border-radius:999px;border:1px solid transparent;
    background:var(--good);color:#fff;transition:background .18s ease}}
  button.switch:hover{{border-color:var(--ink)}}
  button.switch .lbl{{flex:1;text-align:center;font-size:.78rem;
    font-weight:700;letter-spacing:.06em}}
  button.switch .knob{{width:22px;height:22px;border-radius:50%;background:#fff;
    flex:none;box-shadow:0 1px 3px rgba(0,0,0,.35)}}
  button.switch[aria-checked="false"]{{background:var(--muted);flex-direction:row-reverse}}
  button.switch:focus-visible{{outline:2px solid var(--accent);outline-offset:3px}}
  #scanwith[disabled]{{cursor:not-allowed}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:18px 20px;margin-bottom:18px}}
  h2{{margin:0 0 12px;font-size:1.04rem;letter-spacing:.01em}}
  .deal{{display:flex;gap:12px;align-items:baseline;padding:9px 0;
    border-top:1px solid var(--line);font-size:.95rem}}
  .deal:first-of-type{{border-top:0}}
  .deal .amt{{color:var(--good);font-weight:700;white-space:nowrap;min-width:82px}}
  .deal .it{{font-weight:600;min-width:104px}}
  .deal .ti{{color:var(--muted);flex:1;min-width:0;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}}
  .deal .lim{{color:var(--warn);font-size:.85rem;white-space:nowrap}}
  .warn{{background:var(--warn-bg);border-color:transparent}}
  .warn a{{color:inherit}}
  .store-line{{display:flex;justify-content:space-between;gap:12px;
    align-items:center;margin-bottom:10px}}
  .muted{{color:var(--muted);font-size:.9rem}}
  .files{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85rem;
    color:var(--muted);word-break:break-all}}
  .themes{{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:10px}}
  .theme{{padding:0;overflow:hidden;display:block;border-width:2px}}
  .theme img{{width:100%;height:78px;object-fit:cover;display:block}}
  .theme span{{display:block;padding:6px 4px;font-size:.78rem;font-weight:600;
    text-transform:capitalize}}
  .theme.on{{border-color:var(--accent)}}
  label{{display:block;font-size:.82rem;font-weight:700;color:var(--muted);
    margin:12px 0 4px;text-transform:uppercase;letter-spacing:.05em}}
  input[type=text]{{width:100%;font:inherit;padding:9px 11px;border-radius:9px;
    border:1px solid var(--line);background:var(--bg);color:var(--ink)}}
  dialog{{border:0;border-radius:16px;padding:0;max-width:540px;width:calc(100% - 32px);
    background:var(--card);color:var(--ink)}}
  dialog::backdrop{{background:rgba(0,0,0,.45)}}
  dialog .inner{{padding:22px 24px}}
  dialog ol{{padding-left:20px;margin:0 0 14px}}
  dialog li{{margin-bottom:8px}}
  .btnlink{{display:inline-block;font:inherit;font-weight:600;padding:11px 17px;
    border-radius:10px;background:var(--accent);color:var(--accent-ink);
    text-decoration:none}}
  .btnlink:hover{{opacity:.92}}
  .pickers{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px}}
  .picker{{text-align:left;padding:13px 15px}}
  .picker b{{display:block;font-size:1rem}}
  .picker span{{display:block;font-size:.78rem;color:var(--muted);font-weight:500;
    text-transform:uppercase;letter-spacing:.04em;margin-top:2px}}
  .howsteps{{list-style:none;margin:16px 0 4px;padding:0;
    display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
  .howto{{background:var(--bg);border-radius:10px;padding:10px 10px 12px;
    display:flex;flex-direction:column;gap:8px}}
  .howto .art{{background:var(--card);border-radius:8px;padding:4px}}
  .howto svg{{display:block;width:100%;height:auto}}
  .howtext b{{display:block;font-size:.88rem;margin-bottom:3px}}
  .howtext span{{display:block;font-size:.8rem;color:var(--muted);line-height:1.45}}
  @media (max-width:560px){{ .howsteps{{grid-template-columns:1fr}} }}
  .pastefall{{margin-top:12px}}
  .pastefall summary{{font-size:.85rem;color:var(--muted);cursor:pointer}}
  .pastefall textarea{{width:100%;margin-top:8px;font-family:ui-monospace,
    SFMono-Regular,Menlo,monospace;font-size:12.5px;padding:9px 11px;
    border-radius:9px;border:1px solid var(--line);background:var(--bg);
    color:var(--ink);resize:vertical}}
  .promptbox{{display:flex;gap:8px;align-items:flex-start;background:var(--bg);
    border-radius:10px;padding:10px 12px;margin-top:4px}}
  .promptbox code{{flex:1;font-size:.83rem;word-break:break-word;line-height:1.45}}
  @media (max-width:560px){{ .pickers{{grid-template-columns:1fr}} }}
  .listmsg{{font-size:1.06rem;font-weight:600;margin:0 0 16px;
    color:var(--accent);letter-spacing:.01em}}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) .listmsg{{color:var(--good)}}
  }}
  .targets{{display:flex;gap:10px;flex-wrap:wrap}}
  .targets .t{{flex:1 1 92px;background:var(--bg);border-radius:10px;
    padding:10px 12px;min-width:92px}}
  .targets .t b{{display:block;font-size:1.28rem;line-height:1.2}}
  /* .num is a span, so it would otherwise inherit the sublabel's uppercase
     and muted colour and render the unit as a small grey "G". */
  .targets .t .num{{display:flex;align-items:baseline;gap:1px;
    text-transform:none;color:var(--ink);font-size:1rem}}
  .targets .t .num i{{font-style:normal;font-size:1.28rem;font-weight:700;
    line-height:1.2}}
  .targets .t .num input{{width:auto;min-width:0;flex:0 1 auto;
    field-sizing:content}}
  .targets .t input{{display:block;width:100%;font:inherit;font-size:1.28rem;
    font-weight:700;line-height:1.2;padding:0;border:0;background:none;
    color:var(--ink);border-bottom:1.5px dashed transparent;
    -moz-appearance:textfield}}
  .targets .t input::-webkit-outer-spin-button,
  .targets .t input::-webkit-inner-spin-button{{-webkit-appearance:none;margin:0}}
  .targets .t input:hover{{border-bottom-color:var(--line)}}
  .targets .t input:focus{{outline:none;border-bottom-color:var(--accent)}}
  .targets .t.mine{{box-shadow:inset 0 0 0 1.5px var(--accent)}}
  .linkish{{font:inherit;font-size:.85rem;color:var(--accent);background:none;
    border:0;padding:0;margin-top:10px;cursor:pointer;text-decoration:underline}}
  .targets .t span{{font-size:.76rem;color:var(--muted);text-transform:uppercase;
    letter-spacing:.05em}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}}
  .pair{{display:flex;align-items:center;gap:6px}}
  .pair input{{flex:1;min-width:0}}
  .unit{{color:var(--muted);font-size:.85rem}}
  select{{width:100%;font:inherit;padding:9px 11px;border-radius:9px;
    border:1px solid var(--line);background:var(--bg);color:var(--ink)}}
  input[type=number]{{width:100%;font:inherit;padding:9px 11px;border-radius:9px;
    border:1px solid var(--line);background:var(--bg);color:var(--ink)}}
  .meals{{display:flex;gap:14px;flex-wrap:wrap;margin-top:4px}}
  .chk{{display:flex;align-items:center;gap:6px;font-size:.92rem;font-weight:500;
    text-transform:none;letter-spacing:0;color:var(--ink);margin:0}}
  @media (max-width:560px){{ .grid2{{grid-template-columns:1fr}} }}
  .store-help{{border-top:1px solid var(--line);padding:12px 0}}
  .store-help code{{display:block;margin-top:6px;font-size:.82rem;
    background:var(--bg);padding:8px 10px;border-radius:8px;word-break:break-all}}
  .sh-head{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
  .pill{{font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:999px;
    text-transform:uppercase;letter-spacing:.04em}}
  .pill.auto{{background:#e3f1e6;color:#265c35}}
  .pill.need{{background:var(--warn-bg);color:var(--warn)}}
  .spin{{display:inline-block;width:13px;height:13px;border:2px solid currentColor;
    border-right-color:transparent;border-radius:50%;animation:s .7s linear infinite;
    vertical-align:-1px;margin-right:7px}}
  @keyframes s{{to{{transform:rotate(360deg)}}}}
  @media (max-width:560px){{
    header p{{font-size:1.32rem}} .deal{{flex-wrap:wrap}} .deal .ti{{white-space:normal}}
  }}
</style></head><body><div class="wrap">

<div class="note" id="loginbar" role="status" aria-live="polite" hidden>
  <div class="ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/></svg></div>
  <div class="txt">
    <h3 id="loginbar-title"></h3>
    <p id="loginbar-body"></p>
    <div class="acts">
      <a class="go" id="loginbar-go" target="_blank" rel="noopener"></a>
      <button type="button" class="later" id="loginbar-later">Maybe later</button>
    </div>
  </div>
  <button type="button" class="x" id="loginbar-x" aria-label="Dismiss">&times;</button>
</div>

<header>
  <img id="banner" src="/themes/{html.escape(banner_file)}" alt=""
       style="object-position: center {banner_focus}%">
  <div class="veil"></div>
  <div class="txt">
    <h1 id="h-app">{g('app_name')}</h1>
    <p id="h-greet">{html.escape(branding.greeting(brand, hour))}</p>
    <div class="tag" id="h-tag">{g('tagline')}</div>
  </div>
</header>

<div class="card{active_cls}" id="activecard">
  <div class="switchrow">
    <div class="switchtxt">
      <h2><span class="dot" id="active-dot"></span><span id="active-label">{active_title}</span></h2>
      <p class="muted" id="active-note">{active_body}</p>
    </div>
    <button type="button" class="switch" id="active-switch" role="switch"
            aria-checked="{active_aria}" aria-labelledby="active-label">
      <span class="lbl" id="active-state">{active_lbl}</span>
      <span class="knob"></span>
    </button>
  </div>
</div>

<div class="card warn" id="extbar" hidden>
  <div class="store-line"><h2 id="ext-title">{g('extension_title')}</h2></div>
  <p class="muted" id="ext-body">{g('extension_body')}</p>
  <div class="row" style="margin:12px 0 0">
    <a class="btnlink" id="ext-get" href="{g('extension_url')}" target="_blank"
       rel="noopener">{g('extension_install')}</a>
    <button id="ext-have">{g('extension_have')}</button>
  </div>
</div>

<div class="row">
  <button class="primary" id="scanwith"{scan_dis}>{g('scan_button')}</button>
  <button id="refresh">{g('refresh_button')}</button>
  <button id="howto">{g('import_button')}</button>
</div>

<div class="card" id="profile-card">
  <div class="store-line">
    <h2>{g('targets_header')}</h2>
    <button id="editprofile" style="padding:6px 12px;font-size:.85rem">{g('profile_edit_button')}</button>
  </div>
  <div id="targets" class="targets">
    <div class="t{' mine' if 'calories' in tgt.get('custom_fields', []) else ''}">
      <input type="number" id="t-cal" min="800" max="8000" value="{tgt['calories']}"
             aria-label="Calories per day"><span>kcal / day</span></div>
    <div class="t{' mine' if 'protein' in tgt.get('custom_fields', []) else ''}">
      <span class="num"><input type="number" id="t-pro" min="0" max="500"
             value="{tgt['protein']}" aria-label="Protein grams"><i>g</i></span>
      <span>protein</span></div>
    <div class="t{' mine' if 'carbs' in tgt.get('custom_fields', []) else ''}">
      <span class="num"><input type="number" id="t-car" min="0" max="900"
             value="{tgt['carbs']}" aria-label="Carbohydrate grams"><i>g</i></span>
      <span>carbs</span></div>
    <div class="t{' mine' if 'fat' in tgt.get('custom_fields', []) else ''}">
      <span class="num"><input type="number" id="t-fat" min="0" max="400"
             value="{tgt['fat']}" aria-label="Fat grams"><i>g</i></span>
      <span>fat</span></div>
    <div class="t"><b id="t-goal">{html.escape(tgt['goal_label'])}</b><span>goal</span></div>
  </div>
  <button id="t-reset" class="linkish"{'' if tgt.get('custom') else ' hidden'}>Back to the calculated figures</button>
  <p class="muted" id="t-note" style="margin:10px 0 0">{g('targets_note')}</p>
</div>

<p class="listmsg" id="listmsg">{g('list_message')}</p>

<div id="results"><div class="card"><h2>{g('deals_header')}</h2>
  <p class="muted">{g('deals_empty')}</p></div></div>

<div class="card">
  <h2>{g('themes_header')}</h2>
  <div class="themes">{themes_html}</div>
  <p class="muted" style="margin:12px 0 0">Drop any .png or .jpg into the
    <code>themes/</code> folder and it appears here.</p>
</div>

<div class="card">
  <h2>Wording</h2>
  <p class="muted" style="margin:-6px 0 6px">Every heading and greeting is yours to change.</p>
  <label for="f-app">App name</label>
  <input type="text" id="f-app" value="{g('app_name')}">
  <label for="f-greet">Greeting</label>
  <input type="text" id="f-greet" value="{g('greeting_morning')}">
  <label for="f-tag">Tagline</label>
  <input type="text" id="f-tag" value="{g('tagline')}">
  <label for="f-deals">Deals heading</label>
  <input type="text" id="f-deals" value="{g('deals_header')}">
  <label for="f-msg">Shopping list message</label>
  <select id="f-msgpick"><option value="">Choose a message...</option>{msg_opts}</select>
  <input type="text" id="f-msg" value="{g('list_message')}" style="margin-top:8px"
         placeholder="Or write your own">
  <div class="row" style="margin:16px 0 0"><button id="save">{g('save_button')}</button>
    <span class="muted" id="saved" style="align-self:center"></span></div>
</div>

<p class="muted">{g('footer')}</p>
</div>

<dialog id="profiledlg"><div class="inner">
  <h2>{g('profile_title')}</h2>
  <p class="muted">{g('profile_intro')}</p>

  <div class="grid2">
    <div>
      <label for="p-ft">Height</label>
      <div class="pair">
        <input type="number" id="p-ft" min="4" max="8" placeholder="5"
               value="{prof.height_feet if prof.height_feet is not None else ''}">
        <span class="unit">ft</span>
        <input type="number" id="p-in" min="0" max="11" placeholder="10"
               value="{prof.height_inches if prof.height_inches is not None else ''}">
        <span class="unit">in</span>
      </div>
    </div>
    <div>
      <label for="p-wt">Weight</label>
      <div class="pair">
        <input type="number" id="p-wt" min="80" max="700" step="0.5" placeholder="185"
               value="{prof.weight_pounds if prof.weight_pounds is not None else ''}">
        <span class="unit">lb</span>
      </div>
    </div>
    <div>
      <label for="p-age">Age</label>
      <div class="pair">
        <input type="number" id="p-age" min="13" max="100" placeholder="38"
               value="{prof.age if prof.age is not None else ''}">
        <span class="unit">yrs</span>
      </div>
    </div>
    <div>
      <label for="p-sex">Sex</label>
      <select id="p-sex">{sex_opts}</select>
    </div>
    <div>
      <label for="p-goal">Goal</label>
      <select id="p-goal">{goal_opts}</select>
    </div>
    <div>
      <label for="p-diet">Diet</label>
      <input type="text" id="p-diet" value="{html.escape(prof.diet)}"
             placeholder="No restriction">
    </div>
    <div>
      <label for="p-people">People</label>
      <input type="number" id="p-people" min="1" max="12" value="{prof.people}">
    </div>
    <div>
      <label for="p-days">Days to plan</label>
      <input type="number" id="p-days" min="1" max="60" value="{prof.days}">
    </div>
    <div>
      <label for="p-bmin">Budget min</label>
      <input type="number" id="p-bmin" min="0" step="1" value="{prof.budget_min:g}">
    </div>
    <div>
      <label for="p-bmax">Budget max</label>
      <input type="number" id="p-bmax" min="0" step="1" value="{prof.budget_max:g}">
    </div>
  </div>

  <label for="p-activity">Activity level</label>
  <select id="p-activity">{activity_opts}</select>

  <label>Meals to plan</label>
  <div class="meals" id="p-meals">{meals_html}</div>

  <div class="card" style="margin:16px 0 0;background:var(--bg)">
    <h2 style="margin:0 0 8px">Your daily target</h2>
    <div class="targets" id="preview">
      <div class="t"><b id="v-cal">{tgt['calories']}</b><span>kcal</span></div>
      <div class="t"><b id="v-pro">{tgt['protein']}g</b><span>protein</span></div>
      <div class="t"><b id="v-car">{tgt['carbs']}g</b><span>carbs</span></div>
      <div class="t"><b id="v-fat">{tgt['fat']}g</b><span>fat</span></div>
    </div>
    <p class="muted" id="v-note" style="margin:10px 0 0">{g('targets_note')}</p>
  </div>

  <div class="row" style="margin:16px 0 0">
    <button class="primary" id="saveprofile">{g('profile_save_button')}</button>
    <button id="profileclose">Close</button>
    <span class="muted" id="psaved" style="align-self:center"></span>
  </div>
</div></dialog>

<dialog id="scanwiz"><div class="inner">
  <section id="w-pick">
    <h2>{g('scan_pick_title')}</h2>
    <p class="muted">{g('scan_pick_intro')}</p>
    <div class="pickers">{pick_html}</div>
    <div class="row" style="margin:16px 0 0">
      <button id="w-pick-close">Close</button>
      <button id="w-help">{g('scan_help_button')}</button>
    </div>
  </section>

  <section id="w-signin" hidden>
    <h2 id="w-signin-title"></h2>
    <p class="muted">{g('scan_signin_why')}</p>
    <div id="w-signin-links"></div>
    <div class="row" style="margin:18px 0 0">
      <button class="primary" id="w-signin-go">{g('scan_signin_done')}</button>
      <button id="w-signin-back">Back</button>
    </div>
  </section>

  <section id="w-wait" hidden>
    <h2 id="w-wait-title"></h2>
    <p class="muted" id="w-scanner-body" hidden>The Scanner extension is
      reading the store in a new tab. It only reads the page; it never loads,
      clips or buys anything. Leave this window open.</p>
    <div id="w-claude">
    <p class="muted" id="w-claude-lead" hidden>Or scan with Claude instead:</p>
    <p class="muted">{g('scan_wait_body')}</p>
    <div id="w-links"></div>
    <ol class="howsteps" id="w-steps"></ol>
    <label>Give Claude this instruction</label>
    <div class="promptbox"><code id="w-prompt"></code>
      <button id="w-copy" style="padding:6px 12px;font-size:.82rem">Copy</button></div>
    <details class="pastefall">
      <summary>{g('scan_paste_label')}</summary>
      <textarea id="w-paste" rows="5" spellcheck="false"
                placeholder="Boneless Skinless Chicken Breast | $1.99/lb | Limit 4"></textarea>
      <div class="row" style="margin:8px 0 0">
        <button id="w-paste-go">{g('scan_paste_button')}</button>
      </div>
    </details>

    <p class="muted" id="w-ext" hidden style="margin:12px 0 0">
      Need the extension?
      <a href="{g('extension_url')}" target="_blank" rel="noopener">Install Claude for Chrome</a>
    </p>
    </div>
    <p class="muted" id="w-status" style="margin:16px 0 0">
      <span class="spin"></span>{g('scan_waiting')}</p>
    <div class="row" style="margin:14px 0 0"><button id="w-cancel">Cancel</button></div>
  </section>

  <section id="w-done" hidden>
    <div class="note" id="w-redeem" role="status" hidden>
      <div class="ico" aria-hidden="true" id="w-redeem-ico"></div>
      <div class="txt">
        <h3 id="w-redeem-title"></h3>
        <p id="w-redeem-body"></p>
        <ul class="redeem-items" id="w-redeem-items" hidden></ul>
        <div class="acts"><a class="go" id="w-redeem-link" target="_blank" rel="noopener" hidden></a></div>
      </div>
    </div>
    <h2 id="w-done-title"></h2>
    <p id="w-done-body" class="muted"></p>
    <div class="row" style="margin:16px 0 0">
      <button class="primary" id="w-import">{g('scan_import_now')}</button>
      <button id="w-later">{g('scan_import_later')}</button>
    </div>
  </section>

  <section id="w-after" hidden>
    <h2 id="w-after-title"></h2>
    <p id="w-after-body" class="muted"></p>
    <p class="files" id="w-after-path"></p>
    <div class="row" style="margin:16px 0 0">
      <button class="primary" id="w-after-close">Done</button>
      <button id="w-again">Scan another store</button>
    </div>
  </section>
</div></dialog>

<dialog id="scandlg"><div class="inner">
  <h2>{g('scan_title')}</h2>
  <p class="muted">{g('scan_intro')}</p>
  <ol>{scan_steps_html}</ol>
  <h2 style="margin-top:18px">Your stores</h2>
  {stores_html}
  <div class="card warn" style="margin:14px 0 0">{g('scan_note')}</div>
  <div class="row" style="margin:16px 0 0"><button class="primary" id="scanclose">Close</button></div>
</div></dialog>

<dialog id="dlg"><div class="inner">
  <h2>{g('import_title')}</h2>
  <ol>{steps_html}</ol>
  <div class="card warn" style="margin:0 0 16px"><strong>Signed out?</strong>
    Grocers only show coupons to a signed-in session. Sign in to the store in
    Chrome, open its coupon list, then ask Claude (with the Claude for Chrome
    extension) to run <code>browser/harvest.js</code> on that tab.</div>
  <p class="muted">{g('import_note')}</p>
  <div class="row" style="margin:16px 0 0"><button class="primary" id="close">Close</button></div>
</div></dialog>

<script>
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));

const profDlg = $("#profiledlg");
$("#editprofile").onclick = () => profDlg.showModal();
$("#profileclose").onclick = () => profDlg.close();

function profileBody() {{
  const num = id => {{
    const v = $(id).value.trim();
    return v === "" ? null : Number(v);
  }};
  return {{
    height_feet: num("#p-ft"), height_inches: num("#p-in"),
    weight_pounds: num("#p-wt"), goal: $("#p-goal").value,
    age: num("#p-age"), sex: $("#p-sex").value,
    activity: $("#p-activity").value,
    diet: $("#p-diet").value, people: num("#p-people") || 1,
    days: num("#p-days") || 7,
    budget_min: num("#p-bmin") || 0, budget_max: num("#p-bmax") || 0,
    meals: Array.from(document.querySelectorAll("#p-meals input:checked"))
                .map(c => c.value),
  }};
}}

async function postProfile(preview) {{
  const r = await fetch("/api/profile", {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(Object.assign({{preview: preview}}, profileBody()))}});
  return r.json();
}}

function paint(t, scope) {{
  const suffix = scope === "#t-" ? "" : "g";   // the tiles are number inputs
  const set = (sel, value) => {{
    const el = $(sel);
    if (!el) return;
    if (el.tagName === "INPUT") el.value = value; else el.textContent = value + suffix;
  }};
  set(scope + "cal", t.calories);
  set(scope + "pro", t.protein);
  set(scope + "car", t.carbs);
  set(scope + "fat", t.fat);
}}

let previewTimer = null;
function schedulePreview() {{
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {{
    try {{
      const d = await postProfile(true);
      paint(d.target, "#v-");
      $("#v-note").textContent = d.target.personalised
        ? {j('targets_note')}
        : (d.complete
           ? {j('targets_note_partial')}
           : "Add your height and weight for a target sized to you.");
    }} catch (e) {{}}
  }}, 260);
}}
profDlg.querySelectorAll("input, select").forEach(
  el => {{ el.oninput = schedulePreview; el.onchange = schedulePreview; }});

$("#saveprofile").onclick = async () => {{
  const d = await postProfile(false);
  paint(d.target, "#t-");
  paint(d.target, "#v-");
  $("#t-goal").textContent = d.target.goal_label;
  $("#psaved").textContent = "Saved";
  setTimeout(() => {{ $("#psaved").textContent = ""; profDlg.close(); }}, 900);
}};

if ({first_run_js}) profDlg.showModal();

// ---- accepting-scans switch ------------------------------------------------
// Paused means the panel keeps serving this page but refuses a posted scan,
// so the switch stays reachable either way.
const actSw = $("#active-switch");
const PANEL_TXT = {{
  onTitle: {j('panel_active_title')}, onBody: {j('panel_active_body')},
  offTitle: {j('panel_paused_title')}, offBody: {j('panel_paused_body')},
  onLbl: {j('panel_switch_on')}, offLbl: {j('panel_switch_off')}
}};
function paintActive(on) {{
  actSw.setAttribute("aria-checked", on ? "true" : "false");
  $("#active-state").textContent = on ? PANEL_TXT.onLbl : PANEL_TXT.offLbl;
  $("#active-label").textContent = on ? PANEL_TXT.onTitle : PANEL_TXT.offTitle;
  $("#active-note").textContent = on ? PANEL_TXT.onBody : PANEL_TXT.offBody;
  $("#activecard").classList.toggle("paused", !on);
  $("#scanwith").disabled = !on;
}}
actSw.onclick = async () => {{
  const next = actSw.getAttribute("aria-checked") !== "true";
  paintActive(next);                       // optimistic
  try {{
    const r = await fetch("/api/panel", {{
      method: "POST", headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{active: next}})}});
    paintActive(!!(await r.json()).active); // authoritative
  }} catch (e) {{
    paintActive(!next);                    // server unreachable: put it back
  }}
}};
fetch("/api/state").then(r => r.json())
  .then(d => paintActive(d.active !== false)).catch(() => {{}});

// ---- lifetime --------------------------------------------------------------
// This page holds one open connection to the panel. Closing the tab or
// navigating away drops it, and the panel stops -- so closing the tab does not
// leave a server running in the background. Nothing is sent on a timer.
try {{ new EventSource("/api/live"); }} catch (e) {{}}

// ---- Claude for Chrome notice --------------------------------------------
// A page cannot reliably detect an installed extension: the resources this one
// exposes are content-hashed and change with every release, so probing for them
// would report "missing" after any update. Only the browser is certain, so the
// notice informs and can be dismissed rather than claiming anything false.
const CHROMIUM = (() => {{
  try {{
    const brands = (navigator.userAgentData && navigator.userAgentData.brands) || [];
    if (brands.some(b => /Chromium|Google Chrome/i.test(b.brand))) return true;
  }} catch (e) {{}}
  const ua = navigator.userAgent || "";
  return /Chrome|Chromium|CriOS/i.test(ua) && !/Firefox|FxiOS/i.test(ua);
}})();

function stored(key) {{
  try {{ return localStorage.getItem(key); }} catch (e) {{ return null; }}
}}
function store(key, value) {{
  try {{ localStorage.setItem(key, value); }} catch (e) {{}}
}}

(function extensionNotice() {{
  const bar = $("#extbar");
  if (!bar) return;
  if (!CHROMIUM) {{
    // Certain: this browser cannot run it at all.
    $("#ext-body").textContent = {j('extension_wrong_browser')};
    $("#ext-have").hidden = true;
    bar.hidden = false;
    $("#w-ext").hidden = false;
    return;
  }}
  if (stored("wss.hasExtension") === "yes") return;
  bar.hidden = false;
  $("#w-ext").hidden = false;
}})();

// ---- Scanner extension -----------------------------------------------------
// extension/panel-bridge.js announces itself on this page. When it is here, a
// scan runs in the browser with no instruction to copy.
let SCANNER = document.documentElement.dataset.wssScanner || "";
let scannerJob = null;

function scannerFound(version) {{
  SCANNER = version || SCANNER || "yes";
  $("#extbar").hidden = true;
  $("#w-ext").hidden = true;
  const b = $("#scanwith");
  if (b.textContent.trim() === "Scan with Claude") b.textContent = "Scan deals";
}}

addEventListener("message", (e) => {{
  if (e.source !== window || !e.data || e.data.source !== "wss-scanner") return;
  const d = e.data;
  if (d.type === "ready") scannerFound(d.version);
  if (d.type === "progress" && scannerJob) {{
    $("#w-status").innerHTML = '<span class="spin"></span>' + esc(d.text || "");
  }}
  if (d.type === "result" && scannerJob) {{
    scannerJob = null;
    if (d.ok && d.pageUrl) wizState.pageUrl = d.pageUrl;
    if (d.ok) {{
      // Saved by the panel; the poll picks up the new file from here.
      $("#w-status").innerHTML = '<span class="spin"></span>' +
        esc("Read " + d.count + " offers. Matching them to your list...");
    }} else {{
      wizStop();
      $("#w-status").textContent = d.error || "The scan did not finish.";
      $("#w-claude").hidden = false;
      $("#w-claude-lead").hidden = false;
    }}
  }}
}});
postMessage({{source: "wss-panel", type: "hello"}}, location.origin);
if (SCANNER) scannerFound(SCANNER);

$("#ext-have").onclick = () => {{
  store("wss.hasExtension", "yes");
  $("#extbar").hidden = true;
  $("#w-ext").hidden = true;
}};

// ---- Scan with Claude -----------------------------------------------------
const wiz = $("#scanwiz");
let wizState = {{store: null, baseline: 0, xml: "", timer: null}};

function wizStep(id) {{
  ["w-pick", "w-signin", "w-wait", "w-done", "w-after"].forEach(
    s => $("#" + s).hidden = (s !== id));
}}

function wizStop(cancelled) {{
  if (wizState.timer) {{ clearInterval(wizState.timer); wizState.timer = null; }}
  // Release the hold that keeps the panel alive during a scan.
  if (cancelled && wizState.store) {{
    wizPost("cancel", {{store: wizState.store}}).catch(() => {{}});
  }}
}}

async function wizPost(action, body) {{
  const r = await fetch("/api/scan/" + action, {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body)}});
  return r.json();
}}

$("#scanwith").onclick = () => {{ wizStop(); wizStep("w-pick"); wiz.showModal(); }};
$("#w-pick-close").onclick = () => {{ wizStop(true); wiz.close(); }};
$("#w-cancel").onclick = () => {{ wizStop(true); wizStep("w-pick"); }};
$("#w-again").onclick = () => {{ wizStop(true); wizStep("w-pick"); }};
$("#w-after-close").onclick = () => {{ wizStop(true); wiz.close(); location.reload(); }};
$("#w-help").onclick = () => {{ wiz.close(); $("#scandlg").showModal(); }};

document.querySelectorAll(".picker").forEach(el => {{
  el.onclick = async () => {{
    const key = el.dataset.store;
    const d = await wizPost("start", {{store: key}});
    wizState = {{store: key, baseline: d.baseline, xml: "", timer: null, started: d}};
    const links = (d.urls || []).map(
      u => '<p><a href="' + esc(u.url) + '" target="_blank" rel="noopener">' +
           esc(u.label) + '</a></p>').join("");
    $("#w-signin-title").textContent = {j('scan_signin_title')}.replace("{{store}}", d.name);
    $("#w-signin-links").innerHTML = links;
    $("#w-links").innerHTML = links;
    // A store's own reader knows its page (ShopRite's is read signed out).
    if (SCANNER && d.adapter && d.adapter !== "generic") return beginWait();
    wizStep("w-signin");
  }};
}});

$("#w-signin-back").onclick = () => {{ wizStop(true); wizStep("w-pick"); }};

// Only once they say they are signed in does the instruction appear: a scan of
// a signed-out page comes back empty or wrong.
$("#w-signin-go").onclick = () => beginWait();

async function beginWait() {{
  const d = wizState.started;
  if (!d) return;
  $("#w-wait-title").textContent = {j('scan_wait_title')}.replace("{{store}}", d.name);
  $("#w-prompt").textContent = d.prompt;
  try {{
    const steps = await (await fetch("/api/steps?store=" +
                    encodeURIComponent(wizState.store))).text();
    $("#w-steps").innerHTML = steps;
  }} catch (e) {{ $("#w-steps").innerHTML = ""; }}
  $("#w-status").innerHTML = '<span class="spin"></span>' + esc({j('scan_waiting')});
  $("#w-claude").hidden = !!SCANNER;
  $("#w-claude-lead").hidden = true;
  $("#w-scanner-body").hidden = !SCANNER;
  wizStep("w-wait");
  wizState.timer = setInterval(wizPoll, 2500);
  if (SCANNER) {{
    scannerJob = wizState.store;
    postMessage({{source: "wss-panel", type: "scan", store: d.store, name: d.name,
                  adapter: d.adapter, url: (d.urls && d.urls[0]) ? d.urls[0].url : ""}},
                location.origin);
  }}
}}

$("#w-copy").onclick = async () => {{
  try {{
    await navigator.clipboard.writeText($("#w-prompt").textContent);
    $("#w-copy").textContent = "Copied";
    setTimeout(() => $("#w-copy").textContent = "Copy", 1600);
  }} catch (e) {{ $("#w-copy").textContent = "Select and copy"; }}
}};

async function wizPoll() {{
  let d;
  try {{ d = await wizPost("check", {{store: wizState.store, baseline: wizState.baseline}}); }}
  catch (e) {{ return; }}
  if (!d.ready) return;
  wizStop();
  if (d.error) {{
    $("#w-status").textContent = "Could not read the scan: " + esc(d.error);
    return;
  }}
  wizState.xml = d.xml || "";
  showRedeem(wizState.started && wizState.started.redeem, d.count, d.offers || []);
  if (!d.count) {{
    $("#w-done-title").textContent =
      {j('scan_none_title')}.replace("{{store}}", d.name).replace("{{count}}", "0");
    $("#w-done-body").textContent = {j('scan_none_body')};
    $("#w-import").hidden = true;
    $("#w-later").textContent = "Close";
  }} else {{
    $("#w-done-title").textContent = {j('scan_done_title')}
      .replace("{{store}}", d.name).replace("{{count}}", d.count);
    $("#w-done-body").textContent = {j('scan_done_body')};
    $("#w-import").hidden = false;
    $("#w-later").textContent = {j('scan_import_later')};
  }}
  wizStep("w-done");
}}

// ---- friendly notices ----------------------------------------------------
const ICONS = {{
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/>' +
        '<path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/></svg>',
  tag:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0' +
        'L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/></svg>',
  check:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
}};

// Signed in to each store that needs it? true / false / null (cannot tell).
// Answered by the Scanner extension from a cookie's name only.
const ACCOUNT_STORES = {account_json};
const signedIn = {{}};

function askAccounts() {{
  if (!SCANNER) return;
  for (const s of ACCOUNT_STORES) {{
    postMessage({{source: "wss-panel", type: "account", store: s.site}}, location.origin);
  }}
}}

function laterKey(site) {{ return "wss.loginLater." + site; }}

// The bar at the top: shown while you are logged out of a store whose
// coupons need an account. "Maybe later" hides it for this session.
function paintLoginBar() {{
  const bar = $("#loginbar");
  let later = {{}};
  const show = ACCOUNT_STORES.find(s => {{
    try {{ later[s.site] = sessionStorage.getItem(laterKey(s.site)) === "1"; }}
    catch (e) {{ later[s.site] = false; }}
    return signedIn[s.site] === false && !later[s.site];
  }});
  if (!show) {{ bar.hidden = true; return; }}
  $("#loginbar-title").textContent = show.login.title;
  $("#loginbar-body").textContent = show.login.body;
  const go = $("#loginbar-go");
  go.textContent = (show.login.button || "Log in") + " \\u2192";
  go.href = show.url || "#";
  bar.dataset.site = show.site;
  bar.hidden = false;
}}

function loginLater() {{
  const site = $("#loginbar").dataset.site;
  try {{ sessionStorage.setItem(laterKey(site), "1"); }} catch (e) {{}}
  $("#loginbar").hidden = true;
}}
$("#loginbar-later").onclick = loginLater;
$("#loginbar-x").onclick = loginLater;

addEventListener("message", (e) => {{
  if (e.source !== window || !e.data || e.data.source !== "wss-scanner") return;
  if (e.data.type === "account") {{
    signedIn[e.data.store] = e.data.signedIn;
    paintLoginBar();
    if (wizState.started && !$("#w-redeem").hidden) showRedeem(
      wizState.started.redeem, wizState.lastCount, wizState.lastOffers);
  }}
  if (e.data.type === "ready") askAccounts();
}});
// Back from logging in on the store's site: look again.
addEventListener("focus", askAccounts);
document.addEventListener("visibilitychange", () => {{
  if (document.visibilityState === "visible") askAccounts();
}});
askAccounts();

// After a scan: what the store needs before these deals count at the
// register, and for account coupons (ShopRite) each one to load.
function showRedeem(r, count, offers) {{
  const box = $("#w-redeem");
  wizState.lastCount = count; wizState.lastOffers = offers;
  if (!r || !r.title || !count) {{ box.hidden = true; return; }}
  const act = r.level === "action";
  const site = (wizState.started && (wizState.started.adapter || wizState.started.store)) || "";
  const isIn = signedIn[site] === true;
  const words = (act && isIn && r.signed_in) ? r.signed_in : r;
  box.className = "note " + (act ? "warm" : "fresh");
  $("#w-redeem-ico").innerHTML = act ? (isIn ? ICONS.tag : ICONS.user) : ICONS.check;
  $("#w-redeem-title").textContent = words.title;
  $("#w-redeem-body").textContent = words.body || "";
  // "scanned" links go to the exact page the Scanner just read, if it said.
  const url = r.link && ((r.link.scanned && wizState.pageUrl) || r.link.url);
  const a = $("#w-redeem-link");
  a.hidden = !url;
  if (url) {{ a.href = url; a.textContent = (r.link.label || "Open") + " \\u2192"; }}

  // One row per coupon that matched your list: copy its name for the store's
  // coupon search, then load it there. The store has no per-coupon address,
  // so every link opens its coupon list.
  const list = $("#w-redeem-items");
  list.textContent = "";
  list.hidden = !(act && offers.length);
  if (!list.hidden) {{
    const hint = document.createElement("li");
    hint.className = "redeem-hint";
    hint.textContent = "Your " + offers.length + " coupon" + (offers.length === 1 ? "" : "s") +
      " to load. Tip: copy a name, paste it into ShopRite's " +
      '"Search all coupons" box, then tap Load to Card.';
    list.append(hint);
    for (const o of offers) {{
      const li = document.createElement("li");
      const what = document.createElement("span");
      what.className = "what";
      const name = document.createElement("b");
      name.textContent = o.title;
      const detail = document.createElement("span");
      const money = o.savings != null ? "Save $" + Number(o.savings).toFixed(2)
                  : o.sale_price != null ? "$" + Number(o.sale_price).toFixed(2) : "";
      detail.textContent = [money, o.limit ? "limit " + o.limit : ""].filter(Boolean).join(" \\u00b7 ");
      what.append(name, detail);
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copy name";
      copy.onclick = async () => {{
        try {{ await navigator.clipboard.writeText(o.title); copy.textContent = "Copied!"; }}
        catch (e) {{ copy.textContent = "Select it"; }}
        setTimeout(() => copy.textContent = "Copy name", 1500);
      }};
      li.append(what, copy);
      if (url) {{
        const go = document.createElement("a");
        go.href = url; go.target = "_blank"; go.rel = "noopener";
        go.textContent = "Load it \\u2192";
        li.append(go);
      }}
      list.append(li);
    }}
  }}
  box.hidden = false;
}}

$("#w-import").onclick = async () => {{
  const d = await wizPost("import", {{store: wizState.store, xml: wizState.xml}});
  $("#w-after-title").textContent = d.opened ? "Over to the app" : "Almost there";
  $("#w-after-body").textContent = d.opened
    ? {j('scan_imported_body')}
    : "Could not open the app automatically. The file is here (path copied):";
  $("#w-after-path").textContent = d.xml || wizState.xml;
  wizStep("w-after");
}};

$("#w-later").onclick = () => {{
  if (!wizState.xml) {{ wizStop(); wiz.close(); location.reload(); return; }}
  $("#w-after-title").textContent = {j('scan_later_title')};
  $("#w-after-body").textContent = {j('scan_later_body')};
  $("#w-after-path").textContent = wizState.xml;
  wizStep("w-after");
}};

$("#scanclose").onclick = () => $("#scandlg").close();
$("#howto").onclick = () => $("#dlg").showModal();
$("#close").onclick = () => $("#dlg").close();

$("#refresh").onclick = async () => {{
  const b = $("#refresh");
  b.disabled = true;
  b.innerHTML = '<span class="spin"></span>' + esc({j('refresh_working')});
  try {{
    const r = await fetch("/api/refresh", {{method: "POST"}});
    render(await r.json());
  }} catch (e) {{
    $("#results").innerHTML =
      '<div class="card warn">Could not refresh: ' + esc(e.message) + '</div>';
  }} finally {{
    b.disabled = false; b.textContent = {j('refresh_button')};
  }}
}};

function render(d) {{
  if (d.error) {{
    $("#results").innerHTML = '<div class="card warn">' + esc(d.error) + '</div>';
    return;
  }}
  let h = "";
  for (const s of d.stores || []) {{
    h += '<div class="card"><div class="store-line"><h2>' + esc(s.store) +
         '</h2><span class="muted">' + s.count + ' deal' +
         (s.count === 1 ? '' : 's') +
         (s.age ? ' &middot; ' + esc(s.age) : '') + '</span></div>';
    if (!s.count) h += '<p class="muted">Nothing matched your staples.</p>';
    for (const o of s.offers) {{
      h += '<div class="deal"><span class="amt">' + esc(o.amount) +
           '</span><span class="it">' + esc(o.item) + '</span><span class="ti">' +
           esc(o.title) + '</span>' +
           (o.limit ? '<span class="lim">limit ' + o.limit + '</span>' : '') +
           '</div>';
    }}
    if (s.file) h += '<p class="files" style="margin:12px 0 0">' + esc(s.file) + '</p>';
    h += '</div>';
  }}
  for (const n of d.unscanned || []) {{
    h += '<div class="card warn"><h2>' + esc(n.store) +
         ' has not been scanned yet</h2>';
    if (n.error) h += '<p class="muted">' + esc(n.error) + '</p>';
    for (const u of n.urls || [])
      h += '<p><a href="' + esc(u.url) + '" target="_blank" rel="noopener">' +
           esc(u.label) + '</a></p>';
    h += '<p class="muted">Sign in, let the coupon list load, then ask Claude ' +
         '(Claude for Chrome extension) to run browser/harvest.js on that tab. ' +
         'Save what it prints as:</p><p class="files">' + esc(n.path) +
         '</p><p class="muted">Then press Refresh Deals.</p></div>';
  }}
  if (d.when) h += '<p class="muted">Checked ' + esc(d.when) + '</p>';
  $("#results").innerHTML = h || '<div class="card"><p class="muted">Nothing found.</p></div>';
}}

// The tiles are the quickest way to pin a number, so they save on their own.
const TILES = {{"#t-cal": "custom_calories", "#t-pro": "custom_protein",
                "#t-car": "custom_carbs", "#t-fat": "custom_fat"}};

async function saveTiles(field, value) {{
  // Only the box that changed is sent. Sending all four would pin the other
  // three at whatever figure they happened to be showing, which is how
  // editing protein silently froze calories.
  const body = {{}};
  body[field] = value === "" ? null : Number(value);
  const r = await fetch("/api/profile", {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body)}});
  const d = await r.json();
  const mine = d.target.custom_fields || [];
  const map = {{"#t-cal": "calories", "#t-pro": "protein",
                "#t-car": "carbs", "#t-fat": "fat"}};
  for (const [sel, key] of Object.entries(map)) {{
    $(sel).value = d.target[key];
    $(sel).closest(".t").classList.toggle("mine", mine.includes(key));
  }}
  $("#t-reset").hidden = !d.target.custom;
}}

Object.entries(TILES).forEach(([sel, field]) => {{
  const el = $(sel);
  el.addEventListener("change", () => saveTiles(field, el.value.trim()));
  el.addEventListener("keydown", e => {{ if (e.key === "Enter") el.blur(); }});
}});

$("#t-reset").onclick = async () => {{
  await fetch("/api/profile", {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{custom_calories: null, custom_protein: null,
                          custom_carbs: null, custom_fat: null}})}});
  location.reload();
}};

document.querySelectorAll(".theme").forEach(el => {{
  el.onclick = async () => {{
    const name = el.dataset.theme;
    await save({{theme: name}});
    $("#banner").src = "/themes/" + el.dataset.file;
    $("#banner").style.objectPosition = "center " + (el.dataset.focus || 50) + "%";
    document.querySelectorAll(".theme").forEach(x => x.classList.remove("on"));
    el.classList.add("on");
  }};
}});

async function save(patch) {{
  const r = await fetch("/api/branding", {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(patch)}});
  return r.json();
}}

$("#f-msgpick").onchange = () => {{
  if ($("#f-msgpick").value) {{
    $("#f-msg").value = $("#f-msgpick").value;
    $("#listmsg").textContent = $("#f-msgpick").value;
  }}
}};
$("#f-msg").oninput = () => {{ $("#listmsg").textContent = $("#f-msg").value; }};

$("#save").onclick = async () => {{
  await save({{
    app_name: $("#f-app").value, greeting_morning: $("#f-greet").value,
    greeting_afternoon: $("#f-greet").value, greeting_evening: $("#f-greet").value,
    tagline: $("#f-tag").value, deals_header: $("#f-deals").value,
    list_message: $("#f-msg").value,
  }});
  $("#h-app").textContent = $("#f-app").value;
  $("#h-greet").textContent = $("#f-greet").value;
  $("#h-tag").textContent = $("#f-tag").value;
  $("#listmsg").textContent = $("#f-msg").value;
  document.title = $("#f-app").value;
  $("#saved").textContent = "Saved";
  setTimeout(() => $("#saved").textContent = "", 1800);
}};
</script></body></html>"""


# --------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the terminal readable
        pass

    # The scan runs inside the store's page, which is a different origin, and
    # Chrome preflights any request from a public page to a local address.
    # Without these the harvest script cannot hand its result back.
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, page())
        if path.startswith("/themes/"):
            rel = path[len("/themes/"):]
            # Look in your folder first, then the shipped one; and keep the
            # request inside whichever it resolves to.
            full = ""
            for folder in (branding.USER_THEME_DIR, branding.THEME_DIR):
                candidate = os.path.normpath(os.path.join(folder, rel))
                if candidate.startswith(os.path.normpath(folder)) and os.path.isfile(candidate):
                    full = candidate
                    break
            if full:
                ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                with open(full, "rb") as fh:
                    return self._send(200, fh.read(), ctype)
            return self._send(404, b"not found", "text/plain")
        if path in ("/harvest.js", "/browser/harvest.js"):
            script = paths.source("browser", "harvest.js")
            if os.path.isfile(script):
                with open(script, "rb") as fh:
                    return self._send(200, fh.read(),
                                      "application/javascript; charset=utf-8")
            return self._send(404, b"not found", "text/plain")

        if path == "/api/stores":
            # For the Scanner extension's popup: which stores exist, and how
            # each is read.
            return self._send(200, json.dumps({"stores": [
                {"key": s.key, "name": s.name, "urls": s.urls,
                 "adapter": s.adapter or "generic", "redeem": s.redeem}
                for s in stores_mod.load(load_config())]}), "application/json")

        if path == "/api/live":
            return self._live()

        if path == "/api/steps":
            from urllib.parse import parse_qs, urlparse
            key = (parse_qs(urlparse(self.path).query).get("store") or [""])[0]
            store = stores_mod.get(key, load_config())
            return self._send(200, how_to_steps(store.name if store else "the store"))

        if path == "/api/state":
            return self._send(200, json.dumps({
                "branding": branding.load(),
                "themes": branding.themes(),
                "last": _state["last"],
                "active": scanning_active(),
            }), "application/json")
        return self._send(404, b"not found", "text/plain")

    def _live(self):
        """Hold an event stream open for as long as the panel page is open.

        The page never writes to it. The server sends a blank comment each
        second only to learn whether the other end is still there: once the
        tab is closed or navigates away, that write fails and the page is
        counted as gone.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        _page_opened()
        try:
            self.wfile.write(b"retry: 1000\n\n")
            self.wfile.flush()
            while True:
                time.sleep(LIVE_PROBE)
                self.wfile.write(b":\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError,
                OSError):
            pass
        finally:
            _page_closed()
            self.close_connection = True

    def do_HEAD(self):
        """Answer HEAD so a readiness probe sees 200 rather than a 501."""
        path = self.path.split("?")[0]
        known = (path in ("/", "/index.html", "/api/state")
                 or path.startswith("/themes/"))
        self.send_response(200 if known else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"

        if path == "/api/refresh":
            with _lock:
                if _state["running"]:
                    return self._send(409, json.dumps(
                        {"error": "A refresh is already running."}), "application/json")
                _state["running"] = True
            try:
                result = run_refresh()
                _state["last"] = result
                return self._send(200, json.dumps(result), "application/json")
            except Exception as exc:
                return self._send(200, json.dumps({"error": str(exc)}),
                                  "application/json")
            finally:
                _state["running"] = False

        if path == "/api/scanner/report":
            # The Scanner extension's diagnostics for one run: which step
            # failed, how many cards each selector found, samples of what it
            # could not read. The latest per store is kept, plus a one-line
            # history, so a site that changed can be fixed from the report.
            from urllib.parse import parse_qs, urlparse
            key = (parse_qs(urlparse(self.path).query).get("store") or [""])[0]
            key = "".join(c for c in key if c.isalnum() or c in "-_")[:40]
            try:
                report = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}),
                                  "application/json")
            if not key or not isinstance(report, dict):
                return self._send(400, json.dumps({"error": "no store"}),
                                  "application/json")
            folder = paths.data("scanner")
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, f"{key}.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
            summary = {k: report.get(k) for k in
                       ("at", "site", "siteVersion", "ok", "check", "failedAt",
                        "error", "checks")}
            with open(os.path.join(folder, "history.jsonl"), "a",
                      encoding="utf-8") as fh:
                fh.write(json.dumps({"store": key, **summary},
                                    ensure_ascii=False) + "\n")
            return self._send(200, json.dumps({"saved": key}), "application/json")

        if path == "/api/scan/submit":
            # The scan itself, posted straight from the store page. A browser
            # extension cannot write to disk, so the page hands it over here
            # and the panel saves it.
            if not scanning_active():
                # Paused: refuse loudly and write nothing, so the scanning side
                # can show the list instead of believing it was filed.
                return self._send(409, json.dumps(
                    {"error": "the panel is paused and is not accepting scans",
                     "active": False}), "application/json")
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            key = (query.get("store") or [""])[0]
            store = stores_mod.get(key, load_config())
            if store is None:
                return self._send(404, json.dumps({"error": "unknown store"}),
                                  "application/json")
            text = raw.decode("utf-8", errors="replace")
            lines = [ln for ln in text.splitlines() if ln.strip()]
            if not lines:
                return self._send(400, json.dumps(
                    {"error": "the scan was empty"}), "application/json")
            os.makedirs(os.path.dirname(store.harvest_path), exist_ok=True)
            with open(store.harvest_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            return self._send(200, json.dumps(
                {"saved": store.harvest_path, "lines": len(lines),
                 "store": store.name}), "application/json")

        if path == "/api/panel":
            # The switch on the main interface. Absent "active", report only.
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}),
                                  "application/json")
            if "active" in body:
                set_scanning_active(body.get("active"))
            return self._send(200, json.dumps({"active": scanning_active()}),
                              "application/json")

        if path.startswith("/api/scan/"):
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}),
                                  "application/json")
            cfg = load_config()
            store = stores_mod.get(str(body.get("store", "")), cfg)
            if store is None:
                return self._send(404, json.dumps({"error": "unknown store"}),
                                  "application/json")
            brand = branding.load()
            action = path[len("/api/scan/"):]

            if action == "start":
                # Remember what was on disk, so a stale scan is not mistaken
                # for the one the user is about to run.
                baseline = (os.path.getmtime(store.harvest_path)
                            if store.scanned else 0)
                _alive["scanning_since"] = time.monotonic()
                submit = f"{_base['url']}/api/scan/submit?store={store.key}"
                script = f"{_base['url']}/harvest.js"
                # The store's own prompt is what gets used. Sites differ
                # enough -- a widget in a cross-origin frame, a scroll that
                # has to be driven -- that a single generic instruction comes
                # back with a fraction of the offers, which is why stores.py
                # carries one per store. branding's scan_prompt overrides it
                # when set, and is empty by default.
                prompt = store.instruction(
                    submit, script=script,
                    override=str(brand.get("scan_prompt", "")).strip())
                # Same brace-safe substitution for the script variant.
                prompt_script = str(brand.get("scan_prompt_script", ""))
                for token, value in (("{store}", store.name),
                                     ("{submit}", submit),
                                     ("{script}", script)):
                    prompt_script = prompt_script.replace(token, value)
                return self._send(200, json.dumps({
                    "store": store.key, "name": store.name, "urls": store.urls,
                    "adapter": store.adapter or "generic",
                    "redeem": store.redeem,
                    "path": store.harvest_path, "prompt": prompt,
                    "prompt_script": prompt_script, "script": script,
                    "baseline": baseline,
                }), "application/json")

            if action == "check":
                baseline = float(body.get("baseline") or 0)
                if not store.scanned:
                    return self._send(200, json.dumps({"ready": False}),
                                      "application/json")
                mtime = os.path.getmtime(store.harvest_path)
                # Only act on a scan written after the user started this run.
                if mtime <= baseline:
                    return self._send(200, json.dumps({"ready": False}),
                                      "application/json")
                result = build_for(store)
                _alive["scanning_since"] = 0.0     # the scan landed
                return self._send(200, json.dumps({
                    "ready": True, "name": store.name,
                    "count": result.get("count", 0),
                    "xml": result.get("xml", ""),
                    "offers": result.get("offers", []),
                    "error": result.get("error", ""),
                }), "application/json")

            if action == "cancel":
                _alive["scanning_since"] = 0.0
                return self._send(200, json.dumps({"cancelled": True}),
                                  "application/json")

            if action == "import":
                xml = str(body.get("xml") or "")
                # Never hand an arbitrary path to `open`.
                if (not xml or not os.path.isfile(xml)
                        or not os.path.abspath(xml).startswith(OUT_DIR)):
                    return self._send(400, json.dumps(
                        {"error": "no such sales file"}), "application/json")
                app = find_app()
                opened = False
                try:
                    if app:
                        subprocess.run(["open", "-a", app], check=False,
                                       capture_output=True, timeout=15)
                    subprocess.run(["open", "-R", xml], check=False,
                                   capture_output=True, timeout=15)
                    opened = True
                except (OSError, subprocess.SubprocessError):
                    opened = False
                try:
                    subprocess.run(["pbcopy"], input=xml.encode(), check=False,
                                   timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass
                return self._send(200, json.dumps({
                    "opened": opened, "app": os.path.basename(app) if app else "",
                    "xml": xml,
                }), "application/json")

            return self._send(404, json.dumps({"error": "unknown action"}),
                              "application/json")

        if path == "/api/profile":
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}),
                                  "application/json")
            preview = bool(body.pop("preview", False))
            current = profile_mod.load()
            fields = {f for f in profile_mod.Profile.__dataclass_fields__}
            merged = {k: v for k, v in
                      {**profile_mod.asdict(current), **body}.items() if k in fields}
            try:
                prof = profile_mod.Profile(**merged)
            except TypeError as exc:
                return self._send(400, json.dumps({"error": str(exc)}),
                                  "application/json")
            if not preview:
                profile_mod.save(prof)
            return self._send(200, json.dumps({
                "profile": profile_mod.asdict(prof),
                "target": profile_mod.target(prof),
                "complete": prof.complete,
                "saved": not preview,
            }), "application/json")

        if path == "/api/branding":
            try:
                patch = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}),
                                  "application/json")
            return self._send(200, json.dumps(branding.save(patch)),
                              "application/json")

        return self._send(404, b"not found", "text/plain")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--close-grace", "--idle-timeout", dest="close_grace",
                    type=float, default=CLOSE_GRACE,
                    help="stop this many seconds after the last panel page "
                         "closes (0 = never)")
    args = ap.parse_args(argv)

    url = f"http://127.0.0.1:{args.port}"
    _base["url"] = url
    # Bind to loopback only: this panel is for the person at this machine.
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(f"Could not start on port {args.port}: {exc}\n"
              f"Something else is using it. Try:  python3 panel.py --port {args.port + 1}",
              file=sys.stderr)
        return 1
    print(f"{branding.load().get('app_name')} - control panel\n  {url}\n"
          "  Press Ctrl+C to stop.")
    threading.Thread(target=_watchdog, args=(server, args.close_grace),
                     daemon=True).start()
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

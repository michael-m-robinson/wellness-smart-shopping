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
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dealcrawler import (branding, offers as offers_mod, profile as profile_mod,
                         stores as stores_mod, xmlout)
from dealcrawler.sources import harvest

OUT_DIR = os.path.join(HERE, "out")

_state = {"running": False, "last": None}
_lock = threading.Lock()


def load_config() -> dict:
    for name in ("config.json", "config.example.json"):
        path = os.path.join(HERE, name)
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
    return {"found": True, "count": len(offers), "xml": xml_path,
            "mtime": os.path.getmtime(store.harvest_path)}


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


# ------------------------------------------------------------------ page
def page() -> str:
    brand = branding.load()
    hour = datetime.datetime.now().hour
    g = lambda k: html.escape(str(brand.get(k, "")))
    # For values embedded in JavaScript: JSON-encode (quotes included) rather
    # than HTML-escape, which would leak entities into textContent.
    j = lambda k: json.dumps(str(brand.get(k, "")))
    theme = brand.get("theme") or "50s-1"
    theme_files = {t["name"]: t["file"] for t in branding.themes()}
    banner_file = theme_files.get(theme) or next(iter(theme_files.values()), "")
    steps = brand.get("import_steps") or []
    steps_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in steps)
    prof = profile_mod.load()
    tgt = profile_mod.target(prof)
    first_run = not profile_mod.exists()
    presets = brand.get("list_message_presets") or []
    msg_opts = "".join(
        f'<option value="{html.escape(str(m))}">{html.escape(str(m))}</option>'
        for m in presets)
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
        f'title="{html.escape(t["description"])}">'
        f'<img src="/themes/{html.escape(t["thumb"])}" loading="lazy" '
        f'alt="{html.escape(t["name"])}">'
        f'<span>{html.escape(t["name"].replace("-", " "))}</span></button>'
        for t in branding.themes())

    first_run_js = "true" if first_run else "false"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{g('app_name')}</title>
<style>
  :root {{
    --bg:#f7f6f3; --card:#fff; --ink:#1c1b19; --muted:#6b6862;
    --line:#e5e2dc; --accent:#3f7d4f; --accent-ink:#fff;
    --good:#2f7a45; --warn:#9a6212; --warn-bg:#fdf5e6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#16181a; --card:#1e2124; --ink:#eceae6; --muted:#a3a09a;
      --line:#2e3236; --accent:#6fae7d; --accent-ink:#10231a;
      --good:#7cc08e; --warn:#e0b070; --warn-bg:#2a2317;
    }}
  }}
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

<header>
  <img id="banner" src="/themes/{html.escape(banner_file)}" alt="">
  <div class="veil"></div>
  <div class="txt">
    <h1 id="h-app">{g('app_name')}</h1>
    <p id="h-greet">{html.escape(branding.greeting(brand, hour))}</p>
    <div class="tag" id="h-tag">{g('tagline')}</div>
  </div>
</header>

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
  <button class="primary" id="scanwith">{g('scan_button')}</button>
  <button id="refresh">{g('refresh_button')}</button>
  <button id="howto">{g('import_button')}</button>
</div>

<div class="card" id="profile-card">
  <div class="store-line">
    <h2>{g('targets_header')}</h2>
    <button id="editprofile" style="padding:6px 12px;font-size:.85rem">{g('profile_edit_button')}</button>
  </div>
  <div id="targets" class="targets">
    <div class="t"><b id="t-cal">{tgt['calories']}</b><span>kcal / day</span></div>
    <div class="t"><b id="t-pro">{tgt['protein']}g</b><span>protein</span></div>
    <div class="t"><b id="t-car">{tgt['carbs']}g</b><span>carbs</span></div>
    <div class="t"><b id="t-fat">{tgt['fat']}g</b><span>fat</span></div>
    <div class="t"><b id="t-goal">{html.escape(tgt['goal_label'])}</b><span>goal</span></div>
  </div>
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

  <section id="w-wait" hidden>
    <h2 id="w-wait-title"></h2>
    <p class="muted">{g('scan_wait_body')}</p>
    <div id="w-links"></div>
    <label style="margin-top:14px">Give Claude this instruction</label>
    <div class="promptbox"><code id="w-prompt"></code>
      <button id="w-copy" style="padding:6px 12px;font-size:.82rem">Copy</button></div>
    <p class="muted" id="w-ext" hidden style="margin:12px 0 0">
      Need the extension?
      <a href="{g('extension_url')}" target="_blank" rel="noopener">Install Claude for Chrome</a>
    </p>
    <p class="muted" id="w-status" style="margin:16px 0 0">
      <span class="spin"></span>{g('scan_waiting')}</p>
    <div class="row" style="margin:14px 0 0"><button id="w-cancel">Cancel</button></div>
  </section>

  <section id="w-done" hidden>
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
    Chrome, open its weekly ad, then ask Claude (with the Claude for Chrome
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
  $(scope + "cal").textContent = t.calories;
  $(scope + "pro").textContent = t.protein + "g";
  $(scope + "car").textContent = t.carbs + "g";
  $(scope + "fat").textContent = t.fat + "g";
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

$("#ext-have").onclick = () => {{
  store("wss.hasExtension", "yes");
  $("#extbar").hidden = true;
  $("#w-ext").hidden = true;
}};

// ---- Scan with Claude -----------------------------------------------------
const wiz = $("#scanwiz");
let wizState = {{store: null, baseline: 0, xml: "", timer: null}};

function wizStep(id) {{
  ["w-pick", "w-wait", "w-done", "w-after"].forEach(
    s => $("#" + s).hidden = (s !== id));
}}

function wizStop() {{
  if (wizState.timer) {{ clearInterval(wizState.timer); wizState.timer = null; }}
}}

async function wizPost(action, body) {{
  const r = await fetch("/api/scan/" + action, {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body)}});
  return r.json();
}}

$("#scanwith").onclick = () => {{ wizStop(); wizStep("w-pick"); wiz.showModal(); }};
$("#w-pick-close").onclick = () => {{ wizStop(); wiz.close(); }};
$("#w-cancel").onclick = () => {{ wizStop(); wizStep("w-pick"); }};
$("#w-again").onclick = () => {{ wizStop(); wizStep("w-pick"); }};
$("#w-after-close").onclick = () => {{ wizStop(); wiz.close(); location.reload(); }};
$("#w-help").onclick = () => {{ wiz.close(); $("#scandlg").showModal(); }};

document.querySelectorAll(".picker").forEach(el => {{
  el.onclick = async () => {{
    const key = el.dataset.store;
    const d = await wizPost("start", {{store: key}});
    wizState = {{store: key, baseline: d.baseline, xml: "", timer: null}};
    $("#w-wait-title").textContent = {j('scan_wait_title')}.replace("{{store}}", d.name);
    $("#w-prompt").textContent = d.prompt;
    $("#w-links").innerHTML = (d.urls || []).map(
      u => '<p><a href="' + esc(u.url) + '" target="_blank" rel="noopener">' +
           esc(u.label) + '</a></p>').join("");
    $("#w-status").innerHTML = '<span class="spin"></span>' + esc({j('scan_waiting')});
    wizStep("w-wait");
    wizState.timer = setInterval(wizPoll, 2500);
  }};
}});

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

document.querySelectorAll(".theme").forEach(el => {{
  el.onclick = async () => {{
    const name = el.dataset.theme;
    await save({{theme: name}});
    $("#banner").src = "/themes/" + el.dataset.file;
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

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, page())
        if path.startswith("/themes/"):
            rel = path[len("/themes/"):]
            # Keep the request inside themes/ regardless of what was asked for.
            full = os.path.normpath(os.path.join(branding.THEME_DIR, rel))
            if (full.startswith(os.path.realpath(branding.THEME_DIR))
                    or full.startswith(branding.THEME_DIR)) and os.path.isfile(full):
                ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                with open(full, "rb") as fh:
                    return self._send(200, fh.read(), ctype)
            return self._send(404, b"not found", "text/plain")
        if path == "/api/state":
            return self._send(200, json.dumps({
                "branding": branding.load(),
                "themes": branding.themes(),
                "last": _state["last"],
            }), "application/json")
        return self._send(404, b"not found", "text/plain")

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
                prompt = str(brand.get("scan_prompt", "")).format(
                    store=store.name, path=store.harvest_path)
                return self._send(200, json.dumps({
                    "store": store.key, "name": store.name, "urls": store.urls,
                    "path": store.harvest_path, "prompt": prompt,
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
                return self._send(200, json.dumps({
                    "ready": True, "name": store.name,
                    "count": result.get("count", 0),
                    "xml": result.get("xml", ""),
                    "error": result.get("error", ""),
                }), "application/json")

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
    args = ap.parse_args(argv)

    url = f"http://127.0.0.1:{args.port}"
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
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

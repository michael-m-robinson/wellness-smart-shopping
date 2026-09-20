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
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dealcrawler import branding, offers as offers_mod, xmlout
from dealcrawler.fetch import NeedsSignIn
from dealcrawler.sources import costco, harvest, shoprite, stews

SOURCES = {"shoprite": shoprite, "stews": stews, "costco": costco}
OUT_DIR = os.path.join(HERE, "out")

_state = {"running": False, "last": None}
_lock = threading.Lock()


# ----------------------------------------------------------------- crawl
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


def run_refresh(store_keys=None, refresh=True) -> dict:
    cfg = load_config()
    per_weight = cfg.get("per_weight", "convert")
    use_twins = cfg.get("snack_twins", True)
    keys = store_keys or [k for k in SOURCES
                          if cfg.get("stores", {}).get(k, {}).get("enabled", True)]

    stores, needs_signin, written = [], [], []
    for key in keys:
        mod = SOURCES.get(key)
        if mod is None:
            continue
        try:
            found = mod.crawl(refresh=refresh, per_weight=per_weight)
        except NeedsSignIn as exc:
            store_cfg = cfg.get("stores", {}).get(key, {})
            urls = (mod.signin_urls(store_cfg.get("store_id", "000"))
                    if hasattr(mod, "signin_urls") else [exc.url])
            needs_signin.append({"key": key, "store": mod.STORE,
                                 "reason": exc.reason, "urls": urls})
            continue
        except Exception as exc:  # a broken source must not take the panel down
            needs_signin.append({"key": key, "store": mod.STORE,
                                 "reason": f"could not be read ({exc})", "urls": []})
            continue

        found = offers_mod.dedupe(found)
        if use_twins:
            found = offers_mod.dedupe(offers_mod.mirror_twins(found))

        path = ""
        if found:
            os.makedirs(OUT_DIR, exist_ok=True)
            xml = xmlout.render(mod.STORE, found)
            if not xmlout.validate(xml):
                today = datetime.date.today()
                path = os.path.join(OUT_DIR, f"{key}-sales-{today:%Y-%m-%d}.xml")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(xml)
                written.append(path)

        stores.append({
            "key": key, "store": mod.STORE, "count": len(found), "file": path,
            "offers": [{
                "item": o.item_id,
                "amount": (f"save ${o.savings:.2f}" if o.savings is not None
                           else f"${o.sale_price:.2f}"),
                "limit": o.limit, "title": o.title, "basis": o.basis,
            } for o in found],
        })

    return {"stores": stores, "needs_signin": needs_signin, "written": written,
            "when": datetime.datetime.now().strftime("%a %d %b, %H:%M")}


# A store can expose more than one page worth opening (a coupon list and a
# weekly ad), so label each link by what it actually opens.
LINK_LABELS = (
    ("digital-coupon", "Open the digital coupon list"),
    ("weekly-ad", "Open the weekly ad"),
    ("flyer", "Open the weekly flyer"),
    ("warehouse-savings", "Open warehouse savings"),
)


def link_label(url: str, store: str) -> str:
    for needle, label in LINK_LABELS:
        if needle in url:
            return label
    return f"Open {store}"


def scan_help() -> list:
    """Per-store scanning directions, built from the stores actually enabled.

    Each store says whether it can be read without signing in, and gives the
    exact page to open and the exact command to run afterwards.
    """
    cfg = load_config()
    out = []
    for key, mod in SOURCES.items():
        if not cfg.get("stores", {}).get(key, {}).get("enabled", True):
            continue
        store_cfg = cfg.get("stores", {}).get(key, {})
        urls = (mod.signin_urls(store_cfg.get("store_id", "000"))
                if hasattr(mod, "signin_urls") else [])
        # A store with its own crawl() that does not need a browser is automatic.
        public = key == "costco" or key == "shoprite"
        out.append({
            "key": key,
            "store": mod.STORE,
            "urls": [{"url": u, "label": link_label(u, mod.STORE)} for u in urls],
            "public": public,
            "public_note": ("Refresh Deals already reads this store's public "
                            "deals. Scan it as well to pick up the coupons that "
                            "only appear when you are signed in."
                            if public else
                            "This store can only be read from a signed-in "
                            "browser, so it must be scanned."),
            "command": f"python3 crawl.py --harvest {key}=offers.txt",
        })
    return out


# ------------------------------------------------------------------ page
def page() -> str:
    brand = branding.load()
    hour = datetime.datetime.now().hour
    g = lambda k: html.escape(str(brand.get(k, "")))
    theme = brand.get("theme") or "farm-market"
    steps = brand.get("import_steps") or []
    steps_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in steps)
    scan_steps = brand.get("scan_steps") or []
    scan_steps_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in scan_steps)
    stores_html = ""
    for st in scan_help():
        links = "".join(
            f'<p><a href="{html.escape(u["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(u["label"])}</a></p>' for u in st["urls"])
        badge = ('<span class="pill auto">reads without signing in</span>'
                 if st["public"] else
                 '<span class="pill need">needs sign-in</span>')
        stores_html += (
            f'<div class="store-help"><div class="sh-head"><strong>'
            f'{html.escape(st["store"])}</strong>{badge}</div>'
            f'<p class="muted">{html.escape(st["public_note"])}</p>{links}'
            f'<code>{html.escape(st["command"])}</code></div>')
    themes_html = "".join(
        f'<button class="theme{" on" if t["name"] == theme else ""}" '
        f'data-theme="{html.escape(t["name"])}" title="{html.escape(t["description"])}">'
        f'<img src="/themes/{html.escape(t["file"])}" alt="{html.escape(t["name"])}">'
        f'<span>{html.escape(t["name"].replace("-", " "))}</span></button>'
        for t in branding.themes())

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
  <img id="banner" src="/themes/{html.escape(theme)}.png" alt="">
  <div class="veil"></div>
  <div class="txt">
    <h1 id="h-app">{g('app_name')}</h1>
    <p id="h-greet">{html.escape(branding.greeting(brand, hour))}</p>
    <div class="tag" id="h-tag">{g('tagline')}</div>
  </div>
</header>

<div class="row">
  <button class="primary" id="refresh">{g('refresh_button')}</button>
  <button id="scan">{g('scan_button')}</button>
  <button id="howto">{g('import_button')}</button>
</div>

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
  <div class="row" style="margin:16px 0 0"><button id="save">{g('save_button')}</button>
    <span class="muted" id="saved" style="align-self:center"></span></div>
</div>

<p class="muted">{g('footer')}</p>
</div>

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

$("#scan").onclick = () => $("#scandlg").showModal();
$("#scanclose").onclick = () => $("#scandlg").close();
$("#howto").onclick = () => $("#dlg").showModal();
$("#close").onclick = () => $("#dlg").close();

$("#refresh").onclick = async () => {{
  const b = $("#refresh");
  b.disabled = true;
  b.innerHTML = '<span class="spin"></span>{g('refresh_working')}';
  try {{
    const r = await fetch("/api/refresh", {{method: "POST"}});
    render(await r.json());
  }} catch (e) {{
    $("#results").innerHTML =
      '<div class="card warn">Could not refresh: ' + esc(e.message) + '</div>';
  }} finally {{
    b.disabled = false; b.textContent = "{g('refresh_button')}";
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
         (s.count === 1 ? '' : 's') + '</span></div>';
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
  for (const n of d.needs_signin || []) {{
    h += '<div class="card warn"><h2>' + esc(n.store) +
         ' needs you signed in</h2><p class="muted">' + esc(n.reason) + '</p>';
    for (const u of n.urls || [])
      h += '<p><a href="' + esc(u) + '" target="_blank" rel="noopener">Open ' +
           esc(n.store) + ' in a new tab</a></p>';
    h += '<p class="muted">Sign in, open the weekly ad or coupon list, then ask ' +
         'Claude (Claude for Chrome extension) to run browser/harvest.js on that ' +
         'tab and refresh again.</p></div>';
  }}
  if (d.when) h += '<p class="muted">Checked ' + esc(d.when) + '</p>';
  $("#results").innerHTML = h || '<div class="card"><p class="muted">Nothing found.</p></div>';
}}

document.querySelectorAll(".theme").forEach(el => {{
  el.onclick = async () => {{
    const name = el.dataset.theme;
    await save({{theme: name}});
    $("#banner").src = "/themes/" + name + ".png";
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

$("#save").onclick = async () => {{
  await save({{
    app_name: $("#f-app").value, greeting_morning: $("#f-greet").value,
    greeting_afternoon: $("#f-greet").value, greeting_evening: $("#f-greet").value,
    tagline: $("#f-tag").value, deals_header: $("#f-deals").value,
  }});
  $("#h-app").textContent = $("#f-app").value;
  $("#h-greet").textContent = $("#f-greet").value;
  $("#h-tag").textContent = $("#f-tag").value;
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
            name = os.path.basename(path)
            full = os.path.join(branding.THEME_DIR, name)
            if os.path.isfile(full):
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

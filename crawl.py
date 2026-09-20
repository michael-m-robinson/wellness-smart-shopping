#!/usr/bin/env python3
"""Wellness Smart Shopping - turn scanned store deals into sales XML.

This program never contacts a store. Deals are read from your signed-in browser
by the Claude for Chrome extension (see browser/harvest.js), saved into
`harvest/<store>.txt`, and turned into XML here for the shopping app's
"Import Sales XML..." command.

    python3 crawl.py                       # read every store's scan
    python3 crawl.py --report              # show matches, write nothing
    python3 crawl.py --stores costco
    python3 crawl.py --harvest stews=~/Downloads/stews.txt
    python3 crawl.py --scan-help           # how to scan each store
"""

import argparse
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dealcrawler import offers as offers_mod, paths, stores as stores_mod, xmlout
from dealcrawler.sources import harvest

SCAN_HELP = """
  ------------------------------------------------------------------
  {name} has not been scanned yet.
  ------------------------------------------------------------------
  Deals are read from your own signed-in browser, so scan it first:

    1. Sign in to {name} in Chrome and open:
{urls}
    2. Let the coupon list finish loading, and scroll it once.
    3. Ask Claude, with the Claude for Chrome extension enabled:
         "run browser/harvest.js on this tab"
    4. Save what it prints to:
         {path}
    5. Run this again.
  ------------------------------------------------------------------
"""


def load_config(path=None):
    for candidate in ([path] if path else []) + [
            paths.data("config.json"),
            paths.source("config.example.json")]:
        if candidate and os.path.exists(candidate):
            try:
                with open(candidate) as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                continue
    return {}


def scan_help_text(store):
    urls = "\n".join(f"         {u['url']}" for u in store.urls) or "         (no URL configured)"
    return SCAN_HELP.format(name=store.name, urls=urls, path=store.harvest_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stores", default="", help="comma list of store keys")
    ap.add_argument("--harvest", action="append", default=[], metavar="STORE=FILE",
                    help="use a scan file from somewhere other than harvest/")
    ap.add_argument("--out", default=paths.data("out"))
    ap.add_argument("--report", action="store_true", help="print matches, write nothing")
    ap.add_argument("--per-weight", choices=["convert", "skip"], default=None)
    ap.add_argument("--no-snack-twins", action="store_true")
    ap.add_argument("--combined", action="store_true", help="also write an all-stores file")
    ap.add_argument("--scan-help", action="store_true",
                    help="print scanning directions for every store and exit")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    per_weight = args.per_weight or cfg.get("per_weight", "convert")
    use_twins = cfg.get("snack_twins", True) and not args.no_snack_twins

    all_stores = stores_mod.load(cfg)
    by_key = {s.key: s for s in all_stores}

    overrides = {}
    for spec in args.harvest:
        key, _, path = spec.partition("=")
        if not path:
            ap.error(f"--harvest needs STORE=FILE, got {spec!r}")
        if key not in by_key:
            ap.error(f"unknown store {key!r}; known: {', '.join(by_key)}")
        overrides[key] = os.path.expanduser(path)

    if args.stores:
        wanted = [k.strip() for k in args.stores.split(",") if k.strip()]
        for k in wanted:
            if k not in by_key:
                ap.error(f"unknown store {k!r}; known: {', '.join(by_key)}")
        selected = [by_key[k] for k in wanted]
    else:
        selected = all_stores

    if args.scan_help:
        for store in selected:
            print(scan_help_text(store))
        return 0

    all_offers, unscanned, wrote = [], [], []
    for store in selected:
        path = overrides.get(store.key, store.harvest_path)
        if not os.path.isfile(path):
            unscanned.append(store)
            continue
        try:
            found = harvest.parse_file(path, store.name, per_weight)
        except (OSError, ValueError) as exc:
            print(f"  ! could not read {path}: {exc}", file=sys.stderr)
            continue

        found = offers_mod.dedupe(found)
        if use_twins:
            found = offers_mod.dedupe(offers_mod.mirror_twins(found))

        age = store.scan_age_hours
        stamp = f", scanned {age:.0f}h ago" if age is not None and not overrides.get(store.key) else ""
        print(f"{store.name}: {len(found)} matched offer(s){stamp}")
        for o in found:
            amount = (f"save ${o.savings:.2f}" if o.savings is not None
                      else f"${o.sale_price:.2f}/pkg")
            lim = f" limit {o.limit}" if o.limit else ""
            print(f"    {o.item_id:16} {amount:14}{lim:10} {o.title[:52]}")
            if args.report and o.basis:
                print(f"        basis: {o.basis}")
        all_offers.extend(found)

        if not args.report and found:
            os.makedirs(args.out, exist_ok=True)
            xml = xmlout.render(store.name, found)
            problems = xmlout.validate(xml)
            if problems:
                print(f"  ! {store.name} XML rejected: {problems}", file=sys.stderr)
                continue
            dest = os.path.join(args.out, f"{store.key}-sales-{date.today():%Y-%m-%d}.xml")
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(xml)
            wrote.append(dest)

    if not args.report and args.combined and all_offers:
        os.makedirs(args.out, exist_ok=True)
        xml = xmlout.render("All Stores", offers_mod.dedupe(all_offers))
        if not xmlout.validate(xml):
            dest = os.path.join(args.out, f"all-sales-{date.today():%Y-%m-%d}.xml")
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(xml)
            wrote.append(dest)

    for store in unscanned:
        print(scan_help_text(store))

    if wrote:
        print("\nWrote:")
        for p in wrote:
            print(f"  {p}")
        print("\nIn the shopping app: Import Sales XML..., pick a file above.")
    elif not args.report and not unscanned:
        print("\nNo offers matched the catalog in the scans provided.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

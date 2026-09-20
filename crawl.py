#!/usr/bin/env python3
"""Store Deal Crawler -> Smart Shopping List sales XML.

Collects this week's advertised deals, digital coupons and instant savings from
your grocery stores, matches them against the Smart Shopping List catalog, and
writes XML you can load with the app's "Import Sales XML..." command.

    python3 crawl.py                     # crawl every enabled store
    python3 crawl.py --report            # show what matched, write nothing
    python3 crawl.py --stores costco     # one store only
    python3 crawl.py --harvest stews=harvest.txt
"""

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dealcrawler import offers as offers_mod
from dealcrawler import xmlout
from dealcrawler.fetch import NeedsSignIn
from dealcrawler.sources import costco, harvest, shoprite, stews

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = {"shoprite": shoprite, "stews": stews, "costco": costco}

SIGNIN_HELP = """
  ------------------------------------------------------------------
  {store} needs you to be signed in.
  ------------------------------------------------------------------
  {reason}

  To collect these deals:
    1. Open Chrome and sign in to {store} at:
         {urls}
    2. Open the store's weekly ad / digital coupon list and let it
       finish loading.
    3. Ask Claude (with the Claude for Chrome extension enabled) to
       run browser/harvest.js on that page, or paste the contents of
       that file into the browser console yourself.
    4. Save what it prints to a file, then re-run:
         python3 crawl.py --harvest {key}=<that file>
  ------------------------------------------------------------------
"""


def load_config(path):
    if path and os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    default = os.path.join(HERE, "config.json")
    if os.path.exists(default):
        with open(default) as fh:
            return json.load(fh)
    with open(os.path.join(HERE, "config.example.json")) as fh:
        return json.load(fh)


def store_label(key):
    return SOURCES[key].STORE


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stores", default="", help="comma list: shoprite,stews,costco")
    ap.add_argument("--harvest", action="append", default=[], metavar="STORE=FILE",
                    help="use browser-harvested offer text for a store")
    ap.add_argument("--out", default=os.path.join(HERE, "out"), help="output directory")
    ap.add_argument("--report", action="store_true", help="print matches, write no files")
    ap.add_argument("--refresh", action="store_true", help="ignore the local cache")
    ap.add_argument("--per-weight", choices=["convert", "skip"], default=None,
                    help="convert $/lb deals to per-package, or skip them")
    ap.add_argument("--no-snack-twins", action="store_true",
                    help="do not mirror offers onto the snack line items")
    ap.add_argument("--combined", action="store_true",
                    help="also write one all-stores file")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    per_weight = args.per_weight or cfg.get("per_weight", "convert")
    use_twins = cfg.get("snack_twins", True) and not args.no_snack_twins

    harvest_map = {}
    for spec in args.harvest:
        key, _, path = spec.partition("=")
        if not path:
            ap.error(f"--harvest needs STORE=FILE, got {spec!r}")
        if key not in SOURCES:
            ap.error(f"unknown store {key!r}; choose from {', '.join(SOURCES)}")
        harvest_map[key] = path

    if args.stores:
        keys = [k.strip() for k in args.stores.split(",") if k.strip()]
    else:
        keys = [k for k in SOURCES
                if cfg.get("stores", {}).get(k, {}).get("enabled", True)]
    for k in keys:
        if k not in SOURCES:
            ap.error(f"unknown store {k!r}; choose from {', '.join(SOURCES)}")

    all_offers, needs_signin, wrote = [], [], []
    for key in keys:
        mod = SOURCES[key]
        label = mod.STORE
        try:
            if key in harvest_map:
                found = harvest.parse_file(harvest_map[key], label, per_weight)
                origin = f"harvested from {harvest_map[key]}"
            else:
                found = mod.crawl(refresh=args.refresh, per_weight=per_weight)
                origin = "public page"
        except NeedsSignIn as exc:
            store_cfg = cfg.get("stores", {}).get(key, {})
            urls = mod.signin_urls(store_cfg.get("store_id", "000")) \
                if hasattr(mod, "signin_urls") else [exc.url]
            needs_signin.append((key, label, exc.reason, urls))
            continue
        except FileNotFoundError as exc:
            print(f"  {label}: harvest file not found: {exc}", file=sys.stderr)
            continue

        found = offers_mod.dedupe(found)
        if use_twins:
            found = offers_mod.dedupe(offers_mod.mirror_twins(found))
        print(f"{label}: {len(found)} matched offer(s) ({origin})")
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
            xml = xmlout.render(label, found)
            problems = xmlout.validate(xml)
            if problems:
                print(f"  ! {label} XML rejected: {problems}", file=sys.stderr)
                continue
            path = os.path.join(args.out, f"{key}-sales-{date.today():%Y-%m-%d}.xml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(xml)
            wrote.append(path)

    if not args.report and args.combined and all_offers:
        os.makedirs(args.out, exist_ok=True)
        xml = xmlout.render("All Stores", offers_mod.dedupe(all_offers))
        if not xmlout.validate(xml):
            path = os.path.join(args.out, f"all-sales-{date.today():%Y-%m-%d}.xml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(xml)
            wrote.append(path)

    for key, label, reason, urls in needs_signin:
        print(SIGNIN_HELP.format(store=label, reason=reason, key=key,
                                 urls="\n         ".join(urls)))

    if wrote:
        print("\nWrote:")
        for p in wrote:
            print(f"  {p}")
        print("\nIn Smart Shopping List: File > Import Sales XML..., pick a file above.")
    elif not args.report and not needs_signin:
        print("\nNo offers matched the catalog this week.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

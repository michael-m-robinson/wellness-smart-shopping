# Store Deal Crawler

**Turn this week's grocery sales into a shopping list that still hits your
nutrition targets.**

Store Deal Crawler reads the weekly deals, digital coupons and instant savings
from your grocery stores, matches them to the staples on your list, and writes
a small XML file. You import that file into the
[Smart Shopping List](#the-companion-app) desktop app and it re-prices your
list, re-ranks your recipes, and tells you what the trip should actually cost.

> **Free and open source.** Bring your own stores and your own accounts.
> Nothing here is tied to one household, one store or one region.

> 📱 **A mobile version is coming soon.**

---

## Why this exists

Eating well is rarely a knowledge problem. Most people already know they should
buy more lean protein, more produce, more whole grains. The problem is that
those foods look expensive at the shelf, sales change every week, and the deals
that *would* make a healthy basket affordable are scattered across a paper
circular, a digital-coupon list behind a login, and an instant-savings booklet.

So the usual thing happens: you shop by habit, the healthy items get cut when
the total climbs, and the cheap calories stay in the cart.

This tool closes that gap.

- **It looks for deals on the food you actually want to eat.** The matcher only
  recognises staples — lean ground turkey, chicken breast, eggs, plain Greek
  yogurt, lentils, frozen fish, oats, brown rice, produce, olive oil, spices. A
  sale on candy, soda or snack bars is deliberately ignored, so a "good week"
  never means a week of junk.
- **It makes the healthy option the cheap option.** When the app knows chicken
  breast is $1.99/lb and lentils are on sale, it can build the same week of
  meals for less — instead of you discovering the deal after you have already
  bought something else.
- **It protects the nutrition targets.** The XML only adjusts *prices and
  limits*. The app still plans to your calorie and macro goals; a deal can
  change which protein you buy, not whether you hit your protein.
- **It respects purchase limits.** "Limit 4" is carried into the file, so the
  savings you are shown are savings you can really get at the register.
- **It is honest about what a deal is worth.** A `$3.99/lb` advertisement is
  converted into a real per-package price, "2 for $5" becomes a unit price, and
  a discount larger than the item's normal price is capped instead of being
  taken at face value.

The result: a weekly shop where the produce and lean protein survive the budget
cut, because the numbers are on their side.

---

## What you need

| Requirement | Why |
| --- | --- |
| **A Claude subscription** | Required. The sign-in-protected stores are read by Claude driving your browser. |
| **The Claude for Chrome extension** | Required. This is what runs the harvest script inside the store page you are signed in to. |
| **Python 3.9+** | The crawler itself. Standard library only — nothing to install. |
| **Chrome, signed in to your stores** | Digital coupons and member pricing only exist inside your own logged-in session. |
| The Smart Shopping List desktop app | Optional. The XML is plain text and can be read by anything. |

> **Please sign in to your stores before crawling.** Most grocers serve deals
> only to a signed-in session. If you are signed out, the crawler will stop and
> print exactly which store needs you and which page to open — it will not
> quietly return an empty file.

**Why a Claude subscription is needed:** stores like ShopRite and Stew
Leonard's block plain scripts outright (HTTP 403) and render their offers in
JavaScript behind an account. There is no public feed to read. The only
reliable way in is a real browser that is already signed in as you, and that is
what the Claude for Chrome extension provides. Stores that *do* publish a
public deals page — Costco's warehouse savings, for example — are read directly
with no browser and no subscription involved.

---

## Install

```bash
git clone https://github.com/michael-m-robinson/store-deal-crawler.git
cd store-deal-crawler
cp config.example.json config.json
```

Then open `config.json` and set your stores:

```json
{
  "stores": {
    "shoprite": { "enabled": true, "store_id": "000" },
    "stews":    { "enabled": true },
    "costco":   { "enabled": true }
  },
  "per_weight": "convert",
  "snack_twins": true
}
```

Find `store_id` by opening your store on shoprite.com and copying the number
out of the URL: `.../rsid/<store_id>/...`.

---

## Use

```bash
# See what this week's deals match, without writing anything
python3 crawl.py --report

# Write the XML files
python3 crawl.py

# One store at a time
python3 crawl.py --stores costco

# Ignore the local cache and re-fetch
python3 crawl.py --refresh
```

Files land in `out/`, one per store plus an optional combined file:

```
out/shoprite-sales-2026-09-20.xml
out/costco-sales-2026-09-20.xml
```

### Stores that need your browser

When a store is behind a login, the crawler tells you so:

```
  Stew Leonard's needs you to be signed in.
  the site returned HTTP 403; its deals are behind a sign-in or bot
  check and must be read from your signed-in browser
```

To collect those deals:

1. Sign in to the store in Chrome and open its weekly ad / digital coupon list.
2. Ask Claude (with the Claude for Chrome extension on) to run
   `browser/harvest.js` on that tab. It scrolls the page so lazy offers load,
   then prints one offer per line. If you are signed out it says so instead of
   returning nothing.
3. Save that output to a file and feed it back:

```bash
python3 crawl.py --harvest stews=offers.txt
```

### Import into the app

In Smart Shopping List: **Import Sales XML…**, then choose a file from `out/`.
The app applies every offer whose `itemId` it recognises and ignores the rest.

> Account-clipped coupons still have to be clipped in your store account. The
> XML tells the app what a deal is worth; it cannot clip it for you.

---

## Options

| Flag | Effect |
| --- | --- |
| `--report` | Print matches and the reasoning behind each number; write nothing. |
| `--stores a,b` | Limit to specific stores. |
| `--harvest store=file` | Use browser-harvested text for a store. |
| `--refresh` | Bypass the local page cache. |
| `--per-weight convert\|skip` | Convert `$/lb` deals to per-package (default) or drop them. |
| `--no-snack-twins` | Do not mirror a deal onto the snack line items. |
| `--combined` | Also write one all-stores file. |
| `--out DIR` | Change the output directory. |

---

## Adding your own store

Each store is one small module in `dealcrawler/sources/`. A module needs a
`STORE` name, a `crawl()` that returns `Offer` objects, and optionally
`signin_urls()` for the sign-in prompt. Parsing helpers, price maths and the
XML writer are shared, so a new store is usually a parser and a URL. Register
it in the `SOURCES` map in `crawl.py`.

If a store blocks scripts, you do not need a parser at all — point people at
`browser/harvest.js` and accept the harvested text.

---

## The companion app

The XML format is documented in **[docs/XML-IMPORT.md](docs/XML-IMPORT.md)**,
including the full list of catalog item IDs the importer accepts. The format is
plain text and deliberately simple, so you can generate it from a spreadsheet,
a script, or by hand — this crawler is just one producer.

---

## Privacy

- The crawler runs entirely on your machine.
- **It never sees, asks for, or stores your store passwords.** Sign-in happens
  in your own browser; only the visible text of a page you already opened is
  ever read.
- `config.json`, `cache/` and `out/` are git-ignored so your store numbers and
  local data stay off GitHub.

---

## License

[MIT](LICENSE) — free to use, change and redistribute, including commercially.
No warranty: advertised prices change, stores make mistakes, and the matcher is
heuristic. Always check your receipt.

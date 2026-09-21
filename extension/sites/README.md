# Store sites

Each store the Scanner reads is one file here. The file says **what** the page
looks like (selectors, how the list loads, how to turn a card into a line, what
the page's own totals should be). The engine (`../engine/engine.js`) does the
**how**, the same way for every store. When a store changes its page, the fix
is almost always a selector or a pattern in that store's file, nothing else.

| File | Store | Reads | Loads by | Checks itself against |
| --- | --- | --- | --- | --- |
| `shoprite.js` | ShopRite digital coupons | the coupon widget, signed out | scrolling its container | the page's "All Coupons (N)" and "Limit 4 Offers (N)" |
| `stews.js` | Stew Leonard's weekly specials | the online shop's specials collection (the flyer is images) | pressing "Load More" | at least 30 items, at most 5% unreadable |
| `costco.js` | Costco warehouse savings | the public savings page | one sweep down the page | at least 50 offers, at most 8% unreadable |
| `generic.js` | anything else | whatever looks like an offer with a price | a sweep | at least 1 |

## When a scan breaks

1. **Read the report.** Every run (scan or check) sends its diagnostics to the
   control panel, which keeps the latest per store in its data folder:
   `scanner/<store>.json`, plus one line per run in `scanner/history.jsonl`.
   (From a clone that is the project folder; for the desktop app it is
   `~/Library/Application Support/Wellness Smart Shopping/`.)
2. **Find the step.** `failedAt` names it, and `steps` has the numbers:

   | `failedAt` | What changed | Where to fix |
   | --- | --- | --- |
   | `discover` | the landing page no longer links to the list | `discover.link` |
   | `ready` | no card matched `items` - the card markup changed | `items` |
   | `guard` | a sign-in wall, or the page is not the list any more | the page, or `guard` |
   | `load` | the scroll container or the "more" button moved | `load` |
   | `check` | the list loaded short, or too many cards could not be read | see below |

3. **For `check` failures, look at `steps.read.fields`.** It counts, for each
   field `read()` returns, how many cards had it filled. A field that went from
   all-filled to all-empty is the selector that moved. `steps.line.skippedSamples`
   shows the text of cards that produced no line.
4. **`hiddenDuringScan: true`** means the tab was in the background. Pages that
   load as you scroll often stop loading then. That is not a site change; run it
   again with the tab in front.
5. **Fix, bump, re-verify.** Update the selector or pattern, update the "Page
   facts" comment at the top of the file, bump `version`, set `verified` to
   today, update the fixtures in `../test/`, and run a check from the popup
   (**Site checks -> Check this site**).

## A site file

```js
WSS.defineSite({
  key: "stews",                 // matches the store key (or "adapter") in the panel's config
  name: "Stew Leonard's",
  version: 1,                   // bump on every change
  verified: "2026-09-21",       // the day it was last seen working
  startUrl: "https://...",      // where a scan opens
  readableOn: "regex",          // pages this file can read; on any other page of
                                //   the store, the scan opens startUrl instead
  hosts: ["stewleonards.com"],  // which store a page belongs to (toolbar popup)
  signIn: false,                // whether the page needs you signed in

  discover: {                   // optional: a landing page that links to the list
    on: "/storefront",          //   regex on the URL
    link: 'a[href*="..."]',     //   the link to follow
    timeout: 20000,             //   how long to wait for it (ms)
  },

  items: "css selector",        // one element per offer card
  prepare: (doc) => {},         // optional: mark cards no selector can reach
  guard: (doc, H) => null,      // optional: return a message to stop the scan
  load: { type: "...", ... },   // see below

  read: (card, H) => ({...}),   // card -> plain fields (strings)
  line: (row, H) => "a | b | c",// fields -> one line, or null to skip the card

  expect: {
    total: (doc, H) => 140,     // optional: the page's own count; must match exactly
    min: 30,                    // fewer cards than this fails the scan
    maxSkipped: 0.05,           // share of cards allowed to produce no line
    checks: [(ctx) => null],    // optional: return a problem string to fail
  },
  info: (doc, H) => ({}),       // optional: extra facts for the report
});
```

### Loading

| `load.type` | For | Options |
| --- | --- | --- |
| `none` | everything is on the page at once | |
| `scroll-container` | an infinite list inside a scrolling box | `container`, `wait`, `stableRounds` |
| `scroll-window` | an infinite list on the page itself | `wait`, `stableRounds` |
| `more-button` | a list with its own "Load More" button | `text` (an anchored regex, e.g. `"^load more$"`), `wait`, `stableRounds` |
| `sweep` | all there, but renders as it scrolls into view | `step`, `wait`, `settle` |

Loading stops when the card count has not grown for `stableRounds` rounds, or
when it reaches `expect.total`.

### Read-only, by construction

The Scanner never loads, clips or buys anything. Site files never click; the
engine's only press is the `more-button` loader, which presses a button only
when its text matches the site's anchored pattern, and refuses anything
that looks like a cart, coupon, account or store-choice control whatever the
site says (`NEVER_PRESS` in `engine.js`). A test fails if a site file calls
`.click(`.

### The line format

`name | price or discount | limit`, the format the panel's parser reads
(`dealcrawler/sources/harvest.py`). Price words it understands: `$1.00 off`,
`Save $1.00`, `$15.99 after $6.00 off`, `$2.49/lb`, `$3.99 each`, a bare
`$3.99` (a sale price), `2 for $5`. The limit is `Limit N` or `no limit` (the
page stated none). The helpers in `../engine/helpers.js` (`H.money`,
`H.limit`, `H.join`, `H.tidy`, ...) cover most of it.

## Adding a store

1. Write `sites/<key>.js`. Copy the store file closest in shape.
2. Add it to `sites/index.js`.
3. Add its domain to `host_permissions` in `../manifest.json`.
4. In the panel's config, give the store `"adapter": "<key>"` (or use the same key).
5. Add a test with rows from the live page to `../test/sites.test.js`.
6. Reload the extension in `chrome://extensions`, then **Check this site**.

<h1>Wellness Smart Shopping</h1>

[![Version](https://img.shields.io/badge/version-1.1.0-3f7d4f)](https://github.com/michael-m-robinson/wellness-smart-shopping/releases)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-555)](#what-you-need)
[![Desktop app](https://img.shields.io/badge/desktop%20app-macOS%2013%2B-000)](#the-companion-desktop-app)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab)](#what-you-need)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Mobile](https://img.shields.io/badge/mobile-coming%20soon-orange)](#whats-next)

**Build the shopping list your nutrition targets call for — then let this
week's grocery sales pay for it.**

The [companion desktop app](#the-companion-desktop-app) plans your meals and
your list from your calorie and macro targets at ordinary shelf prices. Only
once that list exists does Wellness Smart Shopping go looking: it reads the
weekly deals, digital coupons and instant savings from the store pages **you**
are signed in to, matches them against what the list already asks for, and
writes a small XML file. Import it and the app prices your trip against those
offers and proposes cheaper on-sale substitutes for the optional items.

> **Free and open source.** Bring your own stores and your own accounts.
> Nothing here is tied to one household, one store or one region.

> 📱 **A mobile version is coming soon.**

---

## Where this came from

This started as a personal app. One household, one set of stores, one weekly
meal plan, built to answer a question that kept coming up: *what should we
actually buy this week so we eat well without overspending?*

It worked. And the more it worked, the more it seemed selfish to keep it on one
laptop. Plenty of people find the weekly shop genuinely hard -- not because they
do not know what good food looks like, but because planning it, pricing it and
timing it around what happens to be on sale is a real chore every single week.
That is the part a computer should be doing.

So it has been generalised and given away. Nothing is tied to one family, one
region or one set of stores any more: you bring your own stores, your own
accounts, your own wording and your own look. If it helps you get the right
food into the house each week with less effort, that is the whole point.

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
- **It looks for deals last, on purpose.** Your recipes and your list are
  settled before a single offer is read, so what goes in the basket is decided
  by what you need. A deal then lowers what you pay for those items, or offers
  a swap inside the same role — turkey for beef, quinoa for rice — that you
  approve item by item. Plan the week around the circular instead and you end
  up eating the circular. Build the list with the deals turned off and turned
  on and you get the same list; only the price changes.
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

**Two routes. Terminal is the one to start with.**

| Route | What you run | |
| --- | --- | --- |
| **Terminal** — recommended | `python3 panel.py` | Everything lives in one folder you can see: your config, your scans, the sales file. Nothing to find, nothing to permit. |
| **Desktop app** | Drag it in, press **Scan Deals** | Adds meal plans, recipes and PDFs. Keeps its files in `~/Library/Application Support/`, away from the folder you are working in. |

Both open the same control panel and produce the same file, and the scan
instruction is identical either way.

**Why Terminal first.** The app is a normal macOS app, so it keeps its data in
Application Support rather than beside the project. That is correct for an
installed app, but it puts your scans and sales files somewhere other tools —
including Claude Code — may not be allowed to reach, and a blocked read there
looks like the scan failing rather than a permission being missing. From
Terminal, everything sits in the folder you cloned, which sidesteps that
entirely. Use the app when you want the meal planning and the PDFs.

Then, either way:Then, either way:

| Requirement | Why |
| --- | --- |
| **[The Scanner extension](#scan-with-the-scanner-extension)** | The easy way to scan. It ships in `extension/`; load it into Chrome once. No subscription. |
| **[Claude for Chrome](https://chromewebstore.google.com/detail/fcoeoabgfenejglbffodgkkbkcdhcgfn)** + a Claude subscription | Optional. The fallback for a store the Scanner cannot read yet. |
| **Python 3.9+** | The control panel and crawler. macOS ships it; standard library only, nothing to install. |
| **Chrome, signed in to your stores** | Digital coupons only exist inside your own logged-in session. Edge, Brave and Arc count too. |
| No network access of its own | This program never contacts a store. A test enforces it. |

> **Please sign in to your stores before crawling.** Most grocers serve deals
> only to a signed-in session. If you are signed out, the crawler will stop and
> print exactly which store needs you and which page to open — it will not
> quietly return an empty file.

**Why scanning happens in your browser:** a store's real coupon list exists only
inside your signed-in session, and the pages that show it are JavaScript apps
that block plain scripts outright. There is no public feed to read. Rather than
scrape third-party coupon blogs -- which are noisy, often wrong, and not the
store's own numbers -- this project reads the genuine article: the page you
already have open, in your own browser, with your own account. That is what the
Scanner extension does (and Claude for Chrome, for stores the Scanner does not
know yet).

A useful side effect: **this program has no network access at all.** It cannot
contact a store, so it cannot be blocked, rate-limited, or quietly scrape
anything on your behalf. It only ever reads a file you saved.

---

## Your daily targets

The first time you open the control panel it asks for a few details and works
out the calorie and macro targets your shopping list is sized around:

<p align="center"><img src="docs/img/daily-targets.jpg" alt="The Set your daily targets form: height, weight, goal, diet, people, days, budget and meals, with a live daily target showing kcal, protein, carbs and fat" width="760"></p>

Height, weight, age, sex, activity and goal set the numbers -- the rest size the
shop itself. The target updates live as you type, so you can see what switching
from Maintenance to Cutting, or from Sedentary to Active, actually costs before
committing.

**Any of the four numbers can be typed over.** Click a figure on the targets
card, type your own, and it sticks — a link puts the calculated one back. Leave
a box alone and it keeps calculating, so you can pin protein and let the rest
follow.

Press **Save targets** and it is written to `profile.json` on your machine and
reused from then on. Change it any time with **Edit** on the targets card; there
is no lock-in and nothing is uploaded.

### How the numbers are worked out

Calories come from the **Mifflin-St Jeor equation** -- the resting-energy formula
dietitians use -- multiplied by an activity factor:

| Activity | Factor | Extra protein |
| --- | --- | --- |
| Sedentary - little or no exercise | 1.20 | - |
| Light - 1-3 days a week | 1.375 | +0.05 g/lb |
| Moderate - 3-5 days a week | 1.55 | +0.08 g/lb |
| Active - 6-7 days a week | 1.725 | +0.12 g/lb |
| Very active - physical job or twice daily | 1.90 | +0.15 g/lb |

Training harder raises protein need, not just calories. Without that, the extra
energy would land almost entirely in carbohydrate, which is a poor split for
anyone actually training. Fat is likewise held to at least a quarter of
calories, so a high-activity target does not collapse into a near pure-carb plan.

Your goal then scales the result:

| Goal | Calories | Protein | Fat |
| --- | --- | --- | --- |
| Build Muscle | maintenance x 1.10 | 0.80 g/lb | 0.35 g/lb |
| Maintenance | maintenance x 1.00 | 0.70 g/lb | 0.32 g/lb |
| Cutting | maintenance x 0.84 | 0.75 g/lb | 0.30 g/lb |

Protein and fat come off a *planning weight* capped near BMI 25 plus 20%, so
targets stay sensible across body sizes rather than scaling without limit.
Carbohydrate fills the remaining calories.

**Sex** offers "Prefer not to say", which sits midway between the male and
female constants -- you get a usable number without disclosing it.

If you leave age blank, it falls back to the desktop app's original size-only
estimate, so an unfinished profile still produces workable numbers. There are
tests pinning both paths.

> **This is planning guidance, not clinical advice.** It cannot account for
> medication, health history, body composition or pregnancy. If you have medical
> or dietary needs, use the numbers your clinician gives you.

---

## The control panel

The easiest way to use this. One command:

```bash
python3 panel.py
```

or double-click **Start Panel.command** -- or just press **Scan
Deals...** in the desktop app, which starts it for you. It opens a small page at `http://127.0.0.1:8765` -- entirely on your machine,
nothing uploaded anywhere -- with:

- **Scan deals** -- pick a store, the Scanner extension (or Claude) reads its
  deals from your own browser, and the panel offers to import the result.
- **Your daily target** -- calories and macros sized to you, editable any time.
- **Refresh Deals** -- checks every enabled store and writes the XML.
- **How to Import** -- step-by-step import instructions in a popup.
- **A sign-in panel** -- any store that needs an account is listed with a link
  to open it and instructions for the browser harvest.
- **A look picker** -- 26 bundled images, or drop your own into `themes/`.
- **Wording** -- edit the app name, greeting, tagline, headings and the
  shopping list message; all save straight to `branding.json`.

<p align="center"><img src="docs/img/control-panel.jpg" alt="The control panel: banner with a custom greeting, Refresh Deals and How to Import buttons, matched deals, and a theme picker" width="820"></p>

<p align="center"><em>Refresh, see what matched, import. That's the loop.</em></p>

The panel runs only while its page is open. Close the tab or navigate away and
it stops a few seconds later -- the page holds one open connection to the panel
and nothing is sent on a timer, so there is no heartbeat to keep it alive. A
reload reconnects well inside that grace. A scan in progress holds it open.

### Scan with the Scanner extension

The Scanner is a small Chrome extension in `extension/`. It does the scan
itself -- no instruction to copy, no subscription. Load it once:

1. Open `chrome://extensions` (Edge: `edge://extensions`) and switch on
   **Developer mode**.
2. Press **Load unpacked** and choose the `extension/` folder of this project.

Installed the app from the disk image instead? The Scanner ships inside it:
in the app, **Scan Deals... -> Set Up Scanner...** puts it in
`~/Library/Application Support/Wellness Smart Shopping/Scanner Extension`,
shows that folder in Finder and walks you through the same two steps. The app
refreshes that folder whenever it is updated; press the reload arrow on the
Scanner in the extensions page to pick up the new version.

(`python3 installer.py` checks for it and shows these steps if it is missing.)
Then, in the panel, **Scan deals** -> pick a store. The Scanner opens the store
in a tab, reads every offer, hands them to the panel and closes the tab again;
the panel matches them and offers to import, exactly as below.

- **It only reads.** It never loads, clips or buys anything. The one button
  it ever presses is a list's own "Load More" (Stew's), and it refuses anything
  that looks like a cart, coupon, account or store-choice control. Tests
  enforce both.
- **It checks itself.** ShopRite's scanner compares what it read against the
  page's own "All Coupons (N)" and "Limit 4 Offers (N)" counts. If they differ
  it stops and says so rather than saving part of the list.
- **Its reach is small:** the stores it knows, and `127.0.0.1` to reach the
  panel. The toolbar button scans any other page you point it at.
- **It works without the panel.** Press the toolbar button on a store page:
  if the panel is not running, the offers are shown there to copy.

Each store has a **site file** in `extension/sites/`: ShopRite, Stew Leonard's
and Costco have their own; any other store uses `generic.js`, which reads
anything shaped like an offer with a price. Set `"adapter"` on a store in
`config.json` to choose one. When a store changes its page, its site file is
the one file to fix, and every scan leaves a report saying which step and
selector broke: see [`extension/sites/README.md`](extension/sites/README.md).
Tests: `node --test extension/test/*.test.js`.

| Store | What the Scanner reads | Before you shop |
| --- | --- | --- |
| ShopRite | the digital coupon list, signed out | **Log in and load each coupon to your account** (shoprite.com -> Digital Coupons -> Load to Card). You must be logged in, because it's the only way to load coupons to your account; a coupon you skip rings up at the regular price. |
| Stew Leonard's | this week's specials in Stew's online shop (the flyer itself is only images). Checked against the printed flyer: every discounted item is there except a handful of non-staples; the flyer's other entries are featured everyday prices or points rewards. | nothing to clip - they are the week's prices, and the result links to that specials page. For items marked **APP DEAL**, scan your Member ID in the free Stew Leonard's app (or give your phone number) at checkout, as the flyer says. |
| Costco | the public warehouse savings page | nothing to clip - Costco calls these *instant savings*. You need an **active membership** in the warehouse; limits are per household, and a few deals are online only. |

Those notes appear wherever you act on the deals: on the scan result in the
panel (and the toolbar popup), in the app's import preview, and in a boxed
notice at the top of the shopping list PDF, with **LOAD COUPON FIRST** beside
each ShopRite item. After a ShopRite scan the panel also lists each matched
coupon with **Copy name** (for ShopRite's coupon search) and a link to load it.

**Logged in to ShopRite?** The Scanner checks, and if you are not, the panel
shows a friendly bar at the very top with a **Log in to ShopRite** button
(**Maybe later** hides it for the session). Once you're logged in, the scan
result changes its wording from "log in first" to "now load your coupons".
The check uses Chrome's `cookies` permission to see whether ShopRite's sign-in
cookie *exists*; it never reads the cookie's value, and a test enforces that.

A store's notes are its `"redeem"` setting in `config.json`, so your own stores
can have them too.

### Scan with Claude

**Scan with Claude** is the fallback for a store the Scanner cannot read yet,
and runs the whole loop for you. Press it, pick a store, and
the panel hands you the exact instruction to give Claude:

<p align="center"><img src="docs/img/scan-with-claude.jpg" alt="The Scan with Claude wizard: links to the store's coupon list, three drawn steps, the instruction to give Claude with a Copy button, and a spinner waiting for the scan" width="720"></p>

1. **Pick a store.** Each one shows whether it has been scanned yet.
2. **Open it and sign in.** The panel links straight to that store's coupon list.
3. **Give Claude the instruction** (there is a Copy button) in the Chrome side
   panel, with the Claude for Chrome extension enabled. The window draws the
   three steps, so the side panel does not have to be familiar.
4. **The scan comes straight back.** No file to save: it is matched against
   your staples and turned into XML with no further clicking.
5. **It asks whether to import.** Say yes and it opens the app and reveals the
   file in Finder, with the path on your clipboard. Say **Not now** and it tells
   you exactly where the file is waiting, so you can import whenever you like:

```
/path/to/wellness-smart-shopping/out/shoprite-sales-2026-09-20.xml
```

Nothing is lost by declining -- the file keeps until you use **Import Sales
XML...** in the app. If the scan came through but nothing matched your staples,
it says so plainly rather than writing an empty file; that is just a quiet week
at that store.

#### How the scan gets back without touching your files

A browser extension **cannot write to your disk**, so this does not ask it to.
`browser/harvest.js` runs inside the store's own page, and a page is allowed to
post to a local address — so it posts the offers to the panel on `127.0.0.1`,
which writes them where writing is allowed.

Chrome preflights that request, because it comes from a public page to a local
one, so the panel answers with the headers Chrome asks for, including
`Access-Control-Allow-Private-Network`. Without that the request never arrives.

If the panel is not running, nothing is lost: the script prints the offers
instead, and the Scan window has a box to paste them into.

#### If you do not have the extension yet

The panel says so on arrival, with a link to install it:

> **Scanning needs the Claude for Chrome extension** -- Scan with Claude reads
> deals from the store page you are signed in to, which the Claude for Chrome
> extension makes possible. Everything else here works without it.
> &nbsp; [Get the extension] &nbsp; [I already have it]

Press **I already have it** and the notice never comes back. Open the panel in a
browser that cannot run the extension and it says that instead.

A web page cannot truly detect an installed extension -- the resources this one
exposes are content-hashed and change with every release, so probing for them
would start reporting "missing" after any update. The notice therefore informs
rather than claims, and is dismissible. Only the browser itself is detected with
certainty.

**How to Scan** (inside the wizard) has the same directions in longhand if you
would rather read them first.

### The desktop app

The app's Swift source is in `app/`, so it builds from source:

```bash
cd app
./build.sh                      # -> build/Wellness Smart Shopping.app
./build.sh "My Shopping App"    # or under your own name
```

Needs the Swift toolchain from the Xcode command line tools
(`xcode-select --install`). macOS only. The build names the bundle, sets its
identifier, copies in the theme you picked in the control panel, and ad-hoc
signs it so macOS will open it.

**The coupon finder is gone.** Not relabelled -- deleted. The old build shipped
its own scraper: it fetched store pages, parsed them, and kept sign-in sessions
in an embedded browser. That is ~380 lines lighter now, and with it went the
hard-coded town and store branch the original was built around.

In its place the app has one button, **Scan Deals...**, opening a small
panel that does three things and nothing else:

- **Start Control Panel** finds `panel.py`, starts it, shows progress while it
  comes up, opens your browser on it, and **stops it again when you quit the
  app**. If it cannot find the folder it asks you to point at it once, then
  remembers. Nothing to run by hand.
- **Import Sales XML...** applies the file a scan produced.
- **Clear Imported Deals**, and Close.

**Deals come before PDFs.** **Create 3 Paired PDFs...** waits for this week's
scan: until a sales file has been imported (in the last 7 days), it makes
nothing, pulses **Scan Deals...** and shows a tip saying to scan first. A scan
that matched nothing on your list still counts -- the PDFs are then made at
regular prices. **Clear Imported Deals** clears the scan too.

The per-item list of entry boxes is gone -- deals arrive from a scan, so there
was nothing left to type into it.

> **The app carries its own copy of the control panel**, so an app installed
> from the disk image works wherever you put it. It falls back to a folder you
> picked before, then the usual clone locations, and asks once if it cannot find
> any. **Python 3 is the one thing it needs** -- macOS ships it -- and without it
> the button cannot start anything, though the rest of the app still works and
> you can import a sales file by hand.

What survived untouched: the meal planner, recipes, PDF export, nutrition
targets, and the XML import. The app's own self-test still passes:

```bash
"build/Wellness Smart Shopping.app/Contents/MacOS/SmartShoppingList" \
    --self-test /tmp/a.pdf /tmp/b.pdf /tmp/c.pdf
```

Tests in `test_crawler.py` guard the removal, so the scraper cannot creep back.

### Make it sound like you

Every greeting and heading is data, not code. Copy the example and edit:

```bash
cp branding.example.json branding.json
```

```json
{
  "app_name": "Wellness Smart Shopping",
  "greeting_morning": "Good morning - let's shop well",
  "greeting_evening": "Good evening - let's plan the week",
  "tagline": "Eat well on what's actually on sale this week",
  "deals_header": "This week's deals, matched to your list",
  "theme": "farm-market"
}
```

Anything you leave out falls back to a sensible default, so a two-line
`branding.json` is perfectly valid. You can also edit the common fields straight
from the control panel and hit Save.

### Choosing a look

Twenty-six images ship with the project, in two kinds:

- **Six drawn by code** (`tools/make_themes.py`) -- abstract produce artwork that
  carries no third-party licence at all.
- **Twenty photographs** -- retro 1950s grocery scenes, training and strength,
  open air and green space, and a family at the table. These are AI-generated,
  commissioned for this project and contributed under the same MIT terms, so
  they carry no third-party claim and depict no real person.

Provenance and licensing for both kinds is recorded in
[themes/CREDITS.md](themes/CREDITS.md).

Pick one in the control panel and it becomes the banner; `personalize.py` can
push the same image into the desktop app. Drop any `.png` or `.jpg` into
`themes/` and it appears in the picker too. The grid loads small thumbnails
from `themes/thumbs/` so a large library stays quick.

If you add an image you did not make, check its licence before redistributing
it -- Unsplash, Pexels, Openverse and Wikimedia Commons are good sources, but
their terms vary image by image.

### Your shopping list message

The line above your shopping list is yours. Pick one of the presets in
**Wording**, or type your own:

> Good food, brighter days. &nbsp;&middot;&nbsp; Stronger, healthier, happier
> you. &nbsp;&middot;&nbsp; Progress looks good on you. &nbsp;&middot;&nbsp;
> Eat well. Spend less. Feel better.

It saves to `branding.json` with everything else.

### Personalising a build you already have

Building from `app/` already bakes in your name and theme. To change an existing
bundle without rebuilding:

```bash
python3 personalize.py --list
python3 personalize.py --name "My Shopping App" --theme farm-market --icon
```

It renames the bundle, swaps the picture the app shows, optionally rebuilds the
icon, backs up first, and re-signs so macOS still opens it. macOS only.

---

## Install

**The easy way — a disk image, drag to Applications.**

```bash
cd app && ./make_dmg.sh        # -> app/dist/Wellness Smart Shopping.dmg
```

Double-click the image and the familiar window opens: the app on one side, the
Applications folder on the other. Drag it across and you are done.

**Everything it needs is already inside it.** The control panel, the crawler,
the themes and the browser script all ship in the app's Resources, so there is
no folder to keep beside it, nothing to `pip install`, and no second step. The
binary links Apple's frameworks and nothing else; the Python side is standard
library only. The single outside requirement is `python3`, which macOS provides
— on a Mac that has never installed the command line tools the app says exactly
what to run.

Your settings, scans and sales files live in
`~/Library/Application Support/Wellness Smart Shopping/`, never inside the app,
which is read-only and signed. To uninstall: drag the app to the Trash and
delete that folder.

**Or from a clone**, if you want the crawler and the panel on the command line:

```bash
git clone https://github.com/michael-m-robinson/wellness-smart-shopping.git
cd wellness-smart-shopping
./install.command          # or: python3 installer.py
python3 installer.py --uninstall   # removes the app, settings and caches
```

The setup wizard checks what your machine already has, offers to fix what is
missing, builds the desktop app, runs the tests and leaves you with a working
control panel. **Nothing is installed without asking, and nothing needs `sudo`.**
To look before you leap:

```bash
python3 installer.py --check     # report only, changes nothing
```

**One copy, always.** The app is installed to `~/Applications` and the wizard
removes any other copy of it -- two installed copies is a trap where you open
one, find the old build, and none of your changes are there. Copies are matched
by bundle identifier rather than name, so renaming a build with `build.sh` does
not sneak one past it, and that includes the staging copy `build.sh` leaves in
`app/build/`: macOS indexes it like any other app, so it appears in Launchpad
whether or not you think of it as installed. Removals are deregistered from
LaunchServices too, or the ghost lingers in Launchpad and Spotlight after the
files are gone. Older builds of the *original* app are listed but never removed
unless you say so -- they are yours.

If you have built the app by hand and want to tidy up without reinstalling:

```bash
python3 installer.py --check     # shows every copy it can find
```

> **There are no Python packages to install.** The crawler, the control panel
> and the wizard are standard library only, and the desktop app uses Apple's own
> frameworks with no Swift package dependencies. `requirements/requirements.txt`
> is deliberately empty -- nothing is downloaded at install time, nothing pins a
> version, and nothing can break when an upstream package changes. The real
> requirements are a handful of tools, listed in
> [requirements/README.md](requirements/README.md) and checked by the wizard.

Prefer to do it by hand? Copy the config and go:

```bash
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

# How to scan each store, printed to the terminal
python3 crawl.py --scan-help

# Use a scan saved somewhere else
python3 crawl.py --harvest stews=~/Downloads/stews.txt
```

A store you have not scanned yet prints its own directions instead of failing
silently.

Files land in `out/`, one per store plus an optional combined file:

```
out/shoprite-sales-2026-09-20.xml
out/costco-sales-2026-09-20.xml
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
| `--harvest store=file` | Use a scan saved somewhere other than `harvest/`. |
| `--scan-help` | Print scanning directions for every store. |
| `--per-weight convert\|skip` | Convert `$/lb` deals to per-package (default) or drop them. |
| `--no-snack-twins` | Do not mirror a deal onto the snack line items. |
| `--combined` | Also write one all-stores file. |
| `--out DIR` | Change the output directory. |

---

## Adding your own store

No code required. Because nothing is fetched, a store is just a name and the
pages worth scanning -- add it to `config.json`:

```json
"stores": {
  "mymarket": {
    "enabled": true,
    "name": "My Local Market",
    "urls": [
      { "label": "Open the weekly ad", "url": "https://example.com/weekly-ad" },
      { "label": "Open digital coupons", "url": "https://example.com/coupons" }
    ]
  }
}
```

It appears in the control panel immediately, with its own scan directions and
its own `harvest/mymarket.txt`. The matcher, price maths and XML writer are
shared, so any store benefits from them.

### The scan prompt

Each store hands Claude its own instruction. ShopRite's is specific because its
coupons sit in a cross-origin frame that a plain "read this page" can't see;
every other store gets a general one that loads all offers, checks the count
and posts them back. If your store needs something particular, give it a
`"prompt"` in `config.json` -- write `{submit}` where the panel's address goes:

```json
"mymarket": {
  "name": "My Local Market",
  "prompt": "Open the Coupons tab, click Load More until it stops, then list each offer as: product name | price | limit, and POST the list as plain text to {submit}"
}
```

To use one wording for every store instead, set `scan_prompt` in
`branding.json`. It's empty by default, which means "use each store's own".

## The sales XML format

**[docs/XML-IMPORT.md](docs/XML-IMPORT.md)** documents the file the app imports,
including the full list of catalog item IDs it accepts. The format is plain text
and deliberately simple, so you can generate it from a spreadsheet, a script, or
by hand -- this crawler is just one producer of it.

---

## What's next

- 📱 **A mobile version is coming soon** -- the control panel is already a web
  app, which is the groundwork for it.
- More stores. Adding one needs no code at all -- a name and the pages worth
  scanning, in `config.json`. Contributions welcome.
- The desktop app builds from source in `app/`, so it is open to changes too.

---

## Privacy

- The crawler and the control panel run entirely on your machine, and make no
  network requests of any kind.
- The panel binds to `127.0.0.1` only -- it is not reachable from
  your network.
- Your height, weight and goal stay in `profile.json` on your machine.
- **It never sees, asks for, or stores your store passwords.** Sign-in happens
  in your own browser; only the visible text of a page you already opened is
  ever read.
- `config.json`, `branding.json`, `profile.json`, `harvest/` and `out/`
  are git-ignored so your store numbers and
  local data stay off GitHub.

---

## License

[MIT](LICENSE) — free to use, change and redistribute, including commercially.
No warranty: advertised prices change, stores make mistakes, and the matcher is
heuristic. Always check your receipt.

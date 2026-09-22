<h1>Wellness Smart Shopping</h1>

[![Version](https://img.shields.io/badge/version-1.1.0-3f7d4f)](https://github.com/michael-m-robinson/wellness-smart-shopping/releases)
[![Desktop app](https://img.shields.io/badge/desktop%20app-macOS%2013%2B-000)](#the-desktop-app)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab)](#what-you-need)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Build the shopping list your nutrition targets call for -- priced around this
week's grocery deals.**

Scan the deals at the stores you shop, and the desktop app builds your meal
plan and shopping list around them: in each food category it picks the option
that is on sale this week, while your calorie and macro targets still come
first. A small browser extension reads the deals, a local control panel turns
them into a deal file, and the app turns that into three printable PDFs -- a
shopping list, recipes, and a daily meal plan.

---

## A personal project

This is a personal project. It was built for one household, one weekly shop and
one set of stores -- **ShopRite, Stew Leonard's and Costco**, with BJ's to come
-- to answer a question that kept coming up: *what should we actually buy this
week so we eat well without overspending?*

**Grocery stores from around the US will not be added.** The Scanner reads
exactly the stores above, each with a reader written for its own pages, and
that is where it will stay. The code is open and MIT-licensed, so if your
stores are different you are welcome to fork it and write readers for them --
`extension/sites/README.md` explains how -- but that work will not happen here.

It is shared in the hope that it helps someone. Planning a week of healthy food,
pricing it and timing it around what happens to be on sale is a real chore, and
if some of this saves you part of that chore, it has done its job.

---

## How it works

1. **Scan this week's deals.** In the control panel, **Scan deals -> Scan all my
   stores** runs the Scanner extension on each store in turn. It reads every
   offer from the store's own page and matches it against the food the app
   plans with. Each store's matches are saved as a deal file in
   **Documents > Deals**.
2. **Import them into the app.** **Scan Deals... -> Import Sales XML...** takes
   all of this week's files at once and confirms what it applied.
3. **Create the PDFs.** The app picks the on-sale option in each category,
   prefers recipes that use those picks, and prices the list against the deals.
   It won't make PDFs until every store you have checked has this week's scan.

- **It looks for deals on the food you actually want to eat.** The matcher only
  recognises staples -- lean ground turkey, chicken breast, eggs, plain Greek
  yogurt, lentils, fish, oats, brown rice, produce, olive oil, spices. A sale on
  candy, soda, clothing or shampoo is ignored, so a "good week" never means a
  week of junk.
- **Your target comes first.** In each category the app tracks (proteins, grains
  and starches, produce, beans, dairy, eggs, bread, breakfast) it picks the
  option on sale -- turkey instead of beef, rice instead of quinoa -- and
  recipes that use those picks are preferred. But recipes are ranked on your
  nutrition goal first; a deal only decides between recipes the goal rates the
  same, so you never trade macros for a coupon. Recipe ingredients and your
  favorites are never swapped.
- **Each item is listed where its deal is.** If Stew's has the salmon on sale,
  the salmon is on your Stew's list.
- **It respects purchase limits.** "Limit 4" is carried into the file, so the
  savings you are shown are savings you can really get at the register.
- **It is honest about what a deal is worth.** A `$3.99/lb` advertisement is
  converted into a real per-package price, "2 for $5" becomes a unit price, and
  a discount larger than the item's normal price is capped instead of being
  taken at face value.

---

## What you need

| Requirement | Why |
| --- | --- |
| **A Mac** (macOS 13+) | For the desktop app, which makes the plan and the PDFs. The control panel also runs anywhere Python does. |
| **Python 3.9+** | The control panel. macOS ships it; standard library only, nothing to install. |
| **Chrome or Edge** | To run the [Scanner extension](#the-scanner-extension). Brave and Arc work too. |
| **A ShopRite account** | Only to *use* ShopRite's digital coupons: they must be loaded to your account before you shop. The Scanner itself needs no sign-in anywhere. |

Everything runs on your own machine. The panel and the app never fetch a store
page; the Scanner reads the stores' pages in your own browser.

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

The hub for scanning. Start it from the desktop app (**Scan Deals... -> Start
Control Panel**), or from a clone with:

```bash
python3 panel.py
```

It opens a small page at `http://127.0.0.1:8765` -- entirely on your machine,
nothing uploaded anywhere -- with:

- **Scan deals** -- scan one store, or **Scan all my stores** in one go.
- **"You could be saving money this week"** -- a friendly note at the top until
  a scan this week has found a deal for your list. Its button starts a scan.
- **Your daily target** -- calories and macros sized to you, editable any time.
- **How to Import** -- the steps, and the folder your deal files are in.
- **A look picker** and **Wording** -- the banner image and every greeting and
  heading, saved to `branding.json`.

<p align="center"><img src="docs/img/control-panel.jpg" alt="The control panel: banner with a custom greeting, the scan and import buttons, matched deals, and a theme picker" width="820"></p>

After each scan the panel shows what it found for your list, what the store
needs from you before you shop (below), and where the deal file was saved. A
store with nothing for your list this week still gets its file, so the app
knows it was scanned.

The panel runs only while its page is open. Close the tab or navigate away and
it stops a few seconds later -- the page holds one open connection to the panel
and nothing is sent on a timer. A reload reconnects well inside that grace, and
a scan in progress holds it open.

### Before you shop

| Store | What the Scanner reads | What you need to do |
| --- | --- | --- |
| ShopRite | the digital coupon list | **Log in and load each coupon to your account** (shoprite.com -> Digital Coupons -> Load to Card). You must be logged in, because it's the only way to load coupons to your account; a coupon you skip rings up at the regular price. |
| Stew Leonard's | this week's specials in Stew's online shop (the printed flyer is only images; the online list carries all its sale items bar a handful of non-staples) | Nothing to clip -- they are the week's prices. For anything the flyer marks **APP DEAL**, scan your Member ID in the free Stew Leonard's app (or give your phone number) at checkout. |
| Costco | the public warehouse savings page, grocery department only | Nothing to clip -- Costco calls these *instant savings*. You need an **active membership** in the warehouse; limits are per household, and a few deals are online only. |

These notes appear wherever you act on the deals: on the scan result, in the
app's import confirmation, and in a boxed notice at the top of the shopping list
PDF, with **LOAD COUPON FIRST** beside each ShopRite item. After a ShopRite scan
the panel also lists each coupon to load, with **Copy name** for ShopRite's
coupon search and a link to load it; if the Scanner can see you are logged in
to ShopRite, it says so and gets straight to the coupons. (It checks only that
ShopRite's sign-in cookie *exists*, never its value.)

---

## The Scanner extension

A small Chrome/Edge extension that reads each store's deals and hands them to
the panel. Load it once:

1. Open `chrome://extensions` (Edge: `edge://extensions`) and switch on
   **Developer mode**.
2. Press **Load unpacked** and choose the extension folder: `extension/` in a
   clone, or -- if you installed the app from the disk image -- the folder the
   app makes for you with **Scan Deals... -> Set Up Scanner...**
   (`~/Library/Application Support/Wellness Smart Shopping/Scanner Extension`,
   shown in Finder). The app refreshes that folder when it is updated; press the
   reload arrow on the Scanner in the extensions page to pick up a new version.

Then scan from the panel. The Scanner opens each store in a tab, reads every
offer, files it with the panel and closes the tab again. Leave the tab in front
while it works -- stores stop loading lists in background tabs.

- **It only reads.** It never loads, clips or buys anything. The one button it
  ever presses is a list's own "Load More" (Stew's), and it refuses anything
  that looks like a cart, coupon, account or store-choice control. Tests
  enforce both.
- **It checks itself.** ShopRite's reader compares what it read against the
  page's own "All Coupons (N)" and "Limit 4 Offers (N)" counts; every reader has
  a minimum and a limit on unreadable cards. If a check fails it says so rather
  than saving part of the list.
- **It says what broke.** Every run leaves a report in the panel's data folder
  (`scanner/<store>.json`) naming the step and selector that failed, so when a
  store changes its page the fix is quick. The toolbar popup's **Site checks**
  run a store without filing anything.

Each store has one file in `extension/sites/`; the rest is a shared engine.
[`extension/sites/README.md`](extension/sites/README.md) explains the format
and how to fix a store when its page changes. Tests:
`node --test extension/test/*.test.js`.

---

## The desktop app

The app plans the meals, builds the list and makes three paired PDFs: a
low-ink **shopping list** with checkboxes, **recipes**, and a **daily meal
plan** sized to your targets.

- **Scan Deals...** opens a small panel: **Start Control Panel** (starts the
  panel and opens it in your browser, and stops it when you quit), **Import
  Sales XML...** (opens in Documents > Deals and takes several files at once),
  **Set Up Scanner...**, and **Clear Imported Deals**.
- **Every import ends with a confirmation** -- a green check and what was
  applied, a blue note when nothing matched your list, or an orange warning
  saying why nothing was applied.
- **Deals come before PDFs, from every store you shop.** **Create 3 Paired
  PDFs...** waits until each checked store has a scan from the last 7 days.
  Until then it pulses **Scan Deals...** and a tip names the stores still to
  scan.
- **BJ's is coming soon.** It is listed but greyed out, because the Scanner
  can't read BJ's deals yet. Until it can, BJ's items are bought at ShopRite
  (eggs, milk, chicken, sweet potatoes) and Costco (bulk and frozen).
- **Match Recipes to This List** looks up recipes on TheMealDB, searching for
  this week's on-sale items first. A free key is built in.

Build it from source with the Swift toolchain from the Xcode command line tools
(`xcode-select --install`):

```bash
cd app
./build.sh                      # -> build/Wellness Smart Shopping.app
./make_dmg.sh                   # -> dist/Wellness Smart Shopping.dmg
```

The app carries its own copy of the control panel, so an app installed from
the disk image works wherever you put it. **Python 3 is the one thing it
needs.** Its self-test builds all three PDFs and checks the planning rules:

```bash
"build/Wellness Smart Shopping.app/Contents/MacOS/SmartShoppingList" \
    --self-test /tmp/a.pdf /tmp/b.pdf /tmp/c.pdf
```

---

## Make it yours

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

**The easy way -- a disk image.** Open `Wellness Smart Shopping.dmg` and drag
the app to Applications. Then, in the app, **Scan Deals... -> Set Up
Scanner...** to add the extension to your browser.

Your settings and scans live in
`~/Library/Application Support/Wellness Smart Shopping/`, and your deal files in
`~/Documents/Deals`; nothing is written inside the app, which is read-only and
signed. To uninstall, drag the app to the Trash and delete those two folders
(and remove the Scanner from the extensions page).

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

## Use from the command line

```bash
# See what the saved scans match, without writing anything
python3 crawl.py --report

# Write the deal files
python3 crawl.py

# One store at a time
python3 crawl.py --stores costco
```

Deal files land in `~/Documents/Deals` (Finder: Documents > Deals), one per
store and scan, plus an optional combined file:

```
Documents/Deals/shoprite-sales-2026-09-21.xml
Documents/Deals/stews-sales-2026-09-21.xml
Documents/Deals/costco-sales-2026-09-21.xml
```

Set `WSS_DEALS_DIR` to use another folder. If macOS won't let the panel write to
Documents, it falls back to its own `out/` folder rather than failing.

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

## Scanning with Claude instead

Before the Scanner existed, scanning was done by giving Claude for Chrome an
instruction the panel wrote for each store, and that route still works: without
the Scanner installed, the panel shows the instruction with a Copy button, and a
box to paste Claude's list into. Chrome now stops a store's page from posting to
a local address, so Claude usually hands the list back to you to paste rather
than filing it itself. Each store's instruction is its `"prompt"` in
`config.json`.

---

## The sales XML format

**[docs/XML-IMPORT.md](docs/XML-IMPORT.md)** documents the file the app imports,
including the full list of catalog item IDs it accepts. The format is plain text
and deliberately simple, so you can generate it from a spreadsheet, a script, or
by hand -- this crawler is just one producer of it.

---

## What's next

- **BJ's**, once the Scanner can read its deals.
- 📱 **A mobile version is coming soon** -- the control panel is already a web
  app, which is the groundwork for it.

---

## Privacy

- The control panel and the crawler run entirely on your machine and make no
  network requests of their own. The panel binds to `127.0.0.1` only.
- The Scanner reads the stores' pages in your own browser and sends what it
  read only to the panel on your machine. It never sees or asks for a password,
  and checks only whether ShopRite's sign-in cookie exists -- never its value.
- The desktop app's only network use is TheMealDB, for recipes.
- Your height, weight and goal stay in `profile.json` on your machine.
- `config.json`, `branding.json`, `profile.json`, `harvest/` and `out/` are
  git-ignored, so your local data stays off GitHub.

---

## License

[MIT](LICENSE) -- free to use, change and redistribute. No warranty: advertised
prices change, stores make mistakes, and the matcher is heuristic. Always check
your receipt.

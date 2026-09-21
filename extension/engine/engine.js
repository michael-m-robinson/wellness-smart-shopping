/*
 * The scan engine. Runs inside the store page with helpers.js and one site
 * file, and drives every site through the same steps:
 *
 *   discover  on a landing page, find the link to the real list and go there
 *   prepare   mark cards that no selector can reach on its own (optional)
 *   ready     wait for the first offer card (site.items) to render
 *   guard     site-specific "is this the right page" check (optional)
 *   load      get every card onto the page (scroll a container, the window,
 *             or sweep once for lazy rendering)
 *   read      site.read(card) -> a row of plain fields
 *   keep      site.keep(row) -> false to leave a card out on purpose (Costco:
 *             not groceries). Counted as "filtered", never as unreadable
 *   line      site.line(row) -> "name | price | limit", or null to skip it
 *   check     site.expect: the page's own total, a minimum count, how many
 *             cards may be skipped
 *
 * Whatever happens, the result carries `diagnostics`: which step failed, how
 * many cards each selector found, how often each field came back empty, and
 * samples of skipped cards. The panel saves it, so when a site changes the
 * report says what moved.
 *
 * The engine reads, scrolls and follows links. The one thing it ever presses
 * is a list's own "Load More" button, and only through pressMore(): the site
 * must name the button's exact text, and anything that looks like a cart,
 * coupon, account or order control is refused whatever the site says.
 */
(function (root) {
  const WSS = root.WSS;
  const H = WSS.helpers;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  // Cards on the page now. A site's prepare() runs first, for pages whose
  // cards have to be marked before a selector can find them.
  // Pages that load as you scroll often stop loading in a background tab.
  let hiddenSeen = false;
  const tally = (site) => {
    if (document.visibilityState === "hidden") hiddenSeen = true;
    if (site.prepare) site.prepare(document, WSS.helpers);
    return document.querySelectorAll(site.items).length;
  };

  async function waitFor(test, timeoutMs) {
    const until = Date.now() + timeoutMs;
    while (Date.now() < until) {
      const v = test();
      if (v) return v;
      await sleep(400);
    }
    return test();
  }

  // Never pressed, whatever a site file says: these load coupons to a card,
  // fill a cart, or sign in.
  const NEVER_PRESS = /cart|clip|coupon|card|add|buy|order|checkout|sign|log\s*in|login|register|confirm|subscribe|save|redeem|apply|select|choose|store/i;

  // Press the list's own "more" button, if there is one. Returns true if pressed.
  function pressMore(text) {
    const want = new RegExp(text, "i");
    if (!/^\^.*\$$/.test(text)) throw stepError("load", `more-button text must be anchored: ${text}`);
    const button = Array.from(document.querySelectorAll("button, [role='button']"))
      .find((b) => want.test(H.clean(b.innerText || b.textContent)));
    if (!button) return false;
    const label = H.clean(button.innerText || button.textContent);
    if (NEVER_PRESS.test(label)) throw stepError("load", `refused to press "${label}"`);
    button.click();
    return true;
  }

  // ---------------------------------------------------------------- loading
  // Each returns {rounds, count}. `total` is the page's own count, if known.
  const LOADERS = {
    none: async () => ({ rounds: 0 }),

    // Infinite list inside a scrolling element (ShopRite).
    "scroll-container": async (site, opts, progress, total) => {
      const box = document.querySelector(opts.container);
      if (!box) throw stepError("load", `no scroll container "${opts.container}"`);
      return grow(site, opts, progress, total, () => {
        box.scrollTop = box.scrollHeight;
        box.dispatchEvent(new Event("scroll"));
      });
    },

    // Infinite list on the page itself (Stew's).
    "scroll-window": async (site, opts, progress, total) =>
      grow(site, opts, progress, total, () => {
        window.scrollTo(0, document.documentElement.scrollHeight);
        window.dispatchEvent(new Event("scroll"));
      }),

    // A paged list with its own "Load More" button (Stew's). Also scrolls,
    // for when the same list switches to infinite scroll instead.
    "more-button": async (site, opts, progress, total) =>
      grow(site, opts, progress, total, () => {
        if (!pressMore(opts.text)) {
          window.scrollTo(0, document.documentElement.scrollHeight);
          window.dispatchEvent(new Event("scroll"));
        }
      }),

    // Everything is in the page but renders lazily: pass over it once (Costco).
    sweep: async (site, opts, progress) => {
      const step = opts.step || Math.max(600, window.innerHeight);
      let y = 0, rounds = 0;
      while (y < document.documentElement.scrollHeight && rounds < (opts.maxRounds || 200)) {
        window.scrollTo(0, y);
        y += step;
        rounds++;
        await sleep(opts.wait || 150);
        if (rounds % 5 === 0) progress(`Read ${tally(site)} offers so far`);
      }
      await sleep(opts.settle || 1000);
      window.scrollTo(0, 0);
      return { rounds, count: tally(site) };
    },
  };

  // Scroll, wait, and repeat until the card count stops growing.
  async function grow(site, opts, progress, total, scroll) {
    const wait = opts.wait || 1500;
    const stable = opts.stableRounds || 3;
    let last = -1, still = 0, rounds = 0;
    while (still < stable && rounds < (opts.maxRounds || 80)) {
      scroll();
      await sleep(wait);
      rounds++;
      const n = tally(site);
      progress(`Loaded ${n}${total ? " of " + total : ""} offers`);
      still = n === last ? still + 1 : 0;
      last = n;
      if (total && n >= total) break;
    }
    return { rounds, count: last };
  }

  function stepError(step, message) {
    const e = new Error(message);
    e.step = step;
    return e;
  }

  // ---------------------------------------------------------------- the run
  WSS.run = async function (site, options = {}) {
    const progress = options.progress || (() => {});
    const d = {
      site: site.key, siteVersion: site.version, verified: site.verified,
      url: location.href.split("?")[0], at: new Date().toISOString(),
      steps: {},
    };
    const done = (extra) => ({ diagnostics: d, ...extra });
    hiddenSeen = false;
    const fail = (step, error, extra = {}) => {
      if (hiddenSeen && (step === "check" || step === "ready")) {
        error += " The store tab was in the background during the scan, which can " +
                 "stop a page loading; keep it in front until the scan finishes.";
      }
      d.hiddenDuringScan = hiddenSeen;
      d.failedAt = step;
      d.error = error;
      return done({ ok: false, step, error, ...extra });
    };

    try {
      // discover: a landing page that links to this week's list.
      if (site.discover && new RegExp(site.discover.on).test(location.href)) {
        const link = await waitFor(() => document.querySelector(site.discover.link),
                                   site.discover.timeout || 20000);
        d.steps.discover = { selector: site.discover.link, found: !!link };
        if (!link) {
          return fail("discover", site.discover.missing ||
            `The ${site.name} page no longer links to its deals ("${site.discover.link}").`);
        }
        return done({ navigate: link.href });
      }

      // ready
      const readyMs = (site.ready && site.ready.timeout) || 20000;
      const first = await waitFor(() => tally(site), readyMs);
      d.steps.ready = { selector: site.items, found: first };
      if (!first) {
        // A sign-in prompt explains an empty page better than "nothing found".
        const why = site.guard ? site.guard(document, H) : null;
        if (why) return fail("guard", why);
        return fail("ready", (site.messages && site.messages.notLoaded) ||
          `No ${site.name} offers appeared ("${site.items}" found nothing).`);
      }

      // guard
      if (site.guard) {
        const problem = site.guard(document, H);
        d.steps.guard = { ok: !problem };
        if (problem) return fail("guard", problem);
      }

      // load
      const expect = site.expect || {};
      const total = expect.total ? expect.total(document, H) : null;
      const loadOpts = site.load || { type: "none" };
      const loader = LOADERS[loadOpts.type];
      if (!loader) return fail("load", `unknown load type "${loadOpts.type}"`);
      d.steps.load = { type: loadOpts.type, ...(await loader(site, loadOpts, progress, total)) };

      // read
      tally(site);
      const cards = Array.from(document.querySelectorAll(site.items));
      const rows = cards.map((el) => {
        try { return site.read(el, H); } catch (e) { return { _error: String(e.message || e) }; }
      });
      d.steps.read = { cards: cards.length, fields: fieldCoverage(rows),
                       errors: rows.filter((r) => r && r._error).length };

      // keep + line
      const lines = [], skipped = [], seen = new Set();
      let dupes = 0, filtered = 0;
      rows.forEach((row, i) => {
        if (row && !row._error && site.keep && !site.keep(row, H)) { filtered++; return; }
        const line = row && !row._error ? site.line(row, H) : null;
        if (!line) {
          skipped.push(H.clean(cards[i].innerText).slice(0, 200));
          return;
        }
        const key = line.toLowerCase();
        if (seen.has(key)) { dupes++; return; }
        seen.add(key);
        lines.push(line);
      });
      d.steps.line = { lines: lines.length, skipped: skipped.length, duplicates: dupes, filtered,
                       skippedSamples: skipped.slice(0, 8), sample: lines.slice(0, 5) };

      // check
      const problems = [];
      if (total != null && cards.length !== total) {
        problems.push(`found ${cards.length} offers but the page says ${total}`);
      }
      if (expect.min && cards.length < expect.min) {
        problems.push(`found only ${cards.length} offers (expected at least ${expect.min})`);
      }
      // Unreadable cards are judged against the cards the site wanted.
      const wanted = cards.length - filtered;
      const maxSkip = expect.maxSkipped == null ? 0.1 : expect.maxSkipped;
      if (wanted && skipped.length / wanted > maxSkip) {
        problems.push(`${skipped.length} of ${wanted} offers could not be read`);
      }
      if (expect.minKept && wanted < expect.minKept) {
        problems.push(`only ${wanted} offers were left after filtering (expected at least ${expect.minKept})`);
      }
      for (const check of expect.checks || []) {
        const p = check({ document, rows, cards, lines, H });
        if (p) problems.push(p);
      }
      const info = site.info ? site.info(document, H) : {};
      const checks = { cards: cards.length, lines: lines.length, skipped: skipped.length,
                       filtered, total, ...info };
      d.checks = checks;
      d.hiddenDuringScan = hiddenSeen;
      d.steps.check = { problems };
      if (problems.length) {
        return fail("check", `The ${site.name} scan came up short: ${problems.join("; ")}. ` +
                             "Nothing was sent, so a partial list is not saved.",
                    { lines, checks });
      }
      return done({ ok: true, lines, checks });
    } catch (e) {
      return fail(e.step || "run", String(e.message || e));
    }
  };

  // For each field a site reads: how many rows had it.
  function fieldCoverage(rows) {
    const out = {};
    for (const r of rows) {
      if (!r || r._error) continue;
      for (const [k, v] of Object.entries(r)) {
        out[k] = out[k] || { filled: 0, empty: 0 };
        if (v === "" || v == null) out[k].empty++; else out[k].filled++;
      }
    }
    return out;
  }

  WSS.LOADERS = LOADERS;
  WSS.NEVER_PRESS = NEVER_PRESS;
})(globalThis);

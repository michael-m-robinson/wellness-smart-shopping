/*
 * Store Deal Crawler - browser harvest
 *
 * Run this on a store's weekly-ad or digital-coupon page while you are SIGNED
 * IN. Stores that hide deals behind an account (ShopRite digital coupons,
 * Stew Leonard's flyer, Costco member pricing) cannot be read any other way.
 *
 * How to run it:
 *   - Ask Claude, with the Claude for Chrome extension enabled, to run this
 *     file on the open store tab; or
 *   - paste the whole file into the browser console (DevTools > Console).
 *
 * It scrolls the page so lazily-loaded offers render, then hands the result
 * straight to the control panel running on your machine.
 *
 * A browser extension cannot write to your files, so it does not try: this
 * script runs inside the store's own page, and pages can post to a local
 * address. If the panel is not running it prints the lines instead, and you
 * can paste them into the panel's Scan window.
 */
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // --- sign-in check -------------------------------------------------------
  const bodyText = (document.body.innerText || "").slice(0, 4000);
  const signedOut = /(sign in|log in|create an account)/i.test(bodyText) &&
                    !/(sign out|log out|my account|hi,|welcome back)/i.test(bodyText);
  if (signedOut) {
    console.log(
      "NOT SIGNED IN\n" +
      "This page is showing a sign-in prompt, so its member deals are hidden.\n" +
      "Please sign in to this store in the browser, reopen the weekly ad or\n" +
      "digital coupon list, and run this script again."
    );
    return "NOT SIGNED IN";
  }

  // --- collect -------------------------------------------------------------
  const PRICE = /\$\s*\d+(?:\.\d{1,2})?/;
  const LIMIT = /limit\s+\d+/i;
  // Offer tiles differ per retailer, so match on shape rather than class names.
  const SELECTOR = [
    "[class*='coupon']", "[class*='offer']", "[class*='deal']",
    "[class*='product']", "[class*='card']", "[class*='tile']",
    "[data-testid*='coupon']", "[data-testid*='offer']", "li", "article",
  ].join(",");

  const found = new Map();

  const harvest = () => {
    document.querySelectorAll(SELECTOR).forEach((el) => {
      // Skip containers: we want the smallest node holding one whole offer.
      if (el.querySelector(SELECTOR)) return;
      const text = (el.innerText || "").replace(/\s+/g, " ").trim();
      if (text.length < 8 || text.length > 220) return;
      if (!PRICE.test(text)) return;

      const price = (text.match(PRICE) || [""])[0];
      const limit = (text.match(LIMIT) || [""])[0];
      // The title is the offer text with the price/limit stripped out.
      let title = text.replace(PRICE, " ").replace(LIMIT, " ")
                      .replace(/\s+/g, " ").trim();
      if (title.length < 3) title = text;
      const line = [title, price, limit].filter(Boolean).join(" | ");
      found.set(line.toLowerCase(), line);
    });
  };

  // --- scroll so lazy lists render ----------------------------------------
  const step = Math.max(320, Math.floor(window.innerHeight * 0.8));
  let position = 0, settled = 0;
  for (let i = 0; i < 45; i++) {
    harvest();
    position += step;
    window.scrollTo(0, position);
    await sleep(360);
    harvest();
    const bottom = Math.max(document.body.scrollHeight,
                            document.documentElement.scrollHeight);
    if (position >= bottom) {
      await sleep(420);
      const grown = Math.max(document.body.scrollHeight,
                             document.documentElement.scrollHeight);
      if (grown <= bottom) { settled += 1; if (settled >= 2) break; }
      else { settled = 0; }
    }
  }
  harvest();
  window.scrollTo(0, 0);

  const out = Array.from(found.values()).join("\n");
  if (!out) {
    console.log("NO OFFERS FOUND - open the coupon list and let it load first.");
    return "NO OFFERS FOUND";
  }

  // --- hand it to the control panel ---------------------------------------
  // Guess the store from the address so the panel files it correctly.
  const host = location.hostname.replace(/^www\./, "");
  const STORES = {
    "shoprite.com": "shoprite",
    "stewleonards.com": "stews",
    "costco.com": "costco",
  };
  let store = STORES[host];
  if (!store) {
    for (const [domain, key] of Object.entries(STORES)) {
      if (host.endsWith(domain)) { store = key; break; }
    }
  }

  const PORTS = [8765, 8766, 9000];
  if (store) {
    for (const port of PORTS) {
      try {
        const response = await fetch(
          `http://127.0.0.1:${port}/api/scan/submit?store=${store}`,
          { method: "POST", headers: { "Content-Type": "text/plain" }, body: out });
        if (response.ok) {
          const result = await response.json();
          console.log(`Sent ${result.lines} offers to the control panel. ` +
                      "It will pick them up on its own.");
          return `SENT ${result.lines} offers`;
        }
      } catch (e) { /* panel not on this port; try the next */ }
    }
  }

  console.log(
    "Could not reach the control panel, so here are the offers.\n" +
    "Copy everything below and paste it into the panel's Scan window:\n\n" + out);
  return out;
})();

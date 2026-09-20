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
 * It scrolls the page so lazily-loaded offers render, then prints one offer
 * per line as:  Title | price | limit
 * Copy that output into a text file and feed it back to the crawler:
 *   python3 crawl.py --harvest shoprite=offers.txt
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
  console.log(out || "NO OFFERS FOUND - open the weekly ad or coupon list first.");
  return out;
})();

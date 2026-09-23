/*
 * Stew Leonard's -- this week's specials.
 *
 * The flyer on stewleonards.com (and its print view) is page images with no
 * text, so it cannot be read. The same specials are listed as products in
 * Stew's online shop, in a collection whose address changes every week
 * (.../collections/rc-weekly-specials-9-16-9-22), so the scan starts on the
 * storefront and follows its "This Week's Specials" link.
 *
 * Page facts (verified 2026-09-21, 122 specials):
 *   card      [role="group"][aria-label="Product"]   26 at first, 20 more per
 *             "Load More"; a first visit also shows a store-choice dialog
 *             that locks scrolling (left alone -- the button still works)
 *   name      the product image's alt text
 *   prices    .screen-reader-only  "Current price: $2.49 per pound"
 *                                  "Original Price: $3.99 per pound"
 *             about 3 in 10 cards have no original price: the sale price is
 *             simply the price shown
 *   size      a short line such as "16 oz" or "4 ct"
 *   ends      the heading's range: "Weekly Specials 9/16-9/22" -> 9/22 for every card
 *   No sign-in needed, and no purchase limits are shown.
 */
(function (root) {
  const WSS = root.WSS;
  const H = WSS.helpers;

  // "Current price: $2.49 per pound" -> "$2.49/lb"; "... each (estimated)" -> "$2.72 each"
  function priceField(text) {
    const n = H.money(text);
    if (n == null) return "";
    if (/per\s+pound|\/\s*lb/i.test(text)) return `${H.fmt(n)}/lb`;
    if (/per\s+package/i.test(text)) return `${H.fmt(n)}/pkg`;
    if (/each/i.test(text)) return `${H.fmt(n)} each`;
    return H.fmt(n);
  }

  // The week's end date, from the list's heading (read once per page).
  const weekEnds = new WeakMap();
  function weekEnd(doc) {
    if (!doc) return "";
    if (!weekEnds.has(doc)) {
      const dates = H.dates(H.text(doc, "h1"));
      weekEnds.set(doc, dates[dates.length - 1] || "");
    }
    return weekEnds.get(doc);
  }

  const SIZE = /^\d+(?:\.\d+)?\s*(?:x\s*\d+(?:\.\d+)?\s*)?(?:oz|fl oz|lb|lbs|ct|g|kg|ml|l|gal|pk|pack|qt|pt)\b\.?$/i;

  const site = WSS.defineSite({
    key: "stews",
    name: "Stew Leonard's",
    version: 2,
    verified: "2026-09-21",
    startUrl: "https://shopnow.stewleonards.com/store/stew-leonards/storefront",
    readableOn: "shopnow\\.stewleonards\\.com/store/stew-leonards/(storefront|collections/rc-weekly-specials-)",
    hosts: ["stewleonards.com"],
    signIn: false,
    discover: {
      on: "/storefront",
      link: 'a[href*="/collections/rc-weekly-specials-"]',
      missing: "Stew's storefront no longer links to a \"weekly specials\" collection. " +
               "Update discover.link in extension/sites/stews.js.",
    },

    items: '[role="group"][aria-label="Product"]',
    ready: { timeout: 25000 },
    guard: (doc) => /weekly specials/i.test(H.text(doc, "h1") + " " + doc.title)
      ? null : "This is not Stew's weekly specials list (the heading changed).",
    // 20 more per press. Infinite scroll also exists but stops working behind
    // the "How would you like to shop?" dialog; the button does not.
    load: { type: "more-button", text: "^load more$", wait: 1500, stableRounds: 3 },

    read: (el) => {
      const sr = H.texts(el, ".screen-reader-only");
      const img = el.querySelector("img[alt]");
      const lines = String(el.innerText || "").split("\n").map(H.clean);
      return {
        name: img ? H.clean(img.alt) : "",
        current: sr.find((t) => /^current price/i.test(t)) || "",
        original: sr.find((t) => /^original price/i.test(t)) || "",
        size: lines.find((t) => SIZE.test(t)) || "",
        ends: weekEnd(el.ownerDocument),
      };
    },
    line: (r) => {
      const now = priceField(r.current);
      if (!r.name || !now) return null;
      const was = priceField(r.original);
      const name = r.size && !r.name.includes(r.size) ? `${r.name}, ${r.size}` : r.name;
      return H.join(H.tidy(name), was ? `${now}, was ${was}` : now, null, r.ends);
    },

    expect: { min: 30, maxSkipped: 0.05 },
    info: (doc) => ({ heading: H.text(doc, "h1") }),

    priceField,
  });

  if (typeof module === "object" && module.exports) module.exports = site;
})(globalThis);

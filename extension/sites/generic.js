/*
 * Any store without a site file of its own.
 *
 * Offer tiles differ per retailer, so this matches on shape -- the smallest
 * element holding a price -- rather than on class names, and scrolls the page
 * so lazy lists render. It has no page total to check itself against, so a
 * store worth scanning every week deserves a site file of its own (see
 * sites/README.md).
 */
(function (root) {
  const WSS = root.WSS;
  const H = WSS.helpers;

  const PRICE = /\$\s*\d+(?:\.\d{1,2})?/;
  const SHAPES = [
    "[class*='coupon']", "[class*='offer']", "[class*='deal']",
    "[class*='product']", "[class*='card']", "[class*='tile']",
    "[data-testid*='coupon']", "[data-testid*='offer']", "li", "article",
  ].join(",");

  // "Chicken Breast $1.99/lb Limit 4" -> "Chicken Breast /lb | $1.99 | Limit 4"
  function toLine(text) {
    const t = H.clean(text);
    if (t.length < 8 || t.length > 220 || !PRICE.test(t)) return null;
    const price = t.match(PRICE)[0];
    let title = H.clean(t.replace(PRICE, " ").replace(/limit\s+\d+/i, " "));
    if (title.length < 3) title = t;
    return H.join(title, price, H.limit(t));
  }

  function signedOut(text) {
    const t = String(text || "").slice(0, 4000);
    return /(sign in|log in|create an account)/i.test(t) &&
           !/(sign out|log out|my account|hi,|welcome back)/i.test(t);
  }

  // The engine reads site.items with querySelectorAll, which cannot say
  // "leaf offers only". Tag them first, then select the tag.
  const TAG = "data-wss-offer";
  function prepare(doc) {
    doc.querySelectorAll(SHAPES).forEach((el) => {
      if (!el.hasAttribute(TAG) && !el.querySelector(SHAPES) && PRICE.test(el.textContent || "")) {
        el.setAttribute(TAG, "");
      }
    });
  }

  const site = WSS.defineSite({
    key: "generic",
    name: "this store",
    version: 2,
    verified: "2026-09-21",
    hosts: [],
    signIn: true,

    items: `[${TAG}]`,
    ready: { timeout: 8000 },
    guard: (doc) => {
      if (signedOut(doc.body.innerText)) {
        return "This page is asking you to sign in, so its member deals are hidden. " +
               "Sign in on this tab, then scan again.";
      }
      return null;
    },
    load: { type: "sweep", step: 500, wait: 400, settle: 800 },

    read: (el) => ({ text: el.innerText || el.textContent || "" }),
    line: (r) => toLine(r.text),

    expect: { min: 1, maxSkipped: 0.5 },

    prepare,
    toLine, signedOut,
  });

  if (typeof module === "object" && module.exports) module.exports = site;
})(globalThis);

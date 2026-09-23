/*
 * ShopRite -- digital coupons.
 *
 * The coupon list on shoprite.com sits in a cross-origin iframe, so the scan
 * runs on the widget opened on its own. It keeps the store context and loads
 * signed out ("Login to Load"), so nothing here can load a coupon to a card.
 *
 * Page facts (verified 2026-09-21):
 *   card      .card.coupon-item                 (about 12 more per scroll)
 *   scroll    .scrollable-container, 1.5s per pass
 *   savings   .coupon-savings   "Save $5.00", "Buy 1 Get 1 Free"
 *   text      .coupon-desc      title and body run together; the ellipsis is CSS
 *   badges    .coupon-badge     "New", "Weekly Ad", "Limit 4"
 *   ends      .coupon-expiration-text   "Expires: 09/26/2026 - 5 days left"
 *   totals    "All Coupons - (140)", "Limit 4 Offers - (43)"
 *   signed in shoprite.com sets a cookie named "oidc.user:https://auth.brands.
 *             wakefern.com:<client>" (URL-encoded) while you are signed in;
 *             its header then reads "Hi <name> / My Account"
 */
(function (root) {
  const WSS = root.WSS;
  const H = WSS.helpers;

  const QTY = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
                seven: 7, eight: 8, nine: 9, ten: 10 };
  const QTY_RE = /^(?:any\s+)?(one|two|three|four|five|six|seven|eight|nine|ten)\b\s*(?:\(\d+\))?\s*/i;
  const CONTAINER_RE = /^(?:packages?|pkgs?|bags?|boxes|box|cans?|bottles?|btls?|packs?|jars?|cartons?)\s+(?:of\s+)?/i;
  // Everything after these is terms, not the product.
  const STOPS = [/\s*\(excludes?\b/i, /\s*\(includes?\b/i,
                 /\s+with\s+(?:the\s+)?purchase\s+of\b/i, /\s*\*\s*redeem/i,
                 /\s+save\s+\$/i, /\s+save\s+[\d.]+\s*¢/i,
                 /\s+when\s+you\s+(?:buy|purchase)\b/i, /\s+get\s+(?:one|two|\d+)\b.*free/i];

  // "Save $5.00 on ONE Herbal Essences Shampoo (excludes ...) ONE Herbal ..."
  //   -> "Herbal Essences Shampoo"
  function cleanName(desc) {
    let t = H.clean(desc);
    t = t.replace(/^save\s+(?:\$\s*[\d.]+|[\d.]+\s*¢)\s*/i, "");
    const basket = /^(?:on|off)\s+your\s+total\s+basket\s*/i.test(t);
    t = t.replace(/^(?:on|off)\s+your\s+total\s+basket\s*/i, "")
         .replace(/^(?:on|off)\s+/i, "")
         .replace(/^when\s+you\s+(?:buy|purchase)\s+/i, "")
         .replace(/^buy\s+/i, "");

    // The card repeats its title as its body. Cut at the second copy.
    const head = t.slice(0, 24);
    if (head.length >= 12) {
      const again = t.indexOf(head, 12);
      if (again > 0) t = t.slice(0, again);
    }

    let qty = 1;
    const q = t.match(QTY_RE);
    if (q) {
      qty = QTY[q[1].toLowerCase()] || 1;
      t = t.slice(q[0].length);
    } else {
      // "2 General Mills Cereals" -- but not "12 oz" or "32 ct".
      const n = t.match(/^(\d{1,2})\s+(?=[A-Z][a-z])/);
      if (n && Number(n[1]) > 1) { qty = Number(n[1]); t = t.slice(n[0].length); }
    }
    t = H.tidy(H.cutAt(t.replace(CONTAINER_RE, ""), STOPS));
    if (basket) {
      t = t.replace(/^when\s+you\s+/i, "");
      t = t ? `Total basket - ${t}` : "Total basket";
    }
    if (qty > 1) t += ` (buy ${qty})`;
    return t;
  }

  // "Save $5.00" -> "$5.00 off"; "Save 50¢" -> "$0.50 off"; BOGO as written.
  function savingsField(text) {
    const n = H.money(text);
    return n != null ? `${H.fmt(n)} off` : H.clean(text);
  }

  function chipCounts(text) {
    const all = String(text).match(/All Coupons\s*-?\s*\((\d+)\)/i);
    const limit = String(text).match(/Limit\s*\d+\s*Offers\s*-?\s*\((\d+)\)/i);
    return { all: all ? Number(all[1]) : null, limit: limit ? Number(limit[1]) : null };
  }

  const site = WSS.defineSite({
    key: "shoprite",
    name: "ShopRite",
    version: 3,
    verified: "2026-09-21",
    startUrl: "https://shop-rite-web-prod.azurewebsites.net/",
    readableOn: "^https://shop-rite-web-prod\\.azurewebsites\\.net/",
    hosts: ["shop-rite-web-prod.azurewebsites.net", "shoprite.com"],
    signIn: false,
    // Coupons only count once loaded to a signed-in account, so the panel
    // asks whether you are signed in. Only the cookie's NAME is looked at,
    // never its value (that is the sign-in token).
    account: {
      cookieDomain: "shoprite.com",
      signedInCookie: "^oidc\\.user(%3A|:)",
      signInUrl: "https://www.shoprite.com/sm/planning/rsid/{store_id}/digital-coupon",
    },

    items: ".card.coupon-item",
    ready: { timeout: 20000 },
    messages: { notLoaded: "The ShopRite coupon list did not load. Open shoprite.com, " +
                           "choose your store, and try again." },
    load: { type: "scroll-container", container: ".scrollable-container",
            wait: 1500, stableRounds: 3 },

    read: (el) => ({
      savings: H.text(el, ".coupon-savings"),
      desc: H.text(el, ".coupon-desc"),
      badges: H.texts(el, ".coupon-badge"),
      expires: H.text(el, ".coupon-expiration-text"),
    }),
    line: (r) => {
      const name = cleanName(r.desc);
      if (!name) return null;
      return H.join(name, savingsField(r.savings), H.limit(r.badges.join(" ")),
                    H.dates(r.expires || "")[0]);
    },

    expect: {
      total: (doc) => chipCounts(doc.body.innerText).all,
      min: 20,
      maxSkipped: 0.02,
      checks: [
        ({ document, rows }) => {
          const want = chipCounts(document.body.innerText).limit;
          const got = rows.filter((r) => r && r.badges && H.limit(r.badges.join(" "))).length;
          return want != null && got !== want
            ? `found ${got} limited offers but the page says ${want}` : null;
        },
      ],
    },
    info: (doc) => ({ limitedOnPage: chipCounts(doc.body.innerText).limit }),

    // For tests.
    cleanName, savingsField, chipCounts,
  });

  if (typeof module === "object" && module.exports) module.exports = site;
})(globalThis);

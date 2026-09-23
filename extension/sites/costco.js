/*
 * Costco -- warehouse savings.
 *
 * The savings page is public: no sign-in, all offers in the page, grouped by
 * department. Some tiles render lazily, so the page is swept once top to
 * bottom before reading.
 *
 * Page facts (verified 2026-09-21, 189 offers in 16 departments):
 *   group     [data-testid^="coupon-set-"]          "coupon-set-Grocery"
 *   card      the group's grid > grid item
 *   texts     [data-testid="Text"]   name, size ("14 oz"), "Item 1244454", "Limit 5."
 *             plus labels: "Warehouse", "&", "Online" -- or "Warehouse & Online" as one
 *   price     [data-testid="Text_prices_and_percentages_prices"]        "$15.99"
 *             [data-testid="Text_prices_and_percentages_prepend_text"]  "Save"
 *             [data-testid="Text_prices_and_percentages_append_text"]   "After $6 OFF"
 *   ends      the booklet's "Valid 9/21/26 - 10/18/26" -> 10/18/26 for every card
 *   A few cards show their price only in the image; they are skipped and
 *   listed in the report. Most departments are not food (Apparel, Pharmacy,
 *   Electronics ...); only Grocery is kept -- "Banana Republic ... Pant" once
 *   matched the shopping list as fruit.
 */
(function (root) {
  const WSS = root.WSS;
  const H = WSS.helpers;

  // Labels and price fragments that sit among the card's texts.
  const MARKER = /^(?:(?:warehouse|online)(?:\s*(?:&|and)\s*(?:warehouse|online))?(?:\s+only)?|&|\$|\.|\d+|%|save|buy online)$/i;
  const P = '[data-testid="Text_prices_and_percentages_';
  const FOOD_DEPARTMENTS = /^grocery$/i;

  // The booklet's end date (read once per page).
  const validUntil = new WeakMap();
  function bookletEnd(doc) {
    if (!doc || !doc.body) return "";
    if (!validUntil.has(doc)) {
      const m = H.clean(doc.body.innerText || "").match(/Valid\s+([\d\/]+\s*-\s*[\d\/]+)/i);
      const dates = m ? H.dates(m[1]) : [];
      validUntil.set(doc, dates[dates.length - 1] || "");
    }
    return validUntil.get(doc);
  }

  // One card's price, in words the panel's parser already knows:
  //   Save $6.80              -> "Save $6.80"
  //   $15.99 After $6 OFF     -> "$15.99 after $6.00 off"
  //   Save 25 %               -> "Save 25%"
  function priceField(r) {
    const amount = H.money(r.price);
    if (/save/i.test(r.prepend)) {
      if (amount != null) return `Save ${H.fmt(amount)}`;
      const pct = H.clean(r.price + " " + r.append).match(/(\d+)\s*%/);
      return pct ? `Save ${pct[1]}%` : "";
    }
    if (amount == null) return "";
    const off = H.money(r.append);
    return off != null ? `${H.fmt(amount)} after ${H.fmt(off)} off` : H.fmt(amount);
  }

  const site = WSS.defineSite({
    key: "costco",
    name: "Costco",
    version: 3,
    verified: "2026-09-21",
    startUrl: "https://www.costco.com/o/-/warehouse-savings",
    readableOn: "costco\\.com/o/-/warehouse-savings",
    hosts: ["costco.com"],
    signIn: false,

    items: '[data-testid^="coupon-set-"] > [data-testid="Grid"] > [data-testid="Grid"]',
    ready: { timeout: 25000 },
    load: { type: "sweep", wait: 150, settle: 1500 },

    read: (el) => {
      const texts = H.texts(el, '[data-testid="Text"]').filter((t) => !MARKER.test(t));
      const name = texts[0] || "";
      const rest = texts.slice(1);
      const set = el.closest('[data-testid^="coupon-set-"]');
      return {
        name,
        size: rest.find((t) => !/^item\b|^limit\b|\$|%/i.test(t) && t.length < 40) || "",
        item: (rest.find((t) => /^item\b/i.test(t)) || "").replace(/\.$/, ""),
        limitText: rest.filter((t) => /limit/i.test(t)).join(" "),
        department: set ? set.getAttribute("data-testid").replace("coupon-set-", "") : "",
        prepend: H.text(el, P + 'prepend_text"]'),
        price: H.text(el, P + 'prices"]'),
        append: H.text(el, P + 'append_text"]'),
        ends: bookletEnd(el.ownerDocument),
      };
    },
    // Food only. Department names come from the page ("coupon-set-Grocery").
    keep: (r) => FOOD_DEPARTMENTS.test(r.department),
    line: (r) => {
      const price = priceField(r);
      if (!r.name || !price) return null;
      const name = r.size ? `${r.name}, ${r.size}` : r.name;
      return H.join(H.tidy(name), price, H.limit(r.limitText), r.ends);
    },

    // A handful of cards carry the price only in their picture.
    expect: { min: 50, maxSkipped: 0.08, minKept: 10 },
    info: (doc) => {
      const valid = H.clean(doc.body.innerText).match(/Valid\s+(\d+\/\d+\/\d+\s*-\s*\d+\/\d+\/\d+)/i);
      return { valid: valid ? valid[1] : "",
               departments: doc.querySelectorAll('[data-testid^="coupon-set-"]').length };
    },

    priceField,
  });

  if (typeof module === "object" && module.exports) module.exports = site;
})(globalThis);

/*
 * Shared helpers and the site registry.
 *
 * Loaded everywhere: in the background worker (to know each site's pages),
 * inside the store page (with engine.js, to read it), and in Node (tests).
 * Nothing here touches the DOM except the small text readers, which take an
 * element and so work on any DOM, or none.
 */
(function (root) {
  const WSS = root.WSS = root.WSS || {};
  WSS.sites = WSS.sites || {};

  /*
   * Register a site. See sites/README.md for every field. The ones the
   * background needs (startUrl, runsOn, hosts, discover) are plain data; the
   * ones the page needs (read, line) are functions of an element / a row.
   */
  WSS.defineSite = function (site) {
    for (const key of ["key", "name", "version", "verified", "items", "read", "line"]) {
      if (site[key] === undefined) throw new Error(`site ${site.key || "?"}: missing "${key}"`);
    }
    WSS.sites[site.key] = site;
    return site;
  };

  const H = WSS.helpers = {};

  // Collapse whitespace; "" for null.
  H.clean = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim();

  // The first dollar amount in a string, as a number: "$15.99" -> 15.99,
  // "$ 15 . 99" -> 15.99, "After $6 OFF" -> 6, "50¢" -> 0.5. null if none.
  H.money = (s) => {
    const t = H.clean(s);
    const d = t.match(/\$\s*(\d+)(?:\s*\.\s*(\d{1,2}))?/);
    if (d) return Number(`${d[1]}.${(d[2] || "0").padEnd(2, "0")}`);
    const c = t.match(/(\d+)\s*¢/);
    return c ? Number(c[1]) / 100 : null;
  };

  // 15.9 -> "$15.90"
  H.fmt = (n) => `$${Number(n).toFixed(2)}`;

  // "Limit 5." / "LIMIT 4" -> "Limit 5"; null if the text states none.
  H.limit = (s) => {
    const m = H.clean(s).match(/\blimit\s*(\d+)/i);
    return m ? `Limit ${m[1]}` : null;
  };

  // Text of the first match under el, cleaned; "" if none.
  H.text = (el, selector) => {
    const found = selector ? el.querySelector(selector) : el;
    return found ? H.clean(found.textContent) : "";
  };

  // Cleaned, non-empty texts of every match under el.
  H.texts = (el, selector) =>
    Array.from(el.querySelectorAll(selector)).map((e) => H.clean(e.textContent)).filter(Boolean);

  // Cut a string at the first of several patterns (only if something remains).
  H.cutAt = (s, patterns) => {
    let t = s;
    for (const p of patterns) {
      const m = t.match(p);
      if (m && m.index > 0) t = t.slice(0, m.index);
    }
    return t;
  };

  // Trim trailing punctuation and cap length at a word boundary.
  H.tidy = (s, max = 110) => {
    let t = H.clean(s).replace(/[\s\-–—.,;:]+$/, "");
    if (t.length > max) {
      const cut = t.lastIndexOf(" ", max);
      t = t.slice(0, cut > 40 ? cut : max).replace(/[\s,;:]+$/, "");
    }
    return t;
  };

  // The one line format the panel reads:  name | price or discount | limit
  H.join = (name, price, limit) => `${name} | ${price} | ${limit || "no limit"}`;

  if (typeof module === "object" && module.exports) module.exports = WSS;
})(globalThis);

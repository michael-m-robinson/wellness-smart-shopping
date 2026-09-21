// A tiny stand-in for the DOM: enough for site read() functions and the
// engine's steps, without a browser or any npm package.
function leaf(text, attrs = {}) {
  return { textContent: text, innerText: text, alt: attrs.alt, children: [],
           getAttribute: (k) => attrs[k] ?? null, hasAttribute: (k) => k in attrs };
}

// card({ ".coupon-savings": ["Save $1.00"], ... }, { text, alt, closest })
function card(map, extra = {}) {
  const find = (sel) => (map[sel] || []).map((t) => (typeof t === "string" ? leaf(t) : t));
  const text = extra.text ?? Object.values(map).flat()
    .map((t) => (typeof t === "string" ? t : t.textContent)).join("\n");
  return {
    textContent: text, innerText: text,
    querySelectorAll: (sel) => find(sel),
    querySelector: (sel) => find(sel)[0] || null,
    closest: (sel) => (extra.closest && extra.closest[sel]) || null,
    getAttribute: () => null, hasAttribute: () => false,
  };
}

// Install a fake page: `cards` is an array, or a function (call number) ->
// array, so a list can "grow" as the engine scrolls.
function page({ cards = [], body = "", href = "https://example.com/list", buttons = [],
                visible = true, h1 = "" } = {}) {
  let calls = 0;
  const current = () => (typeof cards === "function" ? cards(calls) : cards);
  const doc = {
    visibilityState: visible ? "visible" : "hidden",
    title: "",
    body: { innerText: body, textContent: body, scrollHeight: 1000 },
    documentElement: { scrollHeight: 1000 },
    querySelectorAll: (sel) => {
      if (sel.startsWith("button")) return buttons;
      if (sel === "h1") return h1 ? [leaf(h1)] : [];
      return current();
    },
    querySelector: (sel) => {
      if (sel.startsWith("a[")) return doc._link || null;
      if (sel === "h1") return h1 ? leaf(h1) : null;
      return current()[0] || null;
    },
  };
  global.document = doc;
  global.location = { href };
  global.window = { innerHeight: 800, scrollTo: () => { calls++; }, dispatchEvent: () => {} };
  global.Event = class { constructor(t) { this.type = t; } };
  return doc;
}

module.exports = { leaf, card, page };

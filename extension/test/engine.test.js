// The engine's steps, self-checks and diagnostics, on a fake page.
const test = require("node:test");
const assert = require("node:assert/strict");
const WSS = require("../engine/helpers.js");
const { card, leaf, page } = require("./fakedom.js");
page();
require("../engine/engine.js");
const H = WSS.helpers;

const offer = (name, price) => card({ ".n": [name], ".p": [price] });
const site = (over = {}) => ({
  key: "t", name: "Test", version: 1, verified: "2026-09-21", items: ".c",
  ready: { timeout: 50 }, load: { type: "none" },
  read: (el) => ({ name: H.text(el, ".n"), price: H.text(el, ".p") }),
  line: (r) => (r.name && r.price ? H.join(r.name, r.price, null) : null),
  ...over,
});

test("a clean page passes and reports what it read", async () => {
  page({ cards: [offer("Eggs", "$2.99"), offer("Oats", "$3.49"), offer("Eggs", "$2.99")] });
  const r = await WSS.run(site());
  assert.equal(r.ok, true);
  assert.deepEqual(r.lines, ["Eggs | $2.99 | no limit", "Oats | $3.49 | no limit"]);
  assert.equal(r.diagnostics.steps.line.duplicates, 1);
  assert.deepEqual(r.diagnostics.steps.read.fields.name, { filled: 3, empty: 0 });
});

test("the page's own total must match", async () => {
  page({ cards: [offer("Eggs", "$2.99")], body: "All (2)" });
  const r = await WSS.run(site({ expect: { total: () => 2 } }));
  assert.equal(r.ok, false);
  assert.equal(r.step, "check");
  assert.match(r.error, /found 1 offers but the page says 2/);
  assert.match(r.error, /Nothing was sent/);
  assert.equal(r.lines.length, 1, "the partial list is still shown to copy");
});

test("too many unreadable cards fail, with samples", async () => {
  page({ cards: [offer("Eggs", "$2.99"), offer("Mystery", ""), offer("Other", "")] });
  const r = await WSS.run(site({ expect: { maxSkipped: 0.1 } }));
  assert.equal(r.ok, false);
  assert.match(r.error, /2 of 3 offers could not be read/);
  assert.equal(r.diagnostics.steps.line.skippedSamples.length, 2);
  assert.deepEqual(r.diagnostics.steps.read.fields.price, { filled: 1, empty: 2 });
});

test("no cards: the ready step fails and names the selector", async () => {
  page({ cards: [] });
  const r = await WSS.run(site());
  assert.equal(r.step, "ready");
  assert.equal(r.diagnostics.failedAt, "ready");
  assert.match(r.error, /"\.c" found nothing/);
});

test("a guard message wins over an empty page", async () => {
  page({ cards: [] });
  const r = await WSS.run(site({ guard: () => "Please sign in." }));
  assert.equal(r.step, "guard");
  assert.equal(r.error, "Please sign in.");
});

test("discover follows the landing page's link", async () => {
  const doc = page({ href: "https://shop.example.com/storefront" });
  doc._link = { href: "https://shop.example.com/collections/specials-9-16" };
  const r = await WSS.run(site({ discover: { on: "/storefront", link: 'a[href*="specials"]' } }));
  assert.equal(r.navigate, "https://shop.example.com/collections/specials-9-16");
  page({ href: "https://shop.example.com/storefront" });
  const missing = await WSS.run(site({ ready: { timeout: 50 },
    discover: { on: "/storefront", link: 'a[href*="specials"]', missing: "no link", timeout: 50 } }));
  assert.equal(missing.step, "discover");
});

test("scrolling stops once the list stops growing", async () => {
  const all = [offer("A", "$1"), offer("B", "$2"), offer("C", "$3")];
  page({ cards: (calls) => all.slice(0, Math.min(1 + calls, 3)) });
  const r = await WSS.run(site({ load: { type: "scroll-window", wait: 1, stableRounds: 2 } }));
  assert.equal(r.ok, true);
  assert.equal(r.lines.length, 3);
  assert.ok(r.diagnostics.steps.load.rounds >= 3);
});

test("a hidden tab is named in the failure", async () => {
  page({ cards: [offer("A", "$1")], visible: false });
  const r = await WSS.run(site({ expect: { total: () => 5 } }));
  assert.equal(r.diagnostics.hiddenDuringScan, true);
  assert.match(r.error, /in the background/);
});

test("more-button presses only an anchored, harmless label", async () => {
  let pressed = 0;
  const more = { innerText: "Load More", textContent: "Load More", click: () => pressed++ };
  page({ cards: [offer("A", "$1")], buttons: [more] });
  await WSS.run(site({ load: { type: "more-button", text: "^load more$", wait: 1, stableRounds: 2 } }));
  assert.ok(pressed > 0);

  const danger = { innerText: "Login to Load", textContent: "Login to Load", click: () => { throw new Error("pressed!"); } };
  page({ cards: [offer("A", "$1")], buttons: [danger] });
  const r = await WSS.run(site({ load: { type: "more-button", text: "^login to load$", wait: 1 } }));
  assert.equal(r.step, "load");
  assert.match(r.error, /refused to press "Login to Load"/);

  page({ cards: [offer("A", "$1")], buttons: [more] });
  const loose = await WSS.run(site({ load: { type: "more-button", text: "load", wait: 1 } }));
  assert.match(loose.error, /must be anchored/);
});

test("cards a site leaves out on purpose are filtered, not unreadable", async () => {
  const shirt = card({ ".n": ["Banana Republic Pant"], ".p": ["$15.99"], ".d": ["Apparel"] });
  const eggs = card({ ".n": ["Eggs"], ".p": ["$2.99"], ".d": ["Grocery"] });
  page({ cards: [shirt, shirt, shirt, eggs] });
  const r = await WSS.run(site({
    read: (el) => ({ name: H.text(el, ".n"), price: H.text(el, ".p"), dept: H.text(el, ".d") }),
    keep: (row) => row.dept === "Grocery",
    expect: { maxSkipped: 0 },
  }));
  assert.equal(r.ok, true);
  assert.deepEqual(r.lines, ["Eggs | $2.99 | no limit"]);
  assert.equal(r.checks.filtered, 3);
  assert.equal(r.checks.skipped, 0);
});

test("the never-press list covers the dangerous controls", () => {
  for (const label of ["Login to Load", "Load to Card", "Add to cart", "Clip", "Confirm", "Sign In", "Change store"]) {
    assert.ok(WSS.NEVER_PRESS.test(label), label);
  }
  for (const label of ["Load More", "Show more"]) assert.ok(!WSS.NEVER_PRESS.test(label), label);
});

// node --test extension/test/*.test.js
// Rows are verbatim from the live pages (verified 2026-09-21).
const test = require("node:test");
const assert = require("node:assert/strict");
const WSS = require("../engine/helpers.js");
require("../sites/shoprite.js");
require("../sites/stews.js");
require("../sites/costco.js");
require("../sites/generic.js");
const { card, leaf } = require("./fakedom.js");
const H = WSS.helpers;
const { shoprite, stews, costco, generic } = WSS.sites;
const lineOf = (site, el) => site.line(site.read(el, H), H);

test("helpers: money, limits, line", () => {
  assert.equal(H.money("$15.99"), 15.99);
  assert.equal(H.money("$ 15 . 99"), 15.99);
  assert.equal(H.money("After $6 OFF"), 6);
  assert.equal(H.money("SAVE 50¢"), 0.5);
  assert.equal(H.money("Buy 1 Get 1 Free"), null);
  assert.equal(H.limit("Limit 5. Selection varies"), "Limit 5");
  assert.equal(H.limit("no cap"), null);
  assert.equal(H.join("Eggs", "$1.00 off", null), "Eggs | $1.00 off | no limit");
});

test("every site declares what the engine and the background need", () => {
  for (const s of Object.values(WSS.sites)) {
    assert.ok(s.version >= 1 && /^\d{4}-\d{2}-\d{2}$/.test(s.verified), s.key);
    if (s.key === "generic") continue;
    assert.ok(s.startUrl && s.readableOn && s.hosts.length, s.key);
    assert.match(s.startUrl, new RegExp(s.readableOn), `${s.key}: startUrl must be readable`);
    assert.ok(s.expect && s.expect.min > 0, `${s.key}: needs a minimum to check against`);
  }
});

// ---------------------------------------------------------------- ShopRite
test("shoprite: names, quantities and terms", () => {
  const cases = [
    ["Save $5.00 on ONE Herbal Essences Pure Plant Essences Shampoo or Conditioner (excludes Treatments, Dual Packs, 100 mL Shampoo and Conditioners, and tr ONE Herbal Essences Pure Plant Essences Shampoo or Conditioner (excludes Treatments, Dual Packs, 100 mL Shampoo and Conditioners, and trial/travel size).",
     "Herbal Essences Pure Plant Essences Shampoo or Conditioner"],
    ["Save $2.00 on any ONE (1) Harry's Plus Razor Handle Pack or Harry's Plus 8ct Cartridge Refill Save $2.00 on any ONE (1) Harry's Plus Razor Handle Pack or Harry's Plus 8ct Cartridge Refill",
     "Harry's Plus Razor Handle Pack or Harry's Plus 8ct Cartridge Refill"],
    ["Save $4.00 on Olay Regenerist Skin Care When you Buy ONE (1) Olay Regenerist Skin Care 1.7-fl. oz., Assorted Varieties, Serum, Moisturizer and Cream *Redeem up to 4 times in a single order.",
     "Olay Regenerist Skin Care"],
    ["Save $1.00 When you Buy ONE (1) The Pink Stuff Foaming Toilet Cleaner 2-Pack - *Redeem up to 4 times in a single order.",
     "The Pink Stuff Foaming Toilet Cleaner 2-Pack"],
    ["Save $0.50 on any ONE (1) package of Angel Soft® Bath Tissue, any size Save $0.50 on any ONE (1) package of Angel Soft® Bath Tissue, any size",
     "Angel Soft® Bath Tissue, any size"],
    ["Save $1.00 off ONE (1) Eggo product with the purchase of ONE (1) qualifying egg or cheese item 6 ct. or higher",
     "Eggo product"],
    ["Save $3.00 on ONE 9 ELEMENTS Laundry Detergent", "9 ELEMENTS Laundry Detergent"],
    ["Save $1.00 when you buy Three (3) cans of Blue Buffalo™ wet dog food (excludes MP)", "Blue Buffalo™ wet dog food (buy 3)"],
    ["SAVE $1.00 on 2 General Mills Cereals", "General Mills Cereals (buy 2)"],
    ["Save $2.00 on any ONE (1) 12 oz or larger bag of Dentalife® Dog Treats", "12 oz or larger bag of Dentalife® Dog Treats"],
    ["Save $15.00 on your total basket when you Spend $50.00 or more on select Similac items",
     "Total basket - Spend $50.00 or more on select Similac items"],
    ["BUY ONE (1) GATORADE® WATER SINGLE SERVE GET ONE (1) FREE", "GATORADE® WATER SINGLE SERVE"],
  ];
  for (const [desc, want] of cases) assert.equal(shoprite.cleanName(desc), want);
});

test("shoprite: a card becomes a line", () => {
  const el = card({ ".coupon-savings": ["Save $1.00"],
                    ".coupon-desc": ["Save $1.00 on Nature’s Own Bread When you Buy ONE (1) Nature’s Own Bread"],
                    ".coupon-badge": ["Weekly Ad", "Limit 4"] });
  assert.equal(lineOf(shoprite, el), "Nature’s Own Bread | $1.00 off | Limit 4");
  const bogo = card({ ".coupon-savings": ["Buy 1 Get 1 Free"],
                      ".coupon-desc": ["BUY ONE (1) GATORADE® WATER SINGLE SERVE GET ONE (1) FREE"],
                      ".coupon-badge": [] });
  assert.equal(lineOf(shoprite, bogo), "GATORADE® WATER SINGLE SERVE | Buy 1 Get 1 Free | no limit");
  assert.deepEqual(shoprite.chipCounts("All Coupons - (140)\nLimit 4 Offers - (43)"), { all: 140, limit: 43 });
});

test("shoprite: knows a signed-in cookie by its name", () => {
  const want = new RegExp(shoprite.account.signedInCookie, "i");
  assert.ok(want.test("oidc.user%3Ahttps%3A%2F%2Fauth.brands.wakefern.com%3AAHWq"));
  assert.ok(want.test("oidc.user:https://auth.brands.wakefern.com:abc"));
  for (const other of ["CUSTOMER_SESSION_ID_COOKIE", "MI9_RSID", "OptanonConsent"]) {
    assert.ok(!want.test(other), other);
  }
});

// ---------------------------------------------------------------- Stew's
test("stews: prices by the pound, each, and with no original price", () => {
  const chicken = card({ ".screen-reader-only": ["Current price: $2.49 per pound", "Original Price: $3.99 per pound"],
                         "img[alt]": [leaf("", { alt: "Stew Leonard's Family Pack Boneless Chicken Breasts" })] },
                       { text: "Local\nCurrent price: $2.49 per pound\n$249\n/lb\nSave $1.50\n38% off\nStew Leonard's Family Pack Boneless Chicken Breasts\nAdd" });
  assert.equal(lineOf(stews, chicken),
               "Stew Leonard's Family Pack Boneless Chicken Breasts | $2.49/lb, was $3.99/lb | no limit");
  const squash = card({ ".screen-reader-only": ["Current price: $2.72 each (estimated)", "Original Price: $5.47 each (estimated)"],
                        "img[alt]": [leaf("", { alt: "Spaghetti Squash" })] },
                      { text: "Spaghetti Squash\n$0.99 / lb\nAbout 2.75 lb each\nAdd" });
  assert.equal(lineOf(stews, squash), "Spaghetti Squash | $2.72 each, was $5.47 each | no limit");
  const snack = card({ ".screen-reader-only": ["Current price: $3.99"],
                       "img[alt]": [leaf("", { alt: "drybox Freeze Dried Berries" })] },
                     { text: "Gluten-freeVegan\nCurrent price: $3.99\n$399\ndrybox Freeze Dried Berries\n0.56 oz\nAdd" });
  assert.equal(lineOf(stews, snack), "drybox Freeze Dried Berries, 0.56 oz | $3.99 | no limit");
  const nameless = card({ ".screen-reader-only": ["Current price: $3.99"] });
  assert.equal(lineOf(stews, nameless), null);
});

// ---------------------------------------------------------------- Costco
const costcoCard = (texts, prices) => card({
  '[data-testid="Text"]': texts,
  '[data-testid="Text_prices_and_percentages_prepend_text"]': prices.prepend ? [prices.prepend] : [],
  '[data-testid="Text_prices_and_percentages_prices"]': prices.price ? [prices.price] : [],
  '[data-testid="Text_prices_and_percentages_append_text"]': prices.append ? [prices.append] : [],
}, { closest: { '[data-testid^="coupon-set-"]': leaf("", { "data-testid": "coupon-set-Grocery" }) } });

test("costco: both price forms, labels and sizes", () => {
  assert.equal(lineOf(costco, costcoCard(
    ["Warehouse", "Online", "Nescafé Taster’s Choice House Blend Instant Coffee", "14 oz", "Item 1244454", "Limit 5.", "$", "15", ".", "99"],
    { price: "$15.99", append: "After $6 OFF" })),
    "Nescafé Taster’s Choice House Blend Instant Coffee, 14 oz | $15.99 after $6.00 off | Limit 5");
  assert.equal(lineOf(costco, costcoCard(
    ["Warehouse & Online", "Vita Coco Coconut Water", "18/11.1 fl oz", "Item 1218891", "Limit 10."],
    { prepend: "Save", price: "$5.80" })),
    "Vita Coco Coconut Water, 18/11.1 fl oz | Save $5.80 | Limit 10");
  assert.equal(lineOf(costco, costcoCard(
    ["Warehouse", "&", "Online", "Brazi Bites Brazilian Cheese Bread", "$4"],
    { prepend: "Save", price: "$4" })),
    "Brazi Bites Brazilian Cheese Bread | Save $4.00 | no limit");
  // Only Grocery is kept: clothes and supplements never reach the list.
  assert.equal(costco.keep({ department: "Grocery" }), true);
  for (const d of ["Apparel", "Pharmacy", "Health & Personal Care", "Household Items"]) {
    assert.equal(costco.keep({ department: d }), false, d);
  }
  // Price only in the picture: skipped, and the engine reports it.
  assert.equal(lineOf(costco, costcoCard(
    ["Warehouse Only", "Philadelphia Original Cream Cheese Spread", "48 oz", "Item 40532", "Limit 6."], {})), null);
});

// ---------------------------------------------------------------- generic
test("generic: shape-matched lines and sign-in detection", () => {
  assert.equal(generic.toLine("Boneless Chicken Breast $1.99/lb Limit 4"),
               "Boneless Chicken Breast /lb | $1.99 | Limit 4");
  assert.equal(generic.toLine("No price here at all"), null);
  assert.equal(generic.signedOut("Sign in to see member deals"), true);
  assert.equal(generic.signedOut("Hi, Sam | Sign out"), false);
});

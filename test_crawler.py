#!/usr/bin/env python3
"""Tests: python3 test_crawler.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dealcrawler.catalog import BY_ID, ITEMS, VALID_IDS
from dealcrawler.matcher import match
from dealcrawler.offers import Offer, dedupe, extract, mirror_twins, parse_limit
from dealcrawler.xmlout import render, safe_note, validate

# The exact item IDs the Smart Shopping List importer accepts. An offer using
# any other ID is silently discarded by the app, so this list is load-bearing.
APP_CATALOG_IDS = {
    "beans", "beef", "blackpepper", "blueberries", "bread", "broth", "chia",
    "chicken", "cinnamon", "cod", "cottage", "cumin", "dinnerveg", "eggs",
    "feta", "fruit", "garlicpowder", "greens", "hummus", "italianseasoning",
    "lentils", "lunchveg", "milk", "oats", "oil", "onionpowder", "paprika",
    "pasta", "peanut", "quinoa", "redpepper", "rice", "salmon", "salt",
    "sauces", "shrimp", "snackeggs", "snackmilk", "snackyogurt", "spices",
    "sweetpotato", "tofu", "tomatoes", "tuna", "turkey", "vinegar", "walnuts",
    "whey", "wraps", "yogurt",
}


class TestCatalog(unittest.TestCase):
    def test_ids_match_the_app(self):
        self.assertEqual(VALID_IDS, APP_CATALOG_IDS)

    def test_ids_unique(self):
        self.assertEqual(len(ITEMS), len(VALID_IDS))

    def test_twins_point_at_real_items(self):
        for item in ITEMS:
            for twin in item.twins:
                self.assertIn(twin, VALID_IDS)


class TestMatcher(unittest.TestCase):
    def test_matches_staples(self):
        for text, want in [
            ("93% Lean Ground Turkey", "turkey"),
            ("Boneless Skinless Chicken Breast", "chicken"),
            ("Natural Peanut Butter 36 oz", "peanut"),
            ("Plain Greek Yogurt 40oz", "yogurt"),
            ("Frozen Blueberries 4 lb", "blueberries"),
            ("Extra Virgin Olive Oil", "oil"),
            ("Brown Rice 2 lb", "rice"),
            ("Old Fashioned Rolled Oats", "oats"),
        ]:
            self.assertEqual(match(text), want, text)

    def test_rejects_lookalikes(self):
        """A wrong match silently corrupts the user's budget, so these matter."""
        for text in [
            "Peanut Butter Cups", "Cinnamon Toast Crunch Cereal", "Rice Cakes",
            "Almond Milk", "Yoplait Yogurt Bars", "Chicken Nuggets",
            "Dog Food Chicken Recipe", "Fish Oil Softgels",
            "Protein Bars Chocolate Peanut Butter", "Tomato Ketchup",
        ]:
            self.assertIsNone(match(text), text)

    def test_disambiguates_compounds(self):
        self.assertEqual(match("Chicken Broth 32 oz"), "broth")
        self.assertEqual(match("Beef Bouillon Cubes"), "broth")
        self.assertEqual(match("Sweet Potatoes 3 lb"), "sweetpotato")


class TestOffers(unittest.TestCase):
    def test_explicit_savings(self):
        o = extract("turkey", "S", "93% lean ground turkey", "Save $2.00 Limit 4")
        self.assertEqual(o.savings, 2.00)
        self.assertEqual(o.limit, 4)

    def test_per_pound_converts_to_package(self):
        # chicken package is 4.5-6.5 lb, midpoint 5.5
        o = extract("chicken", "S", "Chicken Breast", "$1.99/lb")
        self.assertAlmostEqual(o.sale_price, round(1.99 * 5.5, 2))

    def test_per_pound_can_be_skipped(self):
        self.assertIsNone(
            extract("chicken", "S", "Chicken Breast", "$1.99/lb", per_weight="skip"))

    def test_multibuy_becomes_unit_price(self):
        o = extract("tomatoes", "S", "Diced Tomatoes", "2 for $2.00")
        self.assertEqual(o.sale_price, 1.00)

    def test_coupon_shorthand_is_savings(self):
        o = extract("eggs", "S", "Large Eggs", "$1/1 coupon")
        self.assertEqual(o.savings, 1.00)

    def test_absurd_discount_is_capped(self):
        """A $50-off on a $4.39 item is a bulk offer, not a free package."""
        o = extract("turkey", "S", "Ground Turkey", "Save $50.00")
        self.assertLessEqual(o.savings, BY_ID["turkey"].price * 0.5)

    def test_price_above_normal_is_not_a_deal(self):
        self.assertIsNone(extract("tofu", "S", "Tofu", "$9.99"))

    def test_limit_parsing(self):
        self.assertEqual(parse_limit("Limit 4."), 4)
        self.assertIsNone(parse_limit("no limit here"))

    def test_dedupe_keeps_best(self):
        kept = dedupe([
            Offer("eggs", "S", "a", savings=1.0),
            Offer("eggs", "S", "b", savings=2.5),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].savings, 2.5)

    def test_twins_are_mirrored(self):
        ids = {o.item_id for o in mirror_twins([Offer("eggs", "S", "x", savings=1.0)])}
        self.assertEqual(ids, {"eggs", "snackeggs"})


class TestXML(unittest.TestCase):
    def test_matches_app_fixture_shape(self):
        xml = render("ShopRite", [
            Offer("turkey", "ShopRite", "93% lean ground turkey", savings=2.0, limit=4),
            Offer("eggs", "ShopRite", "Large eggs 18ct", sale_price=2.49, limit=6),
        ])
        self.assertIn('<shopriteSales store="ShopRite"', xml)
        self.assertIn('<offer itemId="turkey" savings="2.00" limit="4" '
                      'note="93% lean ground turkey"/>', xml)
        self.assertIn('<offer itemId="eggs" salePrice="2.49" limit="6" '
                      'note="Large eggs 18ct"/>', xml)
        self.assertEqual(validate(xml), [])

    def test_note_is_stripped_of_parser_hostile_characters(self):
        note = safe_note('Bread & "stuff" <b>25% off</b>')
        for ch in '&"<>':
            self.assertNotIn(ch, note)

    def test_validate_flags_unknown_item(self):
        xml = render("S", [Offer("nosuchitem", "S", "x", savings=1.0)])
        self.assertTrue(any("not in app catalog" in p for p in validate(xml)))

    def test_offer_without_price_is_dropped(self):
        xml = render("S", [Offer("eggs", "S", "x")])
        self.assertNotIn("<offer", xml)




class TestBranding(unittest.TestCase):
    """Greetings, headers and imagery must all be overridable, not hard-coded."""

    def test_every_default_is_overridable(self):
        from dealcrawler import branding
        brand = branding.load()
        for key in branding.DEFAULTS:
            self.assertIn(key, brand)

    def test_greeting_follows_time_of_day(self):
        from dealcrawler import branding
        brand = dict(branding.DEFAULTS)
        self.assertEqual(branding.greeting(brand, 9), brand["greeting_morning"])
        self.assertEqual(branding.greeting(brand, 14), brand["greeting_afternoon"])
        self.assertEqual(branding.greeting(brand, 20), brand["greeting_evening"])

    def test_fixed_greeting_wins_when_time_greeting_is_off(self):
        from dealcrawler import branding
        brand = dict(branding.DEFAULTS, use_time_greeting=False, greeting="Hi there")
        self.assertEqual(branding.greeting(brand, 9), "Hi there")

    def test_themes_are_bundled(self):
        from dealcrawler import branding
        names = {t["name"] for t in branding.themes()}
        self.assertTrue({"fresh-greens", "farm-market", "citrus"} <= names)


class TestPanel(unittest.TestCase):
    def test_page_renders_controls(self):
        import panel
        html_out = panel.page()
        for needle in ('id="refresh"', 'id="howto"', "<dialog", 'class="theme'):
            self.assertIn(needle, html_out)

    def test_page_is_ascii_safe(self):
        import panel
        self.assertTrue(all(ord(c) < 128 for c in panel.page()))


class TestScanDirections(unittest.TestCase):
    """The scan popup replaces the desktop app's old coupon button, so its
    per-store directions have to be real and complete."""

    def test_every_enabled_store_gets_directions(self):
        import panel
        keys = {s["key"] for s in panel.scan_help()}
        self.assertTrue({"shoprite", "stews", "costco"} <= keys)

    def test_each_store_has_a_runnable_command(self):
        import panel
        for st in panel.scan_help():
            self.assertIn(st["key"], st["command"])

    def test_each_store_names_where_its_scan_goes(self):
        import panel
        for st in panel.scan_help():
            self.assertTrue(st["path"].endswith(f"{st['key']}.txt"), st["path"])

    def test_links_are_labelled_by_purpose(self):
        import panel
        shoprite = next(s for s in panel.scan_help() if s["key"] == "shoprite")
        labels = [u["label"] for u in shoprite["urls"]]
        # Two ShopRite pages, so the labels must distinguish them.
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("Open the digital coupon list", labels)

    def test_panel_renders_the_scan_dialog(self):
        import panel
        html_out = panel.page()
        for needle in ('id="scan"', 'id="scandlg"', "Your stores"):
            self.assertIn(needle, html_out)


class TestRetireAppButtons(unittest.TestCase):
    """The binary patch is only safe while every replacement fits the original
    byte-for-byte -- Swift keeps the literal's length as a code immediate."""

    def test_replacements_never_exceed_the_original(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        for original, replacement in r.RETIREMENTS:
            self.assertLessEqual(len(replacement), len(original),
                                 msg=replacement[:40])

    def test_padding_restores_the_exact_length(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        for original, replacement in r.RETIREMENTS:
            padded = replacement + b" " * (len(original) - len(replacement))
            self.assertEqual(len(padded), len(original))

    def test_replacements_point_at_the_control_panel(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        joined = b" ".join(rep for _, rep in r.RETIREMENTS).lower()
        self.assertIn(b"control panel", joined)


class TestNoNetworkAccess(unittest.TestCase):
    """Deals come only from a browser scan. Nothing here may fetch a store."""

    SOURCE_FILES = ["crawl.py", "panel.py", "personalize.py"]

    def test_no_http_client_imports(self):
        root = os.path.dirname(os.path.abspath(__file__))
        files = [os.path.join(root, f) for f in self.SOURCE_FILES]
        for sub in ("dealcrawler", os.path.join("dealcrawler", "sources")):
            d = os.path.join(root, sub)
            files += [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".py")]
        banned = ("import urllib", "from urllib", "import requests",
                  "import http.client", "urlopen")
        for path in files:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for needle in banned:
                self.assertNotIn(needle, body,
                                 msg=f"{os.path.basename(path)} still fetches ({needle})")

    def test_stores_are_config_driven(self):
        from dealcrawler import stores
        loaded = stores.load({"stores": {"mymarket": {
            "name": "My Market",
            "urls": [{"label": "Open deals", "url": "https://example.test/deals"}],
        }}})
        keys = {s.key for s in loaded}
        self.assertIn("mymarket", keys)

    def test_store_id_is_templated_into_urls(self):
        from dealcrawler import stores
        shoprite = stores.get("shoprite", {"stores": {"shoprite": {"store_id": "141"}}})
        self.assertTrue(any("/rsid/141/" in u["url"] for u in shoprite.urls))

    def test_disabled_store_is_dropped(self):
        from dealcrawler import stores
        keys = {s.key for s in stores.load({"stores": {"costco": {"enabled": False}}})}
        self.assertNotIn("costco", keys)


if __name__ == "__main__":
    unittest.main(verbosity=2)

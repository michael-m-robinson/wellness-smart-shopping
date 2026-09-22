#!/usr/bin/env python3
"""Tests: python3 test_crawler.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Sales files default to ~/Documents/Deals. Tests must never write there, so
# point them at a throwaway folder before any project module reads the path.
import tempfile as _tempfile
os.environ.setdefault("WSS_DEALS_DIR", _tempfile.mkdtemp(prefix="wss-test-deals-"))

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

    def test_rejects_false_matches_seen_in_real_scans(self):
        """Each of these reached a sales file on 2026-09-21."""
        for title in ("Dove Serum+ Oil Body Wash, Serum+ Body Wash, Plant Milk Body Wash",
                      "Banana Republic Women's Ponte Pant",
                      "Weider Red Yeast Rice Plus, 240 ct",
                      "Campbell's Simply Chicken Noodle Soup, 8/18.6 oz",
                      "Brazi Bites Brazilian Cheese Bread",
                      "MUSCLE MILK® 11 oz 4pk"):
            self.assertIsNone(match(title), title)
        for title, want in (("Nature's Own Bread", "bread"), ("Bananas", "fruit"),
                            ("Rana Family Size Pasta Item 18oz or larger", "pasta"),
                            ("Low Fat Milk 1 gal", "milk")):
            self.assertEqual(match(title), want, title)

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

    def test_example_template_matches_defaults(self):
        """A stale template used to shadow new defaults; keep them in lockstep."""
        import json as _json
        from dealcrawler import branding
        with open(branding.EXAMPLE_FILE, encoding="utf-8") as fh:
            example = _json.load(fh)
        self.assertEqual(set(branding.DEFAULTS),
                         {k for k in example if not k.startswith("_")})

    def test_example_template_is_not_an_override_layer(self):
        from dealcrawler import branding
        self.assertNotIn(branding.EXAMPLE_FILE, str(branding.load))
        # A key only in the template must not reach load().
        self.assertEqual(set(branding.load()) - set(branding.DEFAULTS), set())

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

    def test_page_has_no_stray_control_characters(self):
        """A "\\b" in the page's f-string once became a backspace, silently
        breaking a regex in the script."""
        import panel
        stray = [c for c in panel.page() if ord(c) < 32 and c not in "\n\r\t"]
        self.assertEqual(stray, [])

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
        for needle in ('id="scanwith"', 'id="scandlg"', "Your stores"):
            self.assertIn(needle, html_out)


class TestNoNetworkAccess(unittest.TestCase):
    """Deals come only from a browser scan. Nothing here may fetch a store."""

    SOURCE_FILES = ["crawl.py", "panel.py", "personalize.py"]

    def test_no_http_client_imports(self):
        root = os.path.dirname(os.path.abspath(__file__))
        files = [os.path.join(root, f) for f in self.SOURCE_FILES]
        for sub in ("dealcrawler", os.path.join("dealcrawler", "sources")):
            d = os.path.join(root, sub)
            files += [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".py")]
        # Ban what can open a connection, not the whole urllib package:
        # urllib.parse only splits strings and is used to read a query string.
        banned = ("urllib.request", "from urllib import request", "urlopen",
                  "import requests", "http.client", "socket.create_connection")
        for path in files:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for needle in banned:
                self.assertNotIn(needle, body,
                                 msg=f"{os.path.basename(path)} still fetches ({needle})")
            # A bare `import urllib` would put request within reach.
            self.assertNotIn("\nimport urllib\n", body, os.path.basename(path))

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


class TestProfileTargets(unittest.TestCase):
    """Ported from the desktop app's personalizedNutritionTarget, so the panel
    and the app must not drift apart on a user's numbers."""

    def setUp(self):
        from dealcrawler import profile
        self.profile = profile

    def test_incomplete_profile_uses_the_apps_fallback(self):
        t = self.profile.target(self.profile.Profile())
        self.assertEqual((t["protein"], t["carbs"], t["fat"]), (126, 261, 58))
        self.assertFalse(t["estimated"])

    def test_known_profile_matches_the_apps_arithmetic(self):
        p = self.profile.Profile(height_feet=5, height_inches=10,
                                 weight_pounds=185, goal="maintenance")
        t = self.profile.target(p)
        # maintenance = round((185*10 + 70*4)/10)*10
        self.assertEqual(t["maintenance"], 2130)
        self.assertEqual(t["protein"], 130)   # 185 * 0.70, planning weight capped
        self.assertEqual(t["fat"], 59)        # 185 * 0.32
        self.assertEqual(t["calories"],
                         t["protein"] * 4 + t["carbs"] * 4 + t["fat"] * 9)

    def test_goal_changes_the_multiplier(self):
        base = dict(height_feet=5, height_inches=10, weight_pounds=185)
        cut = self.profile.target(self.profile.Profile(goal="cutting", **base))
        bulk = self.profile.target(self.profile.Profile(goal="buildMuscle", **base))
        self.assertLess(cut["calories"], bulk["calories"])
        self.assertEqual(cut["multiplier"], 0.84)
        self.assertEqual(bulk["multiplier"], 1.10)

    def test_planning_weight_is_capped_for_larger_bodies(self):
        """Protein/fat come off a capped planning weight, not raw body weight."""
        p = self.profile.Profile(height_feet=5, height_inches=6, weight_pounds=400)
        t = self.profile.target(p)
        self.assertLess(t["planning_weight"], 400)

    def test_floors_are_respected(self):
        p = self.profile.Profile(height_feet=4, height_inches=10, weight_pounds=80)
        t = self.profile.target(p)
        self.assertGreaterEqual(t["protein"], 60)
        self.assertGreaterEqual(t["fat"], 40)
        self.assertGreaterEqual(t["carbs"], 100)

    def test_out_of_range_falls_back(self):
        p = self.profile.Profile(height_feet=3, height_inches=0, weight_pounds=50)
        self.assertFalse(p.complete)
        self.assertFalse(self.profile.target(p)["estimated"])

    def test_portion_multiplier_is_bounded(self):
        for w in (80, 185, 700):
            p = self.profile.Profile(height_feet=5, height_inches=10, weight_pounds=w)
            self.assertGreaterEqual(self.profile.portion_multiplier(p), 0.60)
            self.assertLessEqual(self.profile.portion_multiplier(p), 1.60)

    def test_unknown_goal_falls_back_to_maintenance(self):
        p = self.profile.Profile(goal="nonsense")
        self.assertEqual(p.goal, "maintenance")

    def test_panel_renders_the_form(self):
        import panel
        html_out = panel.page()
        for needle in ('id="profiledlg"', 'id="p-ft"', 'id="p-wt"',
                       'id="saveprofile"', 'id="t-cal"'):
            self.assertIn(needle, html_out)


class TestAgeSexActivity(unittest.TestCase):
    """Calories should respond to age, sex and activity, not just body size."""

    def setUp(self):
        from dealcrawler import profile
        self.profile = profile
        self.base = dict(height_feet=5, height_inches=10, weight_pounds=185)

    def _t(self, **kw):
        return self.profile.target(self.profile.Profile(**dict(self.base, **kw)))

    def test_age_switches_to_mifflin(self):
        self.assertEqual(self._t()["basis"], "size-only")
        self.assertEqual(self._t(age=38)["basis"], "mifflin")

    def test_older_age_lowers_calories(self):
        young = self._t(age=25, sex="male", activity="moderate")
        older = self._t(age=65, sex="male", activity="moderate")
        self.assertLess(older["maintenance"], young["maintenance"])

    def test_sex_changes_calories(self):
        male = self._t(age=38, sex="male", activity="moderate")
        female = self._t(age=38, sex="female", activity="moderate")
        self.assertGreater(male["maintenance"], female["maintenance"])

    def test_unspecified_sex_sits_between(self):
        vals = {s: self._t(age=38, sex=s, activity="moderate")["maintenance"]
                for s in ("male", "female", "unspecified")}
        self.assertLess(vals["female"], vals["unspecified"])
        self.assertLess(vals["unspecified"], vals["male"])

    def test_activity_raises_calories(self):
        last = 0
        for level in ("sedentary", "light", "moderate", "active", "athlete"):
            cals = self._t(age=38, sex="male", activity=level)["maintenance"]
            self.assertGreater(cals, last, level)
            last = cals

    def test_activity_also_raises_protein(self):
        """Extra energy must not land almost entirely in carbohydrate."""
        low = self._t(age=38, sex="male", activity="sedentary")
        high = self._t(age=38, sex="male", activity="athlete")
        self.assertGreater(high["protein"], low["protein"])

    def test_fat_holds_a_quarter_of_calories(self):
        for level in ("sedentary", "moderate", "athlete"):
            t = self._t(age=38, sex="male", activity=level)
            share = t["fat"] * 9 / t["calories"]
            self.assertGreater(share, 0.20, level)

    def test_unknown_sex_or_activity_falls_back(self):
        p = self.profile.Profile(sex="nope", activity="nope")
        self.assertEqual(p.sex, self.profile.DEFAULT_SEX)
        self.assertEqual(p.activity, self.profile.DEFAULT_ACTIVITY)

    def test_age_out_of_range_is_not_personalised(self):
        self.assertEqual(self._t(age=5)["basis"], "size-only")

    def test_panel_form_offers_the_new_fields(self):
        import panel
        html_out = panel.page()
        for needle in ('id="p-age"', 'id="p-sex"', 'id="p-activity"'):
            self.assertIn(needle, html_out)


class TestThemeLibrary(unittest.TestCase):
    def test_photo_themes_are_present(self):
        from dealcrawler import branding
        names = {t["name"] for t in branding.themes()}
        self.assertTrue({"50s-1", "fit-1", "nature-1", "family"} <= names)

    def test_every_theme_has_a_thumbnail(self):
        from dealcrawler import branding
        for t in branding.themes():
            self.assertTrue(t["thumb"].startswith("thumbs/"), t["name"])
            full = os.path.join(branding.THEME_DIR, t["thumb"])
            self.assertTrue(os.path.isfile(full), t["thumb"])

    def test_thumbs_directory_is_not_listed_as_a_theme(self):
        from dealcrawler import branding
        self.assertNotIn("thumbs", {t["name"] for t in branding.themes()})

    def test_banner_uses_the_real_file_extension(self):
        import panel
        import re as _re
        src = _re.search(r'id="banner" src="/themes/([^"]+)"', panel.page()).group(1)
        self.assertTrue(src.endswith((".jpg", ".png", ".jpeg")), src)


class TestScanWizard(unittest.TestCase):
    """Scan with Claude: pick a store, wait for the scan, then offer import."""

    def setUp(self):
        import panel
        self.panel = panel
        self.html = panel.page()

    def test_every_step_is_present(self):
        for needle in ('id="scanwiz"', 'id="w-pick"', 'id="w-wait"',
                       'id="w-done"', 'id="w-after"'):
            self.assertIn(needle, self.html)

    def test_a_picker_exists_for_each_store(self):
        keys = {s["key"] for s in self.panel.scan_help()}
        for key in keys:
            self.assertIn(f'data-store="{key}"', self.html)

    def test_import_and_later_are_both_offered(self):
        self.assertIn('id="w-import"', self.html)
        self.assertIn('id="w-later"', self.html)

    def test_later_path_is_shown(self):
        """Declining import must still say where the file is."""
        self.assertIn('id="w-after-path"', self.html)
        from dealcrawler import branding
        self.assertIn("Import Sales XML", branding.load()["scan_later_body"])

    def test_no_html_entities_leak_into_javascript(self):
        """Strings assigned to textContent must be JS-encoded, not HTML-escaped,
        or an apostrophe renders as &#x27; in the UI."""
        script = self.html.split("<script>")[-1]
        # The esc() helper legitimately contains an entity map; ignore that line.
        body = "\n".join(line for line in script.splitlines()
                          if "&lt;" not in line and "&gt;" not in line)
        self.assertNotIn("&#x27;", body)
        self.assertNotIn("&#39;", body)

    def test_no_dead_button_handlers(self):
        """Every $("#id") the script wires up must exist in the markup."""
        import re as _re
        wired = set(_re.findall(r'\$\("#([a-zA-Z0-9_-]+)"\)\.onclick', self.html))
        for ident in wired:
            self.assertIn(f'id="{ident}"', self.html, f'#{ident} has no element')

    def test_build_for_writes_xml_from_a_scan(self):
        """Writes to a temp dir: a test must not litter the project tree, or
        `installer.py --check` stops being side-effect free."""
        import os as _os
        import shutil as _shutil
        import tempfile as _tempfile
        from dealcrawler import stores
        root = _os.path.dirname(_os.path.abspath(__file__))
        store = stores.get("shoprite", self.panel.load_config())
        sample = _os.path.join(root, "examples", "sample-scan.txt")
        created = not _os.path.exists(store.harvest_path)
        _shutil.copyfile(sample, store.harvest_path)
        original_out = self.panel.OUT_DIR
        with _tempfile.TemporaryDirectory() as tmp:
            self.panel.OUT_DIR = tmp
            try:
                result = self.panel.build_for(store)
                self.assertTrue(result["found"])
                self.assertGreater(result["count"], 0)
                self.assertTrue(result["xml"].endswith(".xml"))
                self.assertTrue(result["xml"].startswith(tmp))
            finally:
                self.panel.OUT_DIR = original_out
                if created:
                    _os.remove(store.harvest_path)


class TestExtensionNotice(unittest.TestCase):
    """Scanning depends on the Claude for Chrome extension, so the panel has to
    say so and link to it."""

    def setUp(self):
        import panel
        self.html = panel.page()

    def test_notice_and_install_link_are_present(self):
        from dealcrawler import branding
        brand = branding.load()
        self.assertIn('id="extbar"', self.html)
        self.assertIn(brand["extension_url"], self.html)

    def test_install_url_uses_the_real_extension_id(self):
        from dealcrawler import branding
        brand = branding.load()
        self.assertIn(brand["extension_id"], brand["extension_url"])

    def test_notice_is_dismissible(self):
        self.assertIn('id="ext-have"', self.html)
        self.assertIn("wss.hasExtension", self.html)

    def test_wrong_browser_gets_its_own_message(self):
        from dealcrawler import branding
        self.assertIn("CHROMIUM", self.html)
        self.assertIn(branding.load()["extension_wrong_browser"][:30], self.html)

    def test_localstorage_access_is_guarded(self):
        """Private windows and blocked site data make localStorage throw."""
        self.assertIn("try {", self.html.split("function stored")[1][:200])


class TestListMessage(unittest.TestCase):
    def test_message_and_presets_exist(self):
        from dealcrawler import branding
        brand = branding.load()
        self.assertTrue(brand["list_message"])
        self.assertGreaterEqual(len(brand["list_message_presets"]), 3)

    def test_message_renders_and_is_pickable(self):
        import panel
        html_out = panel.page()
        self.assertIn('id="listmsg"', html_out)
        self.assertIn('id="f-msgpick"', html_out)


class TestDesktopAppSource(unittest.TestCase):
    """The Swift app no longer scrapes stores. These guard the removal, since
    the coupon engine is what made the old button misleading."""

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.abspath(__file__))
        cls.path = os.path.join(root, "app", "main.swift")
        cls.src = ""
        if os.path.isfile(cls.path):
            with open(cls.path, encoding="utf-8") as fh:
                cls.src = fh.read()

    def setUp(self):
        if not self.src:
            self.skipTest("app/main.swift not present")

    def test_no_scraping_machinery_remains(self):
        for gone in ("localCouponSources", "WebScanWindowController",
                     "refreshOfficialOffers", "findOfficialCoupons",
                     "checkShopRiteWebSales", "openConnectSession",
                     "costcoOfficialCoupons", "genericOfficialCoupons",
                     "webSalePrices", "importCopiedCoupons"):
            self.assertNotIn(gone, self.src, gone)

    def test_no_store_urls_are_fetched(self):
        for url in ("livingrichwithcoupons", "warehouse-savings",
                    "stews-flyer", "bjs.com/deals", "rsid/"):
            self.assertNotIn(url, self.src, url)

    def test_no_personal_data(self):
        """Matched structurally so this file need not carry anyone's address.

        The original build hard-coded a town and store branch per retailer,
        e.g. "Somewhere - 106 Example Rd" and "Somewhere - store 141".
        """
        import re as _re
        patterns = [
            _re.compile(r'"[A-Z][A-Za-z.\' -]{2,30} - \d{1,6} [A-Za-z.\' -]{2,28}'
                        r'(?:Rd|Road|St|Street|Ave|Avenue|Blvd|Hwy|Pike|Way|Ln|Dr)"'),
            _re.compile(r'"[A-Z][A-Za-z.\' -]{2,30} - store \d{1,6}"'),
            _re.compile(r'rsid/\d+'),
        ]
        for pattern in patterns:
            found = pattern.search(self.src)
            self.assertIsNone(found, found.group(0) if found else "")

    def test_closing_image_is_generically_named(self):
        """The bundled picture used to carry a person's name."""
        self.assertIn('forResource: name', self.src)
        self.assertIn('["theme"]', self.src)

    def test_button_reads_scan_deals(self):
        # Scanning is the Scanner extension or Claude, so the button names neither.
        self.assertIn('NSButton(title: "Scan Deals..."', self.src)
        self.assertNotIn("Find & Apply Coupons", self.src)
        self.assertNotIn('"Coupons (', self.src)

    def test_no_pdf_until_every_checked_store_is_scanned(self):
        """Deals come first: each checked store needs this week's scan."""
        create = self.src[self.src.index("@objc func createPDF"):]
        create = create[:create.index("private func createPDFNow")]
        self.assertLess(create.index("let missing = unscannedStores()"),
                        create.index("createPDFNow(sender)"))
        self.assertIn("nudgeToScan(missing)", create)
        self.assertIn("still \\(stores.count == 1 ? \"needs\" : \"need\") this week's scan", self.src)
        nudge = self.src[self.src.index("private func nudgeToScan"):]
        nudge = nudge[:nudge.index("private func pulse")]
        self.assertIn("pulse(couponsButton)", nudge)
        self.assertIn("NSPopover()", nudge)
        self.assertIn("of: couponsButton", nudge)

    def test_bjs_is_coming_soon_and_its_items_move(self):
        self.assertIn('let comingSoonStores: Set<String> = ["BJ\'s"]', self.src)
        build = self.src[self.src.index("private func buildWindow"):]
        self.assertIn("bjs.isEnabled = false", build)
        self.assertIn("coming soon", build[build.index("bjs.toolTip"):][:200])
        # Its items are bought elsewhere, never dropped.
        for item in ("eggs", "milk", "chicken", "salmon", "oats"):
            self.assertIn(f'"{item}": ', self.src[self.src.index("let relocatedStore"):][:600])

    def test_deals_pick_within_each_category_goal_first(self):
        self.assertNotIn("presentSaleSwapPreview", self.src)          # applied automatically
        plan = self.src[self.src.index("func recipesForPlan"):][:1400]
        self.assertIn("preferIDs", plan)
        self.assertIn("($0.1, $0.2) > ($1.1, $1.2)", plan)           # goal score first
        self.assertIn("On sale this week, so we picked", self.src)
        self.assertIn("shoppableCatalog(catalog, dealStores: couponSources", self.src)
        self.assertIn("SELF_TEST_SALE_PICKS_OK", self.src)

    def test_app_says_what_a_scan_is_worth_when_no_deals_are_loaded(self):
        launch = self.src[self.src.index("func applicationDidFinishLaunching"):]
        launch = launch[:launch.index("static let savingsMessage")]
        self.assertIn("if verifiedSaleItemIDs().isEmpty", launch)
        self.assertIn("pulse(self.couponsButton)", launch)
        self.assertIn("You could be saving money this week", self.src)

    def test_every_import_says_whether_it_worked(self):
        imp = self.src[self.src.index("@objc func importSalesXML"):]
        imp = imp[:imp.index("/// How an import ended")]
        for outcome in (".couldNotRead(", ".notASalesFile(", "confirmImport(.nothingMatched",
                        "confirmImport(.noneChosen", "confirmImport(.couldNotSave",
                        "confirmImport(.applied"):
            self.assertIn(outcome, imp, outcome)
        self.assertIn("panel.allowsMultipleSelection = true", imp)   # several stores at once
        self.assertIn("recordScan(of: store)", imp)                  # per-store record
        # "Applied" is only claimed after reading the deals back.
        self.assertLess(imp.index("dealsWereSaved"), imp.index("confirmImport(.applied"))
        self.assertIn('"Your deals weren\'t applied"', self.src)
        self.assertIn("Documents/Deals", self.src)          # the picker opens there

    def test_importing_a_sales_file_counts_as_a_scan(self):
        imp = self.src[self.src.index("@objc func importSalesXML"):]
        imp = imp[:imp.index("@objc func clearCoupons")]
        self.assertIn("forKey: dealsScannedAtKey", imp)

    def test_in_app_store_scraping_is_gone(self):
        """Store prices come from scans now; the app no longer fetches store pages."""
        for gone in ("checkInformation", "closestPrice", "usdaKeyField", "Check USDA"):
            self.assertNotIn(gone, self.src, gone)

    def test_app_can_set_up_the_scanner(self):
        self.assertIn('"Set Up Scanner..."', self.src)
        self.assertIn('"Scanner Extension"', self.src)
        self.assertIn("Contents/Resources/panel/extension", self.src)
        build = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "app", "build.sh"), encoding="utf-8").read()
        self.assertIn(" extension ", build)       # the build bundles it

    def test_xml_import_survives(self):
        """The import is the whole point of the pipeline; it must not be lost."""
        for kept in ("func parseSalesXML", "func importSalesXML",
                     "applyDetectedCoupons", "Import Sales XML"):
            self.assertIn(kept, self.src, kept)

    def test_control_panel_handoff_exists(self):
        self.assertIn("func openControlPanel", self.src)
        self.assertIn("127.0.0.1:8765", self.src)

    def test_app_starts_the_panel_rather_than_giving_directions(self):
        self.assertIn("func locateControlPanel", self.src)
        self.assertIn('arguments = ["python3", script.path, "--no-open"]', self.src)

    def test_app_stops_the_panel_it_started(self):
        self.assertIn("func stopControlPanel", self.src)
        self.assertIn("func applicationWillTerminate", self.src)
        self.assertIn("process.terminate()", self.src)

    def test_readiness_probe_uses_get_not_head(self):
        """http.server answers HEAD with 501, which made a live panel look dead."""
        probe = self.src[self.src.index("var controlPanelIsRunning"):]
        probe = probe[:probe.index("func locateControlPanel")]
        self.assertIn('httpMethod = "GET"', probe)
        self.assertNotIn('httpMethod = "HEAD"', probe)

    def test_panel_window_survives_losing_focus(self):
        """NSPanel hides on deactivate by default, so it vanished when the
        browser opened."""
        self.assertIn("panel.hidesOnDeactivate = false", self.src)

    def test_deals_panel_has_no_item_list(self):
        self.assertNotIn("couponFields", self.src)
        self.assertIn('NSButton(title: "Start Control Panel"', self.src)

    def test_closing_the_panel_does_not_wipe_imported_deals(self):
        close = self.src[self.src.index("@objc func saveCoupons"):]
        close = close[:close.index("\n    }")]
        self.assertNotIn("couponValues = saved", close)
        self.assertNotIn("couponFields", close)

    def test_build_script_is_executable(self):
        build = os.path.join(os.path.dirname(self.path), "build.sh")
        self.assertTrue(os.path.isfile(build))
        self.assertTrue(os.access(build, os.X_OK))


class TestPanelHeadProbe(unittest.TestCase):
    def test_head_is_answered(self):
        """The desktop app probes the panel before opening a browser on it."""
        import panel
        self.assertIn("def do_HEAD", open(panel.__file__, encoding="utf-8").read())


class TestInstaller(unittest.TestCase):
    """The setup wizard must be honest about dependencies and safe to re-run."""

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.abspath(__file__))
        cls.root = root
        with open(os.path.join(root, "installer.py"), encoding="utf-8") as fh:
            cls.src = fh.read()

    def test_check_mode_makes_no_changes(self):
        """--check must never write; it is the 'look first' mode."""
        import subprocess as sp

        def snapshot():
            seen = set()
            for dirpath, dirnames, filenames in os.walk(self.root):
                dirnames[:] = [d for d in dirnames
                               if d not in {".git", "__pycache__", "build"}]
                for name in dirnames + filenames:
                    seen.add(os.path.relpath(os.path.join(dirpath, name), self.root))
            return seen

        before = snapshot()
        env = dict(os.environ, WSS_SKIP_TESTS="1")
        sp.run([sys.executable, "installer.py", "--check"],
               cwd=self.root, capture_output=True, timeout=120, env=env)
        self.assertEqual(snapshot() - before, set(), "--check created something")

    def test_requirements_txt_pins_nothing(self):
        path = os.path.join(self.root, "requirements", "requirements.txt")
        with open(path, encoding="utf-8") as fh:
            body = [ln.strip() for ln in fh
                    if ln.strip() and not ln.strip().startswith("#")]
        self.assertEqual(body, [], "there are no third-party packages to pin")

    def test_no_third_party_imports_anywhere(self):
        """The wizard's central claim: standard library only."""
        import importlib.util
        import re as _re
        found = set()
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames
                           if d not in {"build", "__pycache__", ".git"}]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, name), encoding="utf-8",
                          errors="ignore") as fh:
                    for line in fh:
                        m = _re.match(r"\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", line)
                        if m:
                            found.add(m.group(1).split(".")[0])
        for module in found:
            spec = importlib.util.find_spec(module) if module not in sys.builtin_module_names else None
            if spec and spec.origin and "site-packages" in str(spec.origin):
                self.fail(f"third-party dependency crept in: {module}")

    def test_branding_is_not_seeded(self):
        """Copying every default into branding.json would shadow future ones."""
        self.assertIn("branding.json is deliberately NOT created", self.src)
        self.assertNotIn('("branding.example.json", "branding.json")', self.src)

    def test_nothing_installs_without_asking(self):
        for action in ("xcode-select", "shutil.copytree", "build.sh"):
            self.assertIn(action, self.src)
        self.assertIn("def ask(", self.src)

    def test_never_invokes_sudo(self):
        """Checked as a call, not a word -- the docstring mentions it."""
        import re as _re
        for call in _re.finditer(r"(?:subprocess\.(?:run|Popen)|run)\(\s*\[([^\]]*)\]",
                                 self.src):
            self.assertNotIn("sudo", call.group(1))

    def test_any_chromium_browser_counts(self):
        """The extension runs in Edge, Brave and Arc too, not just Chrome."""
        for browser in ("Microsoft Edge", "Brave", "Arc", "Chromium"):
            self.assertIn(browser, self.src)

    def test_only_one_installed_copy_is_allowed(self):
        """Two installed copies is a real trap: you open the old one and
        nothing you changed appears."""
        self.assertIn("def find_installed_copies", self.src)
        self.assertIn("def step_one_copy", self.src)
        self.assertIn("CANONICAL_DIR", self.src)

    def test_copies_are_matched_by_identifier_not_name(self):
        """build.sh can rename the bundle, so the name proves nothing."""
        self.assertIn("OUR_IDENTIFIER_PREFIX", self.src)
        self.assertIn("def bundle_identifier", self.src)

    def test_build_output_counts_as_a_copy(self):
        """It was excluded once as 'only what we install from', and showed up
        as a second entry in Launchpad. macOS indexes it like any other app."""
        self.assertIn('roots.append(os.path.join(HERE, "app", "build"))', self.src)
        self.assertNotIn('os.path.join("app", "build") in path', self.src)

    def test_removals_deregister_from_launchservices(self):
        """Deleting the files alone leaves a ghost in Launchpad and Spotlight."""
        self.assertIn("def unregister", self.src)
        self.assertIn("lsregister", self.src)
        removals = self.src.count("unregister(")
        self.assertGreaterEqual(removals, 4, "every removal path should deregister")

    def test_older_builds_are_not_removed_by_default(self):
        """Someone else's original app is theirs to keep."""
        block = self.src[self.src.index("LEGACY_IDENTIFIERS"):]
        block = block[:block.index("# ------------------------------- steps")] \
            if "# ------------------------------- steps" in block else block
        self.assertIn('ask("Remove those too?", default=False)', self.src)

    def test_duplicate_removal_is_confirmed(self):
        self.assertIn("Remove {len(extras)} duplicate cop", self.src)

    def test_installed_app_is_verified_even_if_build_skipped(self):
        self.assertIn("if not app or not os.path.isdir(app):", self.src)

    def test_double_click_entry_point_exists(self):
        path = os.path.join(self.root, "install.command")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.access(path, os.X_OK))


class TestBundledLayout(unittest.TestCase):
    """Installed, the app is read-only and signed, so nothing may be written
    inside it."""

    def test_data_dir_is_separate_when_bundled(self):
        from dealcrawler import paths
        self.assertTrue(paths.enclosing_app_bundle("/x/Some App.app/Contents/Resources/panel"))
        self.assertIsNone(paths.enclosing_app_bundle("/Users/me/project/panel"))

    def test_data_dir_honours_an_override(self):
        import importlib, os as _os
        from dealcrawler import paths
        original = _os.environ.get("WSS_DATA_DIR")
        _os.environ["WSS_DATA_DIR"] = "/tmp/wss-test-data"
        try:
            reloaded = importlib.reload(paths)
            self.assertEqual(reloaded.DATA_DIR, "/tmp/wss-test-data")
        finally:
            if original is None:
                _os.environ.pop("WSS_DATA_DIR", None)
            else:
                _os.environ["WSS_DATA_DIR"] = original
            importlib.reload(paths)

    def test_writable_files_come_from_the_data_dir(self):
        from dealcrawler import branding, profile, stores, paths
        for path in (branding.USER_FILE, profile.PROFILE_FILE, stores.HARVEST_DIR):
            self.assertTrue(path.startswith(paths.DATA_DIR), path)

    def test_shipped_files_come_from_the_source_dir(self):
        from dealcrawler import branding, paths
        for path in (branding.THEME_DIR, branding.EXAMPLE_FILE):
            self.assertTrue(path.startswith(paths.SOURCE_DIR), path)

    def test_build_ships_the_panel_and_excludes_personal_files(self):
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "app", "build.sh"), encoding="utf-8") as fh:
            build = fh.read()
        self.assertIn("Contents/Resources/panel", build)
        for excluded in ("config.json", "branding.json", "profile.json",
                         "harvest", "out", "__pycache__"):
            self.assertIn(excluded, build)

    def test_dmg_script_makes_a_drag_target(self):
        root = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(root, "app", "make_dmg.sh")
        self.assertTrue(os.access(path, os.X_OK))
        with open(path, encoding="utf-8") as fh:
            dmg = fh.read()
        self.assertIn("ln -s /Applications", dmg)
        self.assertIn("hdiutil create", dmg)

    def test_dmg_window_is_arranged_not_left_to_finder(self):
        """The point of the image is the window that opens: two big icons and
        an arrow, not a default list view."""
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "app", "make_dmg.sh"), encoding="utf-8") as fh:
            dmg = fh.read()
        for setting in ("set icon size of opts", "background picture of opts",
                        "set position of item", "icon view",
                        "UDRW", "UDZO", ".VolumeIcon.icns"):
            self.assertIn(setting, dmg, setting)

    def test_volume_icon_sets_creator_before_flag(self):
        """Order matters: the flag alone fails with -61."""
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "app", "make_dmg.sh"), encoding="utf-8") as fh:
            dmg = fh.read()
        creator = dmg.index("SetFile -c icnC")
        flag = dmg.index('SetFile -a C "$MOUNTED"')
        self.assertLess(creator, flag)

    def test_window_arrow_uses_the_supplied_artwork(self):
        root = os.path.dirname(os.path.abspath(__file__))
        self.assertTrue(os.path.isfile(os.path.join(root, "app", "art", "arrow-source.png")))
        with open(os.path.join(root, "app", "make_dmg.sh"), encoding="utf-8") as fh:
            self.assertIn("--arrow", fh.read())

    def test_icon_is_built_from_the_artwork(self):
        root = os.path.dirname(os.path.abspath(__file__))
        self.assertTrue(os.path.isfile(os.path.join(root, "app", "art", "icon-source.png")))
        with open(os.path.join(root, "app", "build.sh"), encoding="utf-8") as fh:
            self.assertIn("make_icon.py", fh.read())

    def test_app_carries_everything_it_needs(self):
        """No folder beside it, nothing to install separately."""
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "app", "build.sh"), encoding="utf-8") as fh:
            build = fh.read()
        for shipped in ("panel.py", "crawl.py", "dealcrawler", "themes", "browser"):
            self.assertIn(shipped, build, shipped)


class TestScanDelivery(unittest.TestCase):
    """A browser extension cannot write to disk. The scan runs inside the
    store's page and posts itself back, so the panel has to accept that."""

    def setUp(self):
        import panel
        self.panel = panel
        self.html = panel.page()
        root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(root, "browser", "harvest.js"), encoding="utf-8") as fh:
            self.js = fh.read()
        from dealcrawler import branding
        self.brand = branding.load()

    def test_nothing_asks_the_extension_to_write_a_file(self):
        self.assertNotIn("save the result to", self.brand["scan_prompt"])
        for step in self.brand["scan_steps"]:
            self.assertNotIn("harvest/<store>.txt", step)

    def test_harvest_posts_its_result(self):
        self.assertIn("/api/scan/submit", self.js)
        self.assertIn("method: \"POST\"", self.js)

    def test_harvest_falls_back_to_printing(self):
        """If the panel is not running, the offers must not be lost."""
        self.assertIn("Could not reach the control panel", self.js)

    def test_panel_answers_the_cross_origin_preflight(self):
        """Chrome preflights a public page reaching a local address."""
        self.assertTrue(hasattr(self.panel.Handler, "do_OPTIONS"),
                        "the handler must answer a preflight")
        source = open(self.panel.__file__, encoding="utf-8").read()
        for header in ("Access-Control-Allow-Origin",
                       "Access-Control-Allow-Private-Network",
                       "Access-Control-Allow-Methods"):
            self.assertIn(header, source, header)

    def test_submit_saves_a_scan(self):
        import json as _json
        import tempfile as _tempfile
        from dealcrawler import stores
        store = stores.get("shoprite", self.panel.load_config())
        created = not os.path.exists(store.harvest_path)
        try:
            os.makedirs(os.path.dirname(store.harvest_path), exist_ok=True)
            with open(store.harvest_path, "w", encoding="utf-8") as fh:
                fh.write("93% Lean Ground Turkey | $3.49 |\n")
            result = self.panel.build_for(store)
            self.assertTrue(result["found"])
        finally:
            if created and os.path.exists(store.harvest_path):
                os.remove(store.harvest_path)

    def test_prompt_works_from_either_route(self):
        """Terminal or desktop app, the instruction must read the same: it can
        name no folder, because the two installs keep files in different
        places. That holds for every store's own prompt and the generic one."""
        from dealcrawler import stores
        templates = [stores.GENERIC_PROMPT] + [
            st.prompt for st in stores.load(self.panel.load_config()) if st.prompt]
        for prompt in templates:
            for local in ("harvest/", ".txt", "browser/", "panel.py", "/Users/"):
                self.assertNotIn(local, prompt, local)
            self.assertIn("{submit}", prompt)

    def test_prompt_carries_the_panels_real_address(self):
        from dealcrawler import stores
        for st in stores.load(self.panel.load_config()):
            submit = f"http://127.0.0.1:9999/api/scan/submit?store={st.key}"
            filled = st.instruction(submit)
            self.assertIn(submit, filled, st.key)
            self.assertNotIn("{submit}", filled, st.key)

    def test_store_prompt_used_unless_overridden(self):
        """ShopRite's own prompt reaches the user; a branding override replaces
        it and may contain braces without crashing the scan."""
        from dealcrawler import stores
        shoprite = stores.get("shoprite", self.panel.load_config())
        self.assertIn("scrollable-container", shoprite.instruction("S"))
        odd = 'Read {"x": 1} then .a{b} and POST to {submit}'
        self.assertEqual(shoprite.instruction("S", override=odd),
                         'Read {"x": 1} then .a{b} and POST to S')

    def test_script_is_served_for_those_who_prefer_it(self):
        source = open(self.panel.__file__, encoding="utf-8").read()
        self.assertIn('"/harvest.js"', source)

    def test_shoprite_offers_only_the_coupon_list(self):
        from dealcrawler import stores
        store = stores.get("shoprite", self.panel.load_config())
        labels = [u["label"] for u in store.urls]
        self.assertEqual(labels, ["Open the digital coupon list"])

    def test_no_wording_still_points_at_a_weekly_ad(self):
        for key in ("scan_steps", "scan_wait_body", "scan_prompt"):
            value = self.brand[key]
            text = " ".join(value) if isinstance(value, list) else str(value)
            self.assertNotIn("weekly ad", text.lower(), key)

    def test_editing_one_number_leaves_the_others_calculated(self):
        """Sending all four boxes pinned the lot: editing protein froze
        calories at whatever figure happened to be on screen."""
        source = open(self.panel.__file__, encoding="utf-8").read()
        self.assertIn("saveTiles(field, el.value", source)
        self.assertIn("Only the box that changed is sent", source)

    def test_units_are_shown_beside_the_editable_numbers(self):
        """They are number inputs, so the g cannot live in the value."""
        self.assertIn('<i>g</i>', self.html)
        self.assertIn("text-transform:none", self.html)

    def test_paste_box_exists_as_a_fallback(self):
        self.assertIn('id="w-paste"', self.html)
        self.assertIn('id="w-paste-go"', self.html)



class TestScannerExtension(unittest.TestCase):
    """The Chrome extension in extension/ that scans without Claude."""

    HERE = os.path.dirname(os.path.abspath(__file__))

    def manifest(self):
        import json as _json
        with open(os.path.join(self.HERE, "extension", "manifest.json")) as fh:
            return _json.load(fh)

    def test_panel_marks_itself_for_the_bridge(self):
        import panel
        self.assertIn('<meta name="wss-panel"', panel.page())

    def test_each_builtin_store_has_its_own_site_and_prompt(self):
        from dealcrawler import stores
        for key in ("shoprite", "stews", "costco"):
            store = stores.get(key, {})
            self.assertEqual(store.adapter, key)
            self.assertIn("{submit}", store.prompt, key)
        # Stew's flyer is images; the scan starts in the online shop.
        self.assertIn("shopnow.stewleonards.com", stores.get("stews", {}).urls[0]["url"])
        custom = {"stores": {"corner": {"name": "Corner Shop",
                                        "urls": ["https://example.com/ad"]}}}
        self.assertEqual(stores.get("corner", custom).adapter, "")
        pinned = {"stores": {"corner": {"name": "Corner Shop", "adapter": "generic"}}}
        self.assertEqual(stores.get("corner", pinned).adapter, "generic")

    def test_every_named_site_ships_and_is_registered(self):
        from dealcrawler import stores
        index = open(os.path.join(self.HERE, "extension", "sites", "index.js"),
                     encoding="utf-8").read()
        for s in stores.load({}):
            name = s.adapter or "generic"
            self.assertTrue(os.path.isfile(os.path.join(
                self.HERE, "extension", "sites", name + ".js")), name)
            self.assertIn(f'"sites/{name}.js"', index, name)

    def test_extension_can_reach_the_builtin_stores_and_the_panel(self):
        from urllib.parse import urlparse
        from dealcrawler import stores
        hosts = self.manifest()["host_permissions"]
        def covered(host):
            for pattern in hosts:
                h = urlparse(pattern.replace("*.", "")).hostname
                if host == h or host.endswith("." + h):
                    return True
            return False
        self.assertTrue(covered("127.0.0.1"))
        self.assertTrue(covered("shopnow.stewleonards.com"))
        self.assertTrue(covered("shop-rite-web-prod.azurewebsites.net"))
        for s in stores.load({}):
            for u in s.urls:
                self.assertTrue(covered(urlparse(u["url"]).hostname), u["url"])

    def test_extension_asks_for_little(self):
        perms = set(self.manifest()["permissions"])
        # cookies: only to see whether a ShopRite sign-in cookie exists.
        self.assertLessEqual(perms, {"scripting", "activeTab", "storage", "cookies"})
        self.assertNotIn("<all_urls>", self.manifest()["host_permissions"])

    def test_extension_is_read_only(self):
        """Site files never click. The engine presses one thing -- a list's own
        "more" button -- and only after refusing cart/coupon/account labels."""
        folder = os.path.join(self.HERE, "extension", "sites")
        for name in os.listdir(folder):
            if name.endswith(".js"):
                source = open(os.path.join(folder, name), encoding="utf-8").read()
                self.assertNotIn(".click(", source, name)
        engine = open(os.path.join(self.HERE, "extension", "engine", "engine.js"),
                      encoding="utf-8").read()
        self.assertEqual(engine.count(".click("), 1)
        press = engine[engine.index("function pressMore"):]
        press = press[:press.index("\n  }\n")]
        self.assertLess(press.index("NEVER_PRESS.test(label)"), press.index(".click("))
        for word in ("cart", "clip", "coupon", "card", "login", "sign", "confirm"):
            self.assertIn(word, engine[engine.index("const NEVER_PRESS"):][:300])

    def test_adapter_tests_pass(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        folder = os.path.join(self.HERE, "extension", "test")
        files = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                       if f.endswith(".test.js"))
        self.assertGreaterEqual(len(files), 2)
        run = subprocess.run([node, "--test", *files], capture_output=True,
                             text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-2000:])


class TestPanelScript(unittest.TestCase):
    def test_page_script_parses(self):
        """One stray quote in the page's script breaks every button on it."""
        import shutil
        import subprocess
        import tempfile
        import panel
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        html_out = panel.page()
        js = html_out[html_out.rindex("<script>") + 8:html_out.rindex("</script>")]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(js)
        try:
            run = subprocess.run([node, "--check", fh.name], capture_output=True,
                                 text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr[-1500:])
        finally:
            os.unlink(fh.name)


class TestRedeemNotices(unittest.TestCase):
    """ShopRite coupons only count once loaded to a signed-in account; say so
    loudly wherever deals are acted on."""

    def test_each_store_says_what_it_needs(self):
        from dealcrawler import stores
        cfg = {"stores": {"shoprite": {"store_id": "392"}}}
        shoprite = stores.get("shoprite", cfg).redeem
        self.assertEqual(shoprite["level"], "action")
        why = "because it's the only way you can load coupons to your account"
        self.assertIn("You must be logged in to ShopRite", shoprite["body"])
        self.assertIn(why, shoprite["body"])
        self.assertIn("logged in", shoprite["signed_in"]["title"])
        self.assertIn("rsid/392/", shoprite["link"]["url"])
        # Costco: its own terms -- instant savings, membership, no clipping.
        costco = stores.get("costco", cfg).redeem
        self.assertEqual(costco["level"], "info")
        self.assertIn("no clipping", costco["title"].lower())
        self.assertIn("instant savings", costco["body"])
        self.assertIn("membership", costco["body"])
        # Stew's: sale prices, all on its website; APP DEAL items apply when
        # you scan your Member ID (or give your phone number) at checkout.
        stews = stores.get("stews", cfg).redeem
        self.assertEqual(stews["level"], "info")
        self.assertIn("APP DEAL", stews["body"])
        self.assertIn("Member ID", stews["body"])
        self.assertIn("shopnow.stewleonards.com", stews["link"]["url"])
        self.assertTrue(stews["link"]["scanned"])

    def test_a_store_can_set_its_own_notice(self):
        from dealcrawler import stores
        cfg = {"stores": {"corner": {"name": "Corner", "redeem": {
            "level": "action", "title": "Clip first", "body": "In the app."}}}}
        self.assertEqual(stores.get("corner", cfg).redeem["title"], "Clip first")

    def test_savings_notice_sits_at_the_top_until_a_deal_is_found(self):
        import panel
        html_out = panel.page()
        body = html_out[html_out.index("<body>"):]
        self.assertLess(body.index('id="savebar"'), body.index('id="banner"'))
        self.assertIn("You could be saving money this week", body)
        self.assertIn('id="savebar-later"', body)
        self.assertIn('$("#scanwith").click()', html_out)   # it opens the scan
        self.assertNotIn('id="loginbar"', html_out)  # one general notice, not per store
        self.assertIn(".note[hidden]", html_out)     # hidden must beat display:flex

    def test_deals_on_hand_counts_this_weeks_sales_files(self):
        import tempfile
        import panel
        saved = panel.OUT_DIR
        with tempfile.TemporaryDirectory() as tmp:
            panel.OUT_DIR = tmp
            try:
                self.assertEqual(panel.deals_on_hand()["count"], 0)
                with open(os.path.join(tmp, "costco-sales-2026-09-21.xml"), "w") as fh:
                    fh.write('<costcoSales store="Costco"></costcoSales>')   # a quiet week
                self.assertEqual(panel.deals_on_hand()["count"], 0)
                with open(os.path.join(tmp, "stews-sales-2026-09-21.xml"), "w") as fh:
                    fh.write('<s><offer itemId="eggs" savings="1.00"/><offer itemId="oats" savings="2.00"/></s>')
                self.assertEqual(panel.deals_on_hand(), {"count": 2, "stores": ["stews"]})
                old = os.path.join(tmp, "stews-sales-2026-09-21.xml")
                os.utime(old, (0, 0))                                        # last week's
                self.assertEqual(panel.deals_on_hand()["count"], 0)
            finally:
                panel.OUT_DIR = saved

    def test_bridge_tag_cannot_be_overwritten_by_a_result(self):
        """A result field named "source" once replaced the bridge's tag, and
        the panel silently ignored every scan result."""
        here = os.path.dirname(os.path.abspath(__file__))
        bridge = open(os.path.join(here, "extension", "panel-bridge.js"),
                      encoding="utf-8").read()
        self.assertIn('{ ...msg, source: "wss-scanner" }', bridge)
        bg = open(os.path.join(here, "extension", "background.js"), encoding="utf-8").read()
        scan = bg[bg.index("async function scan(job)"):bg.index("async function checkAll")]
        self.assertNotIn(" source:", scan)

    def test_signed_in_check_reads_cookie_names_never_values(self):
        here = os.path.dirname(os.path.abspath(__file__))
        bg = open(os.path.join(here, "extension", "background.js"), encoding="utf-8").read()
        acct = bg[bg.index("async function accountStatus"):]
        acct = acct[:acct.index("\n}\n")]
        self.assertIn("c.name", acct)
        self.assertNotIn(".value", acct)
        self.assertNotIn("fetch(", acct)

    def test_panel_shows_the_banner_on_the_scan_result(self):
        import panel
        html_out = panel.page()
        done = html_out[html_out.index('<section id="w-done"'):]
        self.assertLess(done.index('id="w-redeem"'), done.index('id="w-done-title"'))
        self.assertIn('role="status"', done[:400])
        self.assertIn("showRedeem(wizState.started", html_out)

    def test_app_warns_in_the_preview_and_on_the_pdf(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "app", "main.swift"), encoding="utf-8").read()
        self.assertIn("func redeemNotice(for store: String)", src)
        preview = src[src.index("private func presentScannedDealsPreview"):]
        preview = preview[:preview.index("return alert.runModal()")]
        self.assertIn("redeemBannerView(", preview)
        self.assertNotIn("not card-clip digital coupons", src)
        self.assertIn("for notice in notices { drawRedeemBanner(notice) }", src)
        self.assertIn("LOAD COUPON FIRST", src)
        # The store is on the sales file's root, not on each offer.
        self.assertIn('rootElement()?.attribute(forName: "store")', src)


class TestScannerReports(unittest.TestCase):
    """The panel keeps the Scanner's diagnostics so a broken site can be fixed."""

    def test_report_is_saved_per_store_with_a_history_line(self):
        import json as _json
        import tempfile
        import threading
        import urllib.request as _req   # a loopback call to our own test server
        import panel
        from dealcrawler import paths
        from http.server import ThreadingHTTPServer
        saved = paths.DATA_DIR
        with tempfile.TemporaryDirectory() as tmp:
            paths.DATA_DIR = tmp
            server = ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                port = server.server_address[1]
                body = _json.dumps({"site": "stews", "ok": False, "failedAt": "ready",
                                    "error": "no cards", "steps": {"ready": {"found": 0}}})
                for key in ("stews", "../../etc"):
                    r = _req.urlopen(_req.Request(
                        f"http://127.0.0.1:{port}/api/scanner/report?store={key}",
                        data=body.encode(), headers={"Content-Type": "application/json"}))
                    self.assertEqual(r.status, 200)
                report = _json.load(open(os.path.join(tmp, "scanner", "stews.json")))
                self.assertEqual(report["failedAt"], "ready")
                history = open(os.path.join(tmp, "scanner", "history.jsonl")).read().splitlines()
                self.assertEqual(len(history), 2)
                # A hostile key is flattened into the folder, never outside it.
                self.assertEqual(sorted(os.listdir(os.path.join(tmp, "scanner"))),
                                 ["etc.json", "history.jsonl", "stews.json"])
            finally:
                server.shutdown()
                paths.DATA_DIR = saved


class TestScanEveryStore(unittest.TestCase):
    """Every store gets scanned, and a quiet week still counts as scanned."""

    def test_a_quiet_week_still_writes_the_stores_file(self):
        import tempfile
        import panel

        class Quiet:
            key, name = "costco", "Costco"
        with tempfile.TemporaryDirectory() as tmp:
            saved = panel.OUT_DIR
            panel.OUT_DIR = tmp
            try:
                path = panel.write_sales_file(Quiet, [])
                self.assertTrue(os.path.isfile(path))
                body = open(path).read()
                self.assertIn('store="Costco"', body)
                self.assertNotIn("<offer", body)
                self.assertEqual(panel.deals_on_hand()["count"], 0)   # no deals, but scanned
            finally:
                panel.OUT_DIR = saved

    def test_panel_can_scan_all_stores(self):
        import panel
        html_out = panel.page()
        self.assertIn('id="w-all"', html_out)
        self.assertIn("async function scanAll()", html_out)
        self.assertIn("Import it anyway so the app knows", html_out)


class TestDealsFolder(unittest.TestCase):
    """Sales files go to ~/Documents/Deals, where people can find them."""

    def test_default_is_documents_deals(self):
        from unittest import mock
        from dealcrawler import paths
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WSS_DEALS_DIR", None)
            os.environ.pop("WSS_DATA_DIR", None)
            self.assertEqual(paths._resolve_deals_dir(),
                             os.path.expanduser("~/Documents/Deals"))
        # The desktop app starts the panel with its own WSS_DATA_DIR; deal
        # files must still land in Documents > Deals.
        with mock.patch.dict(os.environ, {"WSS_DATA_DIR": "/tmp/somewhere"}):
            os.environ.pop("WSS_DEALS_DIR", None)
            self.assertEqual(paths._resolve_deals_dir(),
                             os.path.expanduser("~/Documents/Deals"))
        with mock.patch.dict(os.environ, {"WSS_DEALS_DIR": "/tmp/mydeals"}):
            self.assertEqual(paths._resolve_deals_dir(), "/tmp/mydeals")
        self.assertEqual(paths.friendly(os.path.expanduser("~/Documents/Deals")),
                         "Documents > Deals")

    def test_old_app_support_files_move_to_the_deals_folder(self):
        import tempfile
        import panel
        from dealcrawler import paths
        saved = (panel.OUT_DIR, paths.APP_SUPPORT)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                paths.APP_SUPPORT = os.path.join(tmp, "support")
                os.makedirs(os.path.join(paths.APP_SUPPORT, "out"))
                for name in ("stews-sales-2026-09-21.xml", "notes.txt"):
                    open(os.path.join(paths.APP_SUPPORT, "out", name), "w").write("<s/>")
                panel.OUT_DIR = os.path.join(tmp, "Deals")
                self.assertEqual(panel.move_old_sales_files(), ["stews-sales-2026-09-21.xml"])
                self.assertTrue(os.path.isfile(os.path.join(tmp, "Deals", "stews-sales-2026-09-21.xml")))
                self.assertTrue(os.path.isfile(os.path.join(paths.APP_SUPPORT, "out", "notes.txt")))
            finally:
                panel.OUT_DIR, paths.APP_SUPPORT = saved

    def test_unwritable_documents_falls_back_instead_of_failing(self):
        import tempfile
        import panel
        from dealcrawler import paths
        saved_out, saved_data = panel.OUT_DIR, paths.DATA_DIR
        with tempfile.TemporaryDirectory() as tmp:
            locked = os.path.join(tmp, "locked")
            os.makedirs(locked)
            os.chmod(locked, 0o500)                 # like macOS refusing Documents
            try:
                panel.OUT_DIR = os.path.join(locked, "Deals")
                paths.DATA_DIR = os.path.join(tmp, "data")
                self.assertEqual(panel.sales_dir(), os.path.join(tmp, "data", "out"))
            finally:
                os.chmod(locked, 0o700)
                panel.OUT_DIR, paths.DATA_DIR = saved_out, saved_data

    def test_people_are_told_where_the_files_are(self):
        import panel
        html_out = panel.page()
        self.assertIn("Your deal files are saved in", html_out)
        self.assertIn('id="w-done-where"', html_out)
        from dealcrawler import branding
        self.assertTrue(any("Documents > Deals" in s for s in branding.DEFAULTS["import_steps"]))


class TestPanelLifetime(unittest.TestCase):
    """The panel stops when its page closes -- not on a heartbeat."""

    def test_page_holds_a_live_connection_and_sends_no_heartbeat(self):
        import panel
        html_out = panel.page()
        self.assertIn('EventSource("/api/live")', html_out)
        self.assertNotIn("/api/ping", html_out)
        self.assertNotIn("setInterval(() => {{ fetch", html_out)

    def test_pages_are_counted_in_and_out(self):
        import panel
        before = dict(panel._alive)
        try:
            panel._page_opened()
            panel._page_opened()
            panel._page_closed()
            self.assertEqual(panel._alive["pages"], before["pages"] + 1)
            self.assertEqual(panel._alive["empty_since"], 0.0)
            panel._page_closed()
            if before["pages"] == 0:
                self.assertGreater(panel._alive["empty_since"], 0.0)
        finally:
            panel._alive.update(before)


if __name__ == "__main__":
    unittest.main(verbosity=2)

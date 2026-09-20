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

    def test_neutering_covers_every_scrape_target(self):
        """Relabelling alone left the coupon engine fetching store pages."""
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        self.assertTrue(r.SCRAPE_URLS)
        for url in r.SCRAPE_URLS:
            self.assertLessEqual(len(r.BLANK), len(url), url)
            self.assertTrue(url.startswith(b"http"), url)

    def test_scraper_text_replacements_fit(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        for original, replacement in r.SCRAPER_TEXT:
            self.assertLessEqual(len(replacement), len(original), replacement)

    def test_neutering_can_be_opted_out_of(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
        import retire_app_buttons as r
        sample = b"x" * 400 + b"https://www.bjs.com/deals" + b"y" * 400
        with_neuter = dict(r.build_rules(sample, neuter=True))
        without = dict(r.build_rules(sample, neuter=False))
        self.assertIn(b"https://www.bjs.com/deals", with_neuter)
        self.assertNotIn(b"https://www.bjs.com/deals", without)

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
        import os as _os
        import shutil as _shutil
        from dealcrawler import stores
        root = _os.path.dirname(_os.path.abspath(__file__))
        store = stores.get("shoprite", self.panel.load_config())
        sample = _os.path.join(root, "examples", "sample-scan.txt")
        created = not _os.path.exists(store.harvest_path)
        _shutil.copyfile(sample, store.harvest_path)
        try:
            result = self.panel.build_for(store)
            self.assertTrue(result["found"])
            self.assertGreater(result["count"], 0)
            self.assertTrue(result["xml"].endswith(".xml"))
        finally:
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


if __name__ == "__main__":
    unittest.main(verbosity=2)

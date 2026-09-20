"""Smart Shopping List catalog.

The 50 item IDs below are the ONLY values the app's "Import Sales XML..."
importer accepts in an <offer itemId="..."/>. Unknown IDs are silently
ignored by the app, so an offer that fails to match a catalog ID is worth
nothing -- matcher.py exists to avoid that.

price     = the app's normal ("fallback") per-package price, used to sanity
            check savings and to convert a sale price into a savings figure.
package   = the app's package description (what one unit means).
lbs / oz  = package size where known, used to convert per-weight advertised
            prices ($3.99/lb) into the per-package numbers the app expects.
twin      = snack line items that are the same product as another item; a
            sale on the parent applies to them too.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    package: str
    price: float
    lbs: Optional[float] = None
    oz: Optional[float] = None
    # at least one `require` pattern must match for the item to be considered
    require: List[str] = field(default_factory=list)
    # any `exclude` match disqualifies the item outright
    exclude: List[str] = field(default_factory=list)
    # twin item ids that the same offer also applies to
    twins: List[str] = field(default_factory=list)


# Shared exclusions: things that look like a catalog word but are a different product.
GLOBAL_EXCLUDE = [
    r"\bdog\b", r"\bcat\b", r"\bpet\b", r"\bpuppy\b", r"\bkitten\b",
    r"\btreats? for\b", r"\bshampoo\b", r"\bdetergent\b", r"\bsoap\b",
    r"\bcandle\b", r"\btoy\b", r"\bsupplement\b", r"\bgummies\b",
    r"\bvitamin\b", r"\bcapsules?\b", r"\bsoftgels?\b",
]

ITEMS = [
    Item("oats", "Old-fashioned oats", "10 lb", 9.98, lbs=10,
         require=[r"\boats?\b", r"\boatmeal\b", r"\brolled oats\b"],
         exclude=[r"\bcookie", r"\bbar\b", r"\bbars\b", r"\bmilk\b", r"\bcereal cup"]),

    Item("blueberries", "Frozen blueberries", "4 lb", 12.49, lbs=4,
         require=[r"\bblueberr"],
         exclude=[r"\bmuffin", r"\bjam\b", r"\bpreserve", r"\bsyrup\b", r"\byogurt\b"]),

    Item("eggs", "Cage-free eggs", "18 ct", 3.89, twins=["snackeggs"],
         require=[r"\beggs?\b"],
         exclude=[r"\begg ?nog\b", r"\bsubstitute\b", r"\bbeater", r"\bnoodle",
                  r"\bsandwich\b", r"\bbites\b", r"\bwhites? only\b", r"\broll\b"]),

    Item("milk", "Low-fat milk or fortified soy milk", "1 gal", 3.25, twins=["snackmilk"],
         require=[r"\bmilk\b"],
         exclude=[r"\balmond\b", r"\bcoconut\b", r"\boat ?milk\b", r"\bcashew\b",
                  r"\bcondensed\b", r"\bevaporated\b", r"\bchocolate\b", r"\bshake\b",
                  r"\bcreamer\b", r"\bbuttermilk\b", r"\bpowder\b"]),

    Item("bread", "Whole-grain bread", "1 loaf", 4.49,
         require=[r"\bbread\b", r"\bloaf\b", r"\bbagels?\b", r"\bEnglish muffins?\b"],
         exclude=[r"\bcrumbs?\b", r"\bpudding\b", r"\bgarlic bread\b", r"\bbanana bread\b",
                  r"\bstuffing\b", r"\bdough\b"]),

    Item("fruit", "Mixed apples, pears, oranges and bananas", "weekly mix", 12.00,
         require=[r"\bapples?\b", r"\bpears?\b", r"\boranges?\b", r"\bbananas?\b",
                  r"\bclementines?\b", r"\bmandarins?\b", r"\bgrapes?\b"],
         exclude=[r"\bjuice\b", r"\bsauce\b", r"\bpie\b", r"\bcider\b", r"\bdried\b",
                  r"\bchips?\b", r"\bcandy\b", r"\bflavored\b", r"\bpineapple\b"]),

    Item("quinoa", "Organic quinoa", "3 lb", 9.99, lbs=3, require=[r"\bquinoa\b"]),

    Item("beans", "No-salt beans, assorted", "15 oz cans", 1.29, oz=15,
         require=[r"\bbeans?\b", r"\bchickpeas?\b", r"\bgarbanzo\b"],
         exclude=[r"\bgreen beans\b", r"\bcoffee\b", r"\bvanilla\b", r"\bjelly\b",
                  r"\bbaked beans\b", r"\brefried\b", r"\bsoup\b"]),

    Item("tuna", "Light tuna in water", "8 pack", 15.99,
         require=[r"\btuna\b"],
         exclude=[r"\bsteaks?\b", r"\bsushi\b", r"\bpouch salad\b"]),

    Item("wraps", "Whole-wheat wraps and pitas", "2 packs", 7.98,
         require=[r"\bwraps?\b", r"\btortillas?\b", r"\bpitas?\b", r"\bflatbread"],
         exclude=[r"\bchips?\b", r"\bgift\b"]),

    Item("greens", "Spinach, kale and arugula", "weekly mix", 9.00,
         require=[r"\bspinach\b", r"\bkale\b", r"\barugula\b", r"\bspring mix\b",
                  r"\bsalad greens?\b", r"\blettuce\b", r"\bromaine\b"],
         exclude=[r"\bdip\b", r"\bartichoke\b", r"\bfrozen creamed\b", r"\bdressing\b"]),

    Item("lunchveg", "Cucumber, tomato, cabbage and carrots", "weekly mix", 12.00,
         require=[r"\bcucumbers?\b", r"\bcabbage\b", r"\bcarrots?\b",
                  r"\bgrape tomatoes\b", r"\bcherry tomatoes\b"],
         exclude=[r"\bjuice\b", r"\bcake\b", r"\bpickles?\b", r"\bsoup\b"]),

    Item("dinnerveg", "Broccoli, peppers, zucchini and cauliflower", "weekly mix", 18.00,
         require=[r"\bbroccoli\b", r"\bzucchini\b", r"\bcauliflower\b",
                  r"\bbell peppers?\b", r"\basparagus\b", r"\bgreen beans\b",
                  r"\bbrussels sprouts\b"],
         exclude=[r"\bsoup\b", r"\bpizza\b", r"\bcheese sauce\b", r"\bcrust\b", r"\btots\b"]),

    Item("feta", "Feta and mozzarella", "assorted", 5.49,
         require=[r"\bfeta\b", r"\bmozzarella\b"],
         exclude=[r"\bpizza\b", r"\bsticks?\b", r"\bbreaded\b"]),

    Item("whey", "Whey protein powder", "5 lb", 54.99, lbs=5,
         require=[r"\bwhey\b", r"\bprotein powder\b"],
         exclude=[r"\bbars?\b", r"\bready to drink\b", r"\bshake\b"]),

    Item("snackeggs", "Extra eggs for snacks", "18 ct", 3.89, require=[]),
    Item("snackmilk", "Extra milk for smoothies", "1 gal", 3.25, require=[]),
    Item("snackyogurt", "Extra plain Greek yogurt for snacks", "40 oz", 4.79, require=[]),

    Item("chicken", "Boneless skinless chicken breast", "4.5-6.5 lb", 12.05, lbs=5.5,
         require=[r"\bchicken breasts?\b", r"\bboneless skinless\b", r"\bchicken tenders?\b"],
         exclude=[r"\bbroth\b", r"\bstock\b", r"\bnuggets?\b", r"\bbreaded\b", r"\bfried\b",
                  r"\bsoup\b", r"\bsausage\b", r"\bwings?\b", r"\bpatties\b", r"\bstrips\b",
                  r"\bseasoning\b", r"\bbouillon\b"]),

    Item("salmon", "Frozen Atlantic salmon", "2 lb", 20.99, lbs=2,
         require=[r"\bsalmon\b"],
         exclude=[r"\bsmoked\b", r"\blox\b", r"\bburger", r"\bcake", r"\bcanned\b", r"\bpouch\b"]),

    Item("cod", "Fresh cod fillet", "1 lb", 12.99, lbs=1,
         require=[r"\bcod\b", r"\bhaddock\b", r"\bpollock\b", r"\btilapia\b"],
         exclude=[r"\bbreaded\b", r"\bsticks?\b", r"\bbattered\b", r"\bliver oil\b"]),

    Item("turkey", "93% lean ground turkey", "1 lb", 4.39, lbs=1,
         require=[r"\bground turkey\b", r"\bturkey,? ?93\b", r"93%.{0,12}turkey"],
         exclude=[r"\bbreast\b", r"\bdeli\b", r"\bsliced\b", r"\bwhole turkey\b",
                  r"\bbacon\b", r"\bsausage\b", r"\bjerky\b"]),

    Item("beef", "93% lean ground beef", "1 lb", 5.99, lbs=1,
         require=[r"\bground beef\b", r"\bground chuck\b", r"\bground sirloin\b",
                  r"93%.{0,12}beef"],
         exclude=[r"\bbroth\b", r"\bstock\b", r"\bpatties\b", r"\bjerky\b", r"\bsteak\b",
                  r"\bmeatballs?\b", r"\bbouillon\b"]),

    Item("shrimp", "Peeled shrimp", "2 lb", 23.99, lbs=2,
         require=[r"\bshrimp\b"],
         exclude=[r"\bbreaded\b", r"\bpopcorn\b", r"\bcocktail sauce\b", r"\btempura\b"]),

    Item("tofu", "Extra-firm tofu", "14 oz", 2.49, oz=14,
         require=[r"\btofu\b"], exclude=[r"\bdessert\b", r"\bsmoothie\b"]),

    Item("lentils", "Brown and red lentils", "1 lb bags", 3.00, lbs=1,
         require=[r"\blentils?\b"], exclude=[r"\bsoup\b", r"\bchips?\b", r"\bpasta\b"]),

    Item("pasta", "Whole-wheat pasta and noodles", "16 oz", 1.99, oz=16,
         require=[r"\bpasta\b", r"\bspaghetti\b", r"\bpenne\b", r"\brigatoni\b",
                  r"\blinguine\b", r"\bmacaroni\b", r"\brotini\b", r"\bziti\b", r"\bnoodles?\b"],
         exclude=[r"\bsauce\b", r"\bsalad\b", r"\bramen\b", r"\bcup\b", r"\bmac and cheese\b",
                  r"\bfrozen\b", r"\bmeal\b"]),

    Item("rice", "Brown rice", "2 lb", 3.49, lbs=2,
         require=[r"\bbrown rice\b", r"\bwhite rice\b", r"\bjasmine rice\b",
                  r"\bbasmati\b", r"\blong grain rice\b", r"\brice\b"],
         exclude=[r"\brice cakes?\b", r"\brice milk\b", r"\bkrispies\b", r"\bpudding\b",
                  r"\bcauliflower rice\b", r"\bfried rice\b", r"\bseasoned\b", r"\bcrackers?\b",
                  r"\bvinegar\b", r"\bnoodles?\b", r"\bpaper\b"]),

    Item("tomatoes", "No-salt diced tomatoes", "14.5 oz cans", 1.39, oz=14.5,
         require=[r"\bdiced tomatoes\b", r"\bcrushed tomatoes\b", r"\btomato sauce\b",
                  r"\bcanned tomatoes\b", r"\btomato puree\b", r"\bwhole peeled tomatoes\b"],
         exclude=[r"\bketchup\b", r"\bsoup\b", r"\bjuice\b", r"\bfresh\b", r"\bpaste\b"]),

    Item("oil", "Extra virgin olive oil", "3 L", 24.99,
         require=[r"\bolive oil\b", r"\bcanola oil\b", r"\bavocado oil\b", r"\bvegetable oil\b"],
         exclude=[r"\bspray\b", r"\bcooking spray\b", r"\binfused\b", r"\bessential\b", r"\bfish oil\b"]),

    Item("broth", "Low-sodium broth", "32 oz", 2.99, oz=32,
         require=[r"\bbroth\b", r"\bstock\b", r"\bbouillon\b"],
         exclude=[r"\bstockings?\b", r"\bsoup\b", r"\bramen\b"]),

    Item("sauces", "Pesto, salsa, miso and harissa", "assorted jars", 18.00,
         require=[r"\bpesto\b", r"\bsalsa\b", r"\bmiso\b", r"\bharissa\b"],
         exclude=[r"\bchips?\b", r"\bkit\b", r"\bsoup\b"]),

    Item("blackpepper", "Ground black pepper", "1 jar", 1.29,
         require=[r"\bblack pepper\b", r"\bpeppercorns?\b"], exclude=[r"\bsauce\b"]),

    Item("italianseasoning", "Italian seasoning", "1 jar", 1.29,
         require=[r"\bitalian seasoning\b", r"\bitalian herbs?\b"]),

    Item("redpepper", "Crushed red pepper flakes", "1 jar", 1.29,
         require=[r"\bcrushed red pepper\b", r"\bred pepper flakes\b"]),

    Item("vinegar", "Store-brand apple cider or distilled vinegar", "32 oz", 2.29, oz=32,
         require=[r"\bapple cider vinegar\b", r"\bdistilled vinegar\b",
                  r"\bwhite vinegar\b", r"\bbalsamic vinegar\b"]),

    Item("salt", "Iodized table salt", "1 canister", 1.49,
         require=[r"\btable salt\b", r"\biodized salt\b", r"\bkosher salt\b", r"\bsea salt\b"],
         exclude=[r"\bsalted\b", r"\bscrub\b", r"\blamp\b", r"\bsalt ?water\b"]),

    Item("cinnamon", "Ground cinnamon", "1 jar", 1.29,
         require=[r"\bcinnamon\b"],
         exclude=[r"\broll\b", r"\bbun\b", r"\bcereal\b", r"\btoast crunch\b", r"\bbread\b",
                  r"\bcandle\b", r"\bgum\b"]),

    Item("cumin", "Ground cumin", "1 jar", 1.29, require=[r"\bcumin\b"]),
    Item("paprika", "Smoked paprika", "1 jar", 1.29, require=[r"\bpaprika\b"]),
    Item("garlicpowder", "Garlic powder", "1 jar", 1.29,
         require=[r"\bgarlic powder\b", r"\bgranulated garlic\b"]),
    Item("onionpowder", "Onion powder", "1 jar", 1.29, require=[r"\bonion powder\b"]),
    Item("spices", "Core spices and vinegar", "pantry set", 18.00,
         require=[r"\bspice (?:set|rack|kit|assortment)\b", r"\bseasoning (?:set|kit)\b"]),

    Item("yogurt", "Plain Greek yogurt", "40 oz", 4.79, oz=40, twins=["snackyogurt"],
         require=[r"\bgreek yogurt\b", r"\byogurt\b"],
         exclude=[r"\bdrink\b", r"\bsmoothie\b", r"\btube\b", r"\bcovered\b", r"\bparfait\b",
                  r"\bfrozen yogurt\b", r"\bbars?\b", r"\bcups?\b"]),

    Item("cottage", "Low-fat cottage cheese", "48 oz", 5.49, oz=48,
         require=[r"\bcottage cheese\b"]),

    Item("hummus", "Hummus", "2 tubs", 6.99,
         require=[r"\bhummus\b"], exclude=[r"\bchips?\b", r"\bpretzel\b", r"\bsnack pack\b"]),

    Item("peanut", "Natural peanut butter", "36 oz", 6.39, oz=36,
         require=[r"\bpeanut butter\b", r"\balmond butter\b"],
         exclude=[r"\bcups?\b", r"\bcandy\b", r"\bcookies?\b", r"\bcrackers?\b",
                  r"\bice cream\b", r"\bjelly\b", r"\bm&m\b", r"\bbars?\b",
                  r"\bprotein bar", r"\bbaked\b"]),

    Item("walnuts", "Walnuts", "2 lb", 9.49, lbs=2,
         require=[r"\bwalnuts?\b"], exclude=[r"\bcandied\b", r"\bcookies?\b", r"\bbrownie\b"]),

    Item("chia", "Chia seeds", "2 lb", 10.99, lbs=2,
         require=[r"\bchia\b"], exclude=[r"\bdrink\b", r"\bpudding cup\b", r"\bpet\b"]),

    Item("sweetpotato", "Sweet potatoes", "3 lb", 2.89, lbs=3,
         require=[r"\bsweet potato(?:es)?\b", r"\byams?\b"],
         exclude=[r"\bfries\b", r"\bchips?\b", r"\bcasserole\b", r"\bpie\b", r"\btots\b"]),
]

BY_ID = {i.id: i for i in ITEMS}

# Items that are pure twins -- never matched directly, only mirrored from a parent.
TWIN_ONLY = {"snackeggs", "snackmilk", "snackyogurt"}

VALID_IDS = set(BY_ID)

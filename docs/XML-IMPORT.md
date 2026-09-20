# Sales XML import format

This is the file format the **Smart Shopping List** app reads from
**Import Sales XML…**, and the format `crawl.py` writes. It is deliberately
small: a list of offers, each naming a catalog item and either a discount or a
sale price.

## Minimal example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<shopriteSales store="ShopRite" date="2026-09-20">
  <offer itemId="turkey" savings="2.00" limit="4" note="93% lean ground turkey"/>
  <offer itemId="eggs" salePrice="2.49" limit="6" note="Large eggs 18ct"/>
</shopriteSales>
```

## Rules

- The root element carries `store` and `date`. Write **one file per store** —
  `store` describes the whole file, not an individual offer.
- Each `<offer/>` must give `itemId` **and exactly one of** `savings` or
  `salePrice`.
  - `savings` — dollars off **one package**.
  - `salePrice` — the advertised price **of one package**.
- `limit` (optional) is the store's purchase cap. The app honours it when
  totalling savings.
- `note` (optional) is free text shown next to the matched item.
- `itemId` must be one of the catalog IDs below. **Unknown IDs are silently
  ignored**, so a typo costs you the offer with no error.

## Writing it safely

The importer scans for `<offer .../>` elements and reads attributes by hand
rather than using a full XML parser. To stay compatible:

- Keep one offer per line, self-closing, with attributes in the order
  `itemId`, `savings`/`salePrice`, `limit`, `note`.
- Use straight double quotes.
- Keep `note` to plain ASCII. Avoid `&`, `<`, `>`, and quotes entirely rather
  than relying on entity escaping — `dealcrawler/xmlout.py` strips them.
- Prices are plain decimals with no currency symbol: `2.00`, not `$2.00`.

## Per-package, not per-pound

The app budgets in **packages**. A circular advertising `$3.99/lb` must be
converted before it goes in the file: multiply by the package size in the table
below. `crawl.py` does this automatically (`--per-weight convert`, the default);
`--per-weight skip` drops per-weight offers instead.

## Catalog item IDs

All 50 IDs the importer accepts, with the app's normal per-package
price — useful for sanity-checking that a "deal" is actually a discount.

| itemId | Item | Package | Normal price |
| --- | --- | --- | --- |
| `beans` | No-salt beans, assorted | 15 oz cans | $1.29 |
| `beef` | 93% lean ground beef | 1 lb | $5.99 |
| `blackpepper` | Ground black pepper | 1 jar | $1.29 |
| `blueberries` | Frozen blueberries | 4 lb | $12.49 |
| `bread` | Whole-grain bread | 1 loaf | $4.49 |
| `broth` | Low-sodium broth | 32 oz | $2.99 |
| `chia` | Chia seeds | 2 lb | $10.99 |
| `chicken` | Boneless skinless chicken breast | 4.5-6.5 lb | $12.05 |
| `cinnamon` | Ground cinnamon | 1 jar | $1.29 |
| `cod` | Fresh cod fillet | 1 lb | $12.99 |
| `cottage` | Low-fat cottage cheese | 48 oz | $5.49 |
| `cumin` | Ground cumin | 1 jar | $1.29 |
| `dinnerveg` | Broccoli, peppers, zucchini and cauliflower | weekly mix | $18.00 |
| `eggs` | Cage-free eggs | 18 ct | $3.89 |
| `feta` | Feta and mozzarella | assorted | $5.49 |
| `fruit` | Mixed apples, pears, oranges and bananas | weekly mix | $12.00 |
| `garlicpowder` | Garlic powder | 1 jar | $1.29 |
| `greens` | Spinach, kale and arugula | weekly mix | $9.00 |
| `hummus` | Hummus | 2 tubs | $6.99 |
| `italianseasoning` | Italian seasoning | 1 jar | $1.29 |
| `lentils` | Brown and red lentils | 1 lb bags | $3.00 |
| `lunchveg` | Cucumber, tomato, cabbage and carrots | weekly mix | $12.00 |
| `milk` | Low-fat milk or fortified soy milk | 1 gal | $3.25 |
| `oats` | Old-fashioned oats | 10 lb | $9.98 |
| `oil` | Extra virgin olive oil | 3 L | $24.99 |
| `onionpowder` | Onion powder | 1 jar | $1.29 |
| `paprika` | Smoked paprika | 1 jar | $1.29 |
| `pasta` | Whole-wheat pasta and noodles | 16 oz | $1.99 |
| `peanut` | Natural peanut butter | 36 oz | $6.39 |
| `quinoa` | Organic quinoa | 3 lb | $9.99 |
| `redpepper` | Crushed red pepper flakes | 1 jar | $1.29 |
| `rice` | Brown rice | 2 lb | $3.49 |
| `salmon` | Frozen Atlantic salmon | 2 lb | $20.99 |
| `salt` | Iodized table salt | 1 canister | $1.49 |
| `sauces` | Pesto, salsa, miso and harissa | assorted jars | $18.00 |
| `shrimp` | Peeled shrimp | 2 lb | $23.99 |
| `snackeggs` | Extra eggs for snacks | 18 ct | $3.89 |
| `snackmilk` | Extra milk for smoothies | 1 gal | $3.25 |
| `snackyogurt` | Extra plain Greek yogurt for snacks | 40 oz | $4.79 |
| `spices` | Core spices and vinegar | pantry set | $18.00 |
| `sweetpotato` | Sweet potatoes | 3 lb | $2.89 |
| `tofu` | Extra-firm tofu | 14 oz | $2.49 |
| `tomatoes` | No-salt diced tomatoes | 14.5 oz cans | $1.39 |
| `tuna` | Light tuna in water | 8 pack | $15.99 |
| `turkey` | 93% lean ground turkey | 1 lb | $4.39 |
| `vinegar` | Store-brand apple cider or distilled vinegar | 32 oz | $2.29 |
| `walnuts` | Walnuts | 2 lb | $9.49 |
| `whey` | Whey protein powder | 5 lb | $54.99 |
| `wraps` | Whole-wheat wraps and pitas | 2 packs | $7.98 |
| `yogurt` | Plain Greek yogurt | 40 oz | $4.79 |

The three `snack*` IDs are separate line items for the same products as `eggs`,
`milk` and `yogurt`. A sale applies to both; `crawl.py` mirrors it unless you
pass `--no-snack-twins`.

## Validating a file

```bash
python3 -c "import sys; sys.path.insert(0,'.'); from dealcrawler.xmlout import validate; \
print(validate(open(sys.argv[1]).read()) or 'OK')" out/shoprite-sales-2026-09-20.xml
```

This re-reads the file the way the app does and reports unknown item IDs,
offers missing a price, and offers that wrongly carry both `savings` and
`salePrice`.


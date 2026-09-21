import AppKit
import Foundation
import CoreGraphics
import CoreText
import PDFKit
import WebKit
import QuartzCore

struct ShoppingItem {
    let id: String
    let name: String
    let package: String
    let aisle: String
    let store: String
    let meal: String
    let monthlyPackages: Double
    let fallbackPrice: Double
    let sourceURL: String?
}

struct NutritionEstimate {
    let calories: Int
    let proteinGrams: Int
    let carbohydrateGrams: Int
    let fatGrams: Int

    init(proteinGrams: Int, carbohydrateGrams: Int, fatGrams: Int) {
        self.proteinGrams = max(0, proteinGrams)
        self.carbohydrateGrams = max(0, carbohydrateGrams)
        self.fatGrams = max(0, fatGrams)
        self.calories = self.proteinGrams * 4 + self.carbohydrateGrams * 4 + self.fatGrams * 9
    }

    var summary: String {
        "\(calories) kcal | P \(proteinGrams)g | C \(carbohydrateGrams)g | F \(fatGrams)g"
    }

    func adding(_ other: NutritionEstimate) -> NutritionEstimate {
        NutritionEstimate(
            proteinGrams: proteinGrams + other.proteinGrams,
            carbohydrateGrams: carbohydrateGrams + other.carbohydrateGrams,
            fatGrams: fatGrams + other.fatGrams
        )
    }

    func multiplied(by count: Int) -> NutritionEstimate {
        NutritionEstimate(
            proteinGrams: proteinGrams * max(0, count),
            carbohydrateGrams: carbohydrateGrams * max(0, count),
            fatGrams: fatGrams * max(0, count)
        )
    }
}

struct Recipe {
    let title: String
    let baseServings: Int
    let readyMinutes: Int?
    let ingredients: [String]
    let steps: [String]
    let sourceURL: String?
    let sourceName: String
    var goalNote: String? = nil
    var macrosPerServing = NutritionEstimate(proteinGrams: 20, carbohydrateGrams: 50, fatGrams: 15)
    var nutritionSource = "Estimated from listed ingredient amounts; verify package labels."
}

enum NutritionGoal: String, CaseIterable {
    case buildMuscle = "Build Muscle"
    case cutting = "Cutting"
    case maintenance = "Maintenance"
}

struct PersonalizedNutritionTarget {
    let macros: NutritionEstimate
    let estimatedMaintenanceCalories: Int
    let goalMultiplier: Double
    let planningWeightPounds: Double
}

struct MealDBSummary: Decodable {
    let idMeal: String
    let strMeal: String
}

struct MealDBFilterResponse: Decodable {
    let meals: [MealDBSummary]?
}

struct ScheduledRecipe {
    let day: Int
    let recipeIndex: Int
    let prepDay: Int
    let batchServings: Int
    let isPrepDay: Bool
}

struct ListOptions {
    let recipient: String
    let days: Int
    let people: Int
    let budgetMin: Double
    let budgetMax: Double
    let groupByStore: Bool
    let enabledMeals: Set<String>
    let enabledStores: Set<String>
    let nutritionGoal: NutritionGoal
    let heightInches: Double?
    let weightPounds: Double?
    let prioritizeSales: Bool
    let saleItemIDs: Set<String>
    /// item id -> store the imported offer came from (for redeem notices).
    var saleSources: [String: String] = [:]
}

final class PriceBook {
    var prices: [String: Double] = [:]
    var retailerChecked = Set<String>()
    var usdaChecked = Set<String>()
    var lastChecked: Date?

    func price(for item: ShoppingItem) -> Double {
        prices[item.id] ?? item.fallbackPrice
    }
}

let catalog: [ShoppingItem] = [
    ShoppingItem(id: "oats", name: "Old-fashioned oats", package: "10 lb", aisle: "Cereal", store: "BJ's", meal: "Breakfast", monthlyPackages: 0.7, fallbackPrice: 9.98, sourceURL: "https://www.bjs.com/product/name/3000000000001545264"),
    ShoppingItem(id: "blueberries", name: "Frozen blueberries", package: "4 lb", aisle: "Frozen", store: "BJ's", meal: "Breakfast", monthlyPackages: 0.8, fallbackPrice: 12.49, sourceURL: "https://www.bjs.com/product/wellsley-farms-frozen-whole-blueberries-4-lbs/3000000000005505905"),
    ShoppingItem(id: "eggs", name: "Large eggs, best-value package", package: "18 ct", aisle: "Dairy", store: "BJ's", meal: "Breakfast", monthlyPackages: 2.0, fallbackPrice: 3.89, sourceURL: "https://www.bjs.com/category/grocery/dairy/eggs-and-egg-substitutes/3000000000000117233"),
    ShoppingItem(id: "milk", name: "Low-fat or lactose-free dairy milk", package: "1 gal", aisle: "Dairy", store: "BJ's", meal: "Breakfast", monthlyPackages: 1.0, fallbackPrice: 3.25, sourceURL: nil),
    ShoppingItem(id: "chia", name: "Chia seeds", package: "2 lb", aisle: "Baking", store: "Costco", meal: "Breakfast", monthlyPackages: 0.3, fallbackPrice: 10.99, sourceURL: nil),
    ShoppingItem(id: "bread", name: "Store-brand whole-grain bread", package: "1 loaf", aisle: "Bread", store: "ShopRite", meal: "Breakfast", monthlyPackages: 2.0, fallbackPrice: 4.49, sourceURL: nil),
    ShoppingItem(id: "fruit", name: "Value fruit mix: bananas, apples and seasonal fruit", package: "weekly mix", aisle: "Produce", store: "Stew Leonard's", meal: "Breakfast", monthlyPackages: 4.0, fallbackPrice: 7.00, sourceURL: nil),

    ShoppingItem(id: "quinoa", name: "Value quinoa", package: "3 lb", aisle: "Grains", store: "BJ's", meal: "Lunch", monthlyPackages: 0.7, fallbackPrice: 9.99, sourceURL: "https://www.bjs.com/product/wellsley-farms-quinoa--2-lbs-/3000000000000676088/"),
    ShoppingItem(id: "rice", name: "Brown rice", package: "2 lb", aisle: "Rice", store: "ShopRite", meal: "Lunch", monthlyPackages: 1.0, fallbackPrice: 3.49, sourceURL: nil),
    ShoppingItem(id: "beans", name: "Store-brand no-salt beans, assorted", package: "15 oz cans", aisle: "Canned beans", store: "ShopRite", meal: "Lunch", monthlyPackages: 8.0, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "tuna", name: "Light tuna in water", package: "8 pack", aisle: "Canned fish", store: "Costco", meal: "Lunch", monthlyPackages: 0.7, fallbackPrice: 15.99, sourceURL: nil),
    ShoppingItem(id: "hummus", name: "Hummus", package: "2 tubs", aisle: "Deli", store: "Costco", meal: "Lunch", monthlyPackages: 1.0, fallbackPrice: 6.99, sourceURL: nil),
    ShoppingItem(id: "wraps", name: "Store-brand whole-wheat wraps and pitas", package: "2 packs", aisle: "Bread", store: "ShopRite", meal: "Lunch", monthlyPackages: 1.0, fallbackPrice: 7.98, sourceURL: nil),
    ShoppingItem(id: "greens", name: "Value greens: spinach, kale or lettuce", package: "weekly mix", aisle: "Produce", store: "Stew Leonard's", meal: "Lunch", monthlyPackages: 4.0, fallbackPrice: 5.00, sourceURL: nil),
    ShoppingItem(id: "lunchveg", name: "Value vegetables: carrots, cucumber, peppers and tomato", package: "weekly mix", aisle: "Produce", store: "Stew Leonard's", meal: "Lunch", monthlyPackages: 4.0, fallbackPrice: 7.00, sourceURL: nil),
    ShoppingItem(id: "feta", name: "Feta and mozzarella", package: "assorted", aisle: "Dairy", store: "ShopRite", meal: "Lunch", monthlyPackages: 2.0, fallbackPrice: 5.49, sourceURL: nil),

    ShoppingItem(id: "whey", name: "Whey protein powder", package: "5 lb", aisle: "Nutrition", store: "BJ's", meal: "Snack", monthlyPackages: 1.0, fallbackPrice: 54.99, sourceURL: nil),
    ShoppingItem(id: "snackeggs", name: "Extra eggs for snacks", package: "18 ct", aisle: "Dairy", store: "BJ's", meal: "Snack", monthlyPackages: 3.0, fallbackPrice: 3.89, sourceURL: nil),
    ShoppingItem(id: "snackmilk", name: "Extra milk for smoothies", package: "1 gal", aisle: "Dairy", store: "BJ's", meal: "Snack", monthlyPackages: 2.0, fallbackPrice: 3.25, sourceURL: nil),

    ShoppingItem(id: "chicken", name: "Family-pack boneless skinless chicken breast", package: "4.5-6.5 lb", aisle: "Meat", store: "BJ's", meal: "Dinner", monthlyPackages: 1.0, fallbackPrice: 12.05, sourceURL: "https://www.bjs.com/product/wellsley-farms-boneless-skinless-chicken-breasts-45-65-lb/3000000000000300066"),
    ShoppingItem(id: "salmon", name: "Frozen Atlantic salmon", package: "2 lb", aisle: "Frozen seafood", store: "BJ's", meal: "Dinner", monthlyPackages: 1.0, fallbackPrice: 20.99, sourceURL: "https://www.bjs.com/product/wellsley-farms-farm-raised-atlantic-salmon-2-lbs/3000000000000268593"),
    ShoppingItem(id: "shrimp", name: "Peeled shrimp", package: "2 lb", aisle: "Frozen seafood", store: "BJ's", meal: "Dinner", monthlyPackages: 0.8, fallbackPrice: 23.99, sourceURL: nil),
    ShoppingItem(id: "cod", name: "Fresh cod fillet", package: "1 lb", aisle: "Seafood", store: "Stew Leonard's", meal: "Dinner", monthlyPackages: 1.0, fallbackPrice: 12.99, sourceURL: nil),
    ShoppingItem(id: "turkey", name: "93% lean ground turkey", package: "1 lb", aisle: "Meat", store: "ShopRite", meal: "Dinner", monthlyPackages: 3.0, fallbackPrice: 4.39, sourceURL: nil),
    ShoppingItem(id: "beef", name: "93% lean ground beef", package: "1 lb", aisle: "Meat", store: "ShopRite", meal: "Dinner", monthlyPackages: 2.0, fallbackPrice: 5.99, sourceURL: nil),
    ShoppingItem(id: "lentils", name: "Brown and red lentils", package: "1 lb bags", aisle: "Dry beans", store: "ShopRite", meal: "Dinner", monthlyPackages: 2.0, fallbackPrice: 3.00, sourceURL: nil),
    ShoppingItem(id: "pasta", name: "Whole-wheat pasta and noodles", package: "16 oz", aisle: "Pasta", store: "ShopRite", meal: "Dinner", monthlyPackages: 3.0, fallbackPrice: 1.99, sourceURL: nil),
    ShoppingItem(id: "tomatoes", name: "No-salt diced tomatoes", package: "14.5 oz cans", aisle: "Canned tomatoes", store: "ShopRite", meal: "Dinner", monthlyPackages: 7.0, fallbackPrice: 1.39, sourceURL: nil),
    ShoppingItem(id: "sweetpotato", name: "Sweet potatoes", package: "3 lb", aisle: "Produce", store: "BJ's", meal: "Dinner", monthlyPackages: 1.5, fallbackPrice: 2.89, sourceURL: nil),
    ShoppingItem(id: "dinnerveg", name: "Value vegetables: frozen broccoli plus seasonal produce", package: "weekly mix", aisle: "Produce", store: "Stew Leonard's", meal: "Dinner", monthlyPackages: 4.0, fallbackPrice: 9.00, sourceURL: nil),
    ShoppingItem(id: "oil", name: "Canola oil or lowest-cost olive oil", package: "48 oz", aisle: "Oils", store: "BJ's", meal: "Shared pantry", monthlyPackages: 0.4, fallbackPrice: 9.99, sourceURL: "https://www.bjs.com/category/grocery/pantry/wellsley-farms-pantry/"),
    ShoppingItem(id: "broth", name: "Low-sodium bouillon or broth", package: "1 jar or carton", aisle: "Soup", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 1.0, fallbackPrice: 4.29, sourceURL: nil),
    ShoppingItem(id: "sauces", name: "Pesto, salsa and harissa", package: "assorted jars", aisle: "Condiments", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 1.0, fallbackPrice: 18.00, sourceURL: nil),
    ShoppingItem(id: "cinnamon", name: "Ground cinnamon", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "blackpepper", name: "Ground black pepper", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "garlicpowder", name: "Garlic powder", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "onionpowder", name: "Onion powder", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "paprika", name: "Smoked paprika", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "cumin", name: "Ground cumin", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "italianseasoning", name: "Italian seasoning", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "redpepper", name: "Crushed red pepper flakes", package: "1 jar", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.29, sourceURL: nil),
    ShoppingItem(id: "vinegar", name: "Store-brand apple cider or distilled vinegar", package: "32 oz", aisle: "Vinegar", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.20, fallbackPrice: 2.29, sourceURL: nil),
    ShoppingItem(id: "salt", name: "Iodized table salt", package: "1 canister", aisle: "Spices", store: "ShopRite", meal: "Shared pantry", monthlyPackages: 0.10, fallbackPrice: 1.49, sourceURL: nil)
]

let excludedIngredientTerms = ["soy", "tofu", "tempeh", "edamame", "miso", "cabbage", "coleslaw", "sauerkraut", "organic", "cottage cheese", "yogurt", "yoplait", "peanut", "walnut"]


/// What a store needs before its deals count at the register. Kept in step
/// with the "redeem" notices in dealcrawler/stores.py, which the control panel
/// shows after a scan. `mustAct` is true when skipping it means paying full price.
struct RedeemNotice {
    let title: String
    let body: String
    let mustAct: Bool
}

func redeemNotice(for store: String) -> RedeemNotice? {
    let key = store.lowercased()
    if key.contains("shoprite") {
        return RedeemNotice(
            title: "SHOPRITE: LOG IN AND LOAD YOUR COUPONS BEFORE YOU SHOP",
            body: "You must be logged in to ShopRite, because it's the only way you can load coupons to your account. Log in at shoprite.com, open Digital Coupons and tap Load to Card on each item marked LOAD COUPON FIRST. It only takes a minute - and any coupon you skip rings up at the regular price.",
            mustAct: true)
    }
    if key.contains("costco") {
        // Costco's own terms: "instant savings", "Active Costco membership
        // required for warehouse purchases", per-household limits.
        return RedeemNotice(
            title: "COSTCO: GOOD NEWS - NO CLIPPING",
            body: "Costco calls these instant savings: there are no coupons to clip or load. You just need an active Costco membership in the warehouse. Limits are per household, and a few deals are online only.",
            mustAct: false)
    }
    if key.contains("stew") {
        // Weekly specials are the week's prices. For flyer "APP DEAL" items the
        // flyer says: scan your Member ID or enter your phone number at checkout.
        return RedeemNotice(
            title: "STEW LEONARD'S: NO COUPONS TO CLIP",
            body: "These are simply this week's sale prices - all of them are on Stew's website under This Week's Specials. For anything marked APP DEAL, scan your Member ID in the free Stew Leonard's app (or give your phone number) at checkout and the deal is applied for you.",
            mustAct: false)
    }
    return nil
}

struct DetectedCoupon {
    let itemID: String
    let store: String
    let matchedTitle: String
    let savingsPerPackage: Double
    let maximumUses: Int
    let sourceURL: String
    let requiresAccountClip: Bool
}


let couponAliases: [String: [String]] = [
    "oats": ["old fashioned oats", "rolled oats", "oatmeal"],
    "blueberries": ["frozen blueberries"],
    "eggs": ["large eggs", "dozen eggs"],
    "milk": ["low fat milk", "2% milk", "lactose free milk", "dairy milk"],
    "chia": ["chia seeds"],
    "bread": ["whole grain bread", "whole wheat bread"],
    "fruit": ["bananas", "apples", "seasonal fruit"],
    "quinoa": ["quinoa"],
    "rice": ["brown rice"],
    "beans": ["canned beans", "black beans", "kidney beans", "no salt beans"],
    "tuna": ["tuna in water", "canned tuna", "light tuna", "albacore tuna"],
    "hummus": ["hummus"],
    "wraps": ["whole wheat wraps", "whole wheat tortillas", "pita bread"],
    "greens": ["fresh spinach", "fresh kale", "romaine lettuce", "leaf lettuce"],
    "lunchveg": ["fresh carrots", "fresh cucumber", "bell peppers"],
    "feta": ["feta cheese", "mozzarella cheese"],
    "whey": ["whey protein powder"],
    "snackeggs": ["large eggs", "dozen eggs"],
    "snackmilk": ["low fat milk", "2% milk", "lactose free milk", "dairy milk"],
    "chicken": ["boneless skinless chicken breast", "chicken breasts"],
    "salmon": ["atlantic salmon", "salmon fillet"],
    "shrimp": ["peeled shrimp", "raw shrimp"],
    "cod": ["cod fillet", "fresh cod"],
    "turkey": ["ground turkey"],
    "beef": ["lean ground beef", "ground beef"],
    "lentils": ["dry lentils", "brown lentils", "red lentils"],
    "pasta": ["whole wheat pasta", "whole grain pasta"],
    "tomatoes": ["diced tomatoes"],
    "sweetpotato": ["sweet potatoes"],
    "dinnerveg": ["frozen broccoli", "broccoli florets"],
    "oil": ["canola oil", "olive oil"],
    "broth": ["low sodium broth", "chicken broth", "vegetable broth", "bouillon"],
    "sauces": ["pesto", "salsa", "harissa"],
    "cinnamon": ["ground cinnamon", "cinnamon"],
    "blackpepper": ["ground black pepper", "black pepper"],
    "garlicpowder": ["garlic powder"],
    "onionpowder": ["onion powder"],
    "paprika": ["smoked paprika", "paprika"],
    "cumin": ["ground cumin", "cumin"],
    "italianseasoning": ["italian seasoning"],
    "redpepper": ["crushed red pepper", "red pepper flakes"],
    "vinegar": ["apple cider vinegar", "distilled vinegar", "white vinegar"],
    "salt": ["iodized salt", "table salt", "sea salt", "kosher salt"]
]

// Compiled once. `replacingOccurrences(options: .regularExpression)` recompiles its
// pattern on every call, and normalization runs for every alias, item and text line
// during a coupon scan — that recompilation was the scan's dominant cost.
private let couponNonKeepRegex = try! NSRegularExpression(pattern: "[^a-z0-9%.$]+")
private let couponWhitespaceRegex = try! NSRegularExpression(pattern: "\\s+")

private func collapse(_ value: String, using regex: NSRegularExpression, to replacement: String) -> String {
    let range = NSRange(value.startIndex..<value.endIndex, in: value)
    return regex.stringByReplacingMatches(in: value, range: range, withTemplate: replacement)
}

func normalizedCouponText(_ value: String) -> String {
    let folded = value.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "en_US"))
        .lowercased()
        .replacingOccurrences(of: "&amp;", with: "&")
        .replacingOccurrences(of: "&quot;", with: "\"")
        .replacingOccurrences(of: "&#39;", with: "'")
        .replacingOccurrences(of: "®", with: "")
        .replacingOccurrences(of: "™", with: "")
    return collapse(collapse(folded, using: couponNonKeepRegex, to: " "), using: couponWhitespaceRegex, to: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
}

// Aliases normalized once at startup so matching is a plain substring check.
let normalizedCouponAliases: [String: [String]] = couponAliases.mapValues { aliases in
    aliases.map(normalizedCouponText).filter { !$0.isEmpty }
}

// Matches offer text against the whole catalog — a coupon lowers an ingredient's cost
// wherever it is bought, so restricting matches to the scanned store (as before) silently
// dropped most legitimate offers. Same-store items still win ties for cleaner attribution.
func couponCatalogMatch(title: String, store: String, items: [ShoppingItem]) -> ShoppingItem? {
    let normalizedTitle = normalizedCouponText(title)
    guard !normalizedTitle.isEmpty else { return nil }
    var best: (item: ShoppingItem, score: Int)?
    for item in items {
        let aliases = normalizedCouponAliases[item.id] ?? []
        var score = aliases.reduce(0) { current, alias in
            normalizedTitle.contains(alias) ? max(current, alias.count) : current
        }
        guard score > 0 else { continue }
        if item.store == store { score += 1 }
        if best == nil || score > best!.score { best = (item, score) }
    }
    return best?.item
}

// Compiled once and reused across every scanned line (see normalizedCouponText note).
private let couponLimitRegex = try? NSRegularExpression(pattern: #"(?i)limit\s+([0-9]+)"#)
private let couponDollarRegexes: [NSRegularExpression] = [
    #"(?i)\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*off"#,
    #"(?i)save\s*\$\s*([0-9]+(?:\.[0-9]{1,2})?)"#,
    #"(?i)after\s*\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:off|instant savings)"#,
    #"(?i)\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:instant savings|digital coupon|coupon|manufacturer)"#,
    #"(?i)clip\b[^$\n]{0,24}?\$\s*([0-9]+(?:\.[0-9]{1,2})?)"#
].compactMap { try? NSRegularExpression(pattern: $0) }



// A readable third-party weekly-circular page (unlike shoprite.com, which returns 403 to a
// non-browser request). These sources publish FINAL SALE PRICES, not coupon "$ off" amounts,
// so savings are derived as (our package estimate - sale price). Weight-priced lines (e.g.
// "$1.99/lb") are skipped because a per-pound price can't be compared to a per-package estimate.

private let webSalePriceRegex = try? NSRegularExpression(pattern: #"\$\s*([0-9]+(?:\.[0-9]{1,2})?)"#)
private let webSalePerWeightRegex = try? NSRegularExpression(pattern: #"(?i)\$\s*[0-9]+(?:\.[0-9]{1,2})?\s*/?\s*(?:lb|lbs|pound|pounds|oz|ounce|ounces)\b"#)


// Imports a sales file produced by an assisted browser crawl. The XML is authored with exact
// catalog item IDs, so no fuzzy text matching is needed. Schema:
//
//   <shopriteSales store="ShopRite" date="2026-09-20">
//     <offer itemId="turkey" savings="2.00" limit="4" salePrice="2.39" note="93% lean ground turkey"/>
//     <offer itemId="eggs"   salePrice="2.49" limit="6" note="Large eggs, 18 ct"/>
//   </shopriteSales>
//
// Each <offer> needs a catalog itemId plus either `savings` (per package) or `salePrice`
// (savings is derived as our normal price - salePrice). `limit`, `store`, `salePrice`, and
// `note` are optional. Unknown item IDs and non-positive savings are ignored.
func parseSalesXML(_ data: Data, items: [ShoppingItem]) -> [DetectedCoupon] {
    guard let doc = try? XMLDocument(data: data, options: []),
          let nodes = try? doc.nodes(forXPath: "//offer") else { return [] }
    let byID = Dictionary(items.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
    // The crawler writes the store once, on the root (<shopriteSales store="...">);
    // an offer may still carry its own.
    let fileStore = doc.rootElement()?.attribute(forName: "store")?.stringValue
    var bestByItem: [String: DetectedCoupon] = [:]
    for node in nodes {
        guard let element = node as? XMLElement else { continue }
        func attr(_ name: String) -> String? { element.attribute(forName: name)?.stringValue }
        guard let itemId = attr("itemId"), let item = byID[itemId] else { continue }
        var savings = Double(attr("savings") ?? "") ?? 0
        if savings <= 0, let salePrice = Double(attr("salePrice") ?? "") {
            savings = item.fallbackPrice - salePrice
        }
        guard savings > 0 else { continue }
        let store = attr("store") ?? fileStore ?? "ShopRite"
        let limit = max(1, min(25, Int(attr("limit") ?? "") ?? 1))
        let title = attr("note") ?? item.name
        let offer = DetectedCoupon(
            itemID: item.id, store: store, matchedTitle: title,
            savingsPerPackage: min(250, savings), maximumUses: limit,
            sourceURL: "imported-xml", requiresAccountClip: false
        )
        if savings > (bestByItem[item.id]?.savingsPerPackage ?? 0) { bestByItem[item.id] = offer }
    }
    return Array(bestByItem.values)
}

// A WebView window that loads a page, lets it fully render (and the user sign in if needed),
// then harvests the whole rendered page and runs a supplied parser over it. Used both for
// signed-in retailer coupon scans and for public weekly-circular deal pages — both of which
// render their content with JavaScript, so a plain HTTP GET can't see it.

func money(_ value: Double) -> String { String(format: "$%.2f", value) }

func pdfTextHeight(_ text: String, width: CGFloat, font: NSFont) -> CGFloat {
    let paragraph = NSMutableParagraphStyle()
    paragraph.lineBreakMode = .byWordWrapping
    let attributed = NSAttributedString(string: text, attributes: [.font: font, .paragraphStyle: paragraph])
    let framesetter = CTFramesetterCreateWithAttributedString(attributed)
    let size = CTFramesetterSuggestFrameSizeWithConstraints(framesetter, CFRange(location: 0, length: attributed.length), nil, CGSize(width: width, height: 1000), nil)
    return max(ceil(size.height) + 2, ceil(font.ascender - font.descender + font.leading) + 2)
}

@discardableResult
func drawPDFText(_ text: String, in context: CGContext, x: CGFloat, y: CGFloat, width: CGFloat, font: NSFont, color: NSColor = .black, align: NSTextAlignment = .left) -> CGFloat {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = align
    paragraph.lineBreakMode = .byWordWrapping
    let attributed = NSAttributedString(string: text, attributes: [.font: font, .foregroundColor: color, .paragraphStyle: paragraph])
    let framesetter = CTFramesetterCreateWithAttributedString(attributed)
    let height = pdfTextHeight(text, width: width, font: font)
    context.saveGState()
    context.translateBy(x: x, y: y + height)
    context.scaleBy(x: 1, y: -1)
    context.textMatrix = .identity
    context.textPosition = .zero
    let path = CGMutablePath()
    path.addRect(CGRect(x: 0, y: 0, width: width, height: height))
    let frame = CTFramesetterCreateFrame(framesetter, CFRange(location: 0, length: attributed.length), path, nil)
    CTFrameDraw(frame, context)
    context.restoreGState()
    return height
}

func drawPDFLine(_ text: String, in context: CGContext, x: CGFloat, y: CGFloat, font: NSFont, color: NSColor = .black) {
    let attributed = NSAttributedString(string: text, attributes: [.font: font, .foregroundColor: color])
    let line = CTLineCreateWithAttributedString(attributed)
    context.saveGState()
    context.translateBy(x: x, y: y + font.ascender)
    context.scaleBy(x: 1, y: -1)
    context.textMatrix = .identity
    context.textPosition = .zero
    CTLineDraw(line, context)
    context.restoreGState()
}

private func primePDFPage(_ context: CGContext) {
    // Quartz can intermittently omit the leading subpaths of the first complex
    // vector operation on a continuation page. A harmless white pixel makes the
    // heading the second operation and keeps every glyph stable when printed or
    // rendered by Poppler/Preview.
    context.saveGState()
    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: 1, height: 1))
    context.restoreGState()
}

@discardableResult
func drawPDFOutlinedHeading(_ text: String, in context: CGContext, x: CGFloat, y: CGFloat, size: CGFloat, color: NSColor = .black) -> CGFloat {
    let font = NSFont(name: "Helvetica-Bold", size: size) ?? .boldSystemFont(ofSize: size)
    let attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color]
    let measured = (text as NSString).size(withAttributes: attributes)
    let width = max(8, ceil(measured.width) + 6)
    let height = max(8, ceil(font.ascender - font.descender + font.leading) + 6)
    let scale: CGFloat = 3
    let pixelsWide = Int(ceil(width * scale))
    let pixelsHigh = Int(ceil(height * scale))
    guard let bitmap = CGContext(
        data: nil,
        width: pixelsWide,
        height: pixelsHigh,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return height }

    bitmap.scaleBy(x: scale, y: scale)
    bitmap.translateBy(x: 0, y: height)
    bitmap.scaleBy(x: 1, y: -1)
    drawPDFLine(text, in: bitmap, x: 3, y: 2, font: font, color: color)
    guard let image = bitmap.makeImage() else { return height }

    context.saveGState()
    context.interpolationQuality = .high
    context.translateBy(x: x, y: y + height)
    context.scaleBy(x: 1, y: -1)
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    context.restoreGState()
    return height
}

func estimateForCategory(_ category: String?) -> Double {
    let value = (category ?? "").lowercased()
    if value.contains("meat") || value.contains("poultry") { return 6.99 }
    if value.contains("seafood") { return 10.99 }
    if value.contains("dairy") || value.contains("egg") { return 4.49 }
    if value.contains("fruit") || value.contains("vegetable") || value.contains("produce") { return 3.49 }
    if value.contains("grain") || value.contains("bread") || value.contains("cereal") { return 3.49 }
    if value.contains("oil") || value.contains("nut") || value.contains("seed") { return 6.99 }
    return 3.99
}

struct PlannedRow {
    let item: ShoppingItem
    let quantity: Int
    let grossLineTotal: Double
    let couponSavings: Double
    let lineTotal: Double
}

struct ShoppingPlan {
    let rows: [PlannedRow]
    let estimatedTotal: Double
    let error: Double
    let confidence: String
    let targetSpend: Double
    let omittedItems: Int
    let grossSubtotal: Double
    let couponSavings: Double
    let prioritizedSaleItems: Int

    var likelyLow: Double { estimatedTotal * (1 - error) }
    var likelyHigh: Double { estimatedTotal * (1 + error) }
}

func budgetPriority(for item: ShoppingItem, goal: NutritionGoal) -> Int {
    let essential = Set(["oats", "eggs", "chia", "rice", "beans", "lentils", "pasta", "tomatoes", "sweetpotato", "beef", "oil", "cinnamon", "blackpepper", "garlicpowder", "onionpowder", "paprika", "cumin", "italianseasoning", "redpepper", "vinegar"])
    if essential.contains(item.id) { return 1 }
    let frugalProtein = Set(["milk", "chicken", "snackeggs", "snackmilk"])
    if frugalProtein.contains(item.id) { return goal == .buildMuscle ? 2 : 3 }
    let frugalProduce = Set(["fruit", "greens", "lunchveg", "dinnerveg", "bread", "wraps", "broth"])
    if frugalProduce.contains(item.id) { return 3 }
    let moderate = Set(["tuna", "turkey", "beef", "hummus", "blueberries"])
    if moderate.contains(item.id) { return 5 }
    let premium = Set(["whey", "salmon", "shrimp", "cod", "feta", "chia", "sauces", "quinoa"])
    return premium.contains(item.id) ? 9 : 7
}

// Cutting is capped at 2,800 kcal/day (individual days never exceed it). Maintenance is the
// person's sedentary TDEE; Build Muscle uses the SAME calories (body recomposition — build muscle
// at maintenance, which works for higher-body-fat/novice trainees). No calorie floor.
let maximumDailyCalories = 2800

// Protein is based on IDEAL (BMI-25) body weight, not total/fat weight, so it never scales up
// wastefully for a heavier body. 1.8 g per kg of ideal weight sits just above the ~1.6 g/kg point
// where muscle-building benefit plateaus (Morton 2018) — enough to build, without going over.
let proteinPerIdealKg = 1.8

// The size formula (weight x 10 + height x 4) approximates a LIGHTLY-ACTIVE TDEE; this converts
// it to a SEDENTARY maintenance (activity 1.2 vs 1.375). Change if an activity selector is added.
let sedentaryActivityFactor = 1.2 / 1.375

func personalizedNutritionTarget(for options: ListOptions) -> PersonalizedNutritionTarget {
    guard let height = options.heightInches, let weight = options.weightPounds,
          height >= 48, height <= 96, weight >= 80, weight <= 700 else {
        // No valid profile: sedentary-ish default with a moderate protein target.
        let protein = 150, fat = 70
        let calories = 2600
        let carbohydrate = max(100, (calories - (protein * 4 + fat * 9)) / 4)
        let fallback = NutritionEstimate(proteinGrams: protein, carbohydrateGrams: carbohydrate, fatGrams: fat)
        return PersonalizedNutritionTarget(macros: fallback, estimatedMaintenanceCalories: calories, goalMultiplier: 1.0, planningWeightPounds: 180)
    }

    let heightMeters = height * 0.0254
    let idealWeightKg = 25.0 * heightMeters * heightMeters              // BMI-25 "ideal" weight
    let bmi25ReferencePounds = idealWeightKg * 2.2046226218
    let planningWeight = min(weight, bmi25ReferencePounds * 1.20)

    // Sedentary maintenance (true TDEE for a mostly-inactive person).
    let sedentaryMaintenance = (weight * 10.0 + height * 4.0) * sedentaryActivityFactor

    // Cutting = ~20% deficit off maintenance (capped at 2,800). Maintenance and Build Muscle
    // both target maintenance calories (recomposition).
    let goalMultiplier: Double
    let fatPerPlanningPound: Double
    switch options.nutritionGoal {
    case .buildMuscle:
        goalMultiplier = 1.00   // recomp: build at maintenance
        fatPerPlanningPound = 0.35
    case .cutting:
        goalMultiplier = 0.80   // ~20% deficit off maintenance (evidence-based cut)
        fatPerPlanningPound = 0.30
    case .maintenance:
        goalMultiplier = 1.00
        fatPerPlanningPound = 0.32
    }

    // Protein from ideal weight (capped by frame, not fat); fat from the height-capped planning weight.
    let protein = max(60, Int((idealWeightKg * proteinPerIdealKg).rounded()))
    let fat = max(40, Int((planningWeight * fatPerPlanningPound).rounded()))
    let goalCalories = sedentaryMaintenance * goalMultiplier
    let desiredCalories = options.nutritionGoal == .cutting
        ? min(Double(maximumDailyCalories), goalCalories)
        : goalCalories
    // Floor the carbohydrate grams (truncate) so 4P+4C+9F never rounds above the target.
    let carbohydrate = max(100, Int((desiredCalories - Double(protein * 4 + fat * 9)) / 4.0))
    return PersonalizedNutritionTarget(
        macros: NutritionEstimate(proteinGrams: protein, carbohydrateGrams: carbohydrate, fatGrams: fat),
        estimatedMaintenanceCalories: Int(sedentaryMaintenance.rounded()),
        goalMultiplier: goalMultiplier,
        planningWeightPounds: planningWeight
    )
}

func bodySizeMultiplier(for options: ListOptions) -> Double {
    let target = personalizedNutritionTarget(for: options)
    return min(1.60, max(0.60, Double(target.macros.calories) / 2500.0))
}

func profileDescription(for options: ListOptions) -> String {
    guard let totalInches = options.heightInches, let pounds = options.weightPounds else { return "standard portion profile" }
    let feet = Int(totalInches) / 12
    let inches = Int(totalInches.rounded()) % 12
    let target = personalizedNutritionTarget(for: options)
    return "\(feet)'\(inches)\", \(Int(pounds.rounded())) lb | \(options.nutritionGoal.rawValue) daily-average target \(target.macros.summary) | portion factor \(String(format: "%.2f", bodySizeMultiplier(for: options)))x"
}

func makeShoppingPlan(options: ListOptions, items: [ShoppingItem], prices: PriceBook, favorites: Set<String>, coupons: [String: Double] = [:], couponLimits: [String: Int] = [:], requiredItemIDs: Set<String> = [], excludedItemIDs: Set<String> = []) -> ShoppingPlan {
    let checked = prices.retailerChecked.count
    let error = checked >= 4 ? 0.20 : 0.25
    let confidence = checked >= 4 ? "Medium" : "Low-to-moderate"
    let targetSpend = min(options.budgetMax, max(options.budgetMin, 250.0))
    // Calculate personalized package needs first, then choose the most economical
    // combination that approaches the user's frugal target.
    let scale = Double(options.days) / 30.0 * Double(options.people)
    let eligible = items.filter { item in
        // A confirmed sale swap drops the replaced item — but never one the user pinned
        // as a favorite or that a recipe requires.
        if excludedItemIDs.contains(item.id), !requiredItemIDs.contains(item.id), !favorites.contains(item.id) { return false }
        let mealOK = item.meal == "Shared pantry" || options.enabledMeals.contains(item.meal)
        return requiredItemIDs.contains(item.id) || favorites.contains(item.id) || (mealOK && options.enabledStores.contains(item.store))
    }.map { item -> PlannedRow in
        let personalizedScale = bodySizeMultiplier(for: options)
        let quantity = max(1, Int(ceil(item.monthlyPackages * scale * personalizedScale)))
        let gross = prices.price(for: item) * Double(quantity)
        let allowedUses = max(0, min(quantity, couponLimits[item.id] ?? quantity))
        let requestedSavings = max(0, coupons[item.id] ?? 0) * Double(allowedUses)
        let savings = min(gross, requestedSavings)
        return PlannedRow(item: item, quantity: quantity, grossLineTotal: gross, couponSavings: savings, lineTotal: gross - savings)
    }

    var included = eligible.filter { requiredItemIDs.contains($0.item.id) || budgetPriority(for: $0.item, goal: options.nutritionGoal) == 1 || favorites.contains($0.item.id) }
    var includedIDs = Set(included.map { $0.item.id })
    // What lands in the basket is decided on need alone, at the shelf price, with
    // offers deliberately ignored. Look the deals up first and the coupons start
    // choosing your groceries for you. Deals are applied to this list once it is
    // settled, and proposeSaleSwaps then offers substitutes for what is on it.
    var shelfTotal = included.reduce(0) { $0 + $1.grossLineTotal }
    func needPriority(_ row: PlannedRow) -> Int {
        budgetPriority(for: row.item, goal: options.nutritionGoal)
    }
    let candidates = eligible.filter { !includedIDs.contains($0.item.id) }.sorted {
        let left = (needPriority($0), $0.grossLineTotal, $0.item.name)
        let right = (needPriority($1), $1.grossLineTotal, $1.item.name)
        return left < right
    }

    let availableCents = max(0, Int(((options.budgetMax - shelfTotal) * 100).rounded(.down)))
    if availableCents > 0, !candidates.isEmpty {
        struct CandidateSelection {
            let indexes: [Int]
            let valueScore: Int
        }
        var selections = [CandidateSelection?](repeating: nil, count: availableCents + 1)
        selections[0] = CandidateSelection(indexes: [], valueScore: 0)
        for (index, row) in candidates.enumerated() {
            let cost = max(1, Int((row.grossLineTotal * 100).rounded()))
            guard cost <= availableCents else { continue }
            let rowScore = max(1, 12 - needPriority(row))
            for subtotal in stride(from: availableCents, through: cost, by: -1) {
                guard let previous = selections[subtotal - cost] else { continue }
                let proposed = CandidateSelection(indexes: previous.indexes + [index], valueScore: previous.valueScore + rowScore)
                if selections[subtotal] == nil || proposed.valueScore > selections[subtotal]!.valueScore {
                    selections[subtotal] = proposed
                }
            }
        }
        let targetCents = Int((targetSpend * 100).rounded())
        let baseCents = Int((shelfTotal * 100).rounded())
        let bestSubtotal = selections.indices.filter { selections[$0] != nil }.min { left, right in
            let leftDistance = abs(targetCents - (baseCents + left))
            let rightDistance = abs(targetCents - (baseCents + right))
            if leftDistance != rightDistance { return leftDistance < rightDistance }
            let leftScore = selections[left]?.valueScore ?? 0
            let rightScore = selections[right]?.valueScore ?? 0
            if leftScore != rightScore { return leftScore > rightScore }
            return left < right
        } ?? 0
        for index in selections[bestSubtotal]?.indexes ?? [] {
            let row = candidates[index]
            included.append(row)
            includedIDs.insert(row.item.id)
            shelfTotal += row.grossLineTotal
        }
    }

    if options.groupByStore {
        included.sort { ($0.item.store, $0.item.aisle, $0.item.name) < ($1.item.store, $1.item.aisle, $1.item.name) }
    } else {
        included.sort { ($0.item.meal, $0.item.aisle, $0.item.name) < ($1.item.meal, $1.item.aisle, $1.item.name) }
    }

    let total = included.reduce(0) { $0 + $1.lineTotal }
    let grossSubtotal = included.reduce(0) { $0 + $1.grossLineTotal }
    let couponSavings = included.reduce(0) { $0 + $1.couponSavings }
    return ShoppingPlan(
        rows: included,
        estimatedTotal: total,
        error: error,
        confidence: confidence,
        targetSpend: targetSpend,
        omittedItems: max(0, eligible.count - included.count),
        grossSubtotal: grossSubtotal,
        couponSavings: couponSavings,
        prioritizedSaleItems: included.filter { options.prioritizeSales && options.saleItemIDs.contains($0.item.id) && $0.couponSavings > 0 }.count
    )
}

struct SaleSwap {
    let fromID: String
    let toID: String
    let fromName: String
    let toName: String
    let store: String
    let estimatedSavings: Double
}

// Interchangeable catalog items by role. Swaps only ever happen inside one group, so a
// protein is only replaced by another protein, a grain by a grain, and so on. Spices and
// shared-pantry staples are intentionally absent — there's no sensible substitute for them.
let substitutionGroups: [[String]] = [
    ["chicken", "turkey", "beef", "salmon", "shrimp", "cod", "tuna"],
    ["greens", "lunchveg", "dinnerveg", "fruit"],
    ["rice", "quinoa", "pasta", "sweetpotato"],
    ["beans", "lentils"],
    ["milk", "snackmilk"],
    ["eggs", "snackeggs"],
    ["bread", "wraps"],
    ["oats", "chia", "blueberries"]
]

func substitutionGroup(for id: String) -> [String] {
    substitutionGroups.first { $0.contains(id) } ?? []
}

// Given a finalized plan, propose replacing optional (non-recipe, non-favorite, non-sale)
// items with an on-sale sibling in the same group when the sibling is genuinely cheaper net
// of its offer. Pure and side-effect free so the caller can preview before applying.
func proposeSaleSwaps(plan: ShoppingPlan, options: ListOptions, items: [ShoppingItem], prices: PriceBook, favorites: Set<String>, coupons: [String: Double], couponLimits: [String: Int], requiredItemIDs: Set<String>) -> [SaleSwap] {
    guard options.prioritizeSales, !options.saleItemIDs.isEmpty else { return [] }
    let scale = Double(options.days) / 30.0 * Double(options.people)
    let personalizedScale = bodySizeMultiplier(for: options)
    let itemByID = Dictionary(items.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
    let includedIDs = Set(plan.rows.map { $0.item.id })

    func projectedNet(_ item: ShoppingItem) -> Double {
        let quantity = max(1, Int(ceil(item.monthlyPackages * scale * personalizedScale)))
        let gross = prices.price(for: item) * Double(quantity)
        let allowedUses = max(0, min(quantity, couponLimits[item.id] ?? quantity))
        let savings = min(gross, max(0, coupons[item.id] ?? 0) * Double(allowedUses))
        return gross - savings
    }

    var swaps: [SaleSwap] = []
    var usedTargets = Set<String>()
    for row in plan.rows {
        let fromID = row.item.id
        let alreadyOnSale = options.saleItemIDs.contains(fromID) && row.couponSavings > 0
        guard !requiredItemIDs.contains(fromID), !favorites.contains(fromID), !alreadyOnSale else { continue }
        let group = substitutionGroup(for: fromID)
        guard !group.isEmpty else { continue }
        var best: SaleSwap?
        for candidateID in group where candidateID != fromID {
            guard options.saleItemIDs.contains(candidateID), (coupons[candidateID] ?? 0) > 0,
                  !includedIDs.contains(candidateID), !usedTargets.contains(candidateID),
                  let candidate = itemByID[candidateID], options.enabledStores.contains(candidate.store) else { continue }
            let savings = row.lineTotal - projectedNet(candidate)
            guard savings > 0.005 else { continue }
            if best == nil || savings > best!.estimatedSavings {
                best = SaleSwap(fromID: fromID, toID: candidateID, fromName: row.item.name, toName: candidate.name, store: candidate.store, estimatedSavings: savings)
            }
        }
        if let swap = best {
            swaps.append(swap)
            usedTargets.insert(swap.toID)
        }
    }
    return swaps.sorted { $0.estimatedSavings > $1.estimatedSavings }
}

func apiIngredientName(for item: ShoppingItem) -> String {
    let names: [String: String] = [
        "oats": "oats", "blueberries": "blueberries", "eggs": "eggs",
        "milk": "milk", "chia": "chia seeds",
        "bread": "whole grain bread", "fruit": "apples", "quinoa": "quinoa", "rice": "brown rice",
        "beans": "beans", "tuna": "tuna", "hummus": "hummus", "wraps": "whole wheat tortillas",
        "greens": "spinach", "lunchveg": "carrots", "feta": "feta", "chicken": "chicken breast",
        "salmon": "salmon", "shrimp": "shrimp", "cod": "cod", "turkey": "ground turkey",
        "beef": "lean ground beef", "lentils": "lentils", "pasta": "whole wheat pasta", "tomatoes": "tomatoes",
        "sweetpotato": "sweet potatoes", "dinnerveg": "broccoli", "oil": "olive oil", "broth": "vegetable stock",
        "sauces": "salsa", "cinnamon": "spices", "blackpepper": "spices", "garlicpowder": "spices",
        "onionpowder": "spices", "paprika": "spices", "cumin": "spices", "italianseasoning": "spices",
        "redpepper": "spices", "vinegar": "spices", "salt": "salt", "whey": "whey protein",
        "snackeggs": "eggs", "snackmilk": "milk"
    ]
    return names[item.id] ?? item.name
}

func estimateMacrosFromIngredients(title: String, ingredients: [String]) -> NutritionEstimate {
    let text = (title + " " + ingredients.joined(separator: " ")).lowercased()
    var protein = 14
    var carbohydrates = 38
    var fat = 9

    if ["chicken", "turkey"].contains(where: { text.contains($0) }) { protein = 40; fat = max(fat, 11) }
    if text.contains("beef") { protein = 35; fat = max(fat, 18) }
    if ["salmon", "fish", "tuna", "cod", "shrimp", "prawn"].contains(where: { text.contains($0) }) { protein = 34; fat = max(fat, text.contains("salmon") ? 16 : 9) }
    if text.contains("egg") { protein = max(protein, 22); fat = max(fat, 13) }
    if ["bean", "lentil", "chickpea"].contains(where: { text.contains($0) }) { protein = max(protein, 20); carbohydrates = max(carbohydrates, 58) }
    if ["pasta", "noodle", "rice", "potato", "wrap", "pita", "oat"].contains(where: { text.contains($0) }) { carbohydrates = max(carbohydrates, 62) }
    if ["almond", "hazelnut", "nut butter"].contains(where: { text.contains($0) }) { fat = max(fat, 17); protein = max(protein, 18) }
    if ["cream", "cheese", "coconut"].contains(where: { text.contains($0) }) { fat = max(fat, 20) }
    if ["salad", "lettuce", "spinach", "broccoli", "vegetable"].contains(where: { text.contains($0) }) && carbohydrates < 45 { carbohydrates = 32 }

    return NutritionEstimate(proteinGrams: protein, carbohydrateGrams: carbohydrates, fatGrams: fat)
}

let builtInRecipes: [Recipe] = [
    Recipe(title: "Apple Chia Oatmeal", baseServings: 2, readyMinutes: 12,
           ingredients: ["1 cup oats", "2 cups milk or water", "1 apple, chopped", "2 tablespoons chia seeds", "1/2 teaspoon ground cinnamon"],
           steps: ["Simmer oats with milk or water until creamy.", "Stir in apple and cinnamon for the final 3 minutes.", "Divide into bowls and top with chia seeds."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 15, carbohydrateGrams: 59, fatGrams: 9)),
    Recipe(title: "Spinach Egg Toast", baseServings: 2, readyMinutes: 15,
           ingredients: ["4 eggs", "4 slices whole-grain bread", "2 cups greens", "1 teaspoon oil", "1/4 teaspoon black pepper", "1/4 teaspoon garlic powder"],
           steps: ["Toast the bread.", "Wilt greens in oil, add beaten eggs, and scramble until set.", "Serve the eggs and greens over toast."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 23, carbohydrateGrams: 33, fatGrams: 14)),
    Recipe(title: "Banana Chia Overnight Oats", baseServings: 2, readyMinutes: 8,
           ingredients: ["1 cup oats", "1 1/2 cups milk", "1 banana, sliced", "2 tablespoons chia seeds", "Cinnamon"],
           steps: ["Mix oats, milk, chia seeds, and cinnamon.", "Refrigerate overnight.", "Top with banana before eating."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 14, carbohydrateGrams: 57, fatGrams: 9)),
    Recipe(title: "Vegetable Egg Rice Bowls", baseServings: 2, readyMinutes: 25,
           ingredients: ["1 cup cooked brown rice", "3 eggs", "2 cups mixed vegetables", "1 teaspoon oil", "1 teaspoon vinegar", "1/4 teaspoon garlic powder", "1/4 teaspoon black pepper"],
           steps: ["Warm the rice and vegetables in a skillet.", "Push them aside and scramble the eggs until set.", "Add vinegar, garlic powder, and black pepper; divide into two bowls."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 15, carbohydrateGrams: 35, fatGrams: 10)),
    Recipe(title: "Bean and Crunchy Lettuce Wraps", baseServings: 2, readyMinutes: 15,
           ingredients: ["1 can beans, drained", "4 whole-wheat wraps", "2 cups chopped lettuce and cucumber", "1 chopped tomato", "1 tablespoon vinegar", "1/2 teaspoon ground cumin", "1/2 teaspoon smoked paprika", "1/4 teaspoon garlic powder"],
           steps: ["Mash half the beans and mix with the remaining beans.", "Season lettuce, cucumber, and tomato with vinegar, cumin, paprika, and garlic powder.", "Fill and roll the wraps."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 19, carbohydrateGrams: 77, fatGrams: 7)),
    Recipe(title: "Tomato Lentil Soup", baseServings: 2, readyMinutes: 35,
           ingredients: ["3/4 cup dry lentils", "1 can diced tomatoes", "3 cups low-sodium broth", "1 cup carrots or mixed vegetables", "1 teaspoon Italian seasoning", "1/4 teaspoon black pepper"],
           steps: ["Combine everything in a saucepan and bring to a boil.", "Reduce heat and simmer until lentils are tender, about 25 minutes.", "Add water if needed; finish with Italian seasoning and black pepper."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 21, carbohydrateGrams: 62, fatGrams: 2)),
    Recipe(title: "Chicken Broccoli Brown Rice", baseServings: 2, readyMinutes: 30,
           ingredients: ["10 ounces chicken breast, sliced", "2 cups broccoli or mixed vegetables", "1 1/2 cups cooked brown rice", "2 teaspoons oil", "1 tablespoon vinegar", "1/2 teaspoon garlic powder", "1/2 teaspoon smoked paprika", "1/4 teaspoon black pepper"],
           steps: ["Cook chicken in oil until it reaches 165 F.", "Add vegetables and cook until tender-crisp.", "Season and serve over brown rice."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 51, carbohydrateGrams: 44, fatGrams: 10)),
    Recipe(title: "Lean Beef Vegetable Stir-Fry", baseServings: 2, readyMinutes: 25,
           ingredients: ["12 ounces 93% lean ground beef", "3 cups mixed vegetables", "1 1/2 cups cooked brown rice", "2 teaspoons oil", "1 tablespoon vinegar", "1/2 teaspoon garlic powder", "1/4 teaspoon crushed red pepper flakes"],
           steps: ["Brown the beef in a skillet until it reaches 160 F; drain if needed.", "Add vegetables and stir-fry until tender.", "Season and serve with brown rice."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 47, carbohydrateGrams: 46, fatGrams: 23)),
    Recipe(title: "Whole-Wheat Pasta with Tomato and Greens", baseServings: 2, readyMinutes: 25,
           ingredients: ["6 ounces whole-wheat pasta", "1 can diced tomatoes", "2 cups greens", "1 teaspoon oil", "1 teaspoon Italian seasoning", "1/4 teaspoon black pepper"],
           steps: ["Cook pasta according to its package.", "Simmer tomatoes with oil, Italian seasoning, and black pepper; stir in greens to wilt.", "Toss sauce with drained pasta."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 13, carbohydrateGrams: 74, fatGrams: 4)),
    Recipe(title: "Sweet Potato Black Bean Bowls", baseServings: 2, readyMinutes: 35,
           ingredients: ["1 large sweet potato, cubed", "1 can beans, drained", "1 1/2 cups cooked brown rice", "2 cups spinach or kale", "2 teaspoons oil", "1/2 teaspoon ground cumin", "1/2 teaspoon smoked paprika", "1/4 teaspoon onion powder"],
           steps: ["Roast or skillet-cook the sweet potato with cumin, paprika, and onion powder until tender.", "Warm beans and rice.", "Divide into bowls with greens."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 16, carbohydrateGrams: 91, fatGrams: 4)),
    Recipe(title: "Chicken Tomato Lentil Stew", baseServings: 2, readyMinutes: 40,
           ingredients: ["8 ounces chicken breast, cubed", "1/2 cup dry lentils", "1 can diced tomatoes", "3 cups broth", "2 cups mixed vegetables", "1 teaspoon Italian seasoning", "1/4 teaspoon black pepper", "1 teaspoon vinegar"],
           steps: ["Combine ingredients and bring to a gentle boil.", "Simmer until lentils are tender and chicken reaches 165 F.", "Finish with Italian seasoning, black pepper, and vinegar."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 50, carbohydrateGrams: 50, fatGrams: 5)),
    Recipe(title: "Garlic Vegetable Noodles", baseServings: 2, readyMinutes: 25,
           ingredients: ["6 ounces whole-wheat pasta", "2 cups mixed vegetables", "2 teaspoons oil", "1 teaspoon vinegar", "Warm water", "1/2 teaspoon garlic powder", "1/4 teaspoon crushed red pepper flakes"],
           steps: ["Cook pasta and vegetables; reserve some cooking water.", "Whisk oil, vinegar, garlic powder, red pepper flakes, and warm water into a sauce.", "Toss everything together."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 13, carbohydrateGrams: 75, fatGrams: 7)),
    Recipe(title: "Savory Oats with Egg and Greens", baseServings: 2, readyMinutes: 18,
           ingredients: ["1 cup oats", "2 1/2 cups low-sodium broth or water", "2 eggs", "2 cups greens", "1/2 teaspoon Italian seasoning", "1/4 teaspoon black pepper"],
           steps: ["Simmer oats in broth with Italian seasoning and black pepper until thick.", "Stir in greens until wilted.", "Top each bowl with a cooked egg."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 14, carbohydrateGrams: 31, fatGrams: 8)),
    Recipe(title: "Tomato Bean Pita Pockets", baseServings: 2, readyMinutes: 15,
           ingredients: ["1 can beans, drained", "2 whole-wheat pitas or wraps", "1 chopped tomato", "2 cups spinach or lettuce", "1 tablespoon vinegar", "1 teaspoon oil", "1/2 teaspoon ground cumin", "1/4 teaspoon garlic powder"],
           steps: ["Toss beans, tomato, and greens with vinegar, oil, cumin, and garlic powder.", "Warm the pitas or wraps.", "Fill and serve."], sourceURL: nil, sourceName: "Built-in budget recipe", macrosPerServing: NutritionEstimate(proteinGrams: 17, carbohydrateGrams: 72, fatGrams: 5))
]

func recipeCountNeeded(for days: Int) -> Int {
    func groups(_ count: Int) -> Int {
        if count <= 0 { return 0 }
        if count == 1 { return 1 }
        return count % 2 == 0 ? count / 2 : (count - 1) / 2
    }
    return groups((days + 1) / 2) + groups(days / 2)
}

func makeRecipeSchedule(days: Int, people: Int, recipeCount: Int) -> [ScheduledRecipe] {
    guard recipeCount > 0 else { return [] }
    var schedule: [ScheduledRecipe] = []
    var nextRecipe = 0
    for parityStart in [1, 2] {
        let daysForParity = stride(from: parityStart, through: days, by: 2).map { $0 }
        var index = 0
        while index < daysForParity.count {
            let remaining = daysForParity.count - index
            let groupSize = remaining == 3 ? 3 : min(2, remaining)
            let group = Array(daysForParity[index..<(index + groupSize)])
            let recipeIndex = nextRecipe % recipeCount
            nextRecipe += 1
            let batchServings = group.count * people
            for (position, day) in group.enumerated() {
                schedule.append(ScheduledRecipe(day: day, recipeIndex: recipeIndex, prepDay: group[0], batchServings: batchServings, isPrepDay: position == 0))
            }
            index += groupSize
        }
    }
    return schedule.sorted { $0.day < $1.day }
}

func recipeMatchesLifestyle(_ recipe: Recipe, category: String = "", lifestyle: String) -> Bool {
    if category.lowercased() == "dessert" { return false }
    let text = (recipe.title + " " + recipe.ingredients.joined(separator: " ")).lowercased()
    if excludedIngredientTerms.contains(where: { text.contains($0) }) { return false }
    if ["bacon", "sausage", "hot dog", "deep fried", "corned beef"].contains(where: { text.contains($0) }) { return false }
    let landMeat = ["chicken", "turkey", "beef", "pork", "lamb", "bacon", "sausage"]
    let seafood = ["fish", "salmon", "tuna", "shrimp", "prawn", "cod", "anchovy"]
    if lifestyle == "Vegetarian" && (landMeat + seafood).contains(where: { text.contains($0) }) { return false }
    if lifestyle == "Pescatarian" && landMeat.contains(where: { text.contains($0) }) { return false }
    if lifestyle == "Plant-forward" {
        let plants = ["bean", "lentil", "vegetable", "spinach", "broccoli", "lettuce", "tomato", "sweet potato", "oat"]
        if !plants.contains(where: { text.contains($0) }) { return false }
    }
    if lifestyle == "High-fiber balanced" {
        let fiberFoods = ["bean", "lentil", "oat", "brown rice", "whole wheat", "whole-grain", "vegetable", "sweet potato"]
        if !fiberFoods.contains(where: { text.contains($0) }) { return false }
    }
    if (lifestyle == "DASH" || lifestyle == "Low-sodium heart healthy") && ["stock cube", "bouillon cube"].contains(where: { text.contains($0) }) { return false }
    return true
}

func nutritionGoalScore(_ recipe: Recipe, goal: NutritionGoal) -> Int {
    let text = (recipe.title + " " + recipe.ingredients.joined(separator: " ")).lowercased()
    let protein = ["chicken", "turkey", "beef", "fish", "salmon", "tuna", "shrimp", "cod", "egg", "bean", "lentil", "milk"]
    let produce = ["vegetable", "broccoli", "spinach", "greens", "lettuce", "tomato", "carrot", "sweet potato"]
    let wholeFoods = ["oat", "brown rice", "whole wheat", "whole-grain", "bean", "lentil", "vegetable", "fruit"]
    switch goal {
    case .buildMuscle:
        return protein.reduce(0) { $0 + (text.contains($1) ? 2 : 0) }
    case .cutting:
        let positive = protein.reduce(0) { $0 + (text.contains($1) ? 1 : 0) } + produce.reduce(0) { $0 + (text.contains($1) ? 2 : 0) }
        let negative = ["cream", "fried", "sugar", "syrup"].reduce(0) { $0 + (text.contains($1) ? 2 : 0) }
        return positive - negative
    case .maintenance:
        return wholeFoods.reduce(0) { $0 + (text.contains($1) ? 1 : 0) }
    }
}

func saleTerms(for itemIDs: Set<String>) -> [String] {
    catalog.filter { itemIDs.contains($0.id) }.flatMap { item in
        [apiIngredientName(for: item), item.name] + (couponAliases[item.id] ?? [])
    }.map(normalizedCouponText).filter { !$0.isEmpty }
}

func adjustedForProfile(_ recipe: Recipe, options: ListOptions) -> Recipe {
    let baseMacros = recipe.macrosPerServing
    let factor = bodySizeMultiplier(for: options)
    let adjustedMacros = NutritionEstimate(
        proteinGrams: Int((Double(baseMacros.proteinGrams) * factor).rounded()),
        carbohydrateGrams: Int((Double(baseMacros.carbohydrateGrams) * factor).rounded()),
        fatGrams: Int((Double(baseMacros.fatGrams) * factor).rounded())
    )
    let target = personalizedNutritionTarget(for: options)
    let note = "\(options.nutritionGoal.rawValue): multiply each listed per-person ingredient amount by about \(String(format: "%.2f", factor))x. This is one meal's serving estimate, not the full macro target. Breakfast, lunch, dinner and snacks vary by day around the personalized \(target.macros.calories)-kcal seven-day average."
    var adjusted = recipe
    adjusted.goalNote = note
    adjusted.macrosPerServing = adjustedMacros
    return adjusted
}

func recipesForPlan(apiRecipes: [Recipe], days: Int, lifestyle: String, options: ListOptions) -> [Recipe] {
    let needed = recipeCountNeeded(for: days)
    var result: [Recipe] = []
    func score(_ recipe: Recipe) -> Int {
        // Ranked on the goal only. A discount must not decide what you eat this
        // week; it gets its say later, as a substitute for something already needed.
        nutritionGoalScore(recipe, goal: options.nutritionGoal)
    }
    let rankedAPI = apiRecipes.filter { recipeMatchesLifestyle($0, lifestyle: lifestyle) }.sorted { score($0) > score($1) }
    let rankedBuiltIns = builtInRecipes.filter { recipeMatchesLifestyle($0, lifestyle: lifestyle) }.sorted { score($0) > score($1) }
    for recipe in rankedAPI where result.count < needed { result.append(recipe) }
    for recipe in rankedBuiltIns where result.count < needed && !result.contains(where: { $0.title == recipe.title }) { result.append(recipe) }
    if result.isEmpty { result = Array(builtInRecipes.prefix(max(1, needed))) }
    return result.map { adjustedForProfile($0, options: options) }
}

struct RecipeShoppingCoverage {
    let items: [ShoppingItem]
    let requiredItemIDs: Set<String>
    let coveredIngredientLines: Int
    let waterOnlyLines: Int
    let supplementalItemIDs: Set<String>
}

func catalogItemIDs(forIngredient ingredient: String) -> Set<String> {
    let text = normalizedCouponText(ingredient)
    var ids = Set<String>()
    func add(_ id: String, when terms: [String]) {
        if terms.contains(where: { text.contains(normalizedCouponText($0)) }) { ids.insert(id) }
    }

    add("oats", when: ["oats", "oatmeal", "rolled oat"])
    add("blueberries", when: ["blueberry", "blueberries"])
    add("eggs", when: ["egg", "eggs"])
    if !["coconut milk", "almond milk", "oat milk", "cashew milk"].contains(where: text.contains) {
        add("milk", when: ["milk"])
    }
    add("chia", when: ["chia"])
    add("bread", when: ["whole grain bread", "whole wheat bread", "toast"])
    if !text.contains("blueberr") { add("fruit", when: ["apple", "banana", "pear", "orange", "seasonal fruit", "mixed fruit"]) }
    add("quinoa", when: ["quinoa"])
    add("rice", when: ["brown rice", "cooked rice"])
    add("beans", when: ["bean", "beans", "chickpea", "kidney bean"])
    add("tuna", when: ["tuna"])
    add("hummus", when: ["hummus"])
    add("wraps", when: ["wrap", "tortilla", "pita"])
    add("greens", when: ["spinach", "kale", "lettuce", "greens"])
    add("lunchveg", when: ["carrot", "cucumber", "bell pepper", "fresh pepper"])
    add("feta", when: ["feta", "mozzarella"])
    add("whey", when: ["whey protein", "protein powder"])
    if !text.contains("chicken broth") && !text.contains("chicken stock") {
        add("chicken", when: ["chicken breast", "chicken thigh", "chicken tender", "chicken"])
    }
    add("salmon", when: ["salmon"])
    add("shrimp", when: ["shrimp", "prawn"])
    add("cod", when: ["cod"])
    add("turkey", when: ["ground turkey", "turkey breast", "turkey"])
    add("beef", when: ["lean ground beef", "ground beef", "beef"])
    add("lentils", when: ["lentil"])
    add("pasta", when: ["whole wheat pasta", "whole grain pasta", "pasta", "noodle"])
    if text.contains("diced tomato") || text.contains("canned tomato") || text.contains("tomato sauce") || text.contains("tomato paste") || text.contains("tomato puree") {
        ids.insert("tomatoes")
    } else {
        add("lunchveg", when: ["tomato"])
    }
    add("sweetpotato", when: ["sweet potato"])
    add("dinnerveg", when: ["broccoli", "mixed vegetable", "frozen vegetable", "seasonal vegetable"])
    add("oil", when: ["olive oil", "canola oil", "vegetable oil", "cooking oil", " oil"])
    add("broth", when: ["broth", "stock", "bouillon"])
    add("sauces", when: ["pesto", "salsa", "harissa"])
    add("cinnamon", when: ["cinnamon"])
    add("blackpepper", when: ["black pepper"])
    add("garlicpowder", when: ["garlic powder"])
    add("onionpowder", when: ["onion powder"])
    add("paprika", when: ["paprika"])
    add("cumin", when: ["cumin"])
    add("italianseasoning", when: ["italian seasoning"])
    add("redpepper", when: ["crushed red pepper", "red pepper flakes"])
    add("vinegar", when: ["vinegar"])
    add("salt", when: ["salt"])
    return ids
}

func isWaterOnlyRecipeIngredient(_ ingredient: String) -> Bool {
    let text = normalizedCouponText(ingredient)
    return text.contains("water") && !text.contains("water chestnut")
}

func stableSupplementalIngredientID(_ ingredient: String) -> String {
    var hash: UInt64 = 1469598103934665603
    for byte in normalizedCouponText(ingredient).utf8 {
        hash = (hash ^ UInt64(byte)) &* 1099511628211
    }
    return "recipeextra-\(String(hash, radix: 16))"
}

func supplementalIngredientEstimate(_ ingredient: String) -> Double {
    let text = normalizedCouponText(ingredient)
    if ["meat", "chicken", "beef", "turkey", "pork"].contains(where: text.contains) { return 6.99 }
    if ["fish", "salmon", "shrimp", "seafood"].contains(where: text.contains) { return 9.99 }
    if ["oil", "nuts", "seeds", "cheese"].contains(where: text.contains) { return 5.99 }
    if ["fruit", "vegetable", "onion", "garlic", "pepper"].contains(where: text.contains) { return 3.49 }
    return 3.99
}

func recipeShoppingCoverage(recipes: [Recipe], options: ListOptions, baseItems: [ShoppingItem] = catalog) -> RecipeShoppingCoverage {
    var items = baseItems
    var required = Set<String>()
    var supplementalIDs = Set<String>()
    var coveredLines = 0
    var waterLines = 0
    let fallbackStore = ["ShopRite", "BJ's", "Costco", "Stew Leonard's"].first(where: options.enabledStores.contains)
        ?? options.enabledStores.sorted().first
        ?? "ShopRite"

    for recipe in recipes {
        for ingredient in recipe.ingredients {
            let matches = catalogItemIDs(forIngredient: ingredient)
            if !matches.isEmpty {
                required.formUnion(matches)
                coveredLines += 1
            } else if isWaterOnlyRecipeIngredient(ingredient) {
                waterLines += 1
            } else {
                let id = stableSupplementalIngredientID(ingredient)
                required.insert(id)
                coveredLines += 1
                if supplementalIDs.insert(id).inserted {
                    items.append(ShoppingItem(
                        id: id,
                        name: "Recipe ingredient: \(ingredient)",
                        package: "1 recipe-size package",
                        aisle: "Recipe extras",
                        store: fallbackStore,
                        meal: "Shared pantry",
                        monthlyPackages: 0.10,
                        fallbackPrice: supplementalIngredientEstimate(ingredient),
                        sourceURL: nil
                    ))
                }
            }
        }
    }

    items = items.map { item in
        guard required.contains(item.id), !options.enabledStores.contains(item.store) else { return item }
        return ShoppingItem(
            id: item.id, name: item.name, package: item.package, aisle: item.aisle,
            store: fallbackStore, meal: item.meal, monthlyPackages: item.monthlyPackages,
            fallbackPrice: item.fallbackPrice, sourceURL: nil
        )
    }
    return RecipeShoppingCoverage(
        items: items,
        requiredItemIDs: required,
        coveredIngredientLines: coveredLines,
        waterOnlyLines: waterLines,
        supplementalItemIDs: supplementalIDs
    )
}

struct MealChoice {
    let name: String
    let macros: NutritionEstimate
}

struct DailyMealPlan {
    let day: Int
    let breakfast: MealChoice
    let lunch: MealChoice
    let dinner: MealChoice
    let snacks: [MealChoice]

    var snacksTotal: NutritionEstimate {
        snacks.reduce(NutritionEstimate(proteinGrams: 0, carbohydrateGrams: 0, fatGrams: 0)) { $0.adding($1.macros) }
    }

    var total: NutritionEstimate {
        breakfast.macros.adding(lunch.macros).adding(dinner.macros).adding(snacksTotal)
    }
}

private let breakfastChoices = [
    MealChoice(name: "Eggs, milk, oats & blueberries", macros: NutritionEstimate(proteinGrams: 32, carbohydrateGrams: 62, fatGrams: 12)),
    MealChoice(name: "Eggs, whole-grain toast & fruit", macros: NutritionEstimate(proteinGrams: 28, carbohydrateGrams: 56, fatGrams: 18)),
    MealChoice(name: "Chia overnight oats, milk & banana", macros: NutritionEstimate(proteinGrams: 24, carbohydrateGrams: 72, fatGrams: 18)),
    MealChoice(name: "Vegetable egg breakfast wrap", macros: NutritionEstimate(proteinGrams: 30, carbohydrateGrams: 48, fatGrams: 17)),
    MealChoice(name: "Eggs, milk, oats, chia & fruit", macros: NutritionEstimate(proteinGrams: 30, carbohydrateGrams: 55, fatGrams: 20)),
    MealChoice(name: "Banana chia oatmeal with milk", macros: NutritionEstimate(proteinGrams: 22, carbohydrateGrams: 78, fatGrams: 16)),
    MealChoice(name: "Eggs, oatmeal & blueberries", macros: NutritionEstimate(proteinGrams: 31, carbohydrateGrams: 64, fatGrams: 15))
]

private let lunchChoices = [
    MealChoice(name: "Chicken quinoa greens bowl", macros: NutritionEstimate(proteinGrams: 45, carbohydrateGrams: 60, fatGrams: 16)),
    MealChoice(name: "Tuna-bean whole-wheat wrap", macros: NutritionEstimate(proteinGrams: 38, carbohydrateGrams: 54, fatGrams: 13)),
    MealChoice(name: "Lentil sweet-potato bowl", macros: NutritionEstimate(proteinGrams: 28, carbohydrateGrams: 76, fatGrams: 12)),
    MealChoice(name: "Hummus, egg & vegetable pita", macros: NutritionEstimate(proteinGrams: 27, carbohydrateGrams: 58, fatGrams: 17)),
    MealChoice(name: "Salmon brown-rice salad", macros: NutritionEstimate(proteinGrams: 39, carbohydrateGrams: 62, fatGrams: 18)),
    MealChoice(name: "Turkey-bean salad wrap", macros: NutritionEstimate(proteinGrams: 42, carbohydrateGrams: 58, fatGrams: 14)),
    MealChoice(name: "Quinoa, bean & feta salad", macros: NutritionEstimate(proteinGrams: 26, carbohydrateGrams: 68, fatGrams: 16))
]

private func snacksToMeetDailyTarget(base: NutritionEstimate, target: NutritionEstimate) -> [MealChoice] {
    let proteinGap = max(0, target.proteinGrams - base.proteinGrams)
    let carbohydrateGap = max(0, target.carbohydrateGrams - base.carbohydrateGrams)
    let fatGap = max(0, target.fatGrams - base.fatGrams)
    guard proteinGap + carbohydrateGap + fatGap > 0 else { return [] }

    let smoothie = NutritionEstimate(
        proteinGrams: Int(ceil(Double(proteinGap) * 0.62)),
        carbohydrateGrams: Int((Double(carbohydrateGap) * 0.55).rounded()),
        fatGrams: Int((Double(fatGap) * 0.25).rounded())
    )
    let snackPlate = NutritionEstimate(
        proteinGrams: max(0, proteinGap - smoothie.proteinGrams),
        carbohydrateGrams: max(0, carbohydrateGap - smoothie.carbohydrateGrams),
        fatGrams: max(0, fatGap - smoothie.fatGrams)
    )
    return [
        MealChoice(name: "Portion-adjusted milk, chia & oat smoothie", macros: smoothie),
        MealChoice(name: "Portion-adjusted eggs, beans, toast & fruit", macros: snackPlate)
    ]
}

private func scaledChoice(_ choice: MealChoice, by factor: Double) -> MealChoice {
    let macros = NutritionEstimate(
        proteinGrams: Int((Double(choice.macros.proteinGrams) * factor).rounded()),
        carbohydrateGrams: Int((Double(choice.macros.carbohydrateGrams) * factor).rounded()),
        fatGrams: Int((Double(choice.macros.fatGrams) * factor).rounded())
    )
    return MealChoice(name: "\(choice.name) (\(String(format: "%.2f", factor))x portion)", macros: macros)
}

private func variedDailyNutritionTargets(base: NutritionEstimate, days: Int, dailyCeiling: Int = Int.max) -> [NutritionEstimate] {
    guard days > 0 else { return [] }

    // The percentages intentionally sum to zero across a full seven-day block.
    // Protein is never below the personalized minimum; carbohydrate and fat move
    // modestly so calories can vary while each block still averages to the base.
    let caloriePattern = [-0.040, 0.030, -0.010, 0.040, -0.025, 0.015, -0.010]
    let proteinPattern = [0.000, 0.010, 0.020, 0.005, 0.015, 0.025, 0.010]
    let fatPattern = [-0.050, 0.040, -0.020, 0.050, -0.040, 0.020, 0.000]
    var targets: [NutritionEstimate] = []
    var blockStart = 0

    while blockStart < days {
        let blockSize = min(7, days - blockStart)
        let rawCaloriePercentages = Array(caloriePattern.prefix(blockSize))
        let meanPercentage = rawCaloriePercentages.reduce(0, +) / Double(blockSize)
        let centeredCaloriePercentages = rawCaloriePercentages.map { $0 - meanPercentage }
        let proteinDeltas = proteinPattern.prefix(blockSize).map {
            max(0, Int((Double(base.proteinGrams) * $0).rounded()))
        }

        var fatDeltas = Array(fatPattern.prefix(blockSize)).map {
            Int((Double(base.fatGrams) * $0).rounded())
        }
        if blockSize == 1 {
            fatDeltas[0] = 0
        } else {
            fatDeltas[blockSize - 1] = -fatDeltas.dropLast().reduce(0, +)
        }

        var carbohydrateDeltas = [Int](repeating: 0, count: blockSize)
        if blockSize > 1 {
            for index in 0..<(blockSize - 1) {
                let desiredCalorieDelta = Double(base.calories) * centeredCaloriePercentages[index]
                let nonCarbohydrateDelta = Double(proteinDeltas[index] * 4 + fatDeltas[index] * 9)
                carbohydrateDeltas[index] = Int(((desiredCalorieDelta - nonCarbohydrateDelta) / 4.0).rounded())
            }
        }
        // With fat deltas centered at zero, this makes the block's total calorie
        // delta exactly zero: 4P + 4C + 9F reconciles without hidden calories.
        carbohydrateDeltas[blockSize - 1] = -proteinDeltas.reduce(0, +) - carbohydrateDeltas.dropLast().reduce(0, +)

        for index in 0..<blockSize {
            targets.append(NutritionEstimate(
                proteinGrams: base.proteinGrams + proteinDeltas[index],
                carbohydrateGrams: base.carbohydrateGrams + carbohydrateDeltas[index],
                fatGrams: base.fatGrams + fatDeltas[index]
            ))
        }
        blockStart += blockSize
    }
    // Optional per-day ceiling (used by Cutting): no single day may exceed the ceiling. Days the
    // variation pushed above it have their carbohydrate trimmed back to land at the ceiling; days
    // at or below it are untouched. Maintenance/Build Muscle pass Int.max, so nothing is trimmed.
    guard dailyCeiling != Int.max else { return targets }
    return targets.map { day in
        guard day.calories > dailyCeiling else { return day }
        let overflow = day.calories - dailyCeiling
        let trimmedCarb = max(0, day.carbohydrateGrams - Int((Double(overflow) / 4.0).rounded(.up)))
        return NutritionEstimate(proteinGrams: day.proteinGrams, carbohydrateGrams: trimmedCarb, fatGrams: day.fatGrams)
    }
}

func makeDailyMealPlans(options: ListOptions, recipes: [Recipe], schedule: [ScheduledRecipe]) -> [DailyMealPlan] {
    let skipped = MealChoice(name: "Not selected", macros: NutritionEstimate(proteinGrams: 0, carbohydrateGrams: 0, fatGrams: 0))
    let baseTarget = personalizedNutritionTarget(for: options).macros
    // Only Cutting caps individual days at 2,800; Maintenance/Build Muscle are uncapped.
    let dailyCeiling = options.nutritionGoal == .cutting ? maximumDailyCalories : Int.max
    let dailyTargets = variedDailyNutritionTargets(base: baseTarget, days: options.days, dailyCeiling: dailyCeiling)
    // Meals are picked for the target, never for what happens to be discounted --
    // the week's offers are read afterwards, against the list these meals produce.
    let rankedBreakfasts = breakfastChoices
    let rankedLunches = lunchChoices
    return schedule.sorted { $0.day < $1.day }.map { entry in
        let target = dailyTargets[min(max(0, entry.day - 1), dailyTargets.count - 1)]
        let rawBreakfast = options.enabledMeals.contains("Breakfast") ? rankedBreakfasts[(entry.day - 1) % rankedBreakfasts.count] : skipped
        let rawLunch = options.enabledMeals.contains("Lunch") ? rankedLunches[(entry.day + 1) % rankedLunches.count] : skipped
        let recipe = recipes[entry.recipeIndex]
        let rawDinner = options.enabledMeals.contains("Dinner") ? MealChoice(name: recipe.title, macros: recipe.macrosPerServing) : skipped
        let rawBase = rawBreakfast.macros.adding(rawLunch.macros).adding(rawDinner.macros)
        // The personalized target belongs to the whole day. Main meals cover most
        // of that day's varied target; snacks fill only the remaining macro gaps.
        let coverage = options.enabledMeals.contains("Snack") ? 0.82 : 1.0
        let ratios = [
            rawBase.proteinGrams > 0 ? Double(target.proteinGrams) * coverage / Double(rawBase.proteinGrams) : Double.greatestFiniteMagnitude,
            rawBase.carbohydrateGrams > 0 ? Double(target.carbohydrateGrams) * coverage / Double(rawBase.carbohydrateGrams) : Double.greatestFiniteMagnitude,
            rawBase.fatGrams > 0 ? Double(target.fatGrams) * coverage / Double(rawBase.fatGrams) : Double.greatestFiniteMagnitude
        ]
        let mealFactor = max(0.25, min(2.50, ratios.min() ?? 1.0))
        let breakfast = rawBreakfast.name == skipped.name ? skipped : scaledChoice(rawBreakfast, by: mealFactor)
        let lunch = rawLunch.name == skipped.name ? skipped : scaledChoice(rawLunch, by: mealFactor)
        let dinner = rawDinner.name == skipped.name ? skipped : scaledChoice(rawDinner, by: mealFactor)
        let base = breakfast.macros.adding(lunch.macros).adding(dinner.macros)
        let snacks = options.enabledMeals.contains("Snack") ? snacksToMeetDailyTarget(base: base, target: target) : []
        return DailyMealPlan(day: entry.day, breakfast: breakfast, lunch: lunch, dinner: dinner, snacks: snacks)
    }
}

final class DailyMealsPDFWriter {
    private let pageRect = CGRect(x: 0, y: 0, width: 612, height: 792)
    private let margin: CGFloat = 42
    private var context: CGContext!
    private var y: CGFloat = 0
    private var page = 0
    private var shoppingListFilename = "Shopping List.pdf"

    func write(to url: URL, options: ListOptions, plans: [DailyMealPlan], lifestyle: String, shoppingListFilename: String) throws {
        page = 0
        self.shoppingListFilename = shoppingListFilename
        var box = pageRect
        guard let consumer = CGDataConsumer(url: url as CFURL),
              let output = CGContext(consumer: consumer, mediaBox: &box, nil) else {
            throw NSError(domain: "DailyMealsPDF", code: 20)
        }
        context = output
        startPage(options: options, lifestyle: lifestyle)
        for plan in plans {
            if y + 71 > 744 { finishPage(); startPage(options: options, lifestyle: lifestyle, continued: true) }
            drawRow(plan)
        }
        finishPage()
        context.closePDF()
        context = nil
    }

    private func startPage(options: ListOptions, lifestyle: String, continued: Bool = false) {
        page += 1
        context.beginPDFPage(nil)
        context.saveGState()
        context.resetClip()
        context.translateBy(x: 0, y: pageRect.height); context.scaleBy(x: 1, y: -1)
        primePDFPage(context)
        y = 34
        let headingSize: CGFloat = continued ? 18 : 20
        let heading = continued ? "Daily Meal Schedule - continued" : "\(options.days)-Day Meals & Snacks"
        drawPDFOutlinedHeading(heading, in: context, x: margin, y: y, size: headingSize)
        drawText("\(options.recipient) | \(lifestyle) | \(options.nutritionGoal.rawValue)", x: 415, y: y + 5, width: 155, font: .systemFont(ofSize: 8), align: .right)
        y += 34
        let target = personalizedNutritionTarget(for: options)
        let saleNote = options.prioritizeSales
            ? " Meals were planned from the target alone; the week's \(options.saleItemIDs.count) verified offer match\(options.saleItemIDs.count == 1 ? " was" : "es were") applied to the resulting list afterwards."
            : ""
        let goalNote: String
        switch options.nutritionGoal {
        case .cutting: goalNote = "Cutting is a ~20% deficit off maintenance, capped so no day exceeds \(maximumDailyCalories) kcal."
        case .maintenance: goalNote = "Maintenance targets your estimated sedentary daily energy use."
        case .buildMuscle: goalNote = "Build Muscle uses maintenance calories (body recomposition — build muscle while roughly maintaining weight; progressive training drives the growth)."
        }
        let note = "Paired shopping list: \(shoppingListFilename). Personalized from \(profileDescription(for: options)). Daily totals vary slightly. \(goalNote) Protein is set from your ideal (healthy) body weight, ~\(target.macros.proteinGrams) g/day — the point where muscle-building benefit maxes out, so it doesn't scale up with body fat. Each row is breakfast + lunch + dinner + snacks, not a per-meal target.\(saleNote) Estimated sedentary maintenance = \(target.estimatedMaintenanceCalories) kcal (\(options.nutritionGoal.rawValue) x \(String(format: "%.2f", target.goalMultiplier)) = \(target.macros.calories)-kcal target). Fat uses a height-capped planning weight of \(Int(target.planningWeightPounds.rounded())) lb; carbohydrate fills the rest. Adjust portions to product labels. Activity level, age, sex and medical history change actual needs."
        let noteHeight = drawText(note, x: margin, y: y, width: 528, font: .systemFont(ofSize: 7.5), color: .darkGray)
        y += noteHeight + 7
        context.setFillColor(NSColor(calibratedRed: 0.96, green: 0.91, blue: 0.91, alpha: 1).cgColor)
        context.fill(CGRect(x: margin, y: y, width: 528, height: 26))
        context.setStrokeColor(NSColor(calibratedRed: 0.55, green: 0.08, blue: 0.08, alpha: 1).cgColor)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: 26))
        drawText("7-DAY AVG: \(target.macros.calories) kcal | DAILY P >= \(target.macros.proteinGrams)g | C ~\(target.macros.carbohydrateGrams)g | F ~\(target.macros.fatGrams)g", x: margin + 8, y: y + 6, width: 512, font: .boldSystemFont(ofSize: 8), color: NSColor(calibratedRed: 0.45, green: 0.04, blue: 0.04, alpha: 1), align: .center)
        y += 31
        context.setFillColor(NSColor(calibratedWhite: 0.92, alpha: 1).cgColor); context.fill(CGRect(x: margin, y: y, width: 528, height: 26))
        drawText("Day", x: margin + 5, y: y + 6, width: 28, font: .boldSystemFont(ofSize: 7.5))
        drawText("Breakfast", x: 80, y: y + 6, width: 85, font: .boldSystemFont(ofSize: 7.2))
        drawText("Lunch", x: 175, y: y + 6, width: 85, font: .boldSystemFont(ofSize: 7.2))
        drawText("Dinner", x: 270, y: y + 6, width: 105, font: .boldSystemFont(ofSize: 7.2))
        drawText("Snacks", x: 385, y: y + 6, width: 100, font: .boldSystemFont(ofSize: 7.2))
        drawText("Daily total", x: 495, y: y + 6, width: 68, font: .boldSystemFont(ofSize: 7.2))
        y += 26
    }

    private func drawRow(_ plan: DailyMealPlan) {
        let rowHeight: CGFloat = 70
        context.setStrokeColor(NSColor(calibratedWhite: 0.78, alpha: 1).cgColor); context.setLineWidth(0.35)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: rowHeight))
        for x in [75.0, 170.0, 265.0, 380.0, 490.0] { context.move(to: CGPoint(x: x, y: y)); context.addLine(to: CGPoint(x: x, y: y + rowHeight)) }
        context.strokePath()
        context.stroke(CGRect(x: margin + 5, y: y + 29, width: 10, height: 10))
        drawText("\(plan.day)", x: margin + 18, y: y + 27, width: 14, font: .boldSystemFont(ofSize: 8))
        drawMeal(plan.breakfast, x: 80, width: 85)
        drawMeal(plan.lunch, x: 175, width: 85)
        drawMeal(plan.dinner, x: 270, width: 105)
        drawSnacks(plan.snacks, macros: plan.snacksTotal, x: 385, width: 100)
        drawText("\(plan.total.calories) kcal", x: 495, y: y + 9, width: 68, font: .boldSystemFont(ofSize: 7.1))
        drawText("P \(plan.total.proteinGrams)g\nC \(plan.total.carbohydrateGrams)g\nF \(plan.total.fatGrams)g", x: 495, y: y + 24, width: 68, font: .systemFont(ofSize: 6.6), color: .darkGray)
        y += rowHeight
    }

    private func drawMeal(_ meal: MealChoice, x: CGFloat, width: CGFloat) {
        drawText(meal.name, x: x, y: y + 5, width: width, font: .systemFont(ofSize: 6.5))
        drawText(meal.macros.summary, x: x, y: y + 49, width: width, font: .systemFont(ofSize: 4.9), color: .darkGray)
    }

    private func drawSnacks(_ snacks: [MealChoice], macros: NutritionEstimate, x: CGFloat, width: CGFloat) {
        let names = snacks.map { $0.name }.joined(separator: "; ")
        drawText(names, x: x, y: y + 5, width: width, font: .systemFont(ofSize: 5.8))
        drawText(macros.summary, x: x, y: y + 49, width: width, font: .systemFont(ofSize: 4.9), color: .darkGray)
    }

    private func finishPage() {
        drawText("Paired with \(shoppingListFilename) | Estimates should be checked against product labels.", x: margin, y: 766, width: 465, font: .systemFont(ofSize: 6.5), color: .darkGray)
        drawText("\(page)", x: 520, y: 766, width: 50, font: .systemFont(ofSize: 7), color: .darkGray, align: .right)
        context.restoreGState(); context.endPDFPage()
    }

    @discardableResult
    private func drawText(_ text: String, x: CGFloat, y: CGFloat, width: CGFloat, font: NSFont, color: NSColor = .black, align: NSTextAlignment = .left) -> CGFloat {
        drawPDFText(text, in: context, x: x, y: y, width: width, font: font, color: color, align: align)
    }
}

final class RecipePDFWriter {
    private let pageRect = CGRect(x: 0, y: 0, width: 612, height: 792)
    private let margin: CGFloat = 42
    private var context: CGContext!
    private var y: CGFloat = 0
    private var page = 0
    private var shoppingListFilename = "Shopping List.pdf"

    func write(to url: URL, options: ListOptions, recipes: [Recipe], schedule: [ScheduledRecipe], lifestyle: String, nutritionGoal: NutritionGoal, shoppingListFilename: String) throws {
        page = 0
        self.shoppingListFilename = shoppingListFilename
        var box = pageRect
        guard let consumer = CGDataConsumer(url: url as CFURL),
              let output = CGContext(consumer: consumer, mediaBox: &box, nil) else {
            throw NSError(domain: "RecipePDF", code: 20)
        }
        context = output
        beginPage(title: "\(options.days)-Day Recipe Plan", subtitle: "\(options.recipient) | \(lifestyle) | \(nutritionGoal.rawValue)")
        let saleNote = options.prioritizeSales
            ? " Recipes were chosen on nutrition alone; the week's \(options.saleItemIDs.count) verified offer match\(options.saleItemIDs.count == 1 ? " was" : "es were") applied to the shopping list once it was settled. Account offers must still be clipped."
            : ""
        let introHeight = drawText("Paired shopping list: \(shoppingListFilename). One recipe is assigned to every day and adjusted for the entered height, weight and \(nutritionGoal.rawValue) goal. \(profileDescription(for: options)). The listed recipe macros are for that one meal; breakfast, lunch, dinner and snacks vary by day while each seven-day block averages to the calorie target.\(saleNote) Grocery quantities and per-person recipe portions use the calculated factor; selections favor value staples and target about $250. Calories and macros are estimates. Prep days make multiple servings; later days use the labeled saved portion. All recipe paths exclude soy, cabbage, and organic-only requirements.", x: margin, y: y, width: 528, font: .systemFont(ofSize: 8.1), color: .darkGray)
        y += introHeight + 12
        drawHeader("Daily schedule")
        for entry in schedule {
            ensureSpace(39, continuationTitle: "Daily schedule - continued")
            let recipe = recipes[entry.recipeIndex]
            let action: String
            if entry.isPrepDay {
                let saved = max(0, entry.batchServings - options.people)
                let futureDays = schedule.filter { $0.recipeIndex == entry.recipeIndex && $0.prepDay == entry.prepDay && !$0.isPrepDay }.map { "Day \($0.day)" }.joined(separator: " and ")
                action = saved > 0 ? "Cook \(entry.batchServings) servings; eat \(options.people), save \(saved) for \(futureDays)" : "Cook \(entry.batchServings) serving\(entry.batchServings == 1 ? "" : "s")"
            } else {
                action = "Use \(options.people) saved serving\(options.people == 1 ? "" : "s") from Day \(entry.prepDay)"
            }
            drawScheduleRow(day: entry.day, title: recipe.title, action: action, macros: recipe.macrosPerServing)
        }

        newPage(title: "Recipe cards", subtitle: "scale amounts to the batch servings shown")
        for (index, recipe) in recipes.enumerated() {
            drawRecipeCard(recipe, number: index + 1)
        }
        drawText("Food safety: refrigerate cooked food within 2 hours. Use refrigerated leftovers within 3-4 days or freeze the saved portion. Reheat leftovers to 165 F.", x: margin, y: min(y + 6, 730), width: 528, font: .systemFont(ofSize: 8), color: .darkGray)
        finishPage()
        context.closePDF()
        context = nil
    }

    private func beginPage(title: String, subtitle: String) {
        page += 1
        context.beginPDFPage(nil)
        context.saveGState()
        context.resetClip()
        context.translateBy(x: 0, y: pageRect.height); context.scaleBy(x: 1, y: -1)
        primePDFPage(context)
        y = 36
        drawPDFOutlinedHeading(title, in: context, x: margin, y: y, size: 22)
        drawText(subtitle, x: 410, y: y + 6, width: 160, font: .systemFont(ofSize: 8.5), align: .right)
        y += 38
        context.setStrokeColor(NSColor.black.cgColor); context.setLineWidth(1)
        context.move(to: CGPoint(x: margin, y: y)); context.addLine(to: CGPoint(x: 570, y: y)); context.strokePath()
        y += 14
    }

    private func newPage(title: String, subtitle: String) {
        finishPage(); beginPage(title: title, subtitle: subtitle)
    }

    private func finishPage() {
        drawText("Paired with \(shoppingListFilename) | Recipe data: TheMealDB + built-in recipes", x: margin, y: 766, width: 465, font: .systemFont(ofSize: 6.5), color: .darkGray)
        drawText("\(page)", x: 520, y: 766, width: 50, font: .systemFont(ofSize: 7), color: .darkGray, align: .right)
        context.restoreGState(); context.endPDFPage()
    }

    private func ensureSpace(_ amount: CGFloat, continuationTitle: String = "Recipe cards - continued") {
        if y + amount > 748 { newPage(title: continuationTitle, subtitle: "page \(page + 1)") }
    }

    private func drawHeader(_ text: String) {
        context.setFillColor(NSColor(calibratedWhite: 0.92, alpha: 1).cgColor)
        context.fill(CGRect(x: margin, y: y, width: 528, height: 25))
        drawText(text, x: margin + 8, y: y + 5, width: 510, font: .boldSystemFont(ofSize: 11)); y += 29
    }

    private func drawScheduleRow(day: Int, title: String, action: String, macros: NutritionEstimate) {
        let rowHeight: CGFloat = 36
        context.setStrokeColor(NSColor(calibratedWhite: 0.78, alpha: 1).cgColor); context.setLineWidth(0.4)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: rowHeight))
        drawText("Day \(day)", x: margin + 7, y: y + 5, width: 44, font: .boldSystemFont(ofSize: 8.2))
        drawText(title, x: margin + 56, y: y + 4, width: 205, font: .systemFont(ofSize: 8.1))
        drawText(action, x: margin + 268, y: y + 4, width: 250, font: .systemFont(ofSize: 6.8), color: .darkGray)
        drawText("One-meal total/person: \(macros.summary) | combine with the other meals + snacks for that day's total", x: margin + 56, y: y + 20, width: 462, font: .boldSystemFont(ofSize: 6.5), color: .darkGray)
        y += rowHeight
    }

    private func drawRecipeCard(_ recipe: Recipe, number: Int) {
        let cardHeight: CGFloat = 310
        ensureSpace(cardHeight)
        context.setStrokeColor(NSColor(calibratedWhite: 0.72, alpha: 1).cgColor); context.setLineWidth(0.6)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: cardHeight - 8))
        context.setFillColor(NSColor(calibratedWhite: 0.92, alpha: 1).cgColor)
        context.fill(CGRect(x: margin, y: y, width: 528, height: 30))
        drawText("\(number). \(recipe.title)", x: margin + 8, y: y + 6, width: 390, font: .boldSystemFont(ofSize: 11))
        let time = recipe.readyMinutes.map { " | about \($0) min" } ?? ""
        drawText("plan \(recipe.baseServings) servings\(time)", x: 430, y: y + 8, width: 132, font: .systemFont(ofSize: 7.5), align: .right)
        context.setFillColor(NSColor(calibratedWhite: 0.97, alpha: 1).cgColor)
        context.fill(CGRect(x: margin + 1, y: y + 30, width: 526, height: 20))
        drawText("One-meal serving estimate: \(recipe.macrosPerServing.summary) | not the full daily total", x: margin + 10, y: y + 34, width: 508, font: .boldSystemFont(ofSize: 7.5), color: .darkGray)
        drawText("Ingredients", x: margin + 10, y: y + 57, width: 220, font: .boldSystemFont(ofSize: 9))
        var leftY = y + 74
        for line in recipe.ingredients.prefix(10) {
            let h = drawText("- \(line)", x: margin + 10, y: leftY, width: 235, font: .systemFont(ofSize: 7.5))
            leftY += max(14, h + 3)
        }
        drawText("Directions", x: 305, y: y + 57, width: 250, font: .boldSystemFont(ofSize: 9))
        var rightY = y + 74
        for (stepIndex, step) in recipe.steps.prefix(6).enumerated() {
            let h = drawText("\(stepIndex + 1). \(step)", x: 305, y: rightY, width: 250, font: .systemFont(ofSize: 7.5))
            rightY += max(18, h + 4)
        }
        if let goalNote = recipe.goalNote {
            context.setFillColor(NSColor(calibratedWhite: 0.96, alpha: 1).cgColor)
            context.fill(CGRect(x: margin + 8, y: y + 244, width: 512, height: 32))
            drawText(goalNote, x: margin + 12, y: y + 249, width: 504, font: .systemFont(ofSize: 6.8), color: .darkGray)
        }
        drawText("Nutrition estimate: \(recipe.nutritionSource)", x: margin + 10, y: y + 228, width: 508, font: .systemFont(ofSize: 6.3), color: .darkGray)
        let condensed = recipe.ingredients.count > 10 || recipe.steps.count > 6 ? " | Condensed for print; use source for full recipe." : ""
        let source = (recipe.sourceURL.map { "Source: \(recipe.sourceName) | \($0)" } ?? "Source: \(recipe.sourceName)") + condensed
        drawText(source, x: margin + 10, y: y + 281, width: 508, font: .systemFont(ofSize: 6.5), color: .darkGray)
        y += cardHeight
    }

    @discardableResult
    private func drawText(_ text: String, x: CGFloat, y: CGFloat, width: CGFloat, font: NSFont, color: NSColor = .black, align: NSTextAlignment = .left) -> CGFloat {
        drawPDFText(text, in: context, x: x, y: y, width: width, font: font, color: color, align: align)
    }
}

final class PDFWriter {
    let pageRect = CGRect(x: 0, y: 0, width: 612, height: 792)
    let margin: CGFloat = 42
    var context: CGContext!
    var y: CGFloat = 0
    var page = 0

    func write(to url: URL, options: ListOptions, items: [ShoppingItem], prices: PriceBook, favorites: Set<String>, suppliedPlan: ShoppingPlan? = nil) throws {
        page = 0
        var box = pageRect
        guard let consumer = CGDataConsumer(url: url as CFURL),
              let output = CGContext(consumer: consumer, mediaBox: &box, nil) else {
            throw NSError(domain: "PDF", code: 20)
        }
        context = output
        let profile = profileDescription(for: options)
        startPage(title: "Shopping List for \(options.recipient)", subtitle: "\(options.days) days | \(options.people) person\(options.people == 1 ? "" : "s") | \(options.nutritionGoal.rawValue) | \(profile) | Budget \(money(options.budgetMin))-\(money(options.budgetMax))")
        drawInventoryBanner()

        let plan = suppliedPlan ?? makeShoppingPlan(options: options, items: items, prices: prices, favorites: favorites)
        drawEstimate(plan: plan, options: options, retailerCount: prices.retailerChecked.count, usdaCount: prices.usdaChecked.count)
        drawSmall("RECIPE-COMPLETE: Recipes are finalized before this list. Every non-water recipe ingredient is required; the budget optimizer only chooses among optional extras.")
        if plan.omittedItems > 0 {
            drawSmall("Frugal target: \(plan.omittedItems) optional higher-cost or duplicate grocery item(s) were left off to keep the estimate close to \(money(plan.targetSpend)). Recipe ingredients and favorites remain included; either can push the total higher.")
        }
        if options.prioritizeSales {
            let saleNote = plan.prioritizedSaleItems > 0
                ? "DEALS APPLIED: this list was built from your nutrition target at shelf prices, then \(plan.prioritizedSaleItems) verified official offer\(plan.prioritizedSaleItems == 1 ? "" : "s") landed on items it already called for. Regular totals, offer savings, and estimated checkout are shown below. Account offers must still be clipped."
                : "DEALS CHECKED: none of this week's verified offers covered anything on this list, so nothing was substituted."
            drawSmall(saleNote)
            // What each store needs before these offers count at the register.
            let saleStores = Set(plan.rows.compactMap { row -> String? in
                guard row.couponSavings > 0, options.saleItemIDs.contains(row.item.id) else { return nil }
                return options.saleSources[row.item.id] ?? row.item.store
            })
            let notices = saleStores.compactMap { redeemNotice(for: $0) }
                .sorted { $0.mustAct && !$1.mustAct }
            for notice in notices { drawRedeemBanner(notice) }
        }

        var currentGroup = ""
        for row in plan.rows {
            let item = row.item
            let group = options.groupByStore ? "\(item.store) - \(item.aisle)" : item.meal
            if group != currentGroup {
                ensureSpace(58)
                currentGroup = group
                drawGroupHeader(group)
            }
            let favoriteMark = favorites.contains(item.id) ? "★ " : ""
            let verifiedSale = options.prioritizeSales && options.saleItemIDs.contains(item.id) && row.couponSavings > 0
            let saleMark = verifiedSale ? "SALE • " : ""
            let offerDetail = row.couponSavings > 0 ? " | regular \(money(row.grossLineTotal)) | offer -\(money(row.couponSavings))" : ""
            let offerStore = options.saleSources[item.id] ?? item.store
            let mustLoad = verifiedSale && (redeemNotice(for: offerStore)?.mustAct ?? false)
            let sourceDetail = verifiedSale
                ? "\(item.store) / \(item.aisle) • \(mustLoad ? "LOAD COUPON FIRST" : "verified offer")"
                : "\(item.store) / \(item.aisle) • estimate"
            drawRow(name: saleMark + favoriteMark + item.name, detail: "\(row.quantity) x \(item.package)\(offerDetail)", source: sourceDetail, price: money(row.lineTotal))
        }

        drawClosingImage()

        finishPage()
        context.closePDF()
        context = nil
    }

    private func startPage(title: String, subtitle: String) {
        page += 1
        context.beginPDFPage(nil)
        context.saveGState()
        context.resetClip()
        context.translateBy(x: 0, y: pageRect.height)
        context.scaleBy(x: 1, y: -1)
        primePDFPage(context)
        y = 36
        let titleHeight = drawPDFOutlinedHeading(title, in: context, x: margin, y: y, size: 22)
        y += max(31, titleHeight + 5)
        let subtitleHeight: CGFloat
        if subtitle == "continued" {
            subtitleHeight = drawText(subtitle, x: margin, y: y, width: 528, font: .systemFont(ofSize: 8.5), color: .darkGray)
        } else {
            subtitleHeight = drawText(subtitle, x: margin, y: y, width: 528, font: .systemFont(ofSize: 8.5), color: .darkGray)
        }
        y += max(15, subtitleHeight + 3)
        context.setStrokeColor(NSColor.black.cgColor)
        context.setLineWidth(1)
        context.move(to: CGPoint(x: margin, y: y))
        context.addLine(to: CGPoint(x: pageRect.width - margin, y: y))
        context.strokePath()
        y += 12
    }

    private func newPage() {
        finishPage()
        startPage(title: "Shopping List - Page \(page + 1)", subtitle: "continued")
    }

    private func finishPage() {
        drawText("Price note: estimates are not live quotes. Coupon values may come from an accessible official offer feed or manual entry; verify eligibility, clipping, limits, expiration, tax, substitutions, membership, and availability.", x: margin, y: 747, width: 528, font: .systemFont(ofSize: 6.2), color: .darkGray)
        drawText("Generated by Smart Shopping List", x: margin, y: 766, width: 300, font: .systemFont(ofSize: 7), color: .darkGray)
        drawText("\(page)", x: 520, y: 766, width: 50, font: .systemFont(ofSize: 7), color: .darkGray, align: .right)
        context.restoreGState()
        context.endPDFPage()
    }

    private func ensureSpace(_ amount: CGFloat) {
        if y + amount > 744 { newPage() }
    }

    private func drawEstimate(plan: ShoppingPlan, options: ListOptions, retailerCount: Int, usdaCount: Int) {
        ensureSpace(120)
        context.setStrokeColor(NSColor.gray.cgColor)
        context.setFillColor(NSColor(calibratedWhite: 0.96, alpha: 1).cgColor)
        context.addRect(CGRect(x: margin, y: y, width: pageRect.width - margin * 2, height: 106))
        context.drawPath(using: .fillStroke)
        drawText("Estimated checkout", x: margin + 10, y: y + 9, width: 150, font: .boldSystemFont(ofSize: 10))
        drawText(money(plan.estimatedTotal), x: margin + 10, y: y + 27, width: 150, font: .boldSystemFont(ofSize: 18))
        drawText("Likely range", x: 220, y: y + 9, width: 120, font: .boldSystemFont(ofSize: 10))
        drawText("\(money(plan.likelyLow)) - \(money(plan.likelyHigh))", x: 220, y: y + 29, width: 150, font: .systemFont(ofSize: 12))
        drawText("Accuracy", x: 390, y: y + 9, width: 120, font: .boldSystemFont(ofSize: 10))
        drawText("\(plan.confidence) (+/-\(Int(plan.error * 100))%)", x: 390, y: y + 29, width: 160, font: .systemFont(ofSize: 11))
        let budgetStatus: String
        if plan.estimatedTotal > options.budgetMax {
            budgetStatus = "OVER estimated ceiling by \(money(plan.estimatedTotal - options.budgetMax))"
        } else if plan.likelyHigh > options.budgetMax {
            budgetStatus = "Estimate fits; upper range exceeds ceiling by \(money(plan.likelyHigh - options.budgetMax))"
        } else {
            budgetStatus = "Within the budget buffer"
        }
        drawText("Goal: \(options.nutritionGoal.rawValue) | Budget \(money(options.budgetMin))-\(money(options.budgetMax)) | Frugal target \(money(plan.targetSpend))", x: margin + 10, y: y + 55, width: 510, font: .boldSystemFont(ofSize: 8.3))
        drawText(budgetStatus, x: margin + 10, y: y + 70, width: 510, font: .boldSystemFont(ofSize: 8.3))
        let couponText = plan.couponSavings > 0
            ? "Coupons applied: -\(money(plan.couponSavings)) | Before coupons: \(money(plan.grossSubtotal))"
            : "Coupons applied: $0.00"
        let saleText = options.prioritizeSales ? " | Needed items a deal covered: \(plan.prioritizedSaleItems)" : ""
        let checkedText = retailerCount + usdaCount > 0
            ? " | Checked: \(retailerCount) retailer anchors, \(usdaCount) USDA foods" : ""
        drawText("\(couponText)\(saleText)\(checkedText)", x: margin + 10, y: y + 86, width: 500, font: .systemFont(ofSize: 7.6), color: .darkGray)
        y += 118
    }

    private func drawInventoryBanner() {
        context.setFillColor(NSColor(calibratedRed: 0.97, green: 0.91, blue: 0.91, alpha: 1).cgColor)
        context.fill(CGRect(x: margin, y: y, width: 528, height: 30))
        context.setStrokeColor(NSColor(calibratedRed: 0.55, green: 0.08, blue: 0.08, alpha: 1).cgColor)
        context.setLineWidth(0.8)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: 30))
        drawText("PLEASE SKIP ITEMS WE ALREADY HAVE - THANK YOU", x: margin + 8, y: y + 7, width: 512, font: .boldSystemFont(ofSize: 10.5), color: NSColor(calibratedRed: 0.45, green: 0.04, blue: 0.04, alpha: 1), align: .center)
        y += 38
    }

    /// The picture printed at the end of the shopping list. build.sh copies the
    /// theme chosen in the control panel here as "theme".
    private func themeImage() -> NSImage? {
        var candidates: [URL] = []
        for name in ["theme"] {
            for ext in ["png", "jpg", "jpeg"] {
                if let bundled = Bundle.main.url(forResource: name, withExtension: ext) {
                    candidates.append(bundled)
                }
            }
        }
        return candidates.compactMap { NSImage(contentsOf: $0) }.first
    }

    private func drawClosingImage() {
        ensureSpace(116)
        context.setStrokeColor(NSColor(calibratedWhite: 0.72, alpha: 1).cgColor)
        context.setLineWidth(0.5)
        context.stroke(CGRect(x: margin, y: y, width: 528, height: 108))
        drawText("Thanks, Mom!", x: margin + 14, y: y + 22, width: 340, font: .boldSystemFont(ofSize: 16), color: NSColor(calibratedRed: 0.50, green: 0.05, blue: 0.05, alpha: 1))
        drawText("Thank you so much for helping me. If we already have something on the list, please feel free to skip it.", x: margin + 14, y: y + 51, width: 350, font: .systemFont(ofSize: 9), color: .darkGray)
        if let image = themeImage(), let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) {
            let height: CGFloat = 96
            let width = height * CGFloat(cgImage.width) / CGFloat(cgImage.height)
            let x = 540 - width
            context.saveGState()
            context.translateBy(x: x, y: y + 6 + height)
            context.scaleBy(x: 1, y: -1)
            context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
            context.restoreGState()
        }
        y += 116
    }

    private func drawGroupHeader(_ text: String) {
        ensureSpace(32)
        context.setFillColor(NSColor(calibratedWhite: 0.92, alpha: 1).cgColor)
        context.fill(CGRect(x: margin, y: y, width: pageRect.width - margin * 2, height: 24))
        drawText(text, x: margin + 7, y: y + 5, width: pageRect.width - margin * 2 - 14, font: .boldSystemFont(ofSize: 10))
        y += 28
    }

    private func drawRow(name: String, detail: String, source: String, price: String) {
        let nameFont = NSFont.systemFont(ofSize: 8.5)
        let detailFont = NSFont.systemFont(ofSize: 7.5)
        let sourceFont = NSFont.systemFont(ofSize: 7.5)
        let priceFont = NSFont.systemFont(ofSize: 8)
        let nameHeight = pdfTextHeight(name, width: 220, font: nameFont)
        let detailHeight = pdfTextHeight(detail, width: 88, font: detailFont)
        let sourceHeight = pdfTextHeight(source, width: 104, font: sourceFont)
        let priceHeight = pdfTextHeight(price, width: 54, font: priceFont)
        let contentHeight = max(nameHeight, detailHeight, sourceHeight, priceHeight)
        let rowHeight = max(28, contentHeight + 8)
        ensureSpace(rowHeight)
        context.setStrokeColor(NSColor(calibratedWhite: 0.75, alpha: 1).cgColor)
        context.setLineWidth(0.4)
        context.stroke(CGRect(x: margin, y: y, width: pageRect.width - margin * 2, height: rowHeight))
        context.setStrokeColor(NSColor(calibratedWhite: 0.84, alpha: 1).cgColor)
        for x in [296.0, 392.0, 504.0] {
            context.move(to: CGPoint(x: x, y: y))
            context.addLine(to: CGPoint(x: x, y: y + rowHeight))
        }
        context.strokePath()
        context.stroke(CGRect(x: margin + 7, y: y + (rowHeight - 11) / 2, width: 11, height: 11))
        drawText(name, x: margin + 26, y: y + (rowHeight - nameHeight) / 2, width: 220, font: nameFont)
        drawText(detail, x: 300, y: y + (rowHeight - detailHeight) / 2, width: 88, font: detailFont, color: .darkGray, align: .center)
        drawText(source, x: 396, y: y + (rowHeight - sourceHeight) / 2, width: 104, font: sourceFont, color: .darkGray)
        drawText(price, x: 508, y: y + (rowHeight - priceHeight) / 2, width: 54, font: priceFont, align: .right)
        y += rowHeight
    }

    /// A heavy-bordered box that cannot be skimmed past. Low-ink: no fill.
    private func drawRedeemBanner(_ notice: RedeemNotice) {
        let width = pageRect.width - margin * 2
        let inner = width - 28
        let titleFont = NSFont.boldSystemFont(ofSize: notice.mustAct ? 12 : 10.5)
        let bodyFont = NSFont.systemFont(ofSize: 8.5)
        let title = (notice.mustAct ? "!  " : "") + notice.title
        let titleHeight = pdfTextHeight(title, width: inner, font: titleFont)
        let bodyHeight = pdfTextHeight(notice.body, width: inner, font: bodyFont)
        let height = titleHeight + bodyHeight + 26
        ensureSpace(height + 12)
        context.setStrokeColor(NSColor.black.cgColor)
        context.setLineWidth(notice.mustAct ? 3 : 1.5)
        context.stroke(CGRect(x: margin, y: y, width: width, height: height))
        _ = drawText(title, x: margin + 14, y: y + 9, width: inner, font: titleFont)
        _ = drawText(notice.body, x: margin + 14, y: y + 15 + titleHeight, width: inner, font: bodyFont)
        y += height + 12
    }

    private func drawSmall(_ text: String) {
        ensureSpace(38)
        let height = drawText(text, x: margin, y: y + 5, width: pageRect.width - margin * 2, font: .systemFont(ofSize: 7), color: .darkGray)
        y += max(26, height + 8)
    }

    @discardableResult
    private func drawText(_ text: String, x: CGFloat, y: CGFloat, width: CGFloat, font: NSFont, color: NSColor = .black, align: NSTextAlignment = .left) -> CGFloat {
        drawPDFText(text, in: context, x: x, y: y, width: width, font: font, color: color, align: align)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSTextFieldDelegate {
    private let lastShoppingPDFPathKey = "lastShoppingPDFPath"
    var window: NSWindow!
    let priceBook = PriceBook()
    var recipes: [Recipe] = []
    var working = false
    var favoriteIDs = Set<String>()
    var favoritesPanel: NSPanel?
    var couponValues: [String: Double] = [:]
    var couponLimits: [String: Int] = [:]
    var couponSources: [String: String] = [:]
    var controlPanelProcess: Process?
    weak var controlPanelButton: NSButton?
    weak var controlPanelSpinner: NSProgressIndicator?
    var couponsPanel: NSPanel?
    var couponScanStatus: NSTextField?
    var lastPDFURL: URL?
    var lastRecipePDFURL: URL?
    var lastDailyMealsPDFURL: URL?

    let recipientField = NSTextField(string: "Mom")
    let daysField = NSTextField(string: "30")
    let peopleField = NSTextField(string: "1")
    let heightFeetField = NSTextField(string: "6")
    let heightInchesField = NSTextField(string: "5")
    let weightField = NSTextField(string: "300")
    let budgetMinField = NSTextField(string: "200")
    let budgetMaxField = NSTextField(string: "300")
    let grouping = NSPopUpButton()
    let breakfast = NSButton(checkboxWithTitle: "Breakfast", target: nil, action: nil)
    let lunch = NSButton(checkboxWithTitle: "Lunch", target: nil, action: nil)
    let dinner = NSButton(checkboxWithTitle: "Dinner", target: nil, action: nil)
    let snacks = NSButton(checkboxWithTitle: "Snacks", target: nil, action: nil)
    let bjs = NSButton(checkboxWithTitle: "BJ's", target: nil, action: nil)
    let costco = NSButton(checkboxWithTitle: "Costco", target: nil, action: nil)
    let shoprite = NSButton(checkboxWithTitle: "ShopRite", target: nil, action: nil)
    let stews = NSButton(checkboxWithTitle: "Stew Leonard's", target: nil, action: nil)
    let prioritizeSales = NSButton(checkboxWithTitle: "Apply deals to the list", target: nil, action: nil)
    let mealDBKeyField = NSTextField(string: "")
    let keyBenefitBanner = NSTextField(wrappingLabelWithString: "Optional paid TheMealDB supporter key: free key 1 still works. Supporter access adds V2, multi-ingredient filters, higher production access, recipe uploads, and app-store publishing rights under current terms.")
    let recipeDiet = NSPopUpButton()
    let nutritionGoal = NSPopUpButton()
    let status = NSTextField(wrappingLabelWithString: "Ready. Enter height and weight, then choose Build Muscle, Cutting, or Maintenance. Calories and macros are daily totals divided across meals and snacks.")
    let favoritesLabel = NSTextField(labelWithString: "0 saved")
    /// Where the control panel listens. Override with `defaults write
    /// <bundle-id> controlPanelURL http://127.0.0.1:9000` if you moved it.
    /// Where your config, scans and sales files live once installed.
    static var dataDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Library/Application Support")
        let dir = base.appendingPathComponent("Wellness Smart Shopping")
        try? FileManager.default.createDirectory(at: dir,
                                                 withIntermediateDirectories: true)
        return dir
    }

    static var controlPanelURL: String {
        UserDefaults.standard.string(forKey: "controlPanelURL") ?? "http://127.0.0.1:8765"
    }

    let couponsButton = NSButton(title: "Scan Deals...", target: nil, action: nil)
    /// When deals were last imported from a scan. PDFs wait until there is one.
    private let dealsScannedAtKey = "dealsScannedAt"
    /// A scan older than this is last week's deals, so it no longer counts.
    private let dealsFreshFor: TimeInterval = 7 * 24 * 60 * 60
    private var scanNudge: NSPopover?
    let printButton = NSButton(title: "Print Last PDFs...", target: nil, action: nil)

    func applicationDidFinishLaunching(_ notification: Notification) {
        favoriteIDs = Set(UserDefaults.standard.stringArray(forKey: "favoriteItemIDs") ?? [])
        couponValues = (UserDefaults.standard.dictionary(forKey: "couponSavingsByItem") ?? [:]).compactMapValues { ($0 as? NSNumber)?.doubleValue }
        couponLimits = (UserDefaults.standard.dictionary(forKey: "couponLimitsByItem") ?? [:]).compactMapValues { ($0 as? NSNumber)?.intValue }
        couponSources = UserDefaults.standard.dictionary(forKey: "couponSourcesByItem") as? [String: String] ?? [:]
        prioritizeSales.state = (UserDefaults.standard.object(forKey: "prioritizeVerifiedSales") as? Bool ?? true) ? .on : .off
        makeMenu()
        buildWindow()
        // Keep an installed Scanner in step with this build.
        if FileManager.default.fileExists(atPath: AppDelegate.scannerFolder.path) { syncScanner() }
        restoreLastOutput()
        // No deals loaded: say what a scan is worth, and point at the button.
        if verifiedSaleItemIDs().isEmpty {
            status.stringValue = AppDelegate.savingsMessage
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in
                guard let self else { return }
                self.pulse(self.couponsButton)
            }
        }
        NSApp.activate(ignoringOtherApps: true)
    }

    /// The same friendly nudge the control panel shows while no deals are loaded.
    static let savingsMessage = "You could be saving money this week! Press Scan Deals... to load this week's deals - every one it finds comes straight off your total."

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        // We started the control panel, so we stop it.
        stopControlPanel()
    }

    private func makeMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About Smart Shopping List", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit Smart Shopping List", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        NSApp.mainMenu = main
    }

    private func label(_ text: String, frame: NSRect) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.frame = frame
        field.font = .systemFont(ofSize: 12, weight: .medium)
        return field
    }

    private func buildWindow() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 810), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Smart Shopping List"
        window.center()
        let view = NSView(frame: window.contentView!.bounds)
        window.contentView = view

        let title = NSTextField(labelWithString: "Smart Shopping List")
        title.frame = NSRect(x: 28, y: 755, width: 500, height: 34)
        title.font = .boldSystemFont(ofSize: 26)
        view.addSubview(title)
        let subtitle = NSTextField(labelWithString: "Low-ink PDF lists with checkboxes, priced against this week's scanned deals")
        subtitle.frame = NSRect(x: 30, y: 730, width: 680, height: 22)
        subtitle.textColor = .darkGray
        view.addSubview(subtitle)

        view.addSubview(label("Recipient", frame: NSRect(x: 30, y: 685, width: 100, height: 22)))
        recipientField.frame = NSRect(x: 130, y: 682, width: 180, height: 26); view.addSubview(recipientField)
        view.addSubview(label("Days", frame: NSRect(x: 340, y: 685, width: 50, height: 22)))
        daysField.frame = NSRect(x: 390, y: 682, width: 60, height: 26); view.addSubview(daysField)
        view.addSubview(label("People", frame: NSRect(x: 475, y: 685, width: 60, height: 22)))
        peopleField.frame = NSRect(x: 535, y: 682, width: 60, height: 26); view.addSubview(peopleField)

        view.addSubview(label("Monthly budget", frame: NSRect(x: 30, y: 645, width: 110, height: 22)))
        view.addSubview(label("$", frame: NSRect(x: 143, y: 645, width: 15, height: 22)))
        budgetMinField.frame = NSRect(x: 158, y: 642, width: 72, height: 26); view.addSubview(budgetMinField)
        view.addSubview(label("to $", frame: NSRect(x: 242, y: 645, width: 38, height: 22)))
        budgetMaxField.frame = NSRect(x: 280, y: 642, width: 72, height: 26); view.addSubview(budgetMaxField)
        let budgetNote = NSTextField(labelWithString: "Frugal optimizer aims near $250 using value staples")
        budgetNote.frame = NSRect(x: 375, y: 645, width: 335, height: 22); budgetNote.font = .systemFont(ofSize: 10); budgetNote.textColor = .darkGray; view.addSubview(budgetNote)

        view.addSubview(label("Body size", frame: NSRect(x: 30, y: 605, width: 90, height: 22)))
        heightFeetField.frame = NSRect(x: 130, y: 602, width: 48, height: 26); view.addSubview(heightFeetField)
        view.addSubview(label("ft", frame: NSRect(x: 182, y: 605, width: 22, height: 22)))
        heightInchesField.frame = NSRect(x: 205, y: 602, width: 48, height: 26); view.addSubview(heightInchesField)
        view.addSubview(label("in", frame: NSRect(x: 258, y: 605, width: 22, height: 22)))
        weightField.frame = NSRect(x: 292, y: 602, width: 70, height: 26); view.addSubview(weightField)
        view.addSubview(label("lb", frame: NSRect(x: 367, y: 605, width: 24, height: 22)))
        let profileNote = NSTextField(labelWithString: "Sets daily macro ranges, meal portions and package counts")
        profileNote.frame = NSRect(x: 405, y: 605, width: 320, height: 22); profileNote.font = .systemFont(ofSize: 9.5); profileNote.textColor = .darkGray; view.addSubview(profileNote)

        view.addSubview(label("Group", frame: NSRect(x: 30, y: 565, width: 90, height: 22)))
        grouping.frame = NSRect(x: 130, y: 560, width: 220, height: 30)
        grouping.addItems(withTitles: ["Store and aisle", "Meal type"]); view.addSubview(grouping)
        let favoritesButton = NSButton(title: "Manage Favorites...", target: self, action: #selector(manageFavorites(_:)))
        favoritesButton.frame = NSRect(x: 390, y: 560, width: 170, height: 30); favoritesButton.bezelStyle = .rounded; view.addSubview(favoritesButton)
        favoritesLabel.frame = NSRect(x: 568, y: 564, width: 120, height: 22); favoritesLabel.textColor = .darkGray; view.addSubview(favoritesLabel)
        updateFavoritesLabel()

        view.addSubview(label("Meals", frame: NSRect(x: 30, y: 525, width: 90, height: 22)))
        for (button, x) in [(breakfast, 130), (lunch, 240), (dinner, 330), (snacks, 430)] { button.frame = NSRect(x: x, y: 522, width: 100, height: 24); button.state = .on; view.addSubview(button) }
        couponsButton.target = self; couponsButton.action = #selector(manageCoupons(_:)); couponsButton.frame = NSRect(x: 550, y: 518, width: 165, height: 30); couponsButton.bezelStyle = .rounded; view.addSubview(couponsButton)
        updateCouponsButton()
        view.addSubview(label("Stores", frame: NSRect(x: 30, y: 490, width: 90, height: 22)))
        for (button, x, width) in [(bjs, 130, 70), (costco, 205, 80), (shoprite, 290, 95), (stews, 390, 150)] { button.frame = NSRect(x: x, y: 487, width: width, height: 24); button.state = .on; view.addSubview(button) }
        prioritizeSales.frame = NSRect(x: 545, y: 487, width: 180, height: 24)
        prioritizeSales.toolTip = "Meals and the shopping list are always built from your nutrition target first. With this on, the week's imported offers are then applied to that finished list and cheaper on-sale substitutes are proposed for what is on it."
        view.addSubview(prioritizeSales)

        let box = NSBox(frame: NSRect(x: 25, y: 265, width: 710, height: 185))
        box.title = "Recipe matching"
        view.addSubview(box)
        view.addSubview(label("TheMealDB key", frame: NSRect(x: 45, y: 395, width: 190, height: 22)))
        mealDBKeyField.frame = NSRect(x: 240, y: 392, width: 250, height: 26)
        mealDBKeyField.placeholderString = "Blank uses free key 1"
        mealDBKeyField.delegate = self
        view.addSubview(mealDBKeyField)
        view.addSubview(label("Healthy lifestyle", frame: NSRect(x: 45, y: 355, width: 190, height: 22)))
        recipeDiet.frame = NSRect(x: 240, y: 350, width: 250, height: 30)
        recipeDiet.addItems(withTitles: ["Mediterranean", "DASH", "Plant-forward", "Vegetarian", "Pescatarian", "High-fiber balanced", "Low-sodium heart healthy"])
        view.addSubview(recipeDiet)
        view.addSubview(label("Nutrition goal", frame: NSRect(x: 45, y: 315, width: 190, height: 22)))
        nutritionGoal.frame = NSRect(x: 240, y: 310, width: 250, height: 30)
        nutritionGoal.addItems(withTitles: NutritionGoal.allCases.map { $0.rawValue })
        nutritionGoal.selectItem(withTitle: NutritionGoal.cutting.rawValue)
        view.addSubview(nutritionGoal)

        let recipeButton = NSButton(title: "Match Recipes to This List", target: self, action: #selector(fetchRecipes(_:)))
        recipeButton.frame = NSRect(x: 510, y: 386, width: 200, height: 34); recipeButton.bezelStyle = .rounded; view.addSubview(recipeButton)
        keyBenefitBanner.frame = NSRect(x: 45, y: 272, width: 665, height: 34)
        keyBenefitBanner.font = .systemFont(ofSize: 8.5, weight: .medium)
        keyBenefitBanner.textColor = NSColor(calibratedRed: 0.08, green: 0.32, blue: 0.12, alpha: 1)
        keyBenefitBanner.backgroundColor = NSColor(calibratedRed: 0.87, green: 0.97, blue: 0.88, alpha: 1)
        keyBenefitBanner.drawsBackground = true
        keyBenefitBanner.isBezeled = false
        keyBenefitBanner.maximumNumberOfLines = 3
        view.addSubview(keyBenefitBanner)
        updateKeyBenefitBanner()

        status.frame = NSRect(x: 30, y: 158, width: 700, height: 52)
        status.font = .systemFont(ofSize: 11); status.textColor = .darkGray; view.addSubview(status)

        let generate = NSButton(title: "Create 3 Paired PDFs...", target: self, action: #selector(createPDF(_:)))
        generate.frame = NSRect(x: 115, y: 95, width: 300, height: 52)
        generate.bezelStyle = .rounded; generate.keyEquivalent = "\r"; generate.font = .boldSystemFont(ofSize: 14); view.addSubview(generate)
        printButton.target = self; printButton.action = #selector(printLastPDF(_:)); printButton.frame = NSRect(x: 430, y: 95, width: 215, height: 52); printButton.bezelStyle = .rounded; printButton.isEnabled = false; view.addSubview(printButton)

        let footer = NSTextField(wrappingLabelWithString: "Price accuracy is disclosed in the shopping PDF. Nutrition targets are size-and-goal estimates; activity, age, sex, and medical history can change actual needs.")
        footer.frame = NSRect(x: 35, y: 35, width: 690, height: 38); footer.font = .systemFont(ofSize: 9); footer.textColor = .darkGray; footer.alignment = .center; view.addSubview(footer)
        window.makeKeyAndOrderFront(nil)
    }

    func controlTextDidChange(_ notification: Notification) {
        guard let field = notification.object as? NSTextField, field === mealDBKeyField else { return }
        updateKeyBenefitBanner()
    }

    private func updateKeyBenefitBanner() {
        let key = mealDBKeyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        keyBenefitBanner.isHidden = !key.isEmpty
    }

    private func pairedOutputURLs(for shoppingURL: URL) -> (recipe: URL, dailyMeals: URL) {
        let stem = shoppingURL.deletingPathExtension().lastPathComponent
        let folder = shoppingURL.deletingLastPathComponent()
        return (
            folder.appendingPathComponent("\(stem)_Recipes.pdf"),
            folder.appendingPathComponent("\(stem)_Daily_Meals.pdf")
        )
    }

    private func rememberedShoppingURL(defaultDays: Int = 30) -> URL? {
        if let path = UserDefaults.standard.string(forKey: lastShoppingPDFPathKey), !path.isEmpty {
            return URL(fileURLWithPath: path)
        }
        guard let downloads = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first else { return nil }
        let fallback = downloads.appendingPathComponent("Shopping_List_\(defaultDays)_Days_Corrected.pdf")
        return FileManager.default.fileExists(atPath: fallback.path) ? fallback : nil
    }

    private func restoreLastOutput() {
        guard let shoppingURL = rememberedShoppingURL() else { return }
        UserDefaults.standard.set(shoppingURL.path, forKey: lastShoppingPDFPathKey)
        let paired = pairedOutputURLs(for: shoppingURL)
        lastPDFURL = FileManager.default.fileExists(atPath: shoppingURL.path) ? shoppingURL : nil
        lastRecipePDFURL = FileManager.default.fileExists(atPath: paired.recipe.path) ? paired.recipe : nil
        lastDailyMealsPDFURL = FileManager.default.fileExists(atPath: paired.dailyMeals.path) ? paired.dailyMeals : nil
        printButton.isEnabled = lastPDFURL != nil && lastRecipePDFURL != nil && lastDailyMealsPDFURL != nil
        status.stringValue = "Remembered last report: \(shoppingURL.deletingLastPathComponent().lastPathComponent)/\(shoppingURL.lastPathComponent). New reports will default to the same folder."
    }

    private func chosenMeals() -> Set<String> {
        var set = Set<String>()
        if breakfast.state == .on { set.insert("Breakfast") }
        if lunch.state == .on { set.insert("Lunch") }
        if dinner.state == .on { set.insert("Dinner") }
        if snacks.state == .on { set.insert("Snack") }
        return set
    }

    private func chosenStores() -> Set<String> {
        var set = Set<String>()
        if bjs.state == .on { set.insert("BJ's") }
        if costco.state == .on { set.insert("Costco") }
        if shoprite.state == .on { set.insert("ShopRite") }
        if stews.state == .on { set.insert("Stew Leonard's") }
        return set
    }

    private func verifiedSaleItemIDs() -> Set<String> {
        // Any imported deal counts: the store list is no longer fixed, since
        // deals come from whichever store you scanned.
        Set(couponSources.keys.filter { id in
            (couponValues[id] ?? 0) > 0 && !(couponSources[id] ?? "").isEmpty
        })
    }

    private func selectedNutritionGoal() -> NutritionGoal {
        NutritionGoal(rawValue: nutritionGoal.titleOfSelectedItem ?? "") ?? .maintenance
    }

    private func selectedBodyProfile() -> (heightInches: Double?, weightPounds: Double?) {
        guard let feet = Double(heightFeetField.stringValue),
              let inches = Double(heightInchesField.stringValue),
              let weight = Double(weightField.stringValue) else { return (nil, nil) }
        let totalInches = feet * 12 + inches
        guard feet >= 4, feet <= 8, inches >= 0, inches < 12,
              weight >= 80, weight <= 700 else { return (nil, nil) }
        return (totalInches, weight)
    }

    private func updateFavoritesLabel() {
        favoritesLabel.stringValue = "\(favoriteIDs.count) saved"
    }

    @objc func manageFavorites(_ sender: Any?) {
        if let panel = favoritesPanel {
            panel.makeKeyAndOrderFront(nil)
            return
        }
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 560, height: 620), styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        panel.isReleasedWhenClosed = false
        panel.title = "Favorites - included until you unmark them"
        panel.center()
        let scroll = NSScrollView(frame: NSRect(x: 18, y: 58, width: 524, height: 540))
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        let document = NSView(frame: NSRect(x: 0, y: 0, width: 500, height: CGFloat(catalog.count * 32 + 20)))
        for (index, item) in catalog.enumerated() {
            let button = NSButton(checkboxWithTitle: "\(item.name)  -  \(item.store)", target: self, action: #selector(toggleFavorite(_:)))
            button.identifier = NSUserInterfaceItemIdentifier(item.id)
            button.state = favoriteIDs.contains(item.id) ? .on : .off
            button.frame = NSRect(x: 14, y: document.frame.height - CGFloat((index + 1) * 32), width: 465, height: 24)
            document.addSubview(button)
        }
        scroll.documentView = document
        panel.contentView?.addSubview(scroll)
        let close = NSButton(title: "Done", target: self, action: #selector(closeFavorites(_:)))
        close.frame = NSRect(x: 430, y: 16, width: 110, height: 32); close.bezelStyle = .rounded; panel.contentView?.addSubview(close)
        favoritesPanel = panel
        panel.makeKeyAndOrderFront(nil)
    }

    @objc func toggleFavorite(_ sender: NSButton) {
        guard let id = sender.identifier?.rawValue else { return }
        if sender.state == .on { favoriteIDs.insert(id) } else { favoriteIDs.remove(id) }
        UserDefaults.standard.set(Array(favoriteIDs).sorted(), forKey: "favoriteItemIDs")
        updateFavoritesLabel()
        status.stringValue = "Favorites updated. Saved favorites are included in every new weekly list until you unmark them."
    }

    @objc func closeFavorites(_ sender: Any?) {
        favoritesPanel?.orderOut(nil)
    }

    private func updateCouponsButton() {
        // Deals arrive from the control panel now, so the button always names
        // that route rather than counting coupons.
        couponsButton.title = "Scan Deals..."
    }

    @objc func manageCoupons(_ sender: Any?) {
        if let panel = couponsPanel {
            panel.makeKeyAndOrderFront(nil)
            return
        }
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 560, height: 260),
                            styleMask: [.titled, .closable], backing: .buffered, defer: false)
        panel.isReleasedWhenClosed = false
        // NSPanel hides itself when the app deactivates, which would make this
        // vanish the moment the browser opens. Keep it on screen.
        panel.hidesOnDeactivate = false
        panel.title = "Scan Deals"
        panel.center()

        let heading = NSTextField(labelWithString: "Scan this week's deals")
        heading.font = .systemFont(ofSize: 15, weight: .semibold)
        heading.frame = NSRect(x: 24, y: 206, width: 512, height: 24)
        panel.contentView?.addSubview(heading)

        let note = NSTextField(wrappingLabelWithString: "Start the control panel and scan this week's deals there, with the Scanner extension or Claude. It writes a sales file, which you import here. PDFs are made only after a scan.")
        note.frame = NSRect(x: 24, y: 152, width: 512, height: 48)
        note.font = .systemFont(ofSize: 11); note.textColor = .secondaryLabelColor
        panel.contentView?.addSubview(note)

        let startButton = NSButton(title: "Start Control Panel", target: self, action: #selector(openControlPanel(_:)))
        startButton.frame = NSRect(x: 24, y: 104, width: 180, height: 32)
        startButton.bezelStyle = .rounded; startButton.keyEquivalent = "\r"
        panel.contentView?.addSubview(startButton)
        controlPanelButton = startButton

        let importXML = NSButton(title: "Import Sales XML...", target: self, action: #selector(importSalesXML(_:)))
        importXML.toolTip = "Import the sales file the control panel wrote after a scan."
        importXML.frame = NSRect(x: 212, y: 104, width: 170, height: 32)
        importXML.bezelStyle = .rounded
        panel.contentView?.addSubview(importXML)

        let scanner = NSButton(title: "Set Up Scanner...", target: self, action: #selector(setUpScanner(_:)))
        scanner.toolTip = "Put the Scanner extension where your browser can load it, and show how."
        scanner.frame = NSRect(x: 390, y: 104, width: 146, height: 32)
        scanner.bezelStyle = .rounded
        panel.contentView?.addSubview(scanner)

        let spinner = NSProgressIndicator(frame: NSRect(x: 24, y: 68, width: 16, height: 16))
        spinner.style = .spinning; spinner.isDisplayedWhenStopped = false
        panel.contentView?.addSubview(spinner)
        controlPanelSpinner = spinner

        let scanStatus = NSTextField(wrappingLabelWithString: controlPanelIsRunning
            ? "The control panel is running. Scan there, then import the file here."
            : "No deals imported yet. Start the control panel to scan.")
        scanStatus.frame = NSRect(x: 46, y: 56, width: 490, height: 34)
        scanStatus.font = .systemFont(ofSize: 11); scanStatus.textColor = .secondaryLabelColor
        panel.contentView?.addSubview(scanStatus)
        couponScanStatus = scanStatus

        let clear = NSButton(title: "Clear Imported Deals", target: self, action: #selector(clearCoupons(_:)))
        clear.frame = NSRect(x: 24, y: 16, width: 185, height: 32)
        clear.bezelStyle = .rounded
        panel.contentView?.addSubview(clear)

        let close = NSButton(title: "Close", target: self, action: #selector(saveCoupons(_:)))
        close.frame = NSRect(x: 441, y: 16, width: 95, height: 32)
        close.bezelStyle = .rounded
        panel.contentView?.addSubview(close)

        couponsPanel = panel
        panel.makeKeyAndOrderFront(nil)
    }

    // MARK: - The Scanner extension

    /// Where the Scanner lives for the browser to load: a stable folder in
    /// Application Support, so the path survives app updates and the app can
    /// refresh it in place.
    static var scannerFolder: URL {
        dataDirectory.appendingPathComponent("Scanner Extension")
    }

    /// The copy that ships inside the app (Resources/panel/extension).
    private var bundledScanner: URL? {
        let url = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/panel/extension")
        return FileManager.default.fileExists(atPath: url.appendingPathComponent("manifest.json").path) ? url : nil
    }

    /// Copy the bundled Scanner into its folder when missing or out of date.
    /// Returns false if there is nothing to copy (a build without it).
    @discardableResult
    func syncScanner() -> Bool {
        guard let source = bundledScanner else { return false }
        let target = AppDelegate.scannerFolder
        let fm = FileManager.default
        func version(_ dir: URL) -> String? {
            guard let data = try? Data(contentsOf: dir.appendingPathComponent("manifest.json")),
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
            return json["version"] as? String
        }
        let bundledVersion = version(source)
        if fm.fileExists(atPath: target.path), version(target) == bundledVersion,
           let a = try? fm.contentsOfDirectory(atPath: source.appendingPathComponent("sites").path),
           let b = try? fm.contentsOfDirectory(atPath: target.appendingPathComponent("sites").path),
           Set(a) == Set(b),
           // Same version and same site files: compare the site files' bytes too,
           // since a site fix may ship without a version bump.
           a.allSatisfy({ fm.contentsEqual(atPath: source.appendingPathComponent("sites/\($0)").path,
                                           andPath: target.appendingPathComponent("sites/\($0)").path) }) {
            return true
        }
        // Replace the contents, not the folder, so a browser that loaded it
        // keeps pointing at the same place.
        try? fm.createDirectory(at: target, withIntermediateDirectories: true)
        for item in (try? fm.contentsOfDirectory(atPath: target.path)) ?? [] {
            try? fm.removeItem(at: target.appendingPathComponent(item))
        }
        for item in (try? fm.contentsOfDirectory(atPath: source.path)) ?? [] where item != "test" {
            try? fm.copyItem(at: source.appendingPathComponent(item), to: target.appendingPathComponent(item))
        }
        return true
    }

    @objc func setUpScanner(_ sender: Any?) {
        guard syncScanner() else {
            let alert = NSAlert()
            alert.messageText = "This build has no Scanner inside"
            alert.informativeText = "Load the extension folder from the project instead (deal-crawler/extension)."
            alert.runModal()
            return
        }
        let folder = AppDelegate.scannerFolder
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(folder.path, forType: .string)
        NSWorkspace.shared.activateFileViewerSelecting([folder])

        let alert = NSAlert()
        alert.messageText = "Add the Scanner to your browser"
        alert.informativeText = """
        It is one folder, now shown in Finder (its path is on your clipboard). In Chrome or Edge:

        1. Go to chrome://extensions (Edge: edge://extensions).
        2. Switch on Developer mode.
        3. Press Load unpacked and choose the "Scanner Extension" folder.

        That's it. When this app updates, it refreshes that folder; press the reload arrow on the Scanner in the extensions page to pick up the new version.
        """
        alert.addButton(withTitle: "Done")
        alert.runModal()
    }

    private func persistCoupons() {
        UserDefaults.standard.set(couponValues, forKey: "couponSavingsByItem")
        UserDefaults.standard.set(couponLimits, forKey: "couponLimitsByItem")
        UserDefaults.standard.set(couponSources, forKey: "couponSourcesByItem")
        updateCouponsButton()
    }

    private func applyDetectedCoupons(_ matches: [DetectedCoupon], replacingStores: Set<String> = []) {
        let staleIDs = couponSources.compactMap { replacingStores.contains($0.value) ? $0.key : nil }
        for id in staleIDs {
            couponValues.removeValue(forKey: id)
            couponLimits.removeValue(forKey: id)
            couponSources.removeValue(forKey: id)
        }
        for match in matches {
            guard match.savingsPerPackage > 0 else { continue }
            // Keep the best offer for each item. The old `|| couponSources != nil` clause
            // let any later match overwrite an existing one — even a smaller offer, and even
            // a manually entered value — so a second scan could silently downgrade savings.
            if match.savingsPerPackage >= (couponValues[match.itemID] ?? 0) {
                couponValues[match.itemID] = min(250, match.savingsPerPackage)
                couponLimits[match.itemID] = max(1, match.maximumUses)
                couponSources[match.itemID] = match.store
            }
        }
        persistCoupons()
    }

    // Scans the given stores' public offer pages. Returns a status message and the set of
    // stores that returned NO readable offers (a sign-in is almost certainly required for those).


    // When a site's public page has no readable coupons, offer to open a sign-in window so the
    // user's own logged-in session can be scanned (the only reliable way to reach digital coupons).






    // Preview the scanned deals and let the user pick which to apply.
    /// A bold, bordered banner for a store's redeem notice: red when skipping
    /// it means paying full price, amber when it is only something to know.
    private func redeemBannerView(_ notice: RedeemNotice, width: CGFloat) -> NSView {
        let color: NSColor = notice.mustAct ? .systemRed : .systemOrange
        let text = NSMutableAttributedString(
            string: (notice.mustAct ? "⚠︎ " : "") + notice.title + "\n",
            attributes: [.font: NSFont.systemFont(ofSize: 13, weight: .heavy), .foregroundColor: color])
        text.append(NSAttributedString(string: notice.body,
            attributes: [.font: NSFont.systemFont(ofSize: 11.5), .foregroundColor: NSColor.labelColor]))
        let label = NSTextField(wrappingLabelWithString: "")
        label.attributedStringValue = text
        label.preferredMaxLayoutWidth = width - 28
        let fit = label.sizeThatFits(NSSize(width: width - 28, height: 1000))
        let box = NSBox(frame: NSRect(x: 0, y: 0, width: width, height: fit.height + 24))
        box.boxType = .custom
        box.borderWidth = notice.mustAct ? 3 : 2
        box.cornerRadius = 8
        box.borderColor = color
        box.fillColor = color.withAlphaComponent(0.10)
        box.titlePosition = .noTitle
        box.contentViewMargins = NSSize(width: 12, height: 10)
        label.frame = NSRect(x: 12, y: 10, width: width - 28, height: fit.height)
        box.contentView?.addSubview(label)
        return box
    }

    private func presentScannedDealsPreview(_ offers: [DetectedCoupon]) -> [DetectedCoupon]? {
        let sorted = offers.sorted { $0.savingsPerPackage > $1.savingsPerPackage }
        let alert = NSAlert()
        alert.messageText = "Apply these scanned deals?"
        let potential = sorted.reduce(0.0) { $0 + $1.savingsPerPackage }
        let stores = Set(sorted.map { $0.store }).sorted().joined(separator: ", ")
        alert.informativeText = "Matched from this week's \(stores) scan. Savings are estimated against the app's normal price - verify at your store, and uncheck anything that looks off. Potential per-package savings: \(money(potential))."
        alert.addButton(withTitle: "Apply Selected")
        alert.addButton(withTitle: "Cancel")
        let rowHeight = 24
        let width = 470
        let listHeight = min(320, max(1, sorted.count) * rowHeight + 6)
        // What these stores need before the savings count, above the list.
        let notices = Set(sorted.map { $0.store }).compactMap { redeemNotice(for: $0) }
            .sorted { $0.mustAct && !$1.mustAct }
        var banners: [NSView] = []
        for notice in notices { banners.append(redeemBannerView(notice, width: CGFloat(width))) }
        let bannerHeight = banners.reduce(0) { $0 + Int($1.frame.height) + 8 }
        let height = listHeight + bannerHeight
        let container = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        var top = CGFloat(height)
        for banner in banners {
            top -= banner.frame.height
            banner.frame.origin = NSPoint(x: 0, y: top)
            container.addSubview(banner)
            top -= 8
        }
        var boxes: [(NSButton, DetectedCoupon)] = []
        for (index, offer) in sorted.enumerated() {
            let name = catalog.first { $0.id == offer.itemID }?.name ?? offer.matchedTitle
            let box = NSButton(checkboxWithTitle: "\(name) · est. save \(money(offer.savingsPerPackage))/package", target: nil, action: nil)
            box.state = .on
            box.frame = NSRect(x: 0, y: listHeight - (index + 1) * rowHeight, width: width, height: rowHeight)
            container.addSubview(box)
            boxes.append((box, offer))
        }
        alert.accessoryView = container
        return alert.runModal() == .alertFirstButtonReturn ? boxes.filter { $0.0.state == .on }.map { $0.1 } : nil
    }




    /// True when something is already serving on the control panel's port.
    private var controlPanelIsRunning: Bool {
        guard let url = URL(string: AppDelegate.controlPanelURL) else { return false }
        // GET, not HEAD: a plain http.server answers HEAD with 501, which made
        // this report "not running" against a panel that was serving fine.
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 1.5)
        request.httpMethod = "GET"
        let semaphore = DispatchSemaphore(value: 0)
        var ok = false
        URLSession.shared.dataTask(with: request) { _, response, _ in
            ok = (response as? HTTPURLResponse)?.statusCode == 200
            semaphore.signal()
        }.resume()
        _ = semaphore.wait(timeout: .now() + 2)
        return ok
    }

    /// Finds panel.py. Checked in order: a folder the user picked before, then
    /// beside the app, then the usual places a download or clone ends up.
    private func locateControlPanel() -> URL? {
        var candidates: [URL] = []
        // Shipped inside the app: a drag-to-Applications install needs no
        // folder anywhere else.
        candidates.append(Bundle.main.bundleURL
            .appendingPathComponent("Contents/Resources/panel"))
        if let saved = UserDefaults.standard.string(forKey: "controlPanelDirectory") {
            candidates.append(URL(fileURLWithPath: saved))
        }
        let bundle = Bundle.main.bundleURL.deletingLastPathComponent()
        candidates.append(bundle)
        candidates.append(bundle.appendingPathComponent("deal-crawler"))
        candidates.append(bundle.deletingLastPathComponent().appendingPathComponent("deal-crawler"))
        let home = FileManager.default.homeDirectoryForCurrentUser
        for root in ["Downloads", "Documents", "dev", ""] {
            let base = root.isEmpty ? home : home.appendingPathComponent(root)
            for name in ["wellness-smart-shopping", "deal-crawler",
                         "Wellness-Shopper/deal-crawler",
                         "wellness-smart-shopping/deal-crawler"] {
                candidates.append(base.appendingPathComponent(name))
            }
        }
        for dir in candidates {
            let script = dir.appendingPathComponent("panel.py")
            if FileManager.default.fileExists(atPath: script.path) { return script }
        }
        return nil
    }

    /// Asks the user to point at the folder once, then remembers it.
    private func askForControlPanelFolder() -> URL? {
        let open = NSOpenPanel()
        open.canChooseDirectories = true
        open.canChooseFiles = false
        open.allowsMultipleSelection = false
        open.prompt = "Use This Folder"
        open.message = "Where is the Wellness Smart Shopping folder? (the one containing panel.py)"
        guard open.runModal() == .OK, let dir = open.url else { return nil }
        let script = dir.appendingPathComponent("panel.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            let alert = NSAlert()
            alert.messageText = "That folder has no panel.py"
            alert.informativeText = "Pick the folder that contains panel.py."
            alert.runModal()
            return nil
        }
        UserDefaults.standard.set(dir.path, forKey: "controlPanelDirectory")
        return script
    }

    private func setControlPanelBusy(_ busy: Bool, _ message: String) {
        DispatchQueue.main.async {
            self.couponScanStatus?.stringValue = message
            if busy {
                self.controlPanelSpinner?.startAnimation(nil)
                self.controlPanelButton?.isEnabled = false
            } else {
                self.controlPanelSpinner?.stopAnimation(nil)
                self.controlPanelButton?.isEnabled = true
            }
        }
    }

    /// Starts the control panel and opens it, reporting progress as it goes.
    /// The panel is stopped again when this app quits.
    @objc func openControlPanel(_ sender: Any?) {
        guard let url = URL(string: AppDelegate.controlPanelURL) else { return }

        if controlPanelIsRunning {
            NSWorkspace.shared.open(url)
            setControlPanelBusy(false, "Control panel is already running - opened it in your browser.")
            return
        }

        guard let script = locateControlPanel() ?? askForControlPanelFolder() else {
            setControlPanelBusy(false, "Could not find panel.py. Choose the folder that contains it and try again.")
            return
        }

        setControlPanelBusy(true, "Starting the control panel...")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", script.path, "--no-open"]
        process.currentDirectoryURL = script.deletingLastPathComponent()
        // The bundle is read-only and signed, so your files live in
        // Application Support. panel.py honours WSS_DATA_DIR.
        var environment = ProcessInfo.processInfo.environment
        environment["WSS_DATA_DIR"] = AppDelegate.dataDirectory.path
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process.environment = environment
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
        } catch {
            // The only thing this app needs that it does not carry itself.
            // macOS ships python3, but a machine that has never installed the
            // command line tools has only a stub.
            setControlPanelBusy(false, "Could not start the control panel. macOS needs its command line tools for this - open Terminal and run:  xcode-select --install")
            return
        }
        controlPanelProcess = process

        // Wait for it to answer rather than opening a browser on a dead port.
        DispatchQueue.global(qos: .userInitiated).async {
            for attempt in 1...20 {
                Thread.sleep(forTimeInterval: 0.5)
                if !process.isRunning {
                    self.setControlPanelBusy(false, "The control panel stopped while starting up. Try running python3 panel.py in that folder to see why.")
                    self.controlPanelProcess = nil
                    return
                }
                if self.controlPanelIsRunning {
                    DispatchQueue.main.async { NSWorkspace.shared.open(url) }
                    self.setControlPanelBusy(false, "Control panel ready. Scan there, then import the file it writes. It closes when you quit this app.")
                    return
                }
                self.setControlPanelBusy(true, "Waiting for the control panel to come up... (\(attempt * 5)/100)")
            }
            self.setControlPanelBusy(false, "The control panel did not answer in time. Open \(AppDelegate.controlPanelURL) yourself, or run python3 panel.py in that folder.")
        }
    }

    /// The panel is ours to clean up: stop it when the app goes away.
    func stopControlPanel() {
        guard let process = controlPanelProcess, process.isRunning else { return }
        process.terminate()
        controlPanelProcess = nil
    }

    @objc func importSalesXML(_ sender: Any?) {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.xml]
        panel.allowsMultipleSelection = false
        panel.prompt = "Import Sales"
        panel.message = "Choose a sales XML file (catalog itemId + savings or salePrice per offer)."
        guard panel.runModal() == .OK, let url = panel.url, let data = try? Data(contentsOf: url) else { return }
        let offers = parseSalesXML(data, items: catalog)
        // The scan happened, whether or not any of it matched this list.
        UserDefaults.standard.set(Date(), forKey: dealsScannedAtKey)
        guard !offers.isEmpty else {
            couponScanStatus?.stringValue = "No matching offers found in \(url.lastPathComponent). Check the XML uses valid catalog item IDs."
            return
        }
        guard let chosen = presentScannedDealsPreview(offers), !chosen.isEmpty else {
            couponScanStatus?.stringValue = "No offers applied from \(url.lastPathComponent)."
            return
        }
        applyDetectedCoupons(chosen)
        let total = chosen.reduce(0.0) { $0 + $1.savingsPerPackage }
        let mustLoad = Set(chosen.map { $0.store }).compactMap { redeemNotice(for: $0) }.filter { $0.mustAct }
        let reminder = mustLoad.isEmpty ? "" : " Next: log in to ShopRite and load these coupons to your account - it's the only way they come off at the register."
        couponScanStatus?.stringValue = "Imported \(chosen.count) offer(s) from \(url.lastPathComponent) (est. \(money(total))/package saved). Verify at your store.\(reminder)"
    }

    @objc func clearCoupons(_ sender: Any?) {
        couponValues.removeAll()
        couponLimits.removeAll()
        couponSources.removeAll()
        UserDefaults.standard.removeObject(forKey: "couponSavingsByItem")
        UserDefaults.standard.removeObject(forKey: "couponLimitsByItem")
        UserDefaults.standard.removeObject(forKey: "couponSourcesByItem")
        UserDefaults.standard.removeObject(forKey: dealsScannedAtKey)
        updateCouponsButton()
        couponScanStatus?.stringValue = "Imported deals cleared."
        status.stringValue = "Deals cleared. New reports will use regular estimated prices."
    }

    /// Closes the panel. Imported deals are already saved, so there is nothing
    /// to gather here -- the per-item fields this used to read are gone.
    @objc func saveCoupons(_ sender: Any?) {
        couponsPanel?.orderOut(nil)
        let count = couponValues.values.filter { $0 > 0 }.count
        guard count > 0 else { return }
        let perPackage = couponValues.values.reduce(0, +)
        status.stringValue = "\(count) imported deal\(count == 1 ? "" : "s") in effect, \(money(perPackage)) per package; actual savings depend on quantities."
    }


    private func mealDBRecipe(from data: Data) -> (recipe: Recipe, category: String)? {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let meals = json["meals"] as? [[String: Any]], let meal = meals.first,
              let title = meal["strMeal"] as? String, !title.isEmpty else { return nil }
        var ingredients: [String] = []
        for index in 1...20 {
            let ingredient = ((meal["strIngredient\(index)"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !ingredient.isEmpty else { continue }
            let measure = ((meal["strMeasure\(index)"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            ingredients.append(measure.isEmpty ? ingredient : "\(measure) \(ingredient)")
        }
        let rawInstructions = ((meal["strInstructions"] as? String) ?? "Follow the source recipe instructions.")
            .replacingOccurrences(of: "\r", with: "\n")
            .replacingOccurrences(of: ". ", with: ".\n")
        let steps = rawInstructions.split(separator: "\n").map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        let id = (meal["idMeal"] as? String) ?? ""
        let source = ((meal["strSource"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let sourceURL = source.isEmpty ? (id.isEmpty ? nil : "https://www.themealdb.com/meal/\(id)") : source
        let macroEstimate = estimateMacrosFromIngredients(title: title, ingredients: ingredients)
        return (
            Recipe(title: title, baseServings: 2, readyMinutes: nil, ingredients: ingredients, steps: steps.isEmpty ? ["Follow the linked source instructions."] : steps, sourceURL: sourceURL, sourceName: "TheMealDB", macrosPerServing: macroEstimate),
            (meal["strCategory"] as? String) ?? ""
        )
    }

    private func recipeScore(_ recipe: Recipe, basketTerms: [String]) -> (overlap: Int, missing: Int) {
        let pantry = ["salt", "pepper", "water", "garlic", "onion", "spice", "paprika", "cumin", "oregano", "thyme", "rosemary", "parsley", "basil", "vinegar", "lemon", "lime", "oil"]
        var overlap = 0
        var missing = 0
        for line in recipe.ingredients {
            let lower = line.lowercased()
            if pantry.contains(where: { lower.contains($0) }) { continue }
            if basketTerms.contains(where: { lower.contains($0) || $0.contains(lower) }) { overlap += 1 }
            else { missing += 1 }
        }
        return (overlap, missing)
    }

    private func fitsLifestyle(_ recipe: Recipe, category: String, lifestyle: String) -> Bool {
        recipeMatchesLifestyle(recipe, category: category, lifestyle: lifestyle)
    }

    @objc func fetchRecipes(_ sender: Any?) {
        guard !working else { return }
        let days = max(1, min(90, Int(daysField.stringValue) ?? 30))
        let people = max(1, min(12, Int(peopleField.stringValue) ?? 1))
        let enteredMin = max(1, Double(budgetMinField.stringValue) ?? 200)
        let enteredMax = max(1, Double(budgetMaxField.stringValue) ?? 300)
        let meals = chosenMeals(); let stores = chosenStores()
        guard !meals.isEmpty, !stores.isEmpty else { status.stringValue = "Choose at least one meal type and one store first."; return }
        let goal = selectedNutritionGoal()
        let profile = selectedBodyProfile()
        guard profile.heightInches != nil, profile.weightPounds != nil else {
            status.stringValue = "Enter a valid height (4-8 ft, 0-11 in) and weight (80-700 lb) before matching recipes."
            return
        }
        let options = ListOptions(recipient: "Home", days: days, people: people, budgetMin: min(enteredMin, enteredMax), budgetMax: max(enteredMin, enteredMax), groupByStore: true, enabledMeals: meals, enabledStores: stores, nutritionGoal: goal, heightInches: profile.heightInches, weightPounds: profile.weightPounds, prioritizeSales: prioritizeSales.state == .on, saleItemIDs: verifiedSaleItemIDs())
        let plan = makeShoppingPlan(options: options, items: catalog, prices: priceBook, favorites: favoriteIDs, coupons: couponValues, couponLimits: couponLimits)
        let lifestyle = recipeDiet.titleOfSelectedItem ?? "Mediterranean"
        let queryNames = Array(Array(Set(plan.rows.map { apiIngredientName(for: $0.item) })).filter { $0 != "spices" }.prefix(12))
        let enteredMealDBKey = mealDBKeyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let usesSupporterKey = !enteredMealDBKey.isEmpty
        let mealDBKey = usesSupporterKey ? enteredMealDBKey : "1"
        let encodedKey = mealDBKey.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? "1"
        let mealDBBaseURL = "https://www.themealdb.com/api/json/\(usesSupporterKey ? "v2" : "v1")/\(encodedKey)"
        var filterQueries = queryNames
        if usesSupporterKey, queryNames.count >= 2 {
            filterQueries.insert(queryNames.prefix(3).joined(separator: ","), at: 0)
        }
        let basketTerms = plan.rows.flatMap { row in
            apiIngredientName(for: row.item).lowercased().split(separator: " ").map(String.init).filter { $0.count > 3 }
        }
        working = true
        status.stringValue = "Matching TheMealDB \(usesSupporterKey ? "supporter V2" : "free") recipes against \(queryNames.count) basket ingredients for \(goal.rawValue)..."
        let summaryGroup = DispatchGroup(); let lock = NSLock()
        var summaries: [String: MealDBSummary] = [:]
        for ingredient in filterQueries {
            var parts = URLComponents(string: "\(mealDBBaseURL)/filter.php")!
            parts.queryItems = [URLQueryItem(name: "i", value: ingredient)]
            guard let url = parts.url else { continue }
            summaryGroup.enter()
            URLSession.shared.dataTask(with: url) { data, _, _ in
                defer { summaryGroup.leave() }
                guard let data, let response = try? JSONDecoder().decode(MealDBFilterResponse.self, from: data) else { return }
                lock.lock(); for meal in response.meals ?? [] { summaries[meal.idMeal] = meal }; lock.unlock()
            }.resume()
        }
        summaryGroup.notify(queue: .global(qos: .userInitiated)) {
            let candidates = Array(summaries.values.prefix(36))
            let detailGroup = DispatchGroup()
            var scored: [(Recipe, Int)] = []
            for summary in candidates {
                var parts = URLComponents(string: "\(mealDBBaseURL)/lookup.php")!
                parts.queryItems = [URLQueryItem(name: "i", value: summary.idMeal)]
                guard let url = parts.url else { continue }
                detailGroup.enter()
                URLSession.shared.dataTask(with: url) { data, _, _ in
                    defer { detailGroup.leave() }
                    guard let data, let parsed = self.mealDBRecipe(from: data), self.fitsLifestyle(parsed.recipe, category: parsed.category, lifestyle: lifestyle) else { return }
                    let score = self.recipeScore(parsed.recipe, basketTerms: basketTerms)
                    guard score.overlap >= 2, score.missing <= 1 else { return }
                    let goalScore = nutritionGoalScore(parsed.recipe, goal: goal)
                    lock.lock(); scored.append((parsed.recipe, score.overlap * 4 - score.missing * 3 + goalScore)); lock.unlock()
                }.resume()
            }
            detailGroup.notify(queue: .main) {
                self.working = false
                let needed = recipeCountNeeded(for: days)
                self.recipes = scored.sorted { $0.1 > $1.1 }.prefix(needed).map { $0.0 }
                if self.recipes.isEmpty {
                    self.status.stringValue = "TheMealDB returned no strong basket matches for this lifestyle and \(goal.rawValue) goal. Built-in goal-adjusted recipes will still create a complete \(days)-day PDF."
                } else {
                    self.status.stringValue = "Matched \(self.recipes.count) TheMealDB recipes for \(goal.rawValue). Built-in goal-adjusted recipes fill remaining days; one recipe is scheduled every day."
                }
            }
        }
    }

    /// True once this week's deals have been scanned and imported.
    private var hasFreshScan: Bool {
        guard let at = UserDefaults.standard.object(forKey: dealsScannedAtKey) as? Date else { return false }
        return Date().timeIntervalSince(at) < dealsFreshFor
    }

    /// No PDF without deals: point at the scan button instead.
    private func nudgeToScan() {
        let stale = UserDefaults.standard.object(forKey: dealsScannedAtKey) != nil
        let message = stale
            ? "Time for a fresh scan! Your deals are over a week old - press Scan Deals... and your PDFs will be priced with this week's savings."
            : "You could be saving money this week! Press Scan Deals... first - your PDFs are priced with the deals it finds."
        status.stringValue = message
        pulse(couponsButton)

        scanNudge?.close()
        let label = NSTextField(wrappingLabelWithString: message)
        label.font = .systemFont(ofSize: 12)
        label.frame = NSRect(x: 12, y: 10, width: 236, height: 40)
        let content = NSViewController()
        content.view = NSView(frame: NSRect(x: 0, y: 0, width: 260, height: 60))
        content.view.addSubview(label)
        let popover = NSPopover()
        popover.contentViewController = content
        popover.contentSize = content.view.frame.size
        popover.behavior = .transient
        popover.show(relativeTo: couponsButton.bounds, of: couponsButton, preferredEdge: .maxY)
        scanNudge = popover
        DispatchQueue.main.asyncAfter(deadline: .now() + 6) { [weak popover] in popover?.close() }
    }

    /// A ring that swells and fades around a button, a few times over.
    private func pulse(_ button: NSView) {
        guard let host = button.superview else { return }
        host.wantsLayer = true
        guard let layer = host.layer else { return }
        let ring = CALayer()
        ring.frame = button.frame.insetBy(dx: -3, dy: -3)
        ring.cornerRadius = 9
        ring.borderWidth = 3
        ring.borderColor = NSColor.systemGreen.cgColor
        ring.opacity = 0
        layer.addSublayer(ring)

        let grow = CABasicAnimation(keyPath: "transform.scale")
        grow.fromValue = 1.0; grow.toValue = 1.18
        let fade = CABasicAnimation(keyPath: "opacity")
        fade.fromValue = 0.95; fade.toValue = 0.0
        let beat = CAAnimationGroup()
        beat.animations = [grow, fade]
        beat.duration = 0.9
        beat.repeatCount = 4
        beat.timingFunction = CAMediaTimingFunction(name: .easeOut)
        CATransaction.begin()
        CATransaction.setCompletionBlock { ring.removeFromSuperlayer() }
        ring.add(beat, forKey: "pulse")
        CATransaction.commit()
    }

    @objc func createPDF(_ sender: Any?) {
        guard !working else { return }
        // Deals come before PDFs: the list is priced against this week's scan.
        guard hasFreshScan else {
            nudgeToScan()
            return
        }
        let useSales = prioritizeSales.state == .on
        UserDefaults.standard.set(useSales, forKey: "prioritizeVerifiedSales")
        guard useSales else {
            createPDFNow(sender)
            return
        }
        let stores = chosenStores()
        guard !stores.isEmpty else {
            status.stringValue = "Choose at least one store before refreshing sale offers."
            return
        }
        // Deals are imported from a scan rather than fetched here, so
        // tailoring uses whatever has already been imported.
        let count = verifiedSaleItemIDs().count
        if count == 0 {
            status.stringValue = "This week's scan matched nothing on your list - creating it at regular prices."
        } else {
            status.stringValue = "Tailoring the list and recipes around \(count) imported sale item\(count == 1 ? "" : "s")."
        }
        createPDFNow(sender)
    }

    // Preview the proposed on-sale swaps and let the user pick which to apply.
    // Returns the chosen swaps, an empty array to proceed with no swaps, or nil to cancel.
    private func presentSaleSwapPreview(_ swaps: [SaleSwap]) -> [SaleSwap]? {
        let alert = NSAlert()
        alert.messageText = "Swap in this week's sale items?"
        let potential = swaps.reduce(0.0) { $0 + $1.estimatedSavings }
        alert.informativeText = "These optional items can be replaced with on-sale equivalents in the same group. Recipe ingredients and favorites are never touched. Uncheck any you want to keep. Potential savings: \(money(potential))."
        alert.addButton(withTitle: "Apply Selected Swaps")
        alert.addButton(withTitle: "Skip Swaps")
        alert.addButton(withTitle: "Cancel")

        let rowHeight = 24
        let width = 470
        let height = min(320, max(1, swaps.count) * rowHeight + 6)
        let container = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        var boxes: [(NSButton, SaleSwap)] = []
        for (index, swap) in swaps.enumerated() {
            let box = NSButton(checkboxWithTitle: "\(swap.fromName)  →  \(swap.toName)  (\(swap.store)) · save \(money(swap.estimatedSavings))", target: nil, action: nil)
            box.state = .on
            box.frame = NSRect(x: 0, y: height - (index + 1) * rowHeight, width: width, height: rowHeight)
            container.addSubview(box)
            boxes.append((box, swap))
        }
        alert.accessoryView = container

        switch alert.runModal() {
        case .alertFirstButtonReturn: return boxes.filter { $0.0.state == .on }.map { $0.1 }
        case .alertSecondButtonReturn: return []
        default: return nil
        }
    }

    private func createPDFNow(_ sender: Any?) {
        let days = max(1, min(90, Int(daysField.stringValue) ?? 30))
        let people = max(1, min(12, Int(peopleField.stringValue) ?? 1))
        let enteredMin = max(1, Double(budgetMinField.stringValue) ?? 200)
        let enteredMax = max(1, Double(budgetMaxField.stringValue) ?? 300)
        let budgetMin = min(enteredMin, enteredMax)
        let budgetMax = max(enteredMin, enteredMax)
        budgetMinField.stringValue = String(format: "%.0f", budgetMin)
        budgetMaxField.stringValue = String(format: "%.0f", budgetMax)
        let meals = chosenMeals()
        let stores = chosenStores()
        guard !meals.isEmpty, !stores.isEmpty else {
            status.stringValue = "Choose at least one meal type and one store."
            return
        }
        let recipient = recipientField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "Home" : recipientField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let goal = selectedNutritionGoal()
        let profile = selectedBodyProfile()
        guard profile.heightInches != nil, profile.weightPounds != nil else {
            status.stringValue = "Enter a valid height (4-8 ft, 0-11 in) and weight (80-700 lb) before creating PDFs."
            return
        }
        let saleIDs = verifiedSaleItemIDs()
        let options = ListOptions(recipient: recipient, days: days, people: people, budgetMin: budgetMin, budgetMax: budgetMax, groupByStore: grouping.indexOfSelectedItem == 0, enabledMeals: meals, enabledStores: stores, nutritionGoal: goal, heightInches: profile.heightInches, weightPounds: profile.weightPounds, prioritizeSales: prioritizeSales.state == .on, saleItemIDs: saleIDs, saleSources: couponSources)
        // Recipes must be final before budgeting. Their ingredients become required
        // shopping rows, then optional groceries are optimized around what remains.
        let lifestyle = recipeDiet.titleOfSelectedItem ?? "Mediterranean"
        let selectedRecipes = recipesForPlan(apiRecipes: recipes, days: days, lifestyle: lifestyle, options: options)
        let schedule = makeRecipeSchedule(days: days, people: people, recipeCount: selectedRecipes.count)
        let coverage = recipeShoppingCoverage(recipes: selectedRecipes, options: options)
        var plan = makeShoppingPlan(
            options: options, items: coverage.items, prices: priceBook, favorites: favoriteIDs,
            coupons: couponValues, couponLimits: couponLimits, requiredItemIDs: coverage.requiredItemIDs
        )
        var appliedSwaps: [SaleSwap] = []
        if options.prioritizeSales {
            let swaps = proposeSaleSwaps(
                plan: plan, options: options, items: coverage.items, prices: priceBook,
                favorites: favoriteIDs, coupons: couponValues, couponLimits: couponLimits,
                requiredItemIDs: coverage.requiredItemIDs
            )
            if !swaps.isEmpty {
                guard let chosen = presentSaleSwapPreview(swaps) else {
                    status.stringValue = "List not created — sale swaps were cancelled."
                    return
                }
                if !chosen.isEmpty {
                    appliedSwaps = chosen
                    plan = makeShoppingPlan(
                        options: options, items: coverage.items, prices: priceBook, favorites: favoriteIDs,
                        coupons: couponValues, couponLimits: couponLimits,
                        requiredItemIDs: coverage.requiredItemIDs.union(chosen.map { $0.toID }),
                        excludedItemIDs: Set(chosen.map { $0.fromID })
                    )
                }
            }
        }
        if plan.estimatedTotal > budgetMax {
            let alert = NSAlert()
            alert.alertStyle = .warning
            alert.messageText = "This list may exceed the monthly budget"
            alert.informativeText = "Estimated checkout: \(money(plan.estimatedTotal)). Likely range: \(money(plan.likelyLow))-\(money(plan.likelyHigh)). Budget: \(money(budgetMin))-\(money(budgetMax)). Unmarking premium favorites, checking current prices, or reducing people/days can bring it closer to the \(money(plan.targetSpend)) frugal target."
            alert.addButton(withTitle: "Go Back")
            alert.addButton(withTitle: "Create Anyway")
            if alert.runModal() == .alertFirstButtonReturn {
                status.stringValue = "List not created. Adjust favorites or settings to keep the uncertainty-adjusted total within \(money(budgetMax))."
                return
            }
        }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.pdf]
        let rememberedURL = rememberedShoppingURL(defaultDays: days)
        panel.nameFieldStringValue = rememberedURL?.lastPathComponent ?? "Shopping_List_\(days)_Days.pdf"
        panel.directoryURL = rememberedURL?.deletingLastPathComponent() ?? FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
        guard panel.runModal() == .OK, let url = panel.url else { return }
        let paired = pairedOutputURLs(for: url)
        let recipeURL = paired.recipe
        let dailyMealsURL = paired.dailyMeals
        let dailyMealPlans = makeDailyMealPlans(options: options, recipes: selectedRecipes, schedule: schedule)
        do {
            try PDFWriter().write(to: url, options: options, items: coverage.items, prices: priceBook, favorites: favoriteIDs, suppliedPlan: plan)
            try RecipePDFWriter().write(to: recipeURL, options: options, recipes: selectedRecipes, schedule: schedule, lifestyle: lifestyle, nutritionGoal: goal, shoppingListFilename: url.lastPathComponent)
            try DailyMealsPDFWriter().write(to: dailyMealsURL, options: options, plans: dailyMealPlans, lifestyle: lifestyle, shoppingListFilename: url.lastPathComponent)
            lastPDFURL = url
            lastRecipePDFURL = recipeURL
            lastDailyMealsPDFURL = dailyMealsURL
            UserDefaults.standard.set(url.path, forKey: lastShoppingPDFPathKey)
            printButton.isEnabled = true
            let savings = plan.couponSavings > 0 ? " Coupon savings applied: \(money(plan.couponSavings))." : ""
            let saleMessage = options.prioritizeSales
                ? " Deals covered \(plan.prioritizedSaleItems) item\(plan.prioritizedSaleItems == 1 ? "" : "s") the list already needed."
                : ""
            let extras = coverage.supplementalItemIDs.isEmpty ? "" : " Added \(coverage.supplementalItemIDs.count) explicit recipe-extra item(s)."
            let swapMessage: String
            if appliedSwaps.isEmpty {
                swapMessage = ""
            } else {
                let swapped = appliedSwaps.reduce(0.0) { $0 + $1.estimatedSavings }
                swapMessage = " Swapped \(appliedSwaps.count) item(s) for on-sale equivalents (est. \(money(swapped)) saved)."
            }
            status.stringValue = "Created and remembered \(url.lastPathComponent) in \(url.deletingLastPathComponent().lastPathComponent). Recipes were finalized first, and every non-water recipe ingredient is included in the shopping list.\(extras) All filenames stay paired.\(savings)\(saleMessage)\(swapMessage)"
            NSWorkspace.shared.open(url)
            NSWorkspace.shared.open(recipeURL)
            NSWorkspace.shared.open(dailyMealsURL)
        } catch {
            status.stringValue = "Could not create the PDF: \(error.localizedDescription)"
        }
    }

    @objc func printLastPDF(_ sender: Any?) {
        guard let shoppingURL = lastPDFURL, let recipeURL = lastRecipePDFURL, let dailyMealsURL = lastDailyMealsPDFURL else {
            status.stringValue = "Create the shopping, recipe, and daily-meal PDFs first, then use Print Last PDFs."
            return
        }
        let chooser = NSAlert()
        chooser.messageText = "Which PDF would you like to print?"
        chooser.informativeText = "All three files are designed for low-ink printing."
        chooser.addButton(withTitle: "Shopping List")
        chooser.addButton(withTitle: "Recipe Plan")
        chooser.addButton(withTitle: "Daily Meals")
        chooser.addButton(withTitle: "Cancel")
        let response = chooser.runModal()
        let choice = response.rawValue - NSApplication.ModalResponse.alertFirstButtonReturn.rawValue
        if choice == 3 { return }
        let url = choice == 1 ? recipeURL : (choice == 2 ? dailyMealsURL : shoppingURL)
        guard let document = PDFDocument(url: url) else {
            status.stringValue = "macOS could not open the selected PDF for printing."
            return
        }
        guard let operation = document.printOperation(for: NSPrintInfo.shared, scalingMode: .pageScaleToFit, autoRotate: true) else {
            status.stringValue = "macOS could not prepare the print job. Open the PDF and print from Preview instead."
            return
        }
        operation.run()
    }
}

extension AppDelegate {
    /// Lays out the main window (and optionally the Scan Deals panel) and
    /// writes each to a PNG. Used by --snapshot to review the UI headlessly.
    func snapshot(to url: URL, scanPanel: URL?) throws {
        applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
        try Self.writePNG(of: window.contentView, to: url)
        if let scanPanel {
            manageCoupons(nil)
            try Self.writePNG(of: couponsPanel?.contentView, to: scanPanel)
        }
    }

    private static func writePNG(of view: NSView?, to url: URL) throws {
        guard let view, let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else {
            throw NSError(domain: "Snapshot", code: 1)
        }
        view.cacheDisplay(in: view.bounds, to: rep)
        guard let png = rep.representation(using: .png, properties: [:]) else {
            throw NSError(domain: "Snapshot", code: 2)
        }
        try png.write(to: url)
    }
}

if CommandLine.arguments.count >= 3 && CommandLine.arguments[1] == "--self-test" {
    let testApplication = NSApplication.shared
    testApplication.setActivationPolicy(.prohibited)
    testApplication.finishLaunching()
    let target = URL(fileURLWithPath: CommandLine.arguments[2])
    let recipeTarget = CommandLine.arguments.count >= 4
        ? URL(fileURLWithPath: CommandLine.arguments[3])
        : target.deletingLastPathComponent().appendingPathComponent("self-test-recipes.pdf")
    let dailyMealsTarget = CommandLine.arguments.count >= 5
        ? URL(fileURLWithPath: CommandLine.arguments[4])
        : target.deletingLastPathComponent().appendingPathComponent("self-test-daily-meals.pdf")
    let options = ListOptions(
        recipient: "Mom",
        days: 30,
        people: 1,
        budgetMin: 200,
        budgetMax: 300,
        groupByStore: true,
        enabledMeals: Set(["Breakfast", "Lunch", "Dinner", "Snack"]),
        enabledStores: Set(["BJ's", "Costco", "ShopRite", "Stew Leonard's"]),
        nutritionGoal: .cutting,
        heightInches: 77,
        weightPounds: 300,
        prioritizeSales: false,
        saleItemIDs: []
    )
    do {
        let goalTargets = NutritionGoal.allCases.map { goal -> (NutritionGoal, NutritionEstimate) in
            let goalOptions = ListOptions(
                recipient: options.recipient, days: options.days, people: options.people,
                budgetMin: options.budgetMin, budgetMax: options.budgetMax,
                groupByStore: options.groupByStore, enabledMeals: options.enabledMeals,
                enabledStores: options.enabledStores, nutritionGoal: goal,
                heightInches: options.heightInches, weightPounds: options.weightPounds,
                prioritizeSales: options.prioritizeSales, saleItemIDs: options.saleItemIDs
            )
            return (goal, personalizedNutritionTarget(for: goalOptions).macros)
        }
        guard goalTargets.allSatisfy({ $0.1.calories == $0.1.proteinGrams * 4 + $0.1.carbohydrateGrams * 4 + $0.1.fatGrams * 9 }),
              (goalTargets.first { $0.0 == .cutting }?.1.calories ?? 99999) <= 2800,   // only Cutting is capped at 2,800
              (goalTargets.first { $0.0 == .cutting }?.1.calories ?? 0) < (goalTargets.first { $0.0 == .maintenance }?.1.calories ?? 0),
              // Build Muscle ≈ Maintenance (body recomposition at maintenance calories).
              abs((goalTargets.first { $0.0 == .maintenance }?.1.calories ?? 0) - (goalTargets.first { $0.0 == .buildMuscle }?.1.calories ?? -99)) <= 5 else {
            throw NSError(domain: "SelfTest", code: 9, userInfo: [NSLocalizedDescriptionKey: "Personalized goal targets failed arithmetic, ordering, or the recomp/cap checks."])
        }
        for (goal, target) in goalTargets {
            fputs("PERSONALIZED_TARGET \(goal.rawValue) \(target.summary)\n", stderr)
        }
        let testPriceBook = PriceBook()
        let testFavorites = Set(["oats", "greens"])
        let testPlan = makeShoppingPlan(options: options, items: catalog, prices: testPriceBook, favorites: testFavorites)
        let recomputedTotal = testPlan.rows.reduce(0.0) { $0 + $1.lineTotal }
        fputs("FRUGAL_PLAN estimate=\(money(testPlan.estimatedTotal)) target=\(money(testPlan.targetSpend)) low=\(money(testPlan.likelyLow)) high=\(money(testPlan.likelyHigh)) items=\(testPlan.rows.count)\n", stderr)
        guard abs(recomputedTotal - testPlan.estimatedTotal) < 0.005,
              abs(testPlan.likelyLow - testPlan.estimatedTotal * (1 - testPlan.error)) < 0.005,
              abs(testPlan.likelyHigh - testPlan.estimatedTotal * (1 + testPlan.error)) < 0.005,
              abs(testPlan.targetSpend - 250.0) < 0.005,
              abs(testPlan.estimatedTotal - testPlan.targetSpend) <= 5.0,
              testPlan.rows.contains(where: { $0.item.id == "beef" }) else {
            throw NSError(domain: "SelfTest", code: 10, userInfo: [NSLocalizedDescriptionKey: "Shopping-plan arithmetic did not reconcile."])
        }
        let couponPlan = makeShoppingPlan(
            options: options,
            items: catalog,
            prices: testPriceBook,
            favorites: testFavorites,
            coupons: ["eggs": 1.50, "oats": 2.00],
            couponLimits: ["eggs": 1, "oats": 1]
        )
        let couponGross = couponPlan.rows.reduce(0.0) { $0 + $1.grossLineTotal }
        let couponSavings = couponPlan.rows.reduce(0.0) { $0 + $1.couponSavings }
        let couponNet = couponPlan.rows.reduce(0.0) { $0 + $1.lineTotal }
        guard couponPlan.couponSavings > 0,
              abs(couponPlan.grossSubtotal - couponGross) < 0.005,
              abs(couponPlan.couponSavings - couponSavings) < 0.005,
              abs(couponPlan.estimatedTotal - couponNet) < 0.005,
              abs(couponPlan.grossSubtotal - couponPlan.couponSavings - couponPlan.estimatedTotal) < 0.005,
              abs((couponPlan.rows.first { $0.item.id == "eggs" }?.couponSavings ?? 0) - 1.50) < 0.005,
              couponPlan.rows.allSatisfy({ $0.couponSavings >= 0 && $0.couponSavings <= $0.grossLineTotal && abs($0.grossLineTotal - $0.couponSavings - $0.lineTotal) < 0.005 }) else {
            throw NSError(domain: "SelfTest", code: 14, userInfo: [NSLocalizedDescriptionKey: "Coupon arithmetic did not reconcile."])
        }
        fputs("COUPON_PLAN gross=\(money(couponPlan.grossSubtotal)) savings=\(money(couponPlan.couponSavings)) net=\(money(couponPlan.estimatedTotal))\n", stderr)
        let saleOptions = ListOptions(
            recipient: options.recipient, days: options.days, people: options.people,
            budgetMin: options.budgetMin, budgetMax: options.budgetMax,
            groupByStore: options.groupByStore, enabledMeals: options.enabledMeals,
            enabledStores: options.enabledStores, nutritionGoal: options.nutritionGoal,
            heightInches: options.heightInches, weightPounds: options.weightPounds,
            prioritizeSales: true, saleItemIDs: Set(["beef"])
        )
        let saleRecipes = recipesForPlan(apiRecipes: [], days: saleOptions.days, lifestyle: "Mediterranean", options: saleOptions)
        let bannedIngredientFixtures = [
            Recipe(
                title: "Cottage Cheese Fruit Bowl", baseServings: 1, readyMinutes: 5,
                ingredients: ["1 cup cottage cheese", "1 apple"], steps: ["Combine."],
                sourceURL: nil, sourceName: "Self-test"
            ),
            Recipe(
                title: "Yoplait Yogurt Parfait", baseServings: 1, readyMinutes: 5,
                ingredients: ["1 cup Yoplait yogurt", "1 apple"], steps: ["Combine."],
                sourceURL: nil, sourceName: "Self-test"
            ),
            Recipe(
                title: "Peanut Butter Walnut Oats", baseServings: 1, readyMinutes: 5,
                ingredients: ["2 tablespoons peanut butter", "1/4 cup walnuts", "1 cup oats"], steps: ["Combine."],
                sourceURL: nil, sourceName: "Self-test"
            )
        ]
        let bannedIngredientResults = recipesForPlan(apiRecipes: bannedIngredientFixtures, days: 3, lifestyle: "Mediterranean", options: saleOptions)
        let bannedIngredientResultText = bannedIngredientResults.map { $0.title + " " + $0.ingredients.joined(separator: " ") }.joined(separator: " ").lowercased()
        let recipeCoverage = recipeShoppingCoverage(recipes: saleRecipes, options: saleOptions)
        let salePlan = makeShoppingPlan(
            options: saleOptions, items: recipeCoverage.items, prices: testPriceBook, favorites: testFavorites,
            coupons: ["beef": 2.50], couponLimits: ["beef": 2], requiredItemIDs: recipeCoverage.requiredItemIDs
        )
        let ingredientLineCount = saleRecipes.reduce(0) { $0 + $1.ingredients.count }
        let plannedIDs = Set(salePlan.rows.map { $0.item.id })
        // Order of operations: the menu and the basket are settled on need, and only
        // then are offers applied. Planning the identical week with no offers at all
        // must therefore yield the same recipes and the same rows -- the deals may
        // change what it costs and what can be swapped, never what it asks for.
        let noDealOptions = ListOptions(
            recipient: options.recipient, days: options.days, people: options.people,
            budgetMin: options.budgetMin, budgetMax: options.budgetMax,
            groupByStore: options.groupByStore, enabledMeals: options.enabledMeals,
            enabledStores: options.enabledStores, nutritionGoal: options.nutritionGoal,
            heightInches: options.heightInches, weightPounds: options.weightPounds,
            prioritizeSales: false, saleItemIDs: []
        )
        let noDealRecipes = recipesForPlan(apiRecipes: [], days: noDealOptions.days, lifestyle: "Mediterranean", options: noDealOptions)
        let noDealCoverage = recipeShoppingCoverage(recipes: noDealRecipes, options: noDealOptions)
        let noDealPlan = makeShoppingPlan(
            options: noDealOptions, items: noDealCoverage.items, prices: testPriceBook,
            favorites: testFavorites, requiredItemIDs: noDealCoverage.requiredItemIDs
        )
        let unfamiliarRecipe = Recipe(
            title: "API coverage fixture", baseServings: 1, readyMinutes: 10,
            ingredients: ["1 fennel bulb", "2 cups water"], steps: ["Cook."],
            sourceURL: nil, sourceName: "Self-test"
        )
        let unfamiliarCoverage = recipeShoppingCoverage(recipes: [unfamiliarRecipe], options: saleOptions)
        let unfamiliarPlan = makeShoppingPlan(
            options: saleOptions, items: unfamiliarCoverage.items, prices: testPriceBook,
            favorites: [], requiredItemIDs: unfamiliarCoverage.requiredItemIDs
        )
        guard salePlan.prioritizedSaleItems == 1,
              salePlan.rows.contains(where: { $0.item.id == "beef" && abs($0.couponSavings - 5.00) < 0.005 }),
              salePlan.rows.contains(where: { $0.item.id == "chicken" }),
              recipeCoverage.requiredItemIDs.contains("chicken"),
              recipeCoverage.requiredItemIDs.contains("beef"),
              recipeCoverage.requiredItemIDs.isSubset(of: plannedIDs),
              recipeCoverage.coveredIngredientLines + recipeCoverage.waterOnlyLines == ingredientLineCount,
              unfamiliarCoverage.supplementalItemIDs.count == 1,
              unfamiliarCoverage.waterOnlyLines == 1,
              unfamiliarCoverage.requiredItemIDs.isSubset(of: Set(unfamiliarPlan.rows.map { $0.item.id })),
              unfamiliarPlan.rows.contains(where: { $0.item.name.contains("fennel bulb") }),
              !["cottage cheese", "yogurt", "yoplait", "peanut", "walnut"].contains(where: bannedIngredientResultText.contains),
              noDealRecipes.map({ $0.title }) == saleRecipes.map({ $0.title }),
              Set(noDealPlan.rows.map({ $0.item.id })) == plannedIDs,
              salePlan.estimatedTotal < noDealPlan.estimatedTotal else {
            throw NSError(domain: "SelfTest", code: 16, userInfo: [NSLocalizedDescriptionKey: "Recipe-first ingredient reconciliation, deal application, or needs-before-deals ordering failed."])
        }
        fputs("RECIPE_COVERAGE_OK lines=\(ingredientLineCount) requiredItems=\(recipeCoverage.requiredItemIDs.count) extras=\(recipeCoverage.supplementalItemIDs.count) chicken=yes beef=yes\n", stderr)
        fputs("DEALS_AFTER_LIST_OK rows=\(plannedIDs.count) identicalWithoutDeals=yes covered=\(salePlan.prioritizedSaleItems) saved=\(money(noDealPlan.estimatedTotal - salePlan.estimatedTotal))\n", stderr)
        // On-sale swap proposals must never touch a recipe-required item, a favorite, or the
        // sale item itself, must stay inside one substitution group, and must actually save money.
        let swapCandidates = proposeSaleSwaps(
            plan: salePlan, options: saleOptions, items: recipeCoverage.items, prices: testPriceBook,
            favorites: testFavorites, coupons: ["beef": 2.50], couponLimits: ["beef": 2],
            requiredItemIDs: recipeCoverage.requiredItemIDs
        )
        guard swapCandidates.allSatisfy({ swap in
            swap.estimatedSavings > 0
                && swap.fromID != swap.toID
                && saleOptions.saleItemIDs.contains(swap.toID)
                && !recipeCoverage.requiredItemIDs.contains(swap.fromID)
                && !testFavorites.contains(swap.fromID)
                && substitutionGroup(for: swap.fromID).contains(swap.toID)
        }) else {
            throw NSError(domain: "SelfTest", code: 17, userInfo: [NSLocalizedDescriptionKey: "Sale swap proposal violated its safety invariants."])
        }
        fputs("SALE_SWAP_OK count=\(swapCandidates.count)\n", stderr)
        // Directed swap: an optional salmon row must swap to on-sale turkey (same protein group,
        // cheaper net of its coupon) — proving the proposer actually fires, not just stays safe.
        let swapProbeOptions = ListOptions(
            recipient: options.recipient, days: options.days, people: options.people,
            budgetMin: options.budgetMin, budgetMax: options.budgetMax, groupByStore: options.groupByStore,
            enabledMeals: options.enabledMeals, enabledStores: options.enabledStores, nutritionGoal: options.nutritionGoal,
            heightInches: options.heightInches, weightPounds: options.weightPounds,
            prioritizeSales: true, saleItemIDs: Set(["turkey"])
        )
        let salmonItem = catalog.first { $0.id == "salmon" }!
        let probePlan = ShoppingPlan(
            rows: [PlannedRow(item: salmonItem, quantity: 1, grossLineTotal: 20.99, couponSavings: 0, lineTotal: 20.99)],
            estimatedTotal: 20.99, error: 0.25, confidence: "Low", targetSpend: 250, omittedItems: 0,
            grossSubtotal: 20.99, couponSavings: 0, prioritizedSaleItems: 0
        )
        let probeSwaps = proposeSaleSwaps(
            plan: probePlan, options: swapProbeOptions, items: catalog, prices: PriceBook(),
            favorites: [], coupons: ["turkey": 1.00], couponLimits: ["turkey": 5], requiredItemIDs: []
        )
        guard probeSwaps.count == 1, probeSwaps[0].fromID == "salmon", probeSwaps[0].toID == "turkey", probeSwaps[0].estimatedSavings > 0 else {
            throw NSError(domain: "SelfTest", code: 18, userInfo: [NSLocalizedDescriptionKey: "Directed sale swap did not fire as expected."])
        }
        fputs("SALE_SWAP_DIRECTED_OK from=\(probeSwaps[0].fromID) to=\(probeSwaps[0].toID) save=\(money(probeSwaps[0].estimatedSavings))\n", stderr)
        let xmlFixture = """
        <shopriteSales store="ShopRite" date="2026-09-20">
          <offer itemId="turkey" savings="2.00" limit="4" note="93% lean ground turkey"/>
          <offer itemId="eggs" salePrice="2.49" limit="6" note="Large eggs 18ct"/>
          <offer itemId="doesnotexist" savings="5.00"/>
        </shopriteSales>
        """.data(using: .utf8)!
        let xmlOffers = parseSalesXML(xmlFixture, items: catalog)
        let eggsFallback = catalog.first { $0.id == "eggs" }!.fallbackPrice   // 3.89
        guard let turkeyXml = xmlOffers.first(where: { $0.itemID == "turkey" }), abs(turkeyXml.savingsPerPackage - 2.00) < 0.005, turkeyXml.maximumUses == 4,
              let eggsXml = xmlOffers.first(where: { $0.itemID == "eggs" }), abs(eggsXml.savingsPerPackage - (eggsFallback - 2.49)) < 0.005,
              !xmlOffers.contains(where: { $0.itemID == "doesnotexist" }),
              xmlOffers.count == 2 else {
            throw NSError(domain: "SelfTest", code: 20, userInfo: [NSLocalizedDescriptionKey: "Sales XML import parsing failed."])
        }
        fputs("XML_IMPORT_OK turkey=\(money(turkeyXml.savingsPerPackage)) eggs=\(money(eggsXml.savingsPerPackage)) ignoredUnknown=yes\n", stderr)
        let catalogText = catalog.map { $0.name }.joined(separator: " ").lowercased()
        guard !excludedIngredientTerms.contains(where: { catalogText.contains($0) }) else {
            throw NSError(domain: "SelfTest", code: 11, userInfo: [NSLocalizedDescriptionKey: "An excluded ingredient remained in the catalog."])
        }
        try PDFWriter().write(
            to: target,
            options: saleOptions,
            items: recipeCoverage.items,
            prices: testPriceBook,
            favorites: testFavorites,
            suppliedPlan: salePlan
        )
        fputs("SELF_TEST_SHOPPING_OK\n", stderr)
        let testRecipes = saleRecipes
        let testSchedule = makeRecipeSchedule(days: saleOptions.days, people: saleOptions.people, recipeCount: testRecipes.count)
        let recipeText = testRecipes.map { $0.title + " " + $0.ingredients.joined(separator: " ") }.joined(separator: " ").lowercased()
        let scheduledDays = Set(testSchedule.map { $0.day })
        let macrosReconcile = testRecipes.allSatisfy { recipe in
            let macros = recipe.macrosPerServing
            return macros.calories == macros.proteinGrams * 4 + macros.carbohydrateGrams * 4 + macros.fatGrams * 9
                && macros.calories > 0 && macros.proteinGrams > 0
        }
        guard !excludedIngredientTerms.contains(where: { recipeText.contains($0) }),
              testSchedule.count == saleOptions.days,
              scheduledDays == Set(1...saleOptions.days),
              macrosReconcile else {
            throw NSError(domain: "SelfTest", code: 12, userInfo: [NSLocalizedDescriptionKey: "Recipe exclusions or 30-day schedule checks failed."])
        }
        let dailyMealPlans = makeDailyMealPlans(options: saleOptions, recipes: testRecipes, schedule: testSchedule)
        let dailyMealText = dailyMealPlans.map {
            $0.breakfast.name + " " + $0.lunch.name + " " + $0.dinner.name + " " + $0.snacks.map(\.name).joined(separator: " ")
        }.joined(separator: " ").lowercased()
        let expectedTarget = personalizedNutritionTarget(for: saleOptions).macros
        // Hard requirement: no matter the goal, no single day may exceed 2,800 kcal.
        let allDaysUnderCap = dailyMealPlans.allSatisfy { $0.total.calories <= maximumDailyCalories }
        let distinctDailyTotals = Set(dailyMealPlans.map {
            "\($0.total.calories)-\($0.total.proteinGrams)-\($0.total.carbohydrateGrams)-\($0.total.fatGrams)"
        })
        guard dailyMealPlans.count == saleOptions.days,
              dailyMealPlans.allSatisfy({
                  $0.total.calories == $0.total.proteinGrams * 4 + $0.total.carbohydrateGrams * 4 + $0.total.fatGrams * 9
                      && abs(Double($0.total.calories - expectedTarget.calories)) <= Double(expectedTarget.calories) * 0.05
                      && $0.total.proteinGrams >= expectedTarget.proteinGrams
                      && abs(Double($0.total.carbohydrateGrams - expectedTarget.carbohydrateGrams)) <= Double(expectedTarget.carbohydrateGrams) * 0.10
                      && abs(Double($0.total.fatGrams - expectedTarget.fatGrams)) <= Double(expectedTarget.fatGrams) * 0.10
                      && !$0.snacks.isEmpty
              }),
              allDaysUnderCap,
              distinctDailyTotals.count > 1,
              !excludedIngredientTerms.contains(where: dailyMealText.contains) else {
            throw NSError(domain: "SelfTest", code: 13, userInfo: [NSLocalizedDescriptionKey: "Daily meal schedule or macro arithmetic failed."])
        }
        let proteinRange = dailyMealPlans.map { $0.total.proteinGrams }
        let carbohydrateRange = dailyMealPlans.map { $0.total.carbohydrateGrams }
        let fatRange = dailyMealPlans.map { $0.total.fatGrams }
        let calorieRange = dailyMealPlans.map { $0.total.calories }
        fputs("DAILY_MACRO_RANGE C \(carbohydrateRange.min() ?? 0)-\(carbohydrateRange.max() ?? 0)g F \(fatRange.min() ?? 0)-\(fatRange.max() ?? 0)g P \(proteinRange.min() ?? 0)-\(proteinRange.max() ?? 0)g KCAL \(calorieRange.min() ?? 0)-\(calorieRange.max() ?? 0)\n", stderr)
        try RecipePDFWriter().write(to: recipeTarget, options: saleOptions, recipes: testRecipes, schedule: testSchedule, lifestyle: "Mediterranean", nutritionGoal: saleOptions.nutritionGoal, shoppingListFilename: target.lastPathComponent)
        fputs("SELF_TEST_RECIPES_OK\n", stderr)
        try DailyMealsPDFWriter().write(to: dailyMealsTarget, options: saleOptions, plans: dailyMealPlans, lifestyle: "Mediterranean", shoppingListFilename: target.lastPathComponent)
        fputs("SELF_TEST_DAILY_MEALS_OK\n", stderr)
        print("SELF_TEST_OK \(target.path) \(recipeTarget.path) \(dailyMealsTarget.path)")
        exit(0)
    } catch {
        fputs("SELF_TEST_FAILED \(error)\n", stderr)
        exit(1)
    }
} else if CommandLine.arguments.count >= 3 && CommandLine.arguments[1] == "--snapshot" {
    // Render the main window and the Scan Deals panel to PNGs, for reviewing
    // the layout without a screen:  --snapshot main.png [scan-panel.png]
    let snapshotApplication = NSApplication.shared
    snapshotApplication.setActivationPolicy(.accessory)
    let delegate = AppDelegate()
    do {
        try delegate.snapshot(to: URL(fileURLWithPath: CommandLine.arguments[2]),
                              scanPanel: CommandLine.arguments.count >= 4
                                ? URL(fileURLWithPath: CommandLine.arguments[3]) : nil)
        print("SNAPSHOT_OK")
        exit(0)
    } catch {
        fputs("SNAPSHOT_FAILED \(error)\n", stderr)
        exit(1)
    }
} else {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.delegate = delegate
    app.setActivationPolicy(.regular)
    app.run()
}

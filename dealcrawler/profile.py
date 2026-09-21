"""Your profile, and the calorie and macro targets derived from it.

The maths here is a faithful port of the desktop app's own
`personalizedNutritionTarget`, so the panel and the app agree on your numbers
rather than quietly disagreeing.

When you give your age, sex and activity level, calories come from the
Mifflin-St Jeor equation -- the standard used by dietitians -- multiplied by an
activity factor. Without those details it falls back to the app's original
size-only estimate, so an unfinished profile still produces usable numbers.

It remains planning guidance for a shopping list, not a clinical calculation:
medication, health history, body composition and pregnancy are not accounted
for. Anyone with medical or dietary needs should use numbers from their own
clinician.
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Optional

from . import paths

HERE = paths.SOURCE_DIR
PROFILE_FILE = paths.data("profile.json")

GOALS = {
    # key            label            calorie x  protein/lb  fat/lb
    "buildMuscle": ("Build Muscle", 1.10, 0.80, 0.35),
    "maintenance": ("Maintenance", 1.00, 0.70, 0.32),
    "cutting": ("Cutting", 0.84, 0.75, 0.30),
}
DEFAULT_GOAL = "maintenance"

# Mifflin-St Jeor sex constants. "unspecified" sits midway between the two
# rather than assuming one, so nobody has to disclose it to get a usable number.
SEXES = {
    "female": ("Female", -161.0),
    "male": ("Male", 5.0),
    "unspecified": ("Prefer not to say", -78.0),
}
DEFAULT_SEX = "unspecified"

# label, calorie factor, extra protein g/lb. Training harder raises protein
# need, not just calories -- without this the extra energy lands almost entirely
# in carbohydrate, which is a poor split for someone actually training.
ACTIVITY = {
    "sedentary": ("Sedentary - little or no exercise", 1.200, 0.00),
    "light": ("Light - exercise 1-3 days a week", 1.375, 0.05),
    "moderate": ("Moderate - exercise 3-5 days a week", 1.550, 0.08),
    "active": ("Active - exercise 6-7 days a week", 1.725, 0.12),
    "athlete": ("Very active - physical job or training twice a day", 1.900, 0.15),
}

# Keep fat from collapsing to a token share once calories climb.
MIN_FAT_CALORIE_SHARE = 0.25
DEFAULT_ACTIVITY = "moderate"

MIN_AGE, MAX_AGE = 13, 100

# Used when height/weight are missing or out of range, matching the app.
FALLBACK = {"protein": 126, "carbs": 261, "fat": 58,
            "maintenance": 2080, "multiplier": 1.0, "planning_weight": 180.0}

MIN_HEIGHT_IN, MAX_HEIGHT_IN = 48.0, 96.0
MIN_WEIGHT_LB, MAX_WEIGHT_LB = 80.0, 700.0


@dataclass
class Profile:
    height_feet: Optional[int] = None
    height_inches: Optional[int] = None
    weight_pounds: Optional[float] = None
    goal: str = DEFAULT_GOAL
    age: Optional[int] = None
    sex: str = DEFAULT_SEX
    activity: str = DEFAULT_ACTIVITY
    # Set any of these to override what the formula works out. Blank means
    # "use the calculated figure", so you can pin protein and leave the rest.
    custom_calories: Optional[int] = None
    custom_protein: Optional[int] = None
    custom_carbs: Optional[int] = None
    custom_fat: Optional[int] = None
    people: int = 1
    days: int = 7
    budget_min: float = 0.0
    budget_max: float = 0.0
    meals: list = None
    diet: str = "No restriction"

    def __post_init__(self):
        if self.meals is None:
            self.meals = ["Breakfast", "Lunch", "Dinner", "Snacks"]
        if self.goal not in GOALS:
            self.goal = DEFAULT_GOAL
        if self.sex not in SEXES:
            self.sex = DEFAULT_SEX
        if self.activity not in ACTIVITY:
            self.activity = DEFAULT_ACTIVITY

    @property
    def total_inches(self) -> Optional[float]:
        if self.height_feet is None and self.height_inches is None:
            return None
        return (self.height_feet or 0) * 12 + (self.height_inches or 0)

    @property
    def personalised(self) -> bool:
        """True when age is known, so Mifflin-St Jeor can be used."""
        return (self.complete and self.age is not None
                and MIN_AGE <= self.age <= MAX_AGE)

    @property
    def complete(self) -> bool:
        h, w = self.total_inches, self.weight_pounds
        return (h is not None and w is not None
                and MIN_HEIGHT_IN <= h <= MAX_HEIGHT_IN
                and MIN_WEIGHT_LB <= w <= MAX_WEIGHT_LB)


def calories(protein: int, carbs: int, fat: int) -> int:
    return protein * 4 + carbs * 4 + fat * 9


def target(profile: Profile) -> dict:
    """Daily calorie and macro target. Mirrors the app's own calculation."""
    height, weight = profile.total_inches, profile.weight_pounds

    if not profile.complete:
        p, c, f = FALLBACK["protein"], FALLBACK["carbs"], FALLBACK["fat"]
        return _apply_overrides(profile, {
            "calories": calories(p, c, f), "protein": p, "carbs": c, "fat": f,
            "maintenance": FALLBACK["maintenance"],
            "multiplier": FALLBACK["multiplier"],
            "planning_weight": FALLBACK["planning_weight"],
            "goal": profile.goal, "goal_label": GOALS[profile.goal][0],
            "estimated": False, "basis": "fallback",
            "sex_label": SEXES[profile.sex][0],
            "activity_label": ACTIVITY[profile.activity][0],
            "personalised": False,
        })

    _, multiplier, protein_per_lb, fat_per_lb = GOALS[profile.goal]

    if profile.personalised:
        # Mifflin-St Jeor resting energy, then an activity factor.
        kg = weight * 0.45359237
        cm = height * 2.54
        bmr = 10.0 * kg + 6.25 * cm - 5.0 * profile.age + SEXES[profile.sex][1]
        activity_factor = ACTIVITY[profile.activity][1]
        maintenance = int(round(bmr * activity_factor / 10.0)) * 10
        protein_per_lb += ACTIVITY[profile.activity][2]
        basis = "mifflin"
    else:
        # The app's original size-only estimate, for an unfinished profile.
        maintenance = int(round((weight * 10.0 + height * 4.0) / 10.0)) * 10
        basis = "size-only"

    # Protein and fat are set from a planning weight capped near BMI 25 + 20%,
    # so the target does not balloon with body weight.
    height_m = height * 0.0254
    bmi25_pounds = 25.0 * height_m * height_m * 2.2046226218
    planning_weight = min(weight, bmi25_pounds * 1.20)

    desired = maintenance * multiplier
    protein = max(60, int(round(planning_weight * protein_per_lb)))
    fat = max(40, int(round(planning_weight * fat_per_lb)))
    if basis == "mifflin":
        # Hold fat to at least a quarter of calories so a high-activity target
        # does not turn into an almost pure-carbohydrate plan.
        fat = max(fat, int(round(desired * MIN_FAT_CALORIE_SHARE / 9.0)))
    carbs = max(100, int(round((desired - (protein * 4 + fat * 9)) / 4.0)))

    return _apply_overrides(profile, {
        "calories": calories(protein, carbs, fat),
        "protein": protein, "carbs": carbs, "fat": fat,
        "maintenance": maintenance, "multiplier": multiplier,
        "planning_weight": round(planning_weight, 1),
        "goal": profile.goal, "goal_label": GOALS[profile.goal][0],
        "estimated": True, "basis": basis,
        "sex_label": SEXES[profile.sex][0],
        "activity_label": ACTIVITY[profile.activity][0],
        "personalised": profile.personalised,
    })


def _apply_overrides(profile: Profile, computed: dict) -> dict:
    """Your own numbers win. Calories are recomputed from the macros unless you
    set a calorie figure too, so the four never contradict each other."""
    overrides = {
        "protein": profile.custom_protein,
        "carbs": profile.custom_carbs,
        "fat": profile.custom_fat,
    }
    used = {k: v for k, v in overrides.items() if v is not None and v >= 0}
    if used:
        computed.update(used)
        computed["calories"] = calories(computed["protein"], computed["carbs"],
                                        computed["fat"])
    if profile.custom_calories is not None and profile.custom_calories > 0:
        computed["calories"] = profile.custom_calories
        used["calories"] = profile.custom_calories
    computed["custom_fields"] = sorted(used)
    computed["custom"] = bool(used)
    if used:
        computed["basis"] = "yours"
    return computed


def portion_multiplier(profile: Profile) -> float:
    """How much food this person needs relative to the app's baseline."""
    return min(1.60, max(0.60, target(profile)["calories"] / 2500.0))


def summary(profile: Profile) -> str:
    t = target(profile)
    return (f"{t['calories']} kcal | P {t['protein']}g | "
            f"C {t['carbs']}g | F {t['fat']}g")


def load() -> Profile:
    if not os.path.exists(PROFILE_FILE):
        return Profile()
    try:
        with open(PROFILE_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return Profile()
    allowed = {f for f in Profile.__dataclass_fields__}
    return Profile(**{k: v for k, v in data.items() if k in allowed})


def save(profile: Profile) -> Profile:
    with open(PROFILE_FILE, "w", encoding="utf-8") as fh:
        json.dump(asdict(profile), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return profile


def exists() -> bool:
    return os.path.exists(PROFILE_FILE)

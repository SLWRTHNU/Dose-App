from typing import Optional

# BG ranges in mmol/L (boundaries inclusive at the higher end)
# very_low:  <= 4.0
# low:       4.1 - 4.8
# target:    4.9 - 7.0
# high:      8.0 - 10.0
# very_high: 11.0 - 13.0
# critical:  13.1+

TREND_CATEGORIES = {
    "DoubleUp":      "rising_rapidly",
    "SingleUp":      "rising",
    "FortyFiveUp":   "slow_rise",
    "Flat":          "stable",
    "FortyFiveDown": "slow_fall",
    "SingleDown":    "falling_rapidly",
    "DoubleDown":    "falling_very_rapidly",
}

TREND_ARROWS = {
    "DoubleUp":      "↑↑",
    "SingleUp":      "↑",
    "FortyFiveUp":   "↗",
    "Flat":          "→",
    "FortyFiveDown": "↘",
    "SingleDown":    "↓",
    "DoubleDown":    "↓↓",
}

ACTION_TABLE = {
    ("rising_rapidly",    "very_low"):  "",
    ("rising_rapidly",    "low"):       "",
    ("rising_rapidly",    "target"):    "",
    ("rising_rapidly",    "high"):      "",
    ("rising_rapidly",    "very_high"): "water",
    ("rising_rapidly",    "critical"):  "water",

    ("rising",            "very_low"):  "jb:2",
    ("rising",            "low"):       "",
    ("rising",            "target"):    "",
    ("rising",            "high"):      "",
    ("rising",            "very_high"): "water",
    ("rising",            "critical"):  "water",

    ("slow_rise",         "very_low"):  "jb:2",
    ("slow_rise",         "low"):       "",
    ("slow_rise",         "target"):    "",
    ("slow_rise",         "high"):      "",
    ("slow_rise",         "very_high"): "water",
    ("slow_rise",         "critical"):  "water",

    ("stable",            "very_low"):  "jb:3",
    ("stable",            "low"):       "jb:2",
    ("stable",            "target"):    "",
    ("stable",            "high"):      "",
    ("stable",            "very_high"): "",
    ("stable",            "critical"):  "",

    ("slow_fall",         "very_low"):  "jb:4",
    ("slow_fall",         "low"):       "jb:2",
    ("slow_fall",         "target"):    "",
    ("slow_fall",         "high"):      "",
    ("slow_fall",         "very_high"): "",
    ("slow_fall",         "critical"):  "",

    ("falling_rapidly",      "very_low"):  "juicebox",
    ("falling_rapidly",      "low"):       "jb:4",
    ("falling_rapidly",      "target"):    "jb:2",
    ("falling_rapidly",      "high"):      "",
    ("falling_rapidly",      "very_high"): "",
    ("falling_rapidly",      "critical"):  "",

    ("falling_very_rapidly", "very_low"):  "juicebox",
    ("falling_very_rapidly", "low"):       "jb:5",
    ("falling_very_rapidly", "target"):    "jb:3",
    ("falling_very_rapidly", "high"):      "",
    ("falling_very_rapidly", "very_high"): "",
    ("falling_very_rapidly", "critical"):  "",
}

# Higher value = more urgent. Used to detect worsening action during cooldown.
ACTION_SEVERITY: dict[str, int] = {
    "":        0,
    "water":   1,
    "jb:2":    2,
    "jb:3":    3,
    "jb:4":    4,
    "jb:5":    5,
    "juicebox": 6,
}


def classify_bg(bg_mmol: float) -> str:
    if bg_mmol <= 4.0:
        return "very_low"
    if bg_mmol <= 4.8:
        return "low"
    if bg_mmol <= 7.0:
        return "target"
    if bg_mmol <= 10.0:
        return "high"
    if bg_mmol <= 13.0:
        return "very_high"
    return "critical"


def classify_trend(nightscout_direction: str) -> Optional[str]:
    return TREND_CATEGORIES.get(nightscout_direction)


def get_action(bg_mmol: float, nightscout_direction: str) -> str:
    """Return the required action string, or empty string if no action needed."""
    bg_range = classify_bg(bg_mmol)
    trend_cat = classify_trend(nightscout_direction)
    if trend_cat is None:
        return ""
    return ACTION_TABLE.get((trend_cat, bg_range), "")


def is_worse_action(new_action: str, old_action: str) -> bool:
    """Return True if new_action is more urgent than old_action."""
    return ACTION_SEVERITY.get(new_action, 0) > ACTION_SEVERITY.get(old_action, 0)


def trend_arrow(nightscout_direction: str) -> str:
    return TREND_ARROWS.get(nightscout_direction, "?")

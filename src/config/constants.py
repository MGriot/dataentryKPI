"""
Shared domain constants (calculation types, repartition logics, distribution profiles).
"""

# --- Calculation (aggregation) types ---
# Additive types are split across periods so the periods SUM to the annual target;
# level types carry the target as a level, so the periods AVERAGE to it.
CALC_TYPE_SUM = "Sum"
CALC_TYPE_AVERAGE = "Average"
CALC_TYPE_LAST = "Last"
CALC_TYPE_MIN = "Min"
CALC_TYPE_MAX = "Max"
CALC_TYPE_COUNT = "Count"

CALC_TYPES = (CALC_TYPE_SUM, CALC_TYPE_AVERAGE, CALC_TYPE_LAST, CALC_TYPE_MIN, CALC_TYPE_MAX, CALC_TYPE_COUNT)
ADDITIVE_CALC_TYPES = frozenset({CALC_TYPE_SUM, CALC_TYPE_COUNT})

# Names used by earlier versions (and still present in old databases / backups).
_CALC_TYPE_ALIASES = {
    "incremental": CALC_TYPE_SUM,
    "sum": CALC_TYPE_SUM,
    "average": CALC_TYPE_AVERAGE,
    "avg": CALC_TYPE_AVERAGE,
    "mean": CALC_TYPE_AVERAGE,
    "media": CALC_TYPE_AVERAGE,
    "last": CALC_TYPE_LAST,
    "min": CALC_TYPE_MIN,
    "max": CALC_TYPE_MAX,
    "count": CALC_TYPE_COUNT,
}


def normalize_calc_type(value, default: str = CALC_TYPE_SUM) -> str:
    """Maps any accepted spelling (incl. legacy 'Incremental') to a canonical calc type.

    Raises ValueError for unknown values; returns `default` for None/empty.
    """
    if value is None or str(value).strip() == "":
        return default
    canonical = _CALC_TYPE_ALIASES.get(str(value).strip().lower())
    if canonical is None:
        raise ValueError(f"Unknown calculation type '{value}'. Use one of: {', '.join(CALC_TYPES)}.")
    return canonical


def is_additive(calc_type) -> bool:
    try:
        return normalize_calc_type(calc_type) in ADDITIVE_CALC_TYPES
    except ValueError:
        return True


# --- Repartition logic (which periods a template's weights refer to) ---
REPARTITION_LOGIC_YEAR = "Year"
REPARTITION_LOGIC_MONTH = "Month"
REPARTITION_LOGIC_QUARTER = "Quarter"
REPARTITION_LOGIC_WEEK = "Week"
REPARTITION_LOGICS = (REPARTITION_LOGIC_YEAR, REPARTITION_LOGIC_MONTH, REPARTITION_LOGIC_QUARTER, REPARTITION_LOGIC_WEEK)

# --- Distribution profiles (the day-level shape) ---
PROFILE_EVEN = "even_distribution"
PROFILE_ANNUAL_PROGRESSIVE = "annual_progressive"
PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS = "annual_progressive_weekday_bias"
PROFILE_TRUE_ANNUAL_SINUSOIDAL = "true_annual_sinusoidal"
PROFILE_EVENT_BASED = "event_based_spikes_or_dips"
DISTRIBUTION_PROFILES = (
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_EVENT_BASED,
)

# What a KPI with no split assigned gets: an even spread over the year (what the UI promises).
DEFAULT_REPARTITION_LOGIC = REPARTITION_LOGIC_YEAR
DEFAULT_DISTRIBUTION_PROFILE = PROFILE_EVEN

# --- Stored periodic granularities ---
PERIOD_TYPES = ("Day", "Week", "Month", "Quarter", "Year")

# src/core/rollup_engine.py
from typing import List, Dict, Any, Union, Optional
import math

AGGREGATION_SUM = "Sum"
AGGREGATION_AVERAGE = "Average"
AGGREGATION_LAST = "Last"
AGGREGATION_MIN = "Min"
AGGREGATION_MAX = "Max"
AGGREGATION_COUNT = "Count"

SUPPORTED_AGGREGATIONS = [
    AGGREGATION_SUM,
    AGGREGATION_AVERAGE,
    AGGREGATION_LAST,
    AGGREGATION_MIN,
    AGGREGATION_MAX,
    AGGREGATION_COUNT
]

def rollup_series(values: List[Union[float, int]], calculation_type: str = AGGREGATION_SUM) -> Optional[float]:
    """
    Aggregates a sequence of numeric values based on calculation_type.
    
    Supported types:
    - Sum: Sum of all values.
    - Average / Mean: Mean of non-null values.
    - Last: Most recent / last non-null value in sequence.
    - Min: Minimum value.
    - Max: Maximum value.
    - Count: Number of values in sequence.
    """
    clean_values = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]

    if calculation_type.strip().lower() == AGGREGATION_COUNT.lower():
        return float(len(clean_values))

    if not clean_values:
        return None

    calc_clean = calculation_type.strip().lower()

    if calc_clean in [AGGREGATION_SUM.lower(), "incremental"]:
        return float(sum(clean_values))

    elif calc_clean in [AGGREGATION_AVERAGE.lower(), "mean", "media"]:
        return float(sum(clean_values)) / float(len(clean_values))

    elif calc_clean == AGGREGATION_LAST.lower():
        return float(clean_values[-1])

    elif calc_clean == AGGREGATION_MIN.lower():
        return float(min(clean_values))

    elif calc_clean == AGGREGATION_MAX.lower():
        return float(max(clean_values))

    else:
        # Default fallback to Sum
        return float(sum(clean_values))

def aggregate_period_records(
    records: List[Dict[str, Any]],
    value_key: str = "target_value",
    calculation_type: str = AGGREGATION_SUM
) -> Optional[float]:
    """
    Extracts numeric values from a list of record dicts and applies the rollup_series logic.
    """
    vals = [r.get(value_key) for r in records if r.get(value_key) is not None]
    return rollup_series(vals, calculation_type)

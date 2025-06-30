# src/db_core/utils.py
import datetime
import calendar
import numpy as np

# --- Proportion Calculation Helper Functions ---


def get_weighted_proportions(
    num_periods, initial_factor=1.5, final_factor=0.5, decreasing=True
):
    """
    Generates a list of proportions that sum to 1.0, weighted linearly.
    Useful for distributing a total amount across several periods with a
    linearly increasing or decreasing trend.

    Args:
        num_periods (int): The number of periods to generate proportions for.
        initial_factor (float): The starting weight factor.
        final_factor (float): The ending weight factor.
        decreasing (bool): If True, weights decrease; otherwise, they increase.

    Returns:
        list: A list of float proportions, summing to 1.0.
              Returns an empty list if num_periods <= 0.
              Returns [1.0] if num_periods == 1.
    """
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]

    if not decreasing:
        initial_factor, final_factor = final_factor, initial_factor

    if initial_factor == final_factor:  # Handles even distribution
        raw_weights = [1.0] * num_periods
    else:
        raw_weights = np.linspace(initial_factor, final_factor, num_periods).tolist()

    # Ensure all raw_weights are positive before normalization
    min_raw_weight = min(raw_weights)
    if min_raw_weight <= 0:
        # Shift all weights to be positive. The shift amount ensures positivity.
        # Adding a small epsilon (1e-9) to avoid zero weights if min_raw_weight is exactly 0.
        shift = abs(min_raw_weight) + 1e-9
        raw_weights = [w + shift for w in raw_weights]

    total_weight = sum(raw_weights)

    if total_weight == 0:
        # Fallback for an unlikely case where all weights become zero after adjustment
        # (e.g., if initial_factor and final_factor were such that they average to near zero
        # and num_periods is small). Distribute evenly.
        return [1.0 / num_periods] * num_periods
    else:
        return [w / total_weight for w in raw_weights]


def get_parabolic_proportions(num_periods, peak_at_center=True, min_value_epsilon=1e-9):
    """
    Generates a list of proportions that sum to 1.0, following a parabolic curve.
    Useful for distributing a total amount with a peak or valley.

    Args:
        num_periods (int): The number of periods.
        peak_at_center (bool): If True, the parabola peaks at the center (inverted U-shape).
                               If False, it has a valley at the center (U-shape).
        min_value_epsilon (float): A small value to add to ensure all weights are positive.

    Returns:
        list: A list of float proportions, summing to 1.0.
              Returns an empty list if num_periods <= 0.
              Returns [1.0] if num_periods == 1.
    """
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]

    raw_weights = np.zeros(num_periods)
    mid_point_idx = (num_periods - 1) / 2.0  # Center index (can be float)

    for i in range(num_periods):
        raw_weights[i] = (i - mid_point_idx) ** 2

    if peak_at_center:
        # Invert the parabola so the peak is at the center
        raw_weights = np.max(raw_weights) - raw_weights

    raw_weights += min_value_epsilon  # Ensure all weights are positive

    total_weight = np.sum(raw_weights)

    if total_weight == 0:  # Fallback
        return [1.0 / num_periods] * num_periods
    else:
        return (raw_weights / total_weight).tolist()


def get_sinusoidal_proportions(
    num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9
):
    """
    Generates a list of proportions that sum to 1.0, following a sinusoidal curve.
    Useful for distributing a total amount with cyclical variations.

    Args:
        num_periods (int): The number of periods.
        amplitude (float): Amplitude of the sine wave (0 to 1). (1 + amplitude*sin)
                           A value of 0.5 means the wave deviates by +/- 50% around a baseline of 1.
        phase_offset (float): Phase offset for the sine wave in radians.
        min_value_epsilon (float): A small value to ensure all weights are positive.

    Returns:
        list: A list of float proportions, summing to 1.0.
              Returns an empty list if num_periods <= 0.
              Returns [1.0] if num_periods == 1.
    """
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]

    # Generate points from 0 to 2*pi (exclusive of 2*pi for endpoint=False)
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False)
    # Base is 1, sine wave oscillates around it. Max amplitude is 1 for non-negative.
    raw_weights = 1 + amplitude * np.sin(x + phase_offset)

    # Ensure weights are positive. If amplitude is > 1, this clipping is essential.
    raw_weights = np.maximum(raw_weights, min_value_epsilon)

    total_weight = np.sum(raw_weights)

    if total_weight <= 0:  # Fallback, should ideally not happen with min_value_epsilon
        return [1.0 / num_periods] * num_periods
    else:
        return (raw_weights / total_weight).tolist()


# --- Date Helper Functions ---


def get_date_ranges_for_quarters(year):
    """
    Calculates the start and end dates for each quarter of a given year.

    Args:
        year (int): The year for which to calculate quarter dates.

    Returns:
        dict: A dictionary where keys are quarter numbers (1-4) and
              values are tuples of (start_date, end_date) for that quarter.
              Dates are datetime.date objects.
    """
    q_ranges = {}
    q_ranges[1] = (datetime.date(year, 1, 1), datetime.date(year, 3, 31))
    q_ranges[2] = (datetime.date(year, 4, 1), datetime.date(year, 6, 30))
    q_ranges[3] = (datetime.date(year, 7, 1), datetime.date(year, 9, 30))

    # For Q4, correctly determine the last day of December
    q4_end_month = 12
    q4_end_day = calendar.monthrange(year, q4_end_month)[
        1
    ]  # Returns (weekday of first day, num_days_in_month)
    q_ranges[4] = (
        datetime.date(year, 10, 1),
        datetime.date(year, q4_end_month, q4_end_day),
    )
    return q_ranges


def get_kpi_display_name(kpi_data_dict):
    if not kpi_data_dict or not isinstance(kpi_data_dict, dict):
        return "N/D (KPI Data Mancante o Tipo Errato)"
    try:
        g_name = kpi_data_dict.get("group_name", "N/G")
        sg_name = kpi_data_dict.get("subgroup_name", "N/S")
        i_name = kpi_data_dict.get("indicator_name", "N/I")
        g_name = g_name or "N/G (Nome Gruppo Vuoto)"
        sg_name = sg_name or "N/S (Nome Sottogruppo Vuoto)"
        i_name = i_name or "N/I (Nome Indicatore Vuoto)"
        return f"{g_name} > {sg_name} > {i_name}"
    except Exception:
        return "N/D (Errore Display Nome Imprevisto)"


# Note: _placeholder_safe_evaluate_formula was NOT moved here.
# It's not a "general utility" in its current unsafe state.
# It's specifically for formula evaluation within the target_management context.
# If it were made secure and general, it could be considered for db_core/utils.py.

if __name__ == "__main__":
    print("Testing db_core/utils.py...")

    print("\n--- Weighted Proportions ---")
    print(f"Decreasing (3 periods): {get_weighted_proportions(3)}")
    print(
        f"Increasing (4 periods, 0.5 to 1.5): {get_weighted_proportions(4, 0.5, 1.5, decreasing=False)}"
    )
    print(f"Even (5 periods, factor 1 to 1): {get_weighted_proportions(5, 1, 1)}")
    print(f"Single period: {get_weighted_proportions(1)}")
    print(f"Zero periods: {get_weighted_proportions(0)}")
    print(f"Problematic weights (should shift): {get_weighted_proportions(3, -1, 1)}")

    print("\n--- Parabolic Proportions ---")
    print(
        f"Peak at center (5 periods): {get_parabolic_proportions(5, peak_at_center=True)}"
    )
    print(
        f"Valley at center (5 periods): {get_parabolic_proportions(5, peak_at_center=False)}"
    )
    print(f"Single period: {get_parabolic_proportions(1)}")

    print("\n--- Sinusoidal Proportions ---")
    print(f"Standard (12 periods): {get_sinusoidal_proportions(12)}")
    print(
        f"High amplitude (12 periods, amp=0.8): {get_sinusoidal_proportions(12, amplitude=0.8)}"
    )
    print(
        f"Phase shifted (12 periods, phase=np.pi/2): {get_sinusoidal_proportions(12, phase_offset=np.pi/2)}"
    )
    print(f"Single period: {get_sinusoidal_proportions(1)}")

    print("\n--- Date Ranges for Quarters ---")
    current_year = datetime.date.today().year
    print(f"Quarters for {current_year}: {get_date_ranges_for_quarters(current_year)}")
    # Test a leap year
    leap_year = 2024
    print(
        f"Quarters for {leap_year} (Leap Year): {get_date_ranges_for_quarters(leap_year)}"
    )
    # Test a non-leap year
    non_leap_year = 2023
    print(
        f"Quarters for {non_leap_year} (Non-Leap Year): {get_date_ranges_for_quarters(non_leap_year)}"
    )

    print("\nUtils testing finished.")

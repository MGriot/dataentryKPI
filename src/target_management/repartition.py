# your_project_root/target_management/repartition.py
import sqlite3
import json
import datetime
import calendar
import numpy as np
import traceback

# Configuration imports
try:
    from app_config import (
        DB_KPI_DAYS,
        DB_KPI_WEEKS,
        DB_KPI_MONTHS,
        DB_KPI_QUARTERS,
        DB_TARGETS,
    )
    from gui.shared.constants import (
        CALC_TYPE_INCREMENTALE,
        CALC_TYPE_MEDIA,
        REPARTITION_LOGIC_ANNO,
        REPARTITION_LOGIC_MESE,
        REPARTITION_LOGIC_TRIMESTRE,
        REPARTITION_LOGIC_SETTIMANA,
        PROFILE_ANNUAL_PROGRESSIVE,
        PROFILE_EVEN,
        PROFILE_TRUE_ANNUAL_SINUSOIDAL,
        PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
        PROFILE_MONTHLY_SINUSOIDAL,
        PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
        PROFILE_QUARTERLY_PROGRESSIVE,
        PROFILE_QUARTERLY_SINUSOIDAL,
        WEIGHT_INITIAL_FACTOR_INC,
        WEIGHT_FINAL_FACTOR_INC,
        SINE_AMPLITUDE_INCREMENTAL,
        SINE_PHASE_OFFSET,
        WEEKDAY_BIAS_FACTOR_INCREMENTAL,
        WEIGHT_INITIAL_FACTOR_AVG,
        WEIGHT_FINAL_FACTOR_AVG,
        DEVIATION_SCALE_FACTOR_AVG,
        SINE_AMPLITUDE_MEDIA,
        WEEKDAY_BIAS_FACTOR_MEDIA,
    )
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "DB paths or repartition constants will not be correctly defined. "
    )
    # Define placeholders for essential DB paths and constants
    DB_KPI_DAYS, DB_KPI_WEEKS, DB_KPI_MONTHS, DB_KPI_QUARTERS, DB_TARGETS = (
        ":memory_days_repartition_error:",
    ) * 5
    CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA = "Incrementale_fallback", "Media_fallback"
    (
        REPARTITION_LOGIC_ANNO,
        REPARTITION_LOGIC_MESE,
        REPARTITION_LOGIC_TRIMESTRE,
        REPARTITION_LOGIC_SETTIMANA,
    ) = ("Annuale", "Mensile", "Trimestrale", "Settimanale")
    PROFILE_ANNUAL_PROGRESSIVE, PROFILE_EVEN, PROFILE_TRUE_ANNUAL_SINUSOIDAL = (
        "annual_progressive",
        "even",
        "true_annual_sinusoidal",
    )
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS = "annual_progressive_weekday_bias"
    PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE = (
        "monthly_sinusoidal",
        "legacy_intra_period_progressive",
    )
    PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL = (
        "quarterly_progressive",
        "quarterly_sinusoidal",
    )
    WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC = 1.5, 0.5
    SINE_AMPLITUDE_INCREMENTAL, SINE_PHASE_OFFSET, WEEKDAY_BIAS_FACTOR_INCREMENTAL = (
        0.5,
        0,
        1.2,
    )
    WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, DEVIATION_SCALE_FACTOR_AVG = (
        0.8,
        1.2,
        0.2,
    )
    SINE_AMPLITUDE_MEDIA, WEEKDAY_BIAS_FACTOR_MEDIA = 0.2, 1.1


# Module availability flags & Mocks for dependencies
_data_retriever_available = False
_db_core_utils_available = False

try:
    from data_retriever import get_annual_target_entry, get_kpi_detailed_by_id

    _data_retriever_available = True
except ImportError:
    print(
        "WARNING: data_retriever not fully available for repartition.py. Mocks being used."
    )

    def get_annual_target_entry(year, stabilimento_id, kpi_spec_id):
        return None

    def get_kpi_detailed_by_id(kpi_spec_id):
        return None


try:
    from db_core.utils import (
        get_weighted_proportions,
        get_parabolic_proportions,
        get_sinusoidal_proportions,
        get_date_ranges_for_quarters,
    )

    _db_core_utils_available = True
except ImportError:
    print("WARNING: db_core.utils not available for repartition.py. Mocks being used.")

    def get_weighted_proportions(
        num_periods, initial_factor=1.5, final_factor=0.5, decreasing=True
    ):
        return [1.0 / num_periods] * num_periods if num_periods > 0 else []

    def get_parabolic_proportions(
        num_periods, peak_at_center=True, min_value_epsilon=1e-9
    ):
        return [1.0 / num_periods] * num_periods if num_periods > 0 else []

    def get_sinusoidal_proportions(
        num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9
    ):
        return [1.0 / num_periods] * num_periods if num_periods > 0 else []

    def get_date_ranges_for_quarters(year):
        return {
            1: (datetime.date(year, 1, 1), datetime.date(year, 3, 31))
        }  # Simplified mock

# --- Add this block before any use of get_kpi_display_name ---
try:
    from utils.kpi_utils import get_kpi_display_name
except ImportError:

    def get_kpi_display_name(kpi_data_dict):
        # Fallback: minimal display
        return str(kpi_data_dict.get("indicator_name", "N/D"))

# --- Repartition Logic and Calculation ---


def _get_period_allocations(
    annual_target: float,
    user_repartition_logic: str,
    user_repartition_values: dict,  # Expects Python dict (JSON loaded)
    year: int,
    kpi_calc_type: str,
    all_dates_in_year: list,  # List of datetime.date objects
) -> dict:
    """
    Calculates initial allocations to larger periods (month, quarter, week)
    based on user-defined repartition percentages or multipliers.

    For CALC_TYPE_INCREMENTALE:
        - Values in user_repartition_values are percentages of the annual_target for that period.
        - The sum of these percentages is normalized to 100% if it doesn't already sum to 100.
        - Returns a map of {period_index_or_key: allocated_target_sum_for_period}.
    For CALC_TYPE_MEDIA:
        - Values in user_repartition_values are multipliers (as percentages, e.g., 110 for 1.1x)
          applied to the base annual_target (which is treated as an average).
        - Returns a map of {period_index_or_key: multiplier_for_period (e.g., 1.1)}.
    """
    period_allocations = (
        {}
    )  # Key: month_idx (0-11), quarter_idx (0-3), or week_str. Value: allocated sum or multiplier.

    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        if user_repartition_logic == REPARTITION_LOGIC_MESE:
            # User provides { "January": 10, "February": 5, ... } (percentages)
            raw_proportions_list = [
                float(
                    user_repartition_values.get(calendar.month_name[i + 1], 0.0) or 0.0
                )  # Ensure float, handle None
                for i in range(12)
            ]
            total_user_prop_sum = sum(
                p for p in raw_proportions_list if isinstance(p, (int, float))
            )

            if abs(total_user_prop_sum) < 1e-9:  # If sum is zero (e.g. all months 0%)
                final_proportions = [1.0 / 12.0] * 12  # Distribute evenly by default
                print(
                    f"    WARN (get_period_allocations/Inc/Mese): User month proportions sum to zero. Defaulting to even 1/12 distribution."
                )
            elif (
                abs(total_user_prop_sum - 100.0) > 0.01
            ):  # Normalize if not summing to 100
                final_proportions = [
                    (p / total_user_prop_sum) for p in raw_proportions_list
                ]
                print(
                    f"    INFO (get_period_allocations/Inc/Mese): User month proportions (sum: {total_user_prop_sum}%) normalized."
                )
            else:  # Already sums to 100 (or close enough)
                final_proportions = [p / 100.0 for p in raw_proportions_list]

            for i in range(12):  # month_idx 0-11
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
            # User provides { "Q1": 25, "Q2": 30, ... } (percentages)
            raw_proportions_list = [
                float(user_repartition_values.get(f"Q{i + 1}", 0.0) or 0.0)
                for i in range(4)
            ]
            total_user_prop_sum = sum(
                p for p in raw_proportions_list if isinstance(p, (int, float))
            )

            if abs(total_user_prop_sum) < 1e-9:
                final_proportions = [1.0 / 4.0] * 4
                print(
                    f"    WARN (get_period_allocations/Inc/Trim): User quarter proportions sum to zero. Defaulting to even 1/4 distribution."
                )
            elif abs(total_user_prop_sum - 100.0) > 0.01:
                final_proportions = [
                    (p / total_user_prop_sum) for p in raw_proportions_list
                ]
                print(
                    f"    INFO (get_period_allocations/Inc/Trim): User quarter proportions (sum: {total_user_prop_sum}%) normalized."
                )
            else:
                final_proportions = [p / 100.0 for p in raw_proportions_list]

            for i in range(4):  # quarter_idx 0-3
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
            # User provides { "YYYY-Www": percentage, ... }
            # Example: { "2023-W01": 2, "2023-W02": 1.5 }
            sum_of_week_percentages = 0.0
            valid_week_props = {}
            for week_str, prop_val_maybe_str in user_repartition_values.items():
                try:
                    # Validate week_str format "YYYY-Www"
                    datetime.datetime.strptime(
                        week_str + "-1", "%G-W%V-%u"
                    )  # %G, %V for ISO year/week
                    prop_val = float(prop_val_maybe_str or 0.0)
                    valid_week_props[week_str] = prop_val
                    sum_of_week_percentages += prop_val
                except (ValueError, TypeError):
                    print(
                        f"    WARN (get_period_allocations/Inc/Sett): Invalid week format or percentage for '{week_str}': '{prop_val_maybe_str}'. Skipping."
                    )

            unique_iso_weeks_in_year = sorted(
                list(
                    set(
                        f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}"
                        for d in all_dates_in_year
                    )
                )
            )

            if not valid_week_props or abs(sum_of_week_percentages) < 1e-9:
                num_iso_weeks = len(unique_iso_weeks_in_year)
                default_prop_per_week = (
                    (1.0 / num_iso_weeks) if num_iso_weeks > 0 else 0
                )
                for wk_key in unique_iso_weeks_in_year:
                    period_allocations[wk_key] = annual_target * default_prop_per_week
                print(
                    f"    WARN (get_period_allocations/Inc/Sett): No valid week proportions or sum is zero. Defaulting to even distribution over {num_iso_weeks} ISO weeks."
                )
            else:
                normalization_factor = 1.0
                if (
                    abs(sum_of_week_percentages - 100.0) > 0.01
                ):  # Normalize if sum not 100%
                    normalization_factor = (
                        100.0 / sum_of_week_percentages
                        if sum_of_week_percentages != 0
                        else 0
                    )
                    print(
                        f"    INFO (get_period_allocations/Inc/Sett): User week percentages (sum: {sum_of_week_percentages}%) normalized."
                    )

                for week_str, percentage in valid_week_props.items():
                    normalized_percentage = percentage * normalization_factor
                    period_allocations[week_str] = annual_target * (
                        normalized_percentage / 100.0
                    )
                # Ensure all weeks in the year get some allocation if not specified (could be 0 if only specified weeks are used)
                for wk_key in unique_iso_weeks_in_year:
                    if wk_key not in period_allocations:
                        period_allocations[wk_key] = (
                            0.0  # Or distribute remaining if that's the desired logic
                        )

        # Default for REPARTITION_LOGIC_ANNO or unrecognized for Incremental: no specific period allocations, handled by daily distribution.
        else:  # REPARTITION_LOGIC_ANNO or other
            print(
                f"    INFO (get_period_allocations/Inc): Logic '{user_repartition_logic}'. No specific period pre-allocations needed beyond annual."
            )

    elif kpi_calc_type == CALC_TYPE_MEDIA:
        # For MEDIA, user_repartition_values are multipliers (e.g., 110 for 1.1x of base average)
        # The 'annual_target' is the base average.
        if user_repartition_logic == REPARTITION_LOGIC_MESE:
            for i in range(12):  # month_idx 0-11
                month_name = calendar.month_name[i + 1]
                multiplier_perc = float(
                    user_repartition_values.get(month_name, 100.0) or 100.0
                )  # Default 100% (no change)
                period_allocations[i] = (
                    multiplier_perc / 100.0
                )  # Store as actual multiplier e.g. 1.1

        elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
            # Quarter multipliers apply to all months within that quarter
            q_map_month_indices = [
                [0, 1, 2],
                [3, 4, 5],
                [6, 7, 8],
                [9, 10, 11],
            ]  # month_idx 0-11
            for q_idx_0based in range(4):  # quarter_idx 0-3
                q_key = f"Q{q_idx_0based + 1}"
                multiplier_perc = float(
                    user_repartition_values.get(q_key, 100.0) or 100.0
                )
                for month_idx_in_year_0based in q_map_month_indices[q_idx_0based]:
                    period_allocations[month_idx_in_year_0based] = (
                        multiplier_perc / 100.0
                    )

        elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
            # User provides { "YYYY-Www": multiplier_percentage, ... }
            unique_iso_weeks_in_year = sorted(
                list(
                    set(
                        f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}"
                        for d in all_dates_in_year
                    )
                )
            )
            for (
                wk_key
            ) in unique_iso_weeks_in_year:  # Ensure all weeks have a base multiplier
                period_allocations[wk_key] = 1.0  # Default multiplier

            for week_str, mult_val_maybe_str in user_repartition_values.items():
                try:
                    datetime.datetime.strptime(
                        week_str + "-1", "%G-W%V-%u"
                    )  # Validate format
                    multiplier_perc = float(mult_val_maybe_str or 100.0)
                    period_allocations[week_str] = multiplier_perc / 100.0
                except (ValueError, TypeError):
                    print(
                        f"    WARN (get_period_allocations/Media/Sett): Invalid week format or multiplier for '{week_str}': '{mult_val_maybe_str}'. Using default 1.0 for this week if it exists."
                    )
        else:  # REPARTITION_LOGIC_ANNO or other
            print(
                f"    INFO (get_period_allocations/Media): Logic '{user_repartition_logic}'. All days will use base annual average target modified by overall profile."
            )

    return period_allocations


def _get_raw_daily_values_for_repartition(
    year: int,
    annual_target: float,
    kpi_calc_type: str,
    distribution_profile: str,  # e.g., PROFILE_EVEN, PROFILE_ANNUAL_PROGRESSIVE
    profile_params: dict,  # Parsed JSON, e.g., for sine_amplitude, events
    user_repartition_logic: str,
    period_allocations_map: dict,  # Output from _get_period_allocations
    all_dates_in_year: list,  # List of datetime.date objects for the year
) -> np.ndarray:
    """
    Calculates raw daily target values based on annual target, calculation type,
    distribution profile, and any period-specific allocations.
    Event adjustments are applied *after* this function.
    """
    days_in_year = len(all_dates_in_year)
    if days_in_year == 0:
        return np.array([])
    raw_daily_values = np.zeros(days_in_year)

    # --- INCREMENTAL KPI Calculation ---
    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        if distribution_profile == PROFILE_EVEN:
            if (
                user_repartition_logic == REPARTITION_LOGIC_ANNO
                or not period_allocations_map
            ):
                daily_val = annual_target / days_in_year if days_in_year > 0 else 0
                raw_daily_values.fill(daily_val)
            else:  # Distribute period sums evenly within their days
                for d_idx, date_val in enumerate(all_dates_in_year):
                    target_sum_for_this_day_period = 0
                    num_days_in_this_day_period = 0

                    if user_repartition_logic == REPARTITION_LOGIC_MESE:
                        month_idx_0based = date_val.month - 1
                        target_sum_for_this_day_period = period_allocations_map.get(
                            month_idx_0based, 0.0
                        )
                        _, num_days_in_this_day_period = calendar.monthrange(
                            year, date_val.month
                        )
                    elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                        q_idx_0_based = (date_val.month - 1) // 3
                        target_sum_for_this_day_period = period_allocations_map.get(
                            q_idx_0_based, 0.0
                        )
                        q_ranges = get_date_ranges_for_quarters(
                            year
                        )  # Assumes this util is available
                        q_start, q_end = q_ranges[q_idx_0_based + 1]
                        num_days_in_this_day_period = (q_end - q_start).days + 1
                    elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                        iso_y, iso_w, _ = date_val.isocalendar()
                        wk_key = f"{iso_y:04d}-W{iso_w:02d}"
                        target_sum_for_this_day_period = period_allocations_map.get(
                            wk_key, 0.0
                        )
                        # Count actual days in this ISO week within the year's context
                        num_days_in_this_day_period = sum(
                            1
                            for d_in_wk in all_dates_in_year
                            if d_in_wk.isocalendar()[0] == iso_y
                            and d_in_wk.isocalendar()[1] == iso_w
                        )

                    raw_daily_values[d_idx] = (
                        (target_sum_for_this_day_period / num_days_in_this_day_period)
                        if num_days_in_this_day_period > 0
                        else 0
                    )

        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
            # Applies to annual target directly if REPARTITION_LOGIC_ANNO
            # If MESE/TRIMESTRE, this profile logic is usually applied *within* those periods, see below.
            # For now, let's assume this means progressive over the whole year if selected.
            # This part of the original code was complex. A simpler interpretation:
            # If logic is ANNO, then apply annual progressive. Otherwise, the intra-period profiles take over.
            if user_repartition_logic == REPARTITION_LOGIC_ANNO:
                props = get_weighted_proportions(
                    days_in_year,
                    WEIGHT_INITIAL_FACTOR_INC,
                    WEIGHT_FINAL_FACTOR_INC,
                    decreasing=True,
                )
                raw_daily_values = np.array([annual_target * p for p in props])
            else:  # Fallback to even distribution if profile is annual but logic isn't. Daily values will be shaped later.
                raw_daily_values.fill(
                    annual_target / days_in_year if days_in_year > 0 else 0
                )

        elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
            if user_repartition_logic == REPARTITION_LOGIC_ANNO:
                amp = float(
                    profile_params.get("sine_amplitude", SINE_AMPLITUDE_INCREMENTAL)
                )
                phase = float(profile_params.get("sine_phase", SINE_PHASE_OFFSET))
                props = get_sinusoidal_proportions(days_in_year, amp, phase)
                raw_daily_values = np.array([annual_target * p for p in props])
            else:
                raw_daily_values.fill(
                    annual_target / days_in_year if days_in_year > 0 else 0
                )

        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
            if user_repartition_logic == REPARTITION_LOGIC_ANNO:
                base_props = get_weighted_proportions(
                    days_in_year,
                    WEIGHT_INITIAL_FACTOR_INC,
                    WEIGHT_FINAL_FACTOR_INC,
                    decreasing=True,
                )
                adj_props = np.array(
                    [
                        base_props[i]
                        * (
                            WEEKDAY_BIAS_FACTOR_INCREMENTAL
                            if all_dates_in_year[i].weekday() >= 5
                            else 1.0
                        )  # Bias for Sat/Sun
                        for i in range(days_in_year)
                    ]
                )
                current_sum_adj = np.sum(adj_props)
                final_props_adj = (
                    (adj_props / current_sum_adj)
                    if current_sum_adj > 1e-9
                    else (
                        [1.0 / days_in_year] * days_in_year if days_in_year > 0 else []
                    )
                )
                raw_daily_values = np.array(
                    [annual_target * p for p in final_props_adj]
                )
            else:
                raw_daily_values.fill(
                    annual_target / days_in_year if days_in_year > 0 else 0
                )

        # Intra-period profiles for Incremental
        elif distribution_profile in [
            PROFILE_MONTHLY_SINUSOIDAL,
            PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
            PROFILE_QUARTERLY_PROGRESSIVE,
            PROFILE_QUARTERLY_SINUSOIDAL,
        ]:
            if user_repartition_logic == REPARTITION_LOGIC_MESE or (
                user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE
                and distribution_profile
                in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE]
            ):
                # Determine monthly target sums first
                monthly_target_sums_final = [0.0] * 12
                if user_repartition_logic == REPARTITION_LOGIC_MESE:
                    for m_idx_0based in range(12):
                        monthly_target_sums_final[m_idx_0based] = (
                            period_allocations_map.get(m_idx_0based, 0.0)
                        )
                elif (
                    user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE
                ):  # Distribute quarter sum progressively/sinusoidally into months
                    q_map_month_indices = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
                    for q_idx_0based, months_in_q_indices in enumerate(
                        q_map_month_indices
                    ):
                        q_total_sum = period_allocations_map.get(q_idx_0based, 0.0)
                        num_months_in_q = len(months_in_q_indices)
                        if num_months_in_q == 0:
                            continue

                        month_weights_in_q = [
                            1.0 / num_months_in_q
                        ] * num_months_in_q  # Default even
                        if (
                            distribution_profile
                            == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE
                        ):  # Progressive over months in quarter
                            month_weights_in_q = get_weighted_proportions(
                                num_months_in_q,
                                WEIGHT_INITIAL_FACTOR_INC,
                                WEIGHT_FINAL_FACTOR_INC,
                                decreasing=True,
                            )
                        elif (
                            distribution_profile == PROFILE_MONTHLY_SINUSOIDAL
                        ):  # Sinusoidal over months in quarter
                            month_weights_in_q = get_parabolic_proportions(
                                num_months_in_q, peak_at_center=True
                            )  # Or sinusoidal

                        for i, month_idx_in_year_0based in enumerate(
                            months_in_q_indices
                        ):
                            monthly_target_sums_final[month_idx_in_year_0based] = (
                                q_total_sum * month_weights_in_q[i]
                            )

                # Now distribute each month's sum across its days based on profile
                for month_idx_0based, month_sum_val in enumerate(
                    monthly_target_sums_final
                ):
                    if abs(month_sum_val) < 1e-9:
                        continue
                    current_month_1based = month_idx_0based + 1
                    _, num_days_in_month_val = calendar.monthrange(
                        year, current_month_1based
                    )
                    if num_days_in_month_val == 0:
                        continue

                    day_props_in_month_list = [
                        1.0 / num_days_in_month_val
                    ] * num_days_in_month_val  # Default even
                    if distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
                        day_props_in_month_list = get_parabolic_proportions(
                            num_days_in_month_val, peak_at_center=True
                        )  # Parabolic as sinusoidal example
                    elif (
                        distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE
                    ):
                        day_props_in_month_list = get_weighted_proportions(
                            num_days_in_month_val,
                            WEIGHT_INITIAL_FACTOR_INC,
                            WEIGHT_FINAL_FACTOR_INC,
                            decreasing=True,
                        )

                    month_start_date = datetime.date(year, current_month_1based, 1)
                    month_start_day_idx_of_year = (
                        month_start_date - all_dates_in_year[0]
                    ).days

                    for day_of_month_idx, prop in enumerate(day_props_in_month_list):
                        actual_day_idx_in_year = (
                            month_start_day_idx_of_year + day_of_month_idx
                        )
                        if 0 <= actual_day_idx_in_year < days_in_year:
                            raw_daily_values[actual_day_idx_in_year] = (
                                month_sum_val * prop
                            )

            elif (
                user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE
                and distribution_profile
                in [PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]
            ):
                q_date_ranges = get_date_ranges_for_quarters(year)
                for q_idx_0based in range(4):  # quarter 0-3
                    q_total_sum = period_allocations_map.get(q_idx_0based, 0.0)
                    if abs(q_total_sum) < 1e-9:
                        continue

                    q_start_date, q_end_date = q_date_ranges[q_idx_0based + 1]
                    num_days_in_q_val = (q_end_date - q_start_date).days + 1
                    if num_days_in_q_val == 0:
                        continue

                    day_props_in_q_list = [
                        1.0 / num_days_in_q_val
                    ] * num_days_in_q_val  # Default even
                    if distribution_profile == PROFILE_QUARTERLY_PROGRESSIVE:
                        day_props_in_q_list = get_weighted_proportions(
                            num_days_in_q_val,
                            WEIGHT_INITIAL_FACTOR_INC,
                            WEIGHT_FINAL_FACTOR_INC,
                            decreasing=True,
                        )
                    elif distribution_profile == PROFILE_QUARTERLY_SINUSOIDAL:
                        day_props_in_q_list = get_parabolic_proportions(
                            num_days_in_q_val, peak_at_center=True
                        )

                    q_start_day_idx_of_year = (q_start_date - all_dates_in_year[0]).days
                    for day_of_q_idx, prop in enumerate(day_props_in_q_list):
                        actual_day_idx_in_year = q_start_day_idx_of_year + day_of_q_idx
                        if 0 <= actual_day_idx_in_year < days_in_year:
                            raw_daily_values[actual_day_idx_in_year] = (
                                q_total_sum * prop
                            )
            else:  # Fallback for unhandled combo of repartition logic and intra-period profile
                raw_daily_values.fill(
                    annual_target / days_in_year if days_in_year > 0 else 0
                )
                print(
                    f"    WARN (Inc): Unhandled combination of repartition logic '{user_repartition_logic}' and profile '{distribution_profile}'. Defaulting to even daily."
                )

        else:  # Default profile for Incremental
            props = get_weighted_proportions(
                days_in_year,
                WEIGHT_INITIAL_FACTOR_INC,
                WEIGHT_FINAL_FACTOR_INC,
                decreasing=True,
            )
            raw_daily_values = np.array([annual_target * p for p in props])

    # --- MEDIA KPI Calculation ---
    elif kpi_calc_type == CALC_TYPE_MEDIA:
        # Base daily average is annual_target. This is then modified by period multipliers and distribution profiles.
        for d_idx, date_val in enumerate(all_dates_in_year):
            # Step 1: Get base average for the day from period_allocations_map (which stores multipliers)
            base_avg_for_day_from_repart = (
                annual_target  # Default is the overall annual average
            )
            if user_repartition_logic == REPARTITION_LOGIC_MESE:
                month_idx_0based = date_val.month - 1
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(month_idx_0based, 1.0)
                )
            elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                # Recall period_allocations_map for Trimestral Media stores by month_idx
                month_idx_0based = date_val.month - 1
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(month_idx_0based, 1.0)
                )
            elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                iso_y, iso_w, _ = date_val.isocalendar()
                wk_key = f"{iso_y:04d}-W{iso_w:02d}"
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(wk_key, 1.0)
                )

            # Step 2: Apply distribution profile to this base_avg_for_day_from_repart
            if distribution_profile == PROFILE_EVEN:
                raw_daily_values[d_idx] = base_avg_for_day_from_repart

            elif (
                distribution_profile == PROFILE_ANNUAL_PROGRESSIVE
            ):  # Progressive deviation over the year
                # This profile applies a deviation factor that changes over the year.
                # Deviation scale factor controls how much it deviates from base.
                factors_prog = np.linspace(
                    WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
                )  # e.g. 0.8 to 1.2
                deviation_from_one = factors_prog[d_idx] - 1.0  # e.g. -0.2 to +0.2
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (
                    1 + deviation_from_one * DEVIATION_SCALE_FACTOR_AVG
                )

            elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
                amp = float(profile_params.get("sine_amplitude", SINE_AMPLITUDE_MEDIA))
                phase = float(profile_params.get("sine_phase", SINE_PHASE_OFFSET))
                x_annual_sin = np.linspace(0, 2 * np.pi, days_in_year, endpoint=False)
                sine_modulation = amp * np.sin(
                    x_annual_sin[d_idx] + phase
                )  # e.g. if amp=0.1, then +/-10%
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (
                    1 + sine_modulation
                )

            elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
                factors_bias = np.linspace(
                    WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
                )
                deviation_bias = factors_bias[d_idx] - 1.0
                day_target_val_bias = base_avg_for_day_from_repart * (
                    1 + deviation_bias * DEVIATION_SCALE_FACTOR_AVG
                )
                if date_val.weekday() >= 5:  # Saturday or Sunday
                    day_target_val_bias *= WEEKDAY_BIAS_FACTOR_MEDIA
                raw_daily_values[d_idx] = day_target_val_bias

            # Intra-period profiles for Media
            elif distribution_profile in [
                PROFILE_MONTHLY_SINUSOIDAL,
                PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                PROFILE_QUARTERLY_PROGRESSIVE,
                PROFILE_QUARTERLY_SINUSOIDAL,
            ]:
                num_days_in_mod_period, day_idx_in_mod_period = 0, 0

                if distribution_profile in [
                    PROFILE_MONTHLY_SINUSOIDAL,
                    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                ]:
                    _, num_days_in_mod_period = calendar.monthrange(
                        year, date_val.month
                    )
                    day_idx_in_mod_period = date_val.day - 1
                elif distribution_profile in [
                    PROFILE_QUARTERLY_PROGRESSIVE,
                    PROFILE_QUARTERLY_SINUSOIDAL,
                ]:
                    q_idx_0based = (date_val.month - 1) // 3
                    q_ranges_mod = get_date_ranges_for_quarters(year)
                    q_start_mod, q_end_mod = q_ranges_mod[q_idx_0based + 1]
                    num_days_in_mod_period = (q_end_mod - q_start_mod).days + 1
                    day_idx_in_mod_period = (date_val - q_start_mod).days

                if num_days_in_mod_period == 0:
                    raw_daily_values[d_idx] = (
                        base_avg_for_day_from_repart  # Should not happen
                    )
                    continue

                modulation_factor_deviation = (
                    0.0  # This is the +/- deviation, not the final multiplier
                )
                if distribution_profile in [
                    PROFILE_MONTHLY_SINUSOIDAL,
                    PROFILE_QUARTERLY_SINUSOIDAL,
                ]:  # Parabolic used as sinusoidal example
                    # Parabolic weights (peak at center), then normalize to a +/- deviation
                    par_weights_mod_raw = np.zeros(num_days_in_mod_period)
                    mid_idx_mod = (num_days_in_mod_period - 1) / 2.0
                    for i_mod in range(num_days_in_mod_period):
                        par_weights_mod_raw[i_mod] = (i_mod - mid_idx_mod) ** 2
                    par_weights_mod = (
                        np.max(par_weights_mod_raw) - par_weights_mod_raw
                    )  # Inverted: peak at center

                    mean_w_mod = (
                        np.mean(par_weights_mod)
                        if num_days_in_mod_period > 1
                        else par_weights_mod[0]
                    )
                    # Deviation of current day's weight from the mean weight of the period
                    current_day_deviation_from_mean = (
                        par_weights_mod[day_idx_in_mod_period] - mean_w_mod
                    )
                    # Max absolute deviation in the period to normalize current_day_deviation
                    max_abs_dev_in_period = (
                        np.max(np.abs(par_weights_mod - mean_w_mod))
                        if num_days_in_mod_period > 1
                        else 0
                    )

                    normalized_deviation_signal = 0.0
                    if max_abs_dev_in_period > 1e-9:
                        normalized_deviation_signal = (
                            current_day_deviation_from_mean / max_abs_dev_in_period
                        )  # Ranges roughly -1 to 1
                    modulation_factor_deviation = (
                        normalized_deviation_signal * DEVIATION_SCALE_FACTOR_AVG
                    )  # Scale it, e.g. *0.2 for +/-20%

                elif distribution_profile in [
                    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                    PROFILE_QUARTERLY_PROGRESSIVE,
                ]:
                    factors_period_mod = np.linspace(
                        WEIGHT_INITIAL_FACTOR_AVG,
                        WEIGHT_FINAL_FACTOR_AVG,
                        num_days_in_mod_period,
                    )  # e.g. 0.8 to 1.2
                    deviation_from_one_in_period = (
                        factors_period_mod[day_idx_in_mod_period] - 1.0
                    )  # e.g. -0.2 to +0.2
                    modulation_factor_deviation = (
                        deviation_from_one_in_period * DEVIATION_SCALE_FACTOR_AVG
                    )

                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (
                    1 + modulation_factor_deviation
                )

            else:  # Default profile for Media if not specified above
                raw_daily_values[d_idx] = (
                    base_avg_for_day_from_repart  # No specific daily modulation, just period avg.
                )

    else:
        print(
            f"ERROR (get_raw_daily): Tipo calcolo KPI sconosciuto: {kpi_calc_type}. Returning zeros."
        )
    return raw_daily_values


def _apply_event_adjustments_to_daily_values(
    raw_daily_values_input: np.ndarray,
    event_data_list: list,  # List of event dicts from profile_params["events"]
    kpi_calc_type: str,
    annual_target_for_normalization: float,  # Only for CALC_TYPE_INCREMENTALE
    all_dates_in_year: list,  # List of datetime.date objects for the year
) -> np.ndarray:
    """
    Adjusts daily target values based on a list of events (multipliers/additions).
    For INCREMENTAL KPIs, the total sum is re-normalized to the annual_target after adjustments.
    """
    if not event_data_list:
        return raw_daily_values_input

    adjusted_daily_values = np.copy(raw_daily_values_input)  # Work on a copy

    for event in event_data_list:
        try:
            start_event_date_obj = datetime.datetime.strptime(
                event["start_date"], "%Y-%m-%d"
            ).date()
            end_event_date_obj = datetime.datetime.strptime(
                event["end_date"], "%Y-%m-%d"
            ).date()
            multiplier_event = float(
                event.get("multiplier", 1.0)
            )  # Default to no multiplication
            addition_event = float(event.get("addition", 0.0))  # Default to no addition

            if not (0.0 <= multiplier_event):  # Basic sanity for multiplier
                print(
                    f"    WARN (Event Adjust): Invalid event multiplier {multiplier_event} (must be >=0). Skipping this event: {event}"
                )
                continue

            for d_idx, date_val_event_loop in enumerate(all_dates_in_year):
                if start_event_date_obj <= date_val_event_loop <= end_event_date_obj:
                    if kpi_calc_type == CALC_TYPE_MEDIA:
                        adjusted_daily_values[d_idx] = (
                            adjusted_daily_values[d_idx] * multiplier_event
                        ) + addition_event
                    elif kpi_calc_type == CALC_TYPE_INCREMENTALE:
                        # For incremental, multiplier applies, then addition.
                        # Normalization to annual total happens *after* all events.
                        adjusted_daily_values[d_idx] *= multiplier_event
                        adjusted_daily_values[
                            d_idx
                        ] += addition_event  # Direct addition for incremental values
                        # Ensure non-negative if physical quantities
                        # if adjusted_daily_values[d_idx] < 0: adjusted_daily_values[d_idx] = 0
        except (ValueError, KeyError, TypeError) as e_event_proc:
            print(
                f"    WARN (Event Adjust): Invalid event data or processing error, event skipped. Details: {event}, Error: {e_event_proc}"
            )
            continue

    # For INCREMENTAL, re-normalize the sum of daily values to the original annual target
    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        current_total_after_events = np.sum(adjusted_daily_values)
        if (
            abs(annual_target_for_normalization) < 1e-9
        ):  # If original annual target was zero
            adjusted_daily_values.fill(0.0)
            print(
                "    INFO (Event Adjust/Inc): Annual target is zero. All daily values set to zero after events."
            )
        elif (
            abs(current_total_after_events) > 1e-9
        ):  # If new sum is not zero, normalize
            renormalization_factor = (
                annual_target_for_normalization / current_total_after_events
            )
            adjusted_daily_values *= renormalization_factor
            print(
                f"    INFO (Event Adjust/Inc): Incremental daily values re-normalized to annual total {annual_target_for_normalization:.2f} (from {current_total_after_events:.2f})."
            )
        elif (
            abs(current_total_after_events) < 1e-9
            and abs(annual_target_for_normalization) > 1e-9
        ):  # Sum became zero but target isn't
            # This is a tricky case. Distribute evenly? Or error?
            # For now, if events made sum zero but target was non-zero, this implies an issue.
            # Let's fill with even distribution as a fallback.
            print(
                f"    WARN (Event Adjust/Inc): Sum of daily values became zero after events, but annual target is {annual_target_for_normalization:.2f}. Distributing evenly as fallback."
            )
            if len(adjusted_daily_values) > 0:
                adjusted_daily_values.fill(
                    annual_target_for_normalization / len(adjusted_daily_values)
                )

    return adjusted_daily_values


def _aggregate_and_save_periodic_targets(
    daily_targets_with_dates: list,  # List of tuples: [(datetime.date, target_value), ...]
    year: int,
    stabilimento_id: int,
    kpi_spec_id: int,
    target_number: int,  # 1 or 2
    kpi_calc_type: str,
):
    """
    Aggregates daily targets into weekly, monthly, and quarterly targets
    and saves them to their respective databases.
    """
    if not daily_targets_with_dates:
        print(
            f"    INFO (_aggregate_save): No daily targets provided for KPI {kpi_spec_id}, T{target_number}. Skipping aggregation."
        )
        return

    # --- Save Daily Targets ---
    db_daily_recs = []
    for date_obj, daily_target_val in daily_targets_with_dates:
        db_daily_recs.append(
            (
                year,
                stabilimento_id,
                kpi_spec_id,
                target_number,
                date_obj.isoformat(),
                daily_target_val,
            )
        )

    if db_daily_recs:
        try:
            with sqlite3.connect(DB_KPI_DAYS) as conn_days:
                conn_days.executemany(
                    "INSERT INTO daily_targets (year,stabilimento_id,kpi_id,target_number,date_value,target_value) VALUES (?,?,?,?,?,?)",
                    db_daily_recs,
                )
                conn_days.commit()
            print(
                f"      Saved {len(db_daily_recs)} daily targets for KPI {kpi_spec_id}, T{target_number}."
            )
        except sqlite3.Error as e_days:
            print(
                f"      ERROR saving daily targets for KPI {kpi_spec_id}, T{target_number}: {e_days}"
            )
            # Consider if this is fatal for subsequent aggregations.

    # --- Aggregate for Weekly Targets ---
    weekly_agg_data = {}  # Key: "YYYY-Www", Value: list of daily targets in that week
    for date_val, daily_target_val in daily_targets_with_dates:
        iso_y_cal, iso_w_num, _ = date_val.isocalendar()
        week_key_str = f"{iso_y_cal:04d}-W{iso_w_num:02d}"
        if week_key_str not in weekly_agg_data:
            weekly_agg_data[week_key_str] = []
        weekly_agg_data[week_key_str].append(daily_target_val)

    db_week_recs = []
    for wk_key, tgts_in_wk_list in sorted(weekly_agg_data.items()):  # Sort by week key
        if not tgts_in_wk_list:
            continue
        num_days_in_week_for_avg = len(tgts_in_wk_list)
        wt_val = (
            sum(tgts_in_wk_list)
            if kpi_calc_type == CALC_TYPE_INCREMENTALE
            else (
                sum(tgts_in_wk_list) / num_days_in_week_for_avg
                if num_days_in_week_for_avg > 0
                else 0
            )
        )
        db_week_recs.append(
            (year, stabilimento_id, kpi_spec_id, target_number, wk_key, wt_val)
        )

    if db_week_recs:
        try:
            with sqlite3.connect(DB_KPI_WEEKS) as conn_weeks:
                conn_weeks.executemany(
                    "INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)",
                    db_week_recs,
                )
                conn_weeks.commit()
            print(f"      Saved {len(db_week_recs)} weekly targets.")
        except sqlite3.Error as e_weeks:
            print(f"      ERROR saving weekly targets: {e_weeks}")

    # --- Aggregate for Monthly Targets ---
    monthly_agg_data_map = {i: [] for i in range(12)}  # Month index 0-11
    for date_val, daily_target_val in daily_targets_with_dates:
        if date_val.year == year:  # Ensure date is within the target year (should be)
            monthly_agg_data_map[date_val.month - 1].append(daily_target_val)

    db_month_recs = []
    for month_idx_0based in range(12):
        tgts_in_m_list = monthly_agg_data_map[month_idx_0based]
        month_name_str = calendar.month_name[month_idx_0based + 1]
        mt_val = 0.0
        if tgts_in_m_list:  # If list is not empty
            num_days_in_month_for_avg = len(
                tgts_in_m_list
            )  # Actual number of days with data in this month
            mt_val = (
                sum(tgts_in_m_list)
                if kpi_calc_type == CALC_TYPE_INCREMENTALE
                else (
                    sum(tgts_in_m_list) / num_days_in_month_for_avg
                    if num_days_in_month_for_avg > 0
                    else 0
                )
            )
        db_month_recs.append(
            (year, stabilimento_id, kpi_spec_id, target_number, month_name_str, mt_val)
        )

    if db_month_recs:
        try:
            with sqlite3.connect(DB_KPI_MONTHS) as conn_months:
                conn_months.executemany(
                    "INSERT INTO monthly_targets (year,stabilimento_id,kpi_id,target_number,month_value,target_value) VALUES (?,?,?,?,?,?)",
                    db_month_recs,
                )
                conn_months.commit()
            print(f"      Saved {len(db_month_recs)} monthly targets.")
        except sqlite3.Error as e_months:
            print(f"      ERROR saving monthly targets: {e_months}")

    # --- Aggregate for Quarterly Targets (using the just calculated monthly targets) ---
    quarterly_agg_data_map = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    # Create a map of month_name: target_value from db_month_recs for easier lookup
    actual_monthly_tgts_for_q_calc = {rec[4]: rec[5] for rec in db_month_recs}

    month_to_q_map_val = {
        calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13)
    }
    for (
        month_name_str_q,
        monthly_target_val_for_q,
    ) in actual_monthly_tgts_for_q_calc.items():
        if month_name_str_q in month_to_q_map_val:
            quarter_key = month_to_q_map_val[month_name_str_q]
            quarterly_agg_data_map[quarter_key].append(monthly_target_val_for_q)

    db_quarter_recs = []
    for q_name_str in ["Q1", "Q2", "Q3", "Q4"]:  # Ensure order
        tgts_in_q_list = quarterly_agg_data_map[q_name_str]
        qt_val = 0.0
        if (
            tgts_in_q_list
        ):  # If list not empty (i.e., months in this quarter had targets)
            num_months_in_q_for_avg = len(tgts_in_q_list)
            qt_val = (
                sum(tgts_in_q_list)
                if kpi_calc_type == CALC_TYPE_INCREMENTALE
                else (
                    sum(tgts_in_q_list) / num_months_in_q_for_avg
                    if num_months_in_q_for_avg > 0
                    else 0
                )
            )
        db_quarter_recs.append(
            (year, stabilimento_id, kpi_spec_id, target_number, q_name_str, qt_val)
        )

    if db_quarter_recs:
        try:
            with sqlite3.connect(DB_KPI_QUARTERS) as conn_quarters:
                conn_quarters.executemany(
                    "INSERT INTO quarterly_targets (year,stabilimento_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)",
                    db_quarter_recs,
                )
                conn_quarters.commit()
            print(f"      Saved {len(db_quarter_recs)} quarterly targets.")
        except sqlite3.Error as e_quarters:
            print(f"      ERROR saving quarterly targets: {e_quarters}")


# --- Main Repartition Function (Called by annual.py) ---
def calculate_and_save_all_repartitions(
    year: int, stabilimento_id: int, kpi_spec_id: int, target_number: int  # 1 or 2
):
    """
    Main function to calculate and save all periodic repartitions (daily, weekly,
    monthly, quarterly) for a given annual target (Target 1 or Target 2).
    It fetches annual target details, KPI calculation type, then orchestrates
    the calculation and saving steps.
    """
    if not _data_retriever_available or not _db_core_utils_available:
        print(
            f"CRITICAL ERROR (Repart): Missing data_retriever or db_core.utils. Cannot calculate repartitions for KPI {kpi_spec_id}, T{target_number}."
        )
        return

    # --- FIX: Convert Path objects to strings before checking ---
    db_paths_to_check = [
        DB_TARGETS,
        DB_KPI_DAYS,
        DB_KPI_WEEKS,
        DB_KPI_MONTHS,
        DB_KPI_QUARTERS,
    ]
    for db_path_obj in db_paths_to_check:
        db_path_str = str(db_path_obj)
        if db_path_str.startswith(":memory_") or "error_db" in db_path_str:
            raise ConnectionError(
                f"Database path for repartition is not properly configured ({db_path_str})."
            )
    # --- END OF FIX ---

    print(
        f"  Calculating repartitions for: Year={year}, Stab={stabilimento_id}, KPI Spec={kpi_spec_id}, TargetNum={target_number}"
    )

    # 1. Get Annual Target Info
    target_info_row = get_annual_target_entry(year, stabilimento_id, kpi_spec_id)
    if not target_info_row:
        print(
            f"    ERROR: No annual target entry found for KPI {kpi_spec_id}, Year {year}, Stab {stabilimento_id}. Cannot repartition."
        )
        return
    target_info = dict(target_info_row)

    # 2. Get KPI Details
    kpi_details_row = get_kpi_detailed_by_id(kpi_spec_id)
    if not kpi_details_row:
        print(
            f"    ERROR: KPI details not found for KPI Spec ID {kpi_spec_id}. Cannot determine calc_type for repartition."
        )
        return
    kpi_details = dict(kpi_details_row)
    kpi_calc_type = kpi_details.get("calculation_type", CALC_TYPE_INCREMENTALE)

    annual_target_to_use = target_info.get(f"annual_target{target_number}")

    # Clear old data if the target is None
    if annual_target_to_use is None:
        print(
            f"    INFO: Annual target {target_number} for KPI {kpi_spec_id} is None. Cleaning up any existing periodic data."
        )
        dbs_to_clear_for_none = [
            (DB_KPI_DAYS, "daily_targets"),
            (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"),
            (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path_clear, table_name_clear in dbs_to_clear_for_none:
            try:
                with sqlite3.connect(db_path_clear) as conn_clear:
                    conn_clear.execute(
                        f"DELETE FROM {table_name_clear} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                        (year, stabilimento_id, kpi_spec_id, target_number),
                    )
                    conn_clear.commit()
            except sqlite3.Error as e_clear:
                print(
                    f"      WARN: Failed to clear old data from {table_name_clear} for KPI {kpi_spec_id}, T{target_number}: {e_clear}"
                )
        return  # Stop if annual target is None

    # Proceed with calculation
    annual_target_to_use = float(annual_target_to_use)
    user_repart_logic = target_info.get("repartition_logic", REPARTITION_LOGIC_ANNO)
    distribution_profile = target_info.get(
        "distribution_profile", PROFILE_ANNUAL_PROGRESSIVE
    )

    try:
        user_repart_values = json.loads(
            target_info.get("repartition_values", "{}") or "{}"
        )
    except json.JSONDecodeError:
        print(
            f"    WARN: Invalid JSON in 'repartition_values' for KPI {kpi_spec_id}. Using empty dict. Value: '{target_info.get('repartition_values')}'"
        )
        user_repart_values = {}

    try:
        profile_params = json.loads(target_info.get("profile_params", "{}") or "{}")
    except json.JSONDecodeError:
        print(
            f"    WARN: Invalid JSON in 'profile_params' for KPI {kpi_spec_id}. Using empty dict. Value: '{target_info.get('profile_params')}'"
        )
        profile_params = {}

    # 3. Clear any old periodic data for this specific target before saving new
    print(f"    Clearing old periodic data for KPI {kpi_spec_id}, T{target_number}...")
    dbs_to_clear = [
        (DB_KPI_DAYS, "daily_targets"),
        (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"),
        (DB_KPI_QUARTERS, "quarterly_targets"),
    ]
    for db_path_clear, table_name_clear in dbs_to_clear:
        try:
            with sqlite3.connect(db_path_clear) as conn_clear:
                conn_clear.execute(
                    f"DELETE FROM {table_name_clear} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                    (year, stabilimento_id, kpi_spec_id, target_number),
                )
                conn_clear.commit()
        except sqlite3.Error as e_clear_old:
            print(
                f"      WARN: Failed to clear old data from {table_name_clear} for KPI {kpi_spec_id}, T{target_number} before re-calculation: {e_clear_old}"
            )

    # 4. Generate all dates in the year
    try:
        start_of_year = datetime.date(year, 1, 1)
        days_in_year_count = (datetime.date(year, 12, 31) - start_of_year).days + 1
        all_dates_in_year_list = [
            start_of_year + datetime.timedelta(days=i)
            for i in range(days_in_year_count)
        ]
    except ValueError:
        print(
            f"    ERROR: Invalid year {year} for date generation. Cannot repartition."
        )
        return

    # 5. Get initial period allocations
    period_allocations = _get_period_allocations(
        annual_target_to_use,
        user_repart_logic,
        user_repart_values,
        year,
        kpi_calc_type,
        all_dates_in_year_list,
    )

    # 6. Get raw daily values
    raw_daily_target_values = _get_raw_daily_values_for_repartition(
        year,
        annual_target_to_use,
        kpi_calc_type,
        distribution_profile,
        profile_params,
        user_repart_logic,
        period_allocations,
        all_dates_in_year_list,
    )
    if raw_daily_target_values.size == 0:
        print(
            f"    ERROR: No raw daily values generated for KPI {kpi_spec_id}, T{target_number}. Repartition aborted."
        )
        return

    # 7. Apply event adjustments
    event_data_from_params = profile_params.get("events", [])
    if event_data_from_params:
        print(f"    Applying {len(event_data_from_params)} event adjustments...")
        final_daily_target_values = _apply_event_adjustments_to_daily_values(
            raw_daily_target_values,
            event_data_from_params,
            kpi_calc_type,
            annual_target_to_use,
            all_dates_in_year_list,
        )
    else:
        final_daily_target_values = raw_daily_target_values

    # 8. Aggregate daily values and save to all periodic tables
    daily_targets_to_save_with_dates = list(
        zip(all_dates_in_year_list, final_daily_target_values)
    )

    _aggregate_and_save_periodic_targets(
        daily_targets_to_save_with_dates,
        year,
        stabilimento_id,
        kpi_spec_id,
        target_number,
        kpi_calc_type,
    )

    kpi_full_name_display = get_kpi_display_name(kpi_details)
    print(
        f"  Successfully calculated and saved all repartitions for KPI: {kpi_full_name_display} (ID {kpi_spec_id}), Target {target_number}."
    )





if __name__ == "__main__":
    print("--- Running target_management/repartition.py for testing ---")
    # This test block is complex. It needs:
    # - app_config.py to be fully populated with constants.
    # - data_retriever.py and db_core.utils.py to be available and working.
    # - DB_TARGETS and periodic DBs (Days, Weeks, etc.) to exist and be schema-correct.
    # - An annual target entry in DB_TARGETS for the KPI being tested.
    # - A KPI detail entry (via data_retriever) for the KPI being tested.

    # --- Test Setup ---
    # For a real test, you would:
    # 1. Use temporary, dedicated test database files.
    # 2. Populate DB_TARGETS with a test annual_target record.
    # 3. Populate DB_KPIS so that data_retriever.get_kpi_detailed_by_id returns test KPI details.
    # 4. Call calculate_and_save_all_repartitions.
    # 5. Query the periodic DBs to verify the results.

    print("INFO: Repartition module testing requires significant setup.")
    print(
        "      Consider testing through save_annual_targets in annual.py, which calls this."
    )
    print(
        "      Or, implement a dedicated test suite with proper database mocking/setup."
    )

    # Example of a *very* simplified direct call (would need mocks for data_retriever to run standalone)
    if (
        _data_retriever_available
        and _db_core_utils_available
        and not any(
            db.startswith(":memory_") or "error_db" in str(db)
            for db in [DB_TARGETS, DB_KPI_DAYS]
        )
    ):

        print(
            "\nAttempting a simplified test case (requires pre-existing data or robust mocks):"
        )
        test_year_repart = datetime.date.today().year
        test_stab_id_repart = 1  # Assume exists
        test_kpi_spec_id_repart = 1  # Assume exists with an annual target and details

        # Mock get_annual_target_entry for this test
        _get_annual_target_entry_orig = get_annual_target_entry

        def _mock_get_annual_target_entry_repart(year, stab_id, kpi_id):
            if (
                year == test_year_repart
                and stab_id == test_stab_id_repart
                and kpi_id == test_kpi_spec_id_repart
            ):
                return {  # Simulate a sqlite3.Row like dictionary
                    "annual_target1": 1200.0,
                    "annual_target2": 2400.0,
                    "repartition_logic": REPARTITION_LOGIC_MESE,  # Test monthly
                    "repartition_values": json.dumps(
                        {calendar.month_name[i + 1]: (100.0 / 12.0) for i in range(12)}
                    ),  # Evenly
                    "distribution_profile": PROFILE_EVEN,  # Test even distribution within month
                    "profile_params": json.dumps({"events": []}),
                }
            return None

        get_annual_target_entry = _mock_get_annual_target_entry_repart

        # Mock get_kpi_detailed_by_id
        _get_kpi_detailed_by_id_orig = get_kpi_detailed_by_id

        def _mock_get_kpi_detailed_by_id_repart(kpi_id):
            if kpi_id == test_kpi_spec_id_repart:
                return {  # Simulate
                    "calculation_type": CALC_TYPE_INCREMENTALE,
                    "group_name": "TestGrp",
                    "subgroup_name": "TestSubGrp",
                    "indicator_name": "TestKPIName",
                }
            return None

        get_kpi_detailed_by_id = _mock_get_kpi_detailed_by_id_repart

        # Setup minimal schemas for periodic DBs if they are memory/error strings
        temp_db_files_created = []
        periodic_dbs_to_check_setup = {
            "DB_KPI_DAYS": DB_KPI_DAYS,
            "DB_KPI_WEEKS": DB_KPI_WEEKS,
            "DB_KPI_MONTHS": DB_KPI_MONTHS,
            "DB_KPI_QUARTERS": DB_KPI_QUARTERS,
        }
        original_periodic_db_paths = periodic_dbs_to_check_setup.copy()

        for name, path_val in periodic_dbs_to_check_setup.items():
            if path_val.startswith(":memory_") or "error_db" in str(path_val):
                temp_file = f"test_repart_{name.lower()}.sqlite"
                table_sql_name = (
                    name.split("_")[-1].lower() + "_targets"
                )  # daily_targets, etc.
                period_col_name = "date_value"  # Default, adjust if needed per table
                if "WEEKS" in name:
                    period_col_name = "week_value"
                elif "MONTHS" in name:
                    period_col_name = "month_value"
                elif "QUARTERS" in name:
                    period_col_name = "quarter_value"

                with sqlite3.connect(temp_file) as conn_setup:
                    conn_setup.execute(f"DROP TABLE IF EXISTS {table_sql_name};")
                    conn_setup.execute(
                        f"""
                        CREATE TABLE {table_sql_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER, stabilimento_id INTEGER,
                            kpi_id INTEGER, target_number INTEGER, {period_col_name} TEXT, target_value REAL,
                            UNIQUE(year, stabilimento_id, kpi_id, target_number, {period_col_name}));
                    """
                    )
                globals()[name] = temp_file  # Override global DB path for test
                temp_db_files_created.append(temp_file)
                print(f"  Using temp DB '{temp_file}' for {name}")

        try:
            print(
                f"  Running calculate_and_save_all_repartitions for KPI {test_kpi_spec_id_repart}, Target 1..."
            )
            calculate_and_save_all_repartitions(
                test_year_repart, test_stab_id_repart, test_kpi_spec_id_repart, 1
            )

            # Verification (example for monthly)
            with sqlite3.connect(
                globals()["DB_KPI_MONTHS"]
            ) as conn_verify_month:  # Use the potentially overridden global
                cursor = conn_verify_month.execute(
                    "SELECT month_value, target_value FROM monthly_targets WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                    (test_year_repart, test_stab_id_repart, test_kpi_spec_id_repart, 1),
                )
                results = cursor.fetchall()
                assert len(results) == 12, "Should have 12 monthly records"
                for month_name, val in results:
                    assert (
                        abs(val - (1200.0 / 12.0)) < 0.01
                    ), f"Monthly value for {month_name} incorrect: {val}"
                print(
                    f"    SUCCESS: Verified {len(results)} monthly targets, values are as expected (e.g., ~100.0)."
                )

        except Exception as e_test:
            print(f"    ERROR during simplified repartition test: {e_test}")
            print(traceback.format_exc())
        finally:
            # Restore original functions and paths
            get_annual_target_entry = _get_annual_target_entry_orig
            get_kpi_detailed_by_id = _get_kpi_detailed_by_id_orig
            import os

            for name, original_path in original_periodic_db_paths.items():
                current_path = globals()[name]
                if current_path != original_path and os.path.exists(
                    current_path
                ):  # if it was overridden and test file created
                    try:
                        os.remove(current_path)
                        print(f"  Cleaned up temp DB: {current_path}")
                    except OSError:
                        pass
                globals()[name] = original_path  # Restore original path
            print("  Restored original repartition dependencies and DB paths.")
    else:
        print(
            "  Skipping simplified direct test due to missing dependencies (data_retriever, db_core.utils or valid DB paths)."
        )

    print("\n--- Repartition module testing notes complete ---")

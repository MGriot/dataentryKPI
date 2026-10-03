import calendar
import datetime

import numpy as np
import pytest

from src.target_management.repartition import aggregate_periods, compute_daily_values, parse_period_weights

MONTHS = [calendar.month_name[i] for i in range(1, 13)]
LOGICS = [
    ("Year", {}),
    ("Month", {m: w for m, w in zip(MONTHS, [5, 5, 8, 8, 9, 9, 7, 4, 9, 10, 12, 14])}),
    ("Quarter", {"Q1": 10, "Q2": 20, "Q3": 30, "Q4": 40}),
    ("Week", {f"W{i:02d}": (3 if i in (1, 52, 53) else 1) for i in range(1, 54)}),
]
PROFILES = ["even_distribution", "annual_progressive", "annual_progressive_weekday_bias", "true_annual_sinusoidal"]


@pytest.mark.parametrize("year", [2024, 2025, 2026])  # leap year, ISO boundary inside Dec, 53-week year
@pytest.mark.parametrize("logic,values", LOGICS)
@pytest.mark.parametrize("profile", PROFILES)
def test_sum_kpis_add_up_and_never_go_negative(year, logic, values, profile):
    dates, daily = compute_daily_values(year, 120_000, "Sum", logic, values, profile, {})
    assert len(dates) == (366 if calendar.isleap(year) else 365)
    assert daily.sum() == pytest.approx(120_000)
    assert (daily > 0).all(), "every day gets a share (incl. ISO-week boundary days)"


@pytest.mark.parametrize("year", [2024, 2026])
@pytest.mark.parametrize("logic,values", LOGICS)
@pytest.mark.parametrize("calc", ["Average", "Last", "Min", "Max"])
def test_level_kpis_average_to_the_target(year, logic, values, calc):
    _, daily = compute_daily_values(year, 85.0, calc, logic, values, "even_distribution", {})
    assert daily.mean() == pytest.approx(85.0)


def test_month_weights_drive_monthly_totals_and_profile_shapes_days():
    weights = {m: 100 / 12 for m in MONTHS} | {"December": 30}
    dates, daily = compute_daily_values(2026, 1000, "Sum", "Month", weights, "annual_progressive_weekday_bias", {})
    months = aggregate_periods(dates, daily, "Sum")["Month"]
    total_w = sum(weights.values())
    assert months["December"] == pytest.approx(1000 * 30 / total_w)
    assert months["January"] == pytest.approx(1000 * (100 / 12) / total_w)
    # weekday bias inside the month: a Monday gets more than the Sunday before it
    by_date = dict(zip(dates, daily))
    assert by_date[datetime.date(2026, 1, 5)] > by_date[datetime.date(2026, 1, 4)]


def test_quarter_weights_apply_to_average_kpis():
    dates, daily = compute_daily_values(2026, 100.0, "Average", "Quarter", {"Q1": 1, "Q2": 1, "Q3": 1, "Q4": 2}, "even_distribution", {})
    quarters = aggregate_periods(dates, daily, "Average")["Quarter"]
    assert quarters["Q4"] > quarters["Q1"] * 1.9


def test_zero_weight_stays_zero():
    weights = {m: 10 for m in MONTHS} | {"August": 0}
    dates, daily = compute_daily_values(2026, 1100, "Sum", "Month", weights, "even_distribution", {})
    assert aggregate_periods(dates, daily, "Sum")["Month"]["August"] == 0


def test_default_is_even():
    _, daily = compute_daily_values(2026, 365, "Sum")
    assert np.allclose(daily, 1.0)
    _, levels = compute_daily_values(2026, 85, "Average")
    assert np.allclose(levels, 85.0)


def test_week_key_formats():
    assert parse_period_weights("Week", {"W01": 1, "2024-W2": 2, "2024-W03": 3, "w4": 4, "bogus": 9, "W60": 1}) == {1: 1, 2: 2, 3: 3, 4: 4}
    assert parse_period_weights("Month", {"January": 1, "feb": 2, "3": 3}) == {1: 1, 2: 2, 3: 3}
    assert parse_period_weights("Month", {"January": -1, "February": "x"}) == {}


def test_events_are_applied_and_reconciled():
    params = {"events": [{"start_date": "2026-08-01", "end_date": "2026-08-31", "multiplier": 0.0}]}
    dates, daily = compute_daily_values(2026, 1000, "Sum", "Year", {}, "event_based_spikes_or_dips", params)
    months = aggregate_periods(dates, daily, "Sum")["Month"]
    assert months["August"] == 0
    assert daily.sum() == pytest.approx(1000)

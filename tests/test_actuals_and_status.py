# tests/test_actuals_and_status.py
import pytest
from src.services import actuals_service

pytestmark = pytest.mark.usefixtures("db_dir")

def test_actuals_recording_and_retrieval():
    actuals_service.record_actual_measurement(1, 1, "2026-07-01", 100.0)
    actuals_service.record_actual_measurement(1, 1, "2026-07-02", 105.0)

    res = actuals_service.get_actual_measurements(1, 1)
    assert len(res) == 2
    assert res[0]["actual_value"] == 100.0
    assert res[1]["actual_value"] == 105.0

def test_evaluate_performance_status_higher_is_better():
    # Target 100, actual 105 => on_track
    eval1 = actuals_service.evaluate_performance_status(105.0, 100.0, "Higher is Better")
    assert eval1["status"] == "on_track"

    # Target 100, actual 97 => warning (margin 5%)
    eval2 = actuals_service.evaluate_performance_status(97.0, 100.0, "Higher is Better")
    assert eval2["status"] == "warning"

    # Target 100, actual 80 => out_of_range
    eval3 = actuals_service.evaluate_performance_status(80.0, 100.0, "Higher is Better")
    assert eval3["status"] == "out_of_range"

def test_evaluate_performance_status_lower_is_better():
    # Target 100, actual 90 => on_track
    eval1 = actuals_service.evaluate_performance_status(90.0, 100.0, "Lower is Better")
    assert eval1["status"] == "on_track"

    # Target 100, actual 104 => warning
    eval2 = actuals_service.evaluate_performance_status(104.0, 100.0, "Lower is Better")
    assert eval2["status"] == "warning"

    # Target 100, actual 130 => out_of_range
    eval3 = actuals_service.evaluate_performance_status(130.0, 100.0, "Lower is Better")
    assert eval3["status"] == "out_of_range"

def test_trend_slope():
    # Increasing series
    values_up = [10.0, 12.0, 14.0, 16.0, 18.0]
    slope_up = actuals_service.calculate_trend_slope(values_up)
    assert slope_up > 0.0

    # Decreasing series
    values_down = [20.0, 18.0, 16.0, 14.0]
    slope_down = actuals_service.calculate_trend_slope(values_down)
    assert slope_down < 0.0

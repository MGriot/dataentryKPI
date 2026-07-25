# tests/test_rollup_engine.py
import pytest
from src.core import rollup_engine

def test_rollup_sum():
    values = [10.0, 20.0, 30.0]
    assert rollup_engine.rollup_series(values, "Sum") == 60.0

def test_rollup_average():
    values = [10.0, 20.0, 30.0]
    assert rollup_engine.rollup_series(values, "Average") == 20.0

def test_rollup_last():
    values = [10.0, 20.0, 30.0]
    assert rollup_engine.rollup_series(values, "Last") == 30.0

def test_rollup_min_max():
    values = [5.0, 100.0, 2.0, 42.0]
    assert rollup_engine.rollup_series(values, "Min") == 2.0
    assert rollup_engine.rollup_series(values, "Max") == 100.0

def test_rollup_count():
    values = [5.0, 100.0, 2.0, 42.0]
    assert rollup_engine.rollup_series(values, "Count") == 4.0

def test_rollup_none_and_empty():
    assert rollup_engine.rollup_series([], "Sum") is None
    assert rollup_engine.rollup_series([None, None], "Average") is None

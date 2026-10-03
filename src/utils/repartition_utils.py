"""Curve helpers shared by the repartition engine and the split-template weight suggestions."""
import calendar
import datetime

import numpy as np


def ramp_proportions(num_periods: int, start: float = 0.8, end: float = 1.2) -> list:
    """Linear ramp from `start` to `end` (relative weights), normalized to sum to 1."""
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]
    weights = np.linspace(start, end, num_periods)
    return (weights / weights.sum()).tolist()


def sinusoidal_proportions(num_periods: int, amplitude: float = 0.1, phase: float = 0.0) -> list:
    """One full sine cycle around 1.0 (+/- amplitude), normalized to sum to 1."""
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False)
    weights = np.clip(1.0 + amplitude * np.sin(x + phase), 1e-9, None)
    return (weights / weights.sum()).tolist()


def weekday_weights(dates, weekday_weight: float = 1.3, weekend_weight: float = 0.7) -> np.ndarray:
    """Per-day relative weights favouring Mon-Fri. Falls back to flat weights if both are <= 0."""
    weekday_weight, weekend_weight = max(float(weekday_weight), 0.0), max(float(weekend_weight), 0.0)
    if weekday_weight == 0 and weekend_weight == 0:
        weekday_weight = weekend_weight = 1.0
    return np.array([weekend_weight if d.weekday() >= 5 else weekday_weight for d in dates], dtype=float)


def quarter_of(date: datetime.date) -> int:
    return (date.month - 1) // 3 + 1


def days_of_year(year: int) -> list:
    start = datetime.date(year, 1, 1)
    return [start + datetime.timedelta(days=i) for i in range(366 if calendar.isleap(year) else 365)]


def iso_week_label(date: datetime.date) -> str:
    iso = date.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"

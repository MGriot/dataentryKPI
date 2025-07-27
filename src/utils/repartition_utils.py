import numpy as np
import datetime
import calendar

def get_weighted_proportions(num_periods, initial_factor=1.5, final_factor=0.5, decreasing=True):
    """
    Generates a list of proportions that are weighted, either increasing or decreasing.
    The sum of proportions is 1.
    """
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]

    if decreasing:
        weights = np.linspace(initial_factor, final_factor, num_periods)
    else:
        weights = np.linspace(final_factor, initial_factor, num_periods)

    normalized_weights = weights / np.sum(weights)
    return normalized_weights.tolist()

def get_parabolic_proportions(num_periods, peak_at_center=True, min_value_epsilon=1e-9):
    """
    Generates proportions following a parabolic curve. Sum of proportions is 1.
    """
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]

    x = np.linspace(-1, 1, num_periods)
    if peak_at_center:
        y = 1 - x**2
    else:
        y = x**2

    # Ensure no negative values and normalize
    y[y < min_value_epsilon] = min_value_epsilon
    normalized_y = y / np.sum(y)
    return normalized_y.tolist()

def get_sinusoidal_proportions(num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9):
    """
    Generates proportions following a sinusoidal curve. Sum of proportions is 1.
    Amplitude is a fraction of the mean (e.g., 0.5 means +/- 50% of mean).
    """
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]

    # Base sine wave from 0 to 2*pi
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False)
    # Shift and scale to ensure values are positive and sum to 1
    # Mean value will be 1/num_periods, so sine wave modulates around it
    # The amplitude is relative to the mean value for distribution
    mean_prop = 1.0 / num_periods
    
    # Create a sine wave that modulates around 1.0, then scale by mean_prop
    # The sine wave itself should range from (1-amplitude) to (1+amplitude)
    # So, 1 + amplitude * sin(x + phase_offset)
    raw_proportions = mean_prop * (1 + amplitude * np.sin(x + phase_offset))

    # Ensure no values are too small or negative due to large amplitude
    raw_proportions[raw_proportions < min_value_epsilon] = min_value_epsilon

    normalized_proportions = raw_proportions / np.sum(raw_proportions)
    return normalized_proportions.tolist()

def get_date_ranges_for_quarters(year):
    """
    Returns a dictionary of quarter names (Q1, Q2, Q3, Q4) to tuples of (start_date, end_date).
    """
    quarter_ranges = {}
    for q in range(1, 5):
        if q == 1:
            start_month, end_month = 1, 3
        elif q == 2:
            start_month, end_month = 4, 6
        elif q == 3:
            start_month, end_month = 7, 9
        else: # q == 4
            start_month, end_month = 10, 12
        
        start_date = datetime.date(year, start_month, 1)
        end_date = datetime.date(year, end_month, calendar.monthrange(year, end_month)[1])
        quarter_ranges[q] = (start_date, end_date)
    return quarter_ranges

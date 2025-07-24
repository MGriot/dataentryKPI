# Target Generation and Distribution

## Mathematical Models Overview

The system implements sophisticated mathematical models for distributing KPI targets across different time periods. Each model is designed to handle specific business scenarios and temporal patterns.

## Distribution Profiles

### 1. Even Distribution (PROFILE_EVEN)
The simplest distribution model that splits targets equally:

```python
w_i = 1/n  # where n is number of periods
```

**Use Cases:**
- Stable metrics without seasonal variation
- Base reference distributions
- Initial target benchmarking

### 2. Annual Progressive (PROFILE_ANNUAL_PROGRESSIVE)
Implements linear progression throughout the year:

```python
# For period i in [1..n]:
f_i = initial + (final - initial)(i-1)/(n-1)
w_i = f_i / Σf_j  # where j goes from 1 to n
```

**Parameters:**
- `initial`: Starting weight (WEIGHT_INITIAL_FACTOR_INC/AVG)
- `final`: Ending weight (WEIGHT_FINAL_FACTOR_INC/AVG)

**Use Cases:**
- Growth-based targets
- Ramp-up scenarios
- Learning curve adjustments

### 3. Sinusoidal Distribution (PROFILE_TRUE_ANNUAL_SINUSOIDAL)
Models seasonal patterns:

```python
# For period i in [1..n]:
w_i = (1 + A·sin(2π(i-1)/n + φ)) / Σ(1 + A·sin(2π(j-1)/n + φ))
```

**Parameters:**
- `A`: Amplitude (SINE_AMPLITUDE_INCREMENTAL/MEDIA)
- `φ`: Phase offset (SINE_PHASE_OFFSET)

**Use Cases:**
- Seasonal business cycles
- Temperature-dependent metrics
- Recurring patterns
- **Repartition Logic**: Determines the granularity (year, quarter, month, week) and allows for custom weights per period.

---

## Mathematical Profiles and Equations

### 1. Linear/Progressive Distribution

**Equation:**

For $n$ periods, the weight for period $i$ ($i=1,...,n$):

$$
w_i = \frac{f_i}{\sum_{j=1}^n f_j}
$$

where $f_i$ is linearly interpolated between `initial_factor` and `final_factor`:

$$
f_i = \text{initial\_factor} + \frac{(\text{final\_factor} - \text{initial\_factor}) \cdot (i-1)}{n-1}
$$

- **Progressive**: `initial_factor < final_factor` (e.g., 0.5 to 1.5)
- **Regressive**: `initial_factor > final_factor`

**Example (Progressive, 12 months):**

- Jan: $f_1 = 0.5$
- Dec: $f_{12} = 1.5$

**ASCII Chart:**

```
Jan  |*
Feb  |**
Mar  |***
...  ...
Dec  |**************
```

### 2. Parabolic Distribution

**Equation:**

For $n$ periods, centered peak:

$$
w_i = \frac{-(i - c)^2 + c^2 + \epsilon}{\sum_{j=1}^n (-(j - c)^2 + c^2 + \epsilon)}
$$

where $c = \frac{n-1}{2}$ (center), $\epsilon$ is a small positive value to avoid zeros.

- **Peak at center**: Highest in the middle (e.g., summer months)
- **Peak at edges**: Invert the formula

**ASCII Chart (center peak):**

```
Jan  |*
Feb  |**
Mar  |****
Jun  |********
Jul  |********
Dec  |*
```

### 3. Sinusoidal Distribution

**Equation:**

For $n$ periods:

$$
w_i = \frac{1 + A \cdot \sin\left(2\pi \frac{i-1}{n} + \phi\right)}{\sum_{j=1}^n [1 + A \cdot \sin(2\pi \frac{j-1}{n} + \phi)]}
$$

- $A$ = amplitude (0 to 1)
- $\phi$ = phase offset (e.g., $-\pi/2$ to start at minimum)

**Use case:** Seasonality (e.g., higher in summer/winter).

**ASCII Chart (amplitude=0.5):**

```
Jan  |*
Feb  |**
Mar  |****
Jun  |********
Sep  |****
Dec  |*
```

### 4. Even Distribution

**Equation:**

$$
w_i = \frac{1}{n}
$$

**ASCII Chart:**

```
Jan  |****
Feb  |****
...
Dec  |****
```

### 5. Custom/User-defined Weights

User enters explicit weights for each period (e.g., each month must sum to 100%).

---

## Distribution Process

1. **User enters annual target** $T$.
2. **Selects profile** (progressive, sinusoidal, etc.) and repartition logic (month, quarter, etc.).
3. **System computes weights** $w_i$ for each period.
4. **Period value:** $v_i = T \cdot w_i$
5. **Values are saved** in the database for each period.

---

## Example: Monthly Progressive Distribution

Suppose the annual target is $T = 1200$, and the user selects a progressive profile for months:

- $n = 12$, `initial_factor = 0.5`, `final_factor = 1.5`
- Compute $f_i$ for each month, normalize to get $w_i$
- Each month's value: $v_i = 1200 \cdot w_i$

---

## Visual Comparison

| Profile      | Chart (12 periods)         | Description                       |
|--------------|---------------------------|-----------------------------------|
| Even         | ▇▇▇▇▇▇▇▇▇▇▇▇             | Flat, equal for all periods       |
| Progressive  | ▂▃▄▅▆▇███▇▆▅▃            | Increasing over time              |
| Parabolic    | ▂▄▆██▇▇██▆▄▂             | Peak in the middle                |
| Sinusoidal   | ▃▅▇▇▆▅▃▂▃▅▇▇             | Wave, seasonal effect             |

---

## Advanced: Event-based Adjustments

- **Event-based profiles** allow for spikes/dips on specific dates.
- User provides a list of events (date ranges, multipliers/additions).
- The system applies these adjustments to the daily values before aggregation.

---

## Main Functions

### 1. `get_weighted_proportions(...)`

Generates a list of weights for periods (e.g., months) based on linear interpolation between an initial and final factor. Used for progressive or regressive distributions.

- **Parameters**:  
  - `num_periods`: Number of periods (e.g., 12 for months)
  - `initial_factor`, `final_factor`: Start/end weight
  - `decreasing`: Direction of progression

- **Returns**:  
  Normalized weights summing to 1.

### 2. `get_parabolic_proportions(...)`

Creates a parabolic distribution, peaking at the center or edges.

- **Parameters**:  
  - `num_periods`: Number of periods
  - `peak_at_center`: If True, peak in the middle

- **Returns**:  
  Normalized weights.

### 3. `get_sinusoidal_proportions(...)`

Generates a sinusoidal (wave-like) distribution, useful for seasonality.

- **Parameters**:  
  - `num_periods`: Number of periods
  - `amplitude`, `phase_offset`: Shape and phase of the wave

- **Returns**:  
  Normalized weights.

### 4. `save_annual_targets(...)`

- **Purpose**:  
  Saves annual targets and triggers automatic repartition into all lower periods (quarters, months, weeks, days).

- **Logic**:
    1. **Store annual value** in the database.
    2. **Determine distribution profile** and repartition logic (from user or default).
    3. **Compute weights** for each period using the selected profile.
    4. **Multiply annual target by weights** to get period values.
    5. **Save distributed values** into the corresponding period tables.

### 5. `_get_period_allocations(...)` and `_get_raw_daily_values_for_repartition(...)`

- **Purpose**:  
  Internal helpers to compute the actual values for each period, applying the chosen profile and any user overrides.

- **Details**:
    - Handles edge cases (e.g., leap years, custom user weights).
    - Supports event-based adjustments (e.g., spikes/dips for specific dates).

### 6. `_aggregate_and_save_periodic_targets(...)`

- **Purpose**:  
  Aggregates daily values into weeks, months, quarters, and saves them.

---

## Customization

- **Add new profiles**: Implement a new function (e.g., `get_custom_profile_proportions`) and integrate it into the profile selection logic.
- **User-defined weights**: The UI allows manual entry of weights per period, which override automatic profiles.

---

## References

- See `src/database_manager.py` for implementation details.
- [Architecture Overview](architecture.md)

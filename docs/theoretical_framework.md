# Theoretical Framework

## Target Distribution Mathematics

### 1. Basic Distribution Models

#### 1.1 Even Distribution
The most basic distribution model assumes uniform distribution across periods:

```
w_i = 1/n, for all i in [1..n]
```

where:
- w_i is the weight for period i
- n is the total number of periods

Properties:
- Σw_i = 1
- All weights are equal
- No temporal variation

#### 1.2 Linear Progressive Distribution
Implements a linear progression with configurable start and end weights:

```
f_i = a + (b-a)(i-1)/(n-1)
w_i = f_i / Σf_j
```

where:
- a is the initial factor (WEIGHT_INITIAL_FACTOR)
- b is the final factor (WEIGHT_FINAL_FACTOR)
- i is the period index [1..n]

Properties:
- Σw_i = 1 (normalized)
- Monotonic increase/decrease
- Linear progression

### 2. Advanced Distribution Models

#### 2.1 Sinusoidal Distribution
Models cyclical patterns using sine waves:

```
raw_i = 1 + A·sin(2π(i-1)/n + φ)
w_i = raw_i / Σraw_j
```

where:
- A is the amplitude (0 < A < 1)
- φ is the phase offset
- n is the number of periods

Properties:
- Σw_i = 1 (normalized)
- Cyclical variation
- Smooth transitions

#### 2.2 Weekly Bias Adjustment
Incorporates day-of-week effects:

```
base_i = progressive_weight(i)
w_i = base_i * (1 + B·d_i)
w_i_normalized = w_i / Σw_j
```

where:
- B is the bias factor (WEEKDAY_BIAS_FACTOR)
- d_i is the day-of-week modifier [-1..1]

### 3. Hierarchical Distribution

#### 3.1 Period Hierarchies
The system supports nested time periods:

```
Year
└── Quarters (4)
    └── Months (3)
        └── Weeks (~13)
            └── Days (7)
```

Distribution flows down the hierarchy with normalization at each level:

```
annual_target * quarter_weight = quarter_target
quarter_target * month_weight = month_target
...etc.
```

#### 3.2 Weight Propagation
For nested periods:

```
w_ij = w_i * w_j
```

where:
- w_i is parent period weight
- w_j is child period weight
- w_ij is combined weight

### 4. Advanced Concepts

#### 4.1 Formula-Based Targets
Supports dynamic target calculation:

```python
target = eval(formula, context)
```

with safety constraints:
- Limited mathematical operations
- Validated variable references
- Error bounds checking

#### 4.2 Master/Sub KPI Distribution
For hierarchical KPIs:

```
sub_target = master_target * sub_weight
Σsub_weights = 1
```

Properties:
- Conservation of totals
- Weight-based distribution
- Optional manual override

## Implementation Notes

### 1. Numerical Stability

The system implements several safeguards:

1. **Normalization**
   ```python
   def normalize(weights):
       total = sum(weights)
       return [w/total for w in weights]
   ```

2. **Boundary Checks**
   ```python
   assert all(0 <= w <= 1 for w in weights)
   assert abs(sum(weights) - 1.0) < epsilon
   ```

3. **Error Handling**
   - Division by zero protection
   - Overflow prevention
   - NaN checks

### 2. Performance Considerations

1. **Caching**
   - Precomputed weights
   - Cached intermediate results
   - Lazy recalculation

2. **Batch Operations**
   - Vectorized calculations
   - Bulk database updates
   - Transaction management

### 3. Extensibility

The system is designed for easy addition of new distribution models:

1. **New Profile Template**
   ```python
   def new_profile(params):
       def weight_function(i, n):
           # Calculate weight for period i of n
           return weight
       return weight_function
   ```

2. **Profile Registration**
   ```python
   PROFILES = {
       'EVEN': even_distribution,
       'PROGRESSIVE': progressive_distribution,
       # Add new profiles here
   }
   ```

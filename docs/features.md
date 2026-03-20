# Core Features & Logic

This section details the sophisticated algorithms powering the Data Entry KPI system.

## 1. Dynamic Target Distribution

The system solves the problem of breaking down a single Annual Target into granular periodic values (Daily, Weekly, Monthly, Quarterly).

### The "On-the-Fly" Engine
Unlike static systems that compute values once, our engine evaluates targets dynamically:
1.  **Dependency Resolution**: When a calculation runs, the system builds a dependency graph of all KPIs.
2.  **Topological Sort**: KPIs are processed in an order that ensures a "Parent" or "Input" KPI is always calculated before its dependents.
3.  **Daily Evaluation**: For formula-based KPIs, the formula is evaluated **for every single day of the year**.
    *   *Example*: If `KPI_C = KPI_A + KPI_B`, and `KPI_A` is seasonal (high in summer) while `KPI_B` is flat, `KPI_C` will automatically inherit the correct hybrid seasonality.

### Reconciliation
After daily values are generated, a reconciliation step ensures mathematical precision:
- **Sum Check**: For `Incremental` KPIs, the sum of all days must exactly equal the Annual Target.
- **Mean Check**: For `Average` KPIs, the mean of all days must match the Annual Target.
- **Adjustment**: Any floating-point rounding errors (e.g., $0.0000001 difference) are distributed evenly across the period to guarantee data integrity.

## 2. Formulas & Node Graph

### Dual Representation
Formulas can be defined in two ways:
1.  **String-Based**: A Python-like syntax (e.g., `[101] * 1.5 + [102]`). Simple and fast for power users.
2.  **DAG-Based (JSON)**: A Directed Acyclic Graph structure stored as JSON. This powers the "Visual Node Editor," allowing users to drag-and-drop connections between KPIs.

### Safety
The formula engine uses a restricted `eval` context or a custom graph traverser (`src/core/node_engine.py`) to prevent unsafe code execution while supporting mathematical functions like `min`, `max`, `abs`, and `pow`.

## 3. Multivariate Seasonality Prediction

The "Global Splits" feature includes a machine-learning component for predictive modeling.

### The Problem
Determining the correct monthly weight (e.g., "How much of our annual sales happen in January?") is often guesswork.

### The Solution: OLS Regression
The system allows users to upload historical data and "Driver" variables (independent variables).
1.  **Normalization**: All input data is normalized to a 0-1 scale to allow comparison of disparate units (e.g., Temperature vs. Sales).
2.  **Regression**: An Ordinary Least Squares (OLS) regression model fits the Drivers to the Historical Target.
3.  **Coefficient Extraction**: The model reveals which drivers have the most influence (positive or negative).
4.  **Prediction**: The model generates a "Best Fit" curve for the target year, which is converted into percentage weights for the split template.

# Core Features & Logic

This section details the sophisticated algorithms powering the Data Entry KPI system.

## 1. Dynamic Target Distribution

The system solves the problem of breaking down a single Annual Target into granular periodic values (Daily, Weekly, Monthly, Quarterly).

### Reconciliation
After daily values are generated based on the selected distribution profile, a reconciliation step ensures mathematical precision:
- **Sum Check**: For `Incremental` KPIs, the sum of all days must exactly equal the Annual Target.
- **Mean Check**: For `Average` KPIs, the mean of all days must match the Annual Target.
- **Adjustment**: Any floating-point rounding errors (e.g., $0.0000001 difference) are distributed evenly across the period to guarantee data integrity.

## 2. Multivariate Seasonality Prediction

The "Global Splits" feature includes a machine-learning component for predictive modeling.

### The Problem
Determining the correct monthly weight (e.g., "How much of our annual sales happen in January?") is often guesswork.

### The Solution: OLS Regression
The system allows users to upload historical data and "Driver" variables (independent variables).
1.  **Normalization**: All input data is normalized to a 0-1 scale to allow comparison of disparate units (e.g., Temperature vs. Sales).
2.  **Regression**: An Ordinary Least Squares (OLS) regression model fits the Drivers to the Historical Target.
3.  **Coefficient Extraction**: The model reveals which drivers have the most influence (positive or negative).
4.  **Prediction**: The model generates a "Best Fit" curve for the target year, which is converted into percentage weights for the split template.

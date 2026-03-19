# Plan: Advanced Multivariate Prediction

## Objective
Upgrade the seasonal analysis feature to support true multivariate prediction. The user wants to use multiple input variables (historical years + external drivers) to predict multiple output variables (future seasonal weights for target KPIs).

## Mathematical Approach (ML Details)
Since `scikit-learn` is unavailable, we will implement a **Multiple Linear Regression (MLR)** model using `numpy.linalg.lstsq`.

**The Model:**
$$Y = X\beta + \epsilon$$

*   **X (Features):** Matrix where each row is a time period (e.g., Month 1, Month 2...) and columns are:
    *   Historical Target Averages (e.g., avg of 2022, 2023)
    *   External Drivers (e.g., Temperature, Economic Index)
    *   (Optional) Lagged variables for auto-regression
*   **Y (Targets):** The seasonal weights we want to predict. Since we don't have "future truth" to train on in a standard supervised way, we will use a **"Hindcast" Training Strategy**:
    *   **Training:** Train the model to predict *Total Volume* or *Target Value* for past periods based on the drivers.
    *   **Prediction:** Use the trained coefficients $\beta$ to predict values for the *next* cycle (e.g., next 12 months).
    *   **Normalization:** Convert the predicted absolute values into seasonal percentages (sum = 100%).

## Implementation Steps

### 1. Service Layer (`src/services/split_analyzer.py`)
*   **Refactor `analyze_seasonality_from_file`:**
    *   Accept `target_cols` (History) and `feature_cols` (Drivers).
    *   Implement `train_predict_model(df, targets, features)`:
        1.  Prepare `X` matrix (features + intercept).
        2.  Prepare `y` vector (historical target sum).
        3.  Fit $\beta$ using `np.linalg.lstsq(X, y, rcond=None)[0]`.
        4.  Predict `y_pred` using the same `X` (assuming drivers effectively represent the "seasonal shape").
        5.  *Self-Correction:* If drivers are provided for future dates (e.g., forecast weather), we could use those. For now, we assume the relationship between drivers and seasonality holds constant.
*   **Output:** Return dictionary of weights `{ "1": 0.05, "2": 0.10 ... }`.
*   **Metadata:** Return "Model Details" string explaining the coefficients (Driver Influence).

### 2. UI Updates (`AdvancedSplitDialog`)
*   **Inputs:**
    *   Existing Multi-select for "Historical Targets" (Input Y).
    *   Existing Multi-select for "Features" (Input X).
*   **Outputs:**
    *   Display "Prediction Details":
        *   "Model Used: Multiple Linear Regression (OLS)"
        *   "Driver Importance": Show coefficients for each feature to explain *why* the split is shaped that way.
        *   "R² Score": A simple metric to show how well the drivers explain the historical variance.

### 3. Verification
*   Update `test_multivariate_analysis.py` to use the new regression logic and print the "Model Details".

## ML Explanation for User
The tool will explicitly state:
"We use **Multiple Linear Regression (Ordinary Least Squares)** to find the mathematical relationship between your drivers (Features) and your historical volume (Targets). The resulting 'weights' are predicted based on this learned relationship."

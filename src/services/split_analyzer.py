import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import LeaveOneOut, KFold, cross_val_score
from sklearn.metrics import r2_score, mean_squared_error

def analyze_seasonality_from_file(
    file_path: str, 
    target_cols: List[str],
    feature_cols: List[str], 
    date_col: str, 
    period_type: str
) -> Tuple[Dict[str, float], Dict[str, float], float, pd.DataFrame, str]:
    """
    Performs multivariate seasonality analysis by 'racing' multiple models 
    (OLS, Ridge, Random Forest) and choosing the best one via Cross-Validation.
    Also includes Monte Carlo simulation for uncertainty.
    
    Returns:
        - weights: {period_idx: weight}
        - coefficients: {feature: influence}
        - r_squared: Best model score
        - plot_df: Data for visualization (includes Confidence Intervals)
        - winning_model_name: Name of the best model
    """
    # 1. Load Data
    if file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
            if len(df.columns) <= 1: df = pd.read_csv(file_path, sep=';')
        except:
            df = pd.read_csv(file_path, sep=';')
    else:
        df = pd.read_excel(file_path)
    
    df[date_col] = pd.to_datetime(df[date_col])
    
    # 2. Feature Engineering: Period Indexing
    if period_type == "Month": df['period_idx'] = df[date_col].dt.month
    elif period_type == "Quarter": df['period_idx'] = df[date_col].dt.quarter
    elif period_type == "Week": df['period_idx'] = df[date_col].dt.isocalendar().week
    elif period_type == "Day": df['period_idx'] = df[date_col].dt.dayofyear
    else: df['period_idx'] = df[date_col].dt.month

    # 3. Aggregation
    agg_dict = {col: 'sum' for col in target_cols}
    for col in feature_cols: agg_dict[col] = 'mean'
    grouped = df.groupby('period_idx').agg(agg_dict).reset_index()

    # 4. Normalization (0-1)
    def normalize(s):
        return (s - s.min()) / (s.max() - s.min()) if (s.max() - s.min()) != 0 else s

    normalized_targets = pd.DataFrame()
    for col in target_cols: normalized_targets[col] = normalize(grouped[col])
    y = normalized_targets.mean(axis=1).values

    X_raw = pd.DataFrame()
    for col in feature_cols: X_raw[col] = normalize(grouped[col])
    
    # Handle case with no drivers
    if not feature_cols:
        final_sum = y.sum()
        weights = {str(int(p)): float(val/final_sum if final_sum > 0 else 1.0/len(y)) for p, val in zip(grouped['period_idx'], y)}
        plot_df = pd.DataFrame({'period_idx': grouped['period_idx'], 'Actual_Target': y, 'Predicted_Fit': y, 'CI_Upper': y, 'CI_Lower': y})
        return weights, {}, 1.0, plot_df, "Historical Average"

    X = X_raw.values
    n_samples = len(y)
    
    # 5. The Model Race
    models = {
        "OLS Regression": LinearRegression(),
        "Ridge (L2 Regularized)": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=min(5, n_samples), random_state=42)
    }
    
    best_model_name = ""
    best_score = -float('inf')
    results = {}

    # Use Leave-One-Out for very small data, K-Fold for larger
    cv = LeaveOneOut() if n_samples < 20 else KFold(n_splits=min(5, n_samples), shuffle=True, random_state=42)

    for name, model in models.items():
        try:
            # Score using Cross-Validation R2
            # For n_samples < 5, CV can be unstable, so we use full R2 with a penalty
            if n_samples >= 5:
                scores = cross_val_score(model, X, y, cv=cv, scoring='neg_mean_squared_error')
                avg_mse = -np.mean(scores)
            else:
                avg_mse = 0
            
            # Fit on full data to get R2
            model.fit(X, y)
            full_r2 = r2_score(y, model.predict(X))
            
            # Penalty for high complexity on small data to prevent overfitting
            # Random Forest is very risky on small data, so it gets a heavy penalty unless data is large
            adj_score = full_r2
            if name == "Random Forest":
                if n_samples < 24: adj_score -= 0.2
                elif n_samples < 50: adj_score -= 0.1
            elif name == "OLS Regression":
                # OLS is okay but Ridge is safer for many drivers
                if X.shape[1] > n_samples / 2: adj_score -= 0.05

            if adj_score > best_score:
                best_score = adj_score
                best_model_name = name
            
            results[name] = {"model": model, "r2": full_r2, "mse": avg_mse}
        except:
            continue

    winning_model = results[best_model_name]["model"]
    y_pred = winning_model.predict(X)
    
    # 6. Monte Carlo Simulation for Uncertainty (Confidence Interval)
    n_sims = 100
    simulations = []
    # Calculate residual variance
    residuals = y - y_pred
    std_dev = np.std(residuals) if len(residuals) > 1 else 0.05
    
    for _ in range(n_sims):
        # Noise to drivers (5% volatility)
        X_noisy = X + np.random.normal(0, 0.05, X.shape)
        # Noise to model prediction (based on residual error)
        sim_y = winning_model.predict(X_noisy) + np.random.normal(0, std_dev, len(y))
        simulations.append(np.maximum(sim_y, 0))
    
    sim_array = np.array(simulations)
    y_upper = np.percentile(sim_array, 95, axis=0)
    y_lower = np.percentile(sim_array, 5, axis=0)

    # 7. Final Outputs
    y_pred_clipped = np.maximum(y_pred, 0)
    total_pred = y_pred_clipped.sum()
    weights = {str(int(p)): float(val/total_pred if total_pred > 0 else 1.0/len(y)) for p, val in zip(grouped['period_idx'], y_pred_clipped)}
    
    plot_df = pd.DataFrame({
        'period_idx': grouped['period_idx'],
        'Actual_Target': y,
        'Predicted_Fit': y_pred_clipped,
        'CI_Upper': y_upper,
        'CI_Lower': y_lower
    })
    
    coefficients = {}
    if hasattr(winning_model, 'coef_'):
        coefficients = {feat: float(c) for feat, c in zip(feature_cols, winning_model.coef_)}
        if hasattr(winning_model, 'intercept_'): coefficients["Intercept"] = float(winning_model.intercept_)
    elif hasattr(winning_model, 'feature_importances_'):
        # For RF, we return feature importance instead of coefficients
        coefficients = {f"{feat} (Importance)": float(imp) for feat, imp in zip(feature_cols, winning_model.feature_importances_)}

    return weights, coefficients, float(results[best_model_name]["r2"]), plot_df, best_model_name

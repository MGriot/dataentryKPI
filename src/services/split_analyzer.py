# src/services/split_analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

def analyze_seasonality_from_file(
    file_path: str, 
    target_cols: List[str],
    feature_cols: List[str], 
    date_col: str, 
    period_type: str
) -> Tuple[Dict[str, float], Dict[str, float], float, pd.DataFrame]:
    """
    Performs multivariate seasonality analysis using Multiple Linear Regression (OLS).
    """
    # Load data
    if file_path.endswith('.csv'):
        # Try different separators
        try:
            df = pd.read_csv(file_path)
            # Simple check if it actually parsed columns
            if len(df.columns) <= 1:
                df = pd.read_csv(file_path, sep=';')
        except:
            df = pd.read_csv(file_path, sep=';')
    else:
        df = pd.read_excel(file_path)
    
    # Ensure date column is datetime
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Create period bucket
    if period_type == "Month":
        df['period_idx'] = df[date_col].dt.month
    elif period_type == "Quarter":
        df['period_idx'] = df[date_col].dt.quarter
    elif period_type == "Week":
        df['period_idx'] = df[date_col].dt.isocalendar().week
    elif period_type == "Day":
        df['period_idx'] = df[date_col].dt.dayofyear
    else:
        df['period_idx'] = df[date_col].dt.month

    # Group by period
    agg_dict = {}
    for col in target_cols: agg_dict[col] = 'sum'
    for col in feature_cols: agg_dict[col] = 'mean'
        
    grouped = df.groupby('period_idx').agg(agg_dict).reset_index()

    # Prepare Y (Target): Average of normalized historical targets
    def normalize(s):
        return (s - s.min()) / (s.max() - s.min()) if (s.max() - s.min()) != 0 else s

    normalized_targets = pd.DataFrame()
    for col in target_cols:
        normalized_targets[col] = normalize(grouped[col])
    
    y = normalized_targets.mean(axis=1).values

    # Start building plot_df
    plot_df = pd.DataFrame({'period_idx': grouped['period_idx'], 'Actual_Target': y})

    # Prepare X (Features): Drivers + Intercept
    X_raw = pd.DataFrame()
    for col in feature_cols:
        norm_feat = normalize(grouped[col])
        X_raw[col] = norm_feat
        plot_df[f"Driver_{col}"] = norm_feat
    
    # Base case: No features -> Use historical average directly
    if not feature_cols:
        final_sum = y.sum()
        if final_sum == 0: 
            weights = {str(int(p)): 1.0/len(grouped) for p in grouped['period_idx']}
        else:
            weights = {str(int(p)): float(val/final_sum) for p, val in zip(grouped['period_idx'], y)}
        plot_df['Predicted_Fit'] = y
        return weights, {}, 1.0, plot_df

    # Add intercept column
    X = np.c_[np.ones(X_raw.shape[0]), X_raw.values] 

    # Fit OLS Model: y = X*beta
    beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

    # Predict
    y_pred = X @ beta
    plot_df['Predicted_Fit'] = y_pred
    
    # Ensure non-negative predictions for seasonality weights
    y_pred_clipped = np.maximum(y_pred, 0)

    # Normalize prediction to sum to 1.0
    total_pred = y_pred_clipped.sum()
    if total_pred == 0:
        final_weights = {str(int(p)): 1.0/len(grouped) for p in grouped['period_idx']}
    else:
        final_weights = {str(int(p)): float(val/total_pred) for p, val in zip(grouped['period_idx'], y_pred_clipped)}

    # Calculate Metrics
    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    coefficients = {"Intercept": float(beta[0])}
    for idx, col in enumerate(feature_cols):
        coefficients[col] = float(beta[idx+1])

    return final_weights, coefficients, float(r_squared), plot_df

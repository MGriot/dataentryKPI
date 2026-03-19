# src/services/split_analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

def analyze_seasonality_from_file(
    file_path: str, 
    target_col: str, 
    feature_cols: List[str], 
    date_col: str, 
    period_type: str
) -> Dict[str, float]:
    """
    Performs multivariate seasonality analysis.
    Uses a weighted correlation approach:
    1. Aggregates target and features by the chosen Period.
    2. Calculates weights for the target based on its own history.
    3. If features are provided, it performs a simple linear combination 
       weighted by the absolute correlation of each feature to the target.
    """
    # Load data
    df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
    
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
        df['period_idx'] = df[date_col].dt.dayofyear # Or date for specific year
    else:
        df['period_idx'] = df[date_col].dt.month # Fallback

    # Group by period and sum/mean
    # Target uses SUM (to see total volume per period)
    # Features use MEAN (to see average intensity/trend per period)
    agg_dict = {target_col: 'sum'}
    for col in feature_cols:
        agg_dict[col] = 'mean'
        
    grouped = df.groupby('period_idx').agg(agg_dict).reset_index()

    if not feature_cols:
        # Simple univariate analysis
        total = grouped[target_col].sum()
        if total == 0: return {str(p): 1.0/len(grouped) for p in grouped['period_idx']}
        weights = grouped.set_index('period_idx')[target_col] / total
        return {str(p): float(w) for p, w in weights.items()}

    # Multivariate Logic:
    # 1. Normalize columns to 0-1 scale to compare different units
    def normalize(s):
        return (s - s.min()) / (s.max() - s.min()) if (s.max() - s.min()) != 0 else s

    normalized_df = grouped.copy()
    normalized_df[target_col] = normalize(grouped[target_col])
    for col in feature_cols:
        normalized_df[col] = normalize(grouped[col])

    # 2. Calculate correlations to see which feature matters most
    correlations = {}
    for col in feature_cols:
        # Simple Pearson correlation
        corr = grouped[target_col].corr(grouped[col])
        correlations[col] = abs(corr) if not np.isnan(corr) else 0.0

    total_corr = sum(correlations.values())
    
    # 3. Combine target seasonality with feature-driven trends
    # Weight: 60% historical target trend, 40% correlated features trend
    base_seasonality = normalize(grouped[target_col])
    
    feature_seasonality = pd.Series(0.0, index=grouped.index)
    if total_corr > 0:
        for col in feature_cols:
            weight = correlations[col] / total_corr
            feature_seasonality += normalized_df[col] * weight
    else:
        feature_seasonality = base_seasonality

    combined = (base_seasonality * 0.6) + (feature_seasonality * 0.4)
    
    # Final Normalization to ensure sum = 1.0
    final_sum = combined.sum()
    if final_sum == 0: 
        return {str(p): 1.0/len(grouped) for p in grouped['period_idx']}
    
    final_weights = combined / final_sum
    
    # Map back to period labels
    result = {}
    for i, row in grouped.iterrows():
        result[str(int(row['period_idx']))] = float(final_weights[i])
        
    return result

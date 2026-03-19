# src/services/split_analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

def analyze_seasonality_from_file(
    file_path: str, 
    target_cols: List[str], # Changed to List
    feature_cols: List[str], 
    date_col: str, 
    period_type: str
) -> Dict[str, float]:
    """
    Performs multivariate seasonality analysis.
    Uses a weighted correlation approach:
    1. Aggregates target(s) and features by the chosen Period.
    2. Calculates baseline weights by averaging all provided Target Columns.
    3. Refines the baseline using correlated features.
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
        df['period_idx'] = df[date_col].dt.dayofyear
    else:
        df['period_idx'] = df[date_col].dt.month

    # Group by period
    agg_dict = {}
    for col in target_cols: agg_dict[col] = 'sum'
    for col in feature_cols: agg_dict[col] = 'mean'
        
    grouped = df.groupby('period_idx').agg(agg_dict).reset_index()

    def normalize(s):
        return (s - s.min()) / (s.max() - s.min()) if (s.max() - s.min()) != 0 else s

    # 1. Calculate Baseline Seasonality (Average of all Target Columns)
    normalized_targets = pd.DataFrame()
    for col in target_cols:
        normalized_targets[col] = normalize(grouped[col])
    
    base_seasonality = normalized_targets.mean(axis=1)

    if not feature_cols:
        # Final Normalization of baseline
        final_sum = base_seasonality.sum()
        if final_sum == 0: return {str(p): 1.0/len(grouped) for p in grouped['period_idx']}
        weights = base_seasonality / final_sum
        return {str(int(p)): float(weights[i]) for i, p in enumerate(grouped['period_idx'])}

    # 2. Multivariate Logic
    # Calculate correlations against the AVERAGE baseline target
    correlations = {}
    normalized_features = pd.DataFrame()
    for col in feature_cols:
        normalized_features[col] = normalize(grouped[col])
        corr = base_seasonality.corr(normalized_features[col])
        correlations[col] = abs(corr) if not np.isnan(corr) else 0.0

    total_corr = sum(correlations.values())
    
    feature_seasonality = pd.Series(0.0, index=grouped.index)
    if total_corr > 0:
        for col in feature_cols:
            weight = correlations[col] / total_corr
            feature_seasonality += normalized_features[col] * weight
    else:
        feature_seasonality = base_seasonality

    # 3. Combine: 60% historical average, 40% correlated drivers
    combined = (base_seasonality * 0.6) + (feature_seasonality * 0.4)
    
    final_sum = combined.sum()
    if final_sum == 0: 
        return {str(int(p)): 1.0/len(grouped) for p in grouped['period_idx']}
    
    final_weights = combined / final_sum
    
    result = {str(int(row['period_idx'])): float(final_weights[i]) for i, row in grouped.iterrows()}
    return result

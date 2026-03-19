# src/services/split_analyzer.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

def analyze_seasonality_from_file(file_path: str, indicator_col: str, date_col: str, period_type: str) -> Dict[str, float]:
    """
    Analyzes a CSV/XLSX file to extract seasonality weights.
    Returns a dictionary of {period: weight}.
    """
    df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
    
    # Convert date_col to datetime
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Group by period
    if period_type == "Month":
        df['period'] = df[date_col].dt.month
    elif period_type == "Quarter":
        df['period'] = df[date_col].dt.quarter
    elif period_type == "Week":
        df['period'] = df[date_col].dt.isocalendar().week
    elif period_type == "Day":
        df['period'] = df[date_col].dt.date
    else:
        df['period'] = df[date_col].dt.year

    # Aggregate indicator column
    weights = df.groupby('period')[indicator_col].sum()
    
    # Normalize to 1.0 sum
    total = weights.sum()
    if total == 0:
        return {str(p): 1.0/len(weights) for p in weights.index}
    
    normalized = weights / total
    return {str(p): float(w) for p, w in normalized.items()}

def suggest_split_from_multivariate(df: pd.DataFrame, target_col: str, feature_cols: List[str]) -> Dict[str, float]:
    """
    Placeholder for more advanced multivariate logic.
    For now, just return weights based on target_col.
    """
    # Logic to be implemented: correlation analysis, etc.
    return {}

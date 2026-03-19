import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.services import split_analyzer
import os

def generate_test_data(file_path):
    """Generates synthetic data for multivariate seasonality testing."""
    # 2 years of daily data
    dates = pd.date_range(start="2023-01-01", end="2024-12-31", freq="D")
    
    # Base seasonality (Sine wave)
    base = np.sin(np.linspace(0, 4 * np.pi, len(dates))) + 2
    
    # Target 1: 2023 (High noise)
    t1 = base + np.random.normal(0, 0.5, len(dates))
    # Target 2: 2024 (Clean trend)
    t2 = base + np.random.normal(0, 0.1, len(dates))
    
    # Feature 1: Highly correlated with target
    f1 = base * 1.5 + np.random.normal(0, 0.2, len(dates))
    # Feature 2: Inversely correlated or random noise
    f2 = np.random.uniform(0, 10, len(dates))
    
    df = pd.DataFrame({
        "date": dates,
        "hist_2023": t1,
        "hist_2024": t2,
        "driver_sales": f1,
        "noise": f2
    })
    
    df.to_csv(file_path, index=False)
    return df

def test_and_plot():
    test_file = "test_multivariate_data.csv"
    df = generate_test_data(test_file)
    
    target_cols = ["hist_2023", "hist_2024"]
    feature_cols = ["driver_sales", "noise"]
    
    # Perform Analysis
    weights = split_analyzer.analyze_seasonality_from_file(
        test_file, target_cols, feature_cols, "date", "Month"
    )
    
    # Prepare Plotting Data
    # 1. Historical Targets Aggregated by Month
    df['month'] = df['date'].dt.month
    monthly_targets = df.groupby('month')[target_cols].sum()
    for col in target_cols:
        monthly_targets[col] = monthly_targets[col] / monthly_targets[col].sum()
    
    baseline_avg = monthly_targets.mean(axis=1)
    
    # 2. Result Weights
    result_months = sorted([int(m) for m in weights.keys()])
    result_vals = [weights[str(m)] for m in result_months]
    
    # Visualization
    plt.figure(figsize=(12, 7))
    
    # Plot Initial Historical Trends (Normalized)
    plt.subplot(2, 1, 1)
    for col in target_cols:
        plt.plot(monthly_targets.index, monthly_targets[col], marker='o', alpha=0.4, label=f"Initial: {col}")
    plt.plot(monthly_targets.index, baseline_avg, 'k--', linewidth=2, label="Calculated Average Baseline")
    plt.title("Initial Data & Baseline Averaging")
    plt.ylabel("Weight %")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot Result after Multivariate refinement
    plt.subplot(2, 1, 2)
    plt.bar(result_months, result_vals, color='skyblue', alpha=0.7, label="Final Multivariate Weights")
    plt.plot(monthly_targets.index, baseline_avg, 'r-', marker='x', label="Original Baseline (Target Only)")
    plt.title("Final Analysis Result (Including Multi-feature Drivers)")
    plt.xlabel("Month")
    plt.ylabel("Weight %")
    plt.xticks(range(1, 13))
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("multivariate_test_results.png")
    print("Test complete. Plot saved as 'multivariate_test_results.png'.")
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    test_and_plot()

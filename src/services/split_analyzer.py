"""
Multivariate seasonality predictor: derives per-period split weights from historical data.

Targets are aggregated per period (month / quarter / ISO week) and expressed as a share of
their mean, drivers are aggregated (mean) and scaled, then OLS, Ridge and Random Forest
are raced and the best fit (complexity-penalised) predicts the seasonal profile. A Monte
Carlo run gives a 5-95% band.

The returned weights use the same keys and units as Global Split templates -- month names,
"Q1".."Q4" or "W01".."W53", as percentages summing to 100 -- so they can be published as a
split as-is.
"""
import calendar
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

SUPPORTED_PERIOD_TYPES = ("Month", "Quarter", "Week")
MAX_ROWS = 1_000_000
MAX_COLUMNS = 200


def period_label(period_type: str, idx: int) -> str:
    if period_type == "Month":
        return calendar.month_name[idx]
    if period_type == "Quarter":
        return f"Q{idx}"
    return f"W{idx:02d}"


def _load(file_path: str) -> pd.DataFrame:
    suffix = Path(file_path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, nrows=MAX_ROWS)
    elif suffix in (".csv", ".txt", ""):
        df = pd.read_csv(file_path, sep=None, engine="python", nrows=MAX_ROWS)
    else:
        raise ValueError("Upload a .csv or .xlsx file.")
    if df.shape[1] > MAX_COLUMNS:
        raise ValueError(f"Too many columns (max {MAX_COLUMNS}).")
    return df


def _share_of_mean(s: pd.Series) -> pd.Series:
    mean = s.mean()
    return s / mean if mean else pd.Series(np.ones(len(s)), index=s.index)


def _min_max(s: pd.Series) -> pd.Series:
    span = s.max() - s.min()
    return (s - s.min()) / span if span else pd.Series(np.zeros(len(s)), index=s.index)


def _to_weights(period_idx, values: np.ndarray, period_type: str) -> Dict[str, float]:
    clipped = np.clip(np.asarray(values, dtype=float), 0, None)
    total = clipped.sum()
    shares = clipped / total if total > 0 else np.full(len(clipped), 1.0 / len(clipped))
    return {period_label(period_type, int(p)): round(float(v) * 100, 4) for p, v in zip(period_idx, shares)}


def analyze_seasonality_from_file(
    file_path: str,
    target_cols: List[str],
    feature_cols: List[str],
    date_col: str,
    period_type: str,
) -> Tuple[Dict[str, float], Dict[str, float], float, pd.DataFrame, str]:
    """Returns (weights, coefficients, r_squared, plot_df, model_name). Raises ValueError on bad input."""
    if period_type not in SUPPORTED_PERIOD_TYPES:
        raise ValueError(f"period_type must be one of: {', '.join(SUPPORTED_PERIOD_TYPES)}.")
    if not target_cols:
        raise ValueError("Pick at least one target column.")

    df = _load(file_path)
    missing = [c for c in [date_col, *target_cols, *feature_cols] if c not in df.columns]
    if missing:
        raise ValueError(f"Column(s) not found in the file: {', '.join(missing)}")
    for col in [*target_cols, *feature_cols]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, *target_cols])
    if df.empty:
        raise ValueError("No usable rows (check the date column and that targets are numeric).")

    if period_type == "Month":
        df["period_idx"] = df[date_col].dt.month
    elif period_type == "Quarter":
        df["period_idx"] = df[date_col].dt.quarter
    else:
        df["period_idx"] = df[date_col].dt.isocalendar().week.astype(int)

    # Average per period across years (a sum would over-weight periods that appear in more years).
    n_years = df.groupby("period_idx")[date_col].apply(lambda s: s.dt.isocalendar().year.nunique() if period_type == "Week" else s.dt.year.nunique())
    agg = {col: "sum" for col in target_cols} | {col: "mean" for col in feature_cols}
    grouped = df.groupby("period_idx").agg(agg)
    for col in target_cols:
        grouped[col] = grouped[col] / n_years.reindex(grouped.index).clip(lower=1)
    grouped = grouped.reset_index()

    y = pd.concat([_share_of_mean(grouped[c]) for c in target_cols], axis=1).mean(axis=1).to_numpy()
    labels = [period_label(period_type, int(p)) for p in grouped["period_idx"]]

    if not feature_cols:
        plot_df = pd.DataFrame({"period_idx": grouped["period_idx"], "period": labels, "Actual_Target": y,
                                "Predicted_Fit": y, "CI_Upper": y, "CI_Lower": y})
        return _to_weights(grouped["period_idx"], y, period_type), {}, 1.0, plot_df, "Historical Average"

    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.metrics import r2_score

    X = pd.concat([_min_max(grouped[c].fillna(grouped[c].mean())) for c in feature_cols], axis=1).to_numpy()
    n_samples = len(y)
    models = {
        "OLS Regression": LinearRegression(),
        "Ridge (L2 Regularized)": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=min(5, n_samples), random_state=42),
    }
    best_name, best_score, fitted = None, -np.inf, {}
    for name, model in models.items():
        try:
            model.fit(X, y)
            r2 = r2_score(y, model.predict(X)) if n_samples > 1 else 0.0
        except Exception:
            continue
        score = r2
        if name == "Random Forest":
            score -= 0.2 if n_samples < 24 else (0.1 if n_samples < 50 else 0.0)
        elif name == "OLS Regression" and X.shape[1] > n_samples / 2:
            score -= 0.05
        fitted[name] = (model, r2)
        if score > best_score:
            best_name, best_score = name, score

    if best_name is None:
        plot_df = pd.DataFrame({"period_idx": grouped["period_idx"], "period": labels, "Actual_Target": y,
                                "Predicted_Fit": y, "CI_Upper": y, "CI_Lower": y})
        return _to_weights(grouped["period_idx"], y, period_type), {}, 0.0, plot_df, "Historical Average (models failed)"

    model, r2 = fitted[best_name]
    y_pred = np.clip(model.predict(X), 0, None)

    rng = np.random.default_rng(42)
    std_dev = float(np.std(y - y_pred)) if n_samples > 1 else 0.05
    sims = np.array([
        np.clip(model.predict(X + rng.normal(0, 0.05, X.shape)) + rng.normal(0, std_dev, n_samples), 0, None)
        for _ in range(100)
    ])
    plot_df = pd.DataFrame({
        "period_idx": grouped["period_idx"], "period": labels, "Actual_Target": y, "Predicted_Fit": y_pred,
        "CI_Upper": np.percentile(sims, 95, axis=0), "CI_Lower": np.percentile(sims, 5, axis=0),
    })

    if hasattr(model, "coef_"):
        coefficients = {feat: float(c) for feat, c in zip(feature_cols, model.coef_)}
        coefficients["Intercept"] = float(model.intercept_)
    else:
        coefficients = {f"{feat} (Importance)": float(imp) for feat, imp in zip(feature_cols, model.feature_importances_)}

    return _to_weights(grouped["period_idx"], y_pred, period_type), coefficients, float(r2), plot_df, best_name

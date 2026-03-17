"""
models/helpers.py – Pure mathematical helpers used by Model 2 scoring.
No database or file-system dependencies.
"""
import pandas as pd


def normalize_0_100(series: pd.Series) -> pd.Series:
    """Min-max scale a Series to 0–100."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.0, index=series.index)
    return (series - mn) / (mx - mn) * 100


def amount_band(total_outstanding: float) -> int:
    """Map total outstanding amount to a discrete band score."""
    v = float(total_outstanding) if total_outstanding else 0.0
    if v < 100_000_000:
        return 10
    elif v < 500_000_000:
        return 30
    elif v < 1_000_000_000:
        return 60
    else:
        return 100


def source_flag(product_source: str) -> int:
    """Return weight for product source."""
    return 10 if str(product_source).upper() == "COREBANK" else 5

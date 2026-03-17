"""
Model 2 – Risk Score & Priority Ranking (Decision Under Risk)
Computes a weighted risk score from behavioral and outstanding data.
"""
import pandas as pd

from models.helpers import normalize_0_100, amount_band, source_flag


def compute_risk_scores(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """
    df must have columns:
        num_overdue_6m, max_dpd_6m, dpd_current,
        total_outstanding, product_source
    Returns df with risk_score and priority_rank added.
    weights keys: alpha, beta, gamma, delta, epsilon
    """
    alpha = float(weights.get("alpha", 20))
    beta  = float(weights.get("beta",  25))
    gamma = float(weights.get("gamma", 0.5))
    delta = float(weights.get("delta", 10))
    eps   = float(weights.get("epsilon", 5))

    df = df.copy()

    df["_norm_overdue"] = normalize_0_100(df["num_overdue_6m"].fillna(0))
    df["_norm_dpd6m"]   = normalize_0_100(df["max_dpd_6m"].fillna(0))
    df["_amount_band"]  = df["total_outstanding"].apply(amount_band)
    df["_source_flag"]  = df["product_source"].apply(source_flag)

    df["risk_score"] = (
        alpha * df["_norm_overdue"]
        + beta  * df["_norm_dpd6m"]
        + gamma * df["dpd_current"].fillna(0)
        + delta * df["_amount_band"]
        + eps   * df["_source_flag"]
    ).round(2)

    df["priority_rank"] = (
        df["risk_score"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    df.drop(columns=["_norm_overdue", "_norm_dpd6m", "_amount_band", "_source_flag"],
            inplace=True)
    return df


def weights_from_config(config_row) -> dict:
    """Convert a sqlite3.Row or dict config row into a weights dict."""
    if hasattr(config_row, "keys"):
        # sqlite3.Row
        return {
            "alpha":   config_row["alpha_num_overdue_6m"],
            "beta":    config_row["beta_max_dpd_6m"],
            "gamma":   config_row["gamma_dpd_current"],
            "delta":   config_row["delta_amount_band"],
            "epsilon": config_row["epsilon_product_source_mortgage"],
        }
    return {
        "alpha":   config_row.get("alpha_num_overdue_6m", 20),
        "beta":    config_row.get("beta_max_dpd_6m",      25),
        "gamma":   config_row.get("gamma_dpd_current",    0.5),
        "delta":   config_row.get("delta_amount_band",    10),
        "epsilon": config_row.get("epsilon_product_source_mortgage", 5),
    }

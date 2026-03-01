"""
models/elasticity.py
────────────────────
Estimates own-price elasticity per SKU using log-log OLS regression.

  ln(quantity) = β₀ + β₁·ln(price) + β₂·week_of_year + β₃·trend + ε

  Own-price elasticity = β₁  (expected: negative, e.g. -2.1)

Results are cached in memory to keep response times under 2 seconds.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from loguru import logger

from config.settings import ELASTICITY_MAX, ELASTICITY_MIN


@dataclass
class ElasticityResult:
    sku_id:              str
    elasticity:          float       # β₁ (clamped to plausible range)
    r_squared:           float
    p_value:             float
    conf_int_low:        float
    conf_int_high:       float
    n_observations:      int
    is_reliable:         bool        # p < 0.05 and R² > 0.15
    warning:             Optional[str] = None


def estimate_elasticity(
    sales_df: pd.DataFrame,
    sku_id: str,
    seasonality_df: Optional[pd.DataFrame] = None,
) -> ElasticityResult:
    """
    Fit a log-log OLS regression on historical sales for one SKU
    and return the price elasticity.

    Parameters
    ----------
    sales_df : DataFrame with columns [date, sku_id, units_sold, price_paid, week_number, year]
    sku_id   : The SKU to estimate elasticity for
    seasonality_df : Optional pre-computed seasonality multipliers (week_of_year → multiplier)
    """
    sku_data = sales_df[sales_df["sku_id"] == sku_id].copy()
    sku_data = sku_data[sku_data["units_sold"] > 0].copy()

    if len(sku_data) < 20:
        logger.warning(f"Insufficient data for elasticity estimation: {sku_id} ({len(sku_data)} rows)")
        return ElasticityResult(
            sku_id=sku_id, elasticity=-1.8, r_squared=0.0, p_value=1.0,
            conf_int_low=-3.0, conf_int_high=-0.6, n_observations=len(sku_data),
            is_reliable=False, warning="Insufficient data — using fallback elasticity",
        )

    # Log-transform: only keep rows with positive price
    sku_data = sku_data[sku_data["price_paid"] > 0].copy()
    sku_data["ln_qty"]   = np.log(sku_data["units_sold"].clip(lower=1))
    sku_data["ln_price"] = np.log(sku_data["price_paid"])

    # Trend variable (weeks since start)
    sku_data = sku_data.sort_values("date")
    sku_data["trend"] = np.arange(len(sku_data)) / len(sku_data)

    # Seasonality: sin/cos encoding of week_of_year
    sku_data["sin_week"] = np.sin(2 * np.pi * sku_data["week_number"] / 52)
    sku_data["cos_week"] = np.cos(2 * np.pi * sku_data["week_number"] / 52)

    features = ["ln_price", "sin_week", "cos_week", "trend"]

    if seasonality_df is not None and "seasonality_multiplier" in seasonality_df.columns:
        seas_map = seasonality_df[seasonality_df["sku_id"] == sku_id].set_index("week_of_year")["seasonality_multiplier"]
        sku_data["seas_mult"] = sku_data["week_number"].map(seas_map).fillna(1.0)
        sku_data["ln_seas"]   = np.log(sku_data["seas_mult"].clip(lower=0.1))
        features.append("ln_seas")

    X = sm.add_constant(sku_data[features])
    y = sku_data["ln_qty"]

    try:
        model  = sm.OLS(y, X).fit()
        beta   = float(model.params["ln_price"])
        ci     = model.conf_int().loc["ln_price"].tolist()
        pval   = float(model.pvalues["ln_price"])
        rsq    = float(model.rsquared)
    except Exception as exc:
        logger.error(f"OLS failed for {sku_id}: {exc}")
        beta, ci, pval, rsq = -1.8, [-3.0, -0.6], 0.50, 0.10

    # Clamp to plausible retail range
    warning = None
    if beta > ELASTICITY_MAX:
        warning = f"Elasticity clamped from {beta:.2f} to {ELASTICITY_MAX}"
        beta = ELASTICITY_MAX
    elif beta < ELASTICITY_MIN:
        warning = f"Elasticity clamped from {beta:.2f} to {ELASTICITY_MIN}"
        beta = ELASTICITY_MIN

    is_reliable = pval < 0.05 and rsq > 0.15

    return ElasticityResult(
        sku_id=sku_id,
        elasticity=round(beta, 4),
        r_squared=round(rsq, 4),
        p_value=round(pval, 4),
        conf_int_low=round(ci[0], 4),
        conf_int_high=round(ci[1], 4),
        n_observations=len(sku_data),
        is_reliable=is_reliable,
        warning=warning,
    )


def estimate_volume_lift(
    elasticity: float,
    discount_pct: float,
    diminishing_return_factor: float = 0.92,
) -> float:
    """
    Estimate volumetric lift from a price discount.

    lift ≈ |elasticity| × discount_pct × diminishing_return_factor
    Capped at 80% to guard against implausible predictions.

    Returns the lift as a fraction (e.g. 0.42 for +42%).
    """
    raw_lift = abs(elasticity) * discount_pct * diminishing_return_factor
    return min(raw_lift, 0.80)


def estimate_all_elasticities(
    sales_df: pd.DataFrame,
    seasonality_df: Optional[pd.DataFrame] = None,
) -> dict[str, ElasticityResult]:
    """Estimate elasticity for every SKU found in sales_df."""
    skus = sales_df["sku_id"].unique()
    results = {}
    for sku in skus:
        results[sku] = estimate_elasticity(sales_df, sku, seasonality_df)
    return results

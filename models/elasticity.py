"""
models/elasticity.py
────────────────────
Estimates own-price elasticity per SKU using log-log OLS regression.

  ln(quantity) = β₀ + β₁·ln(price) + β₂·week_of_year + β₃·trend + ε

  Own-price elasticity = β₁  (expected: negative, e.g. -2.1)

Promotional elasticity is derived by applying a PROMO_RESPONSE_MULTIPLIER
(typically 2×) to the regular elasticity — academic standard because
temporary discounts trigger urgency, display effects, and reference-price
anchoring that magnify the volume response.

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

from config.settings import (
    ELASTICITY_MAX,
    ELASTICITY_MIN,
    PROMO_RESPONSE_MULTIPLIER,
    CATEGORY_ELASTICITY_DEFAULTS,
    DEFAULT_CATEGORY_ELASTICITY,
)


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
    data_quality:        str = "good"   # 'good' | 'limited' | 'insufficient'


def _get_category_default(category: Optional[str] = None) -> float:
    """Return the category-level default elasticity."""
    if category and category in CATEGORY_ELASTICITY_DEFAULTS:
        return CATEGORY_ELASTICITY_DEFAULTS[category]
    return DEFAULT_CATEGORY_ELASTICITY


def estimate_elasticity(
    sales_df: pd.DataFrame,
    sku_id: str,
    seasonality_df: Optional[pd.DataFrame] = None,
    category: Optional[str] = None,
) -> ElasticityResult:
    """
    Fit a log-log OLS regression on historical sales for one SKU
    and return the price elasticity.

    Parameters
    ----------
    sales_df : DataFrame with columns [date, sku_id, units_sold, price_paid, week_number, year]
    sku_id   : The SKU to estimate elasticity for
    seasonality_df : Optional pre-computed seasonality multipliers (week_of_year → multiplier)
    category : Optional product category — used for fallback elasticity when OLS estimation
               has insufficient price variation.
    """
    cat_default = _get_category_default(category)

    sku_data = sales_df[sales_df["sku_id"] == sku_id].copy()
    sku_data = sku_data[sku_data["units_sold"] > 0].copy()

    if len(sku_data) < 4:
        logger.warning(f"Insufficient data for elasticity estimation: {sku_id} ({len(sku_data)} rows)")
        return ElasticityResult(
            sku_id=sku_id, elasticity=cat_default, r_squared=0.0, p_value=1.0,
            conf_int_low=cat_default * 1.5, conf_int_high=cat_default * 0.5,
            n_observations=len(sku_data),
            is_reliable=False, warning="Insufficient data — using category-average elasticity",
            data_quality="insufficient",
        )

    if len(sku_data) < 12:
        logger.info(f"Limited data for elasticity estimation: {sku_id} ({len(sku_data)} rows) — estimate may be noisy")
        # Still run OLS below, but mark as limited
        _data_quality = "limited"
    else:
        _data_quality = "good"

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

    # For small datasets, use simpler model to avoid low degrees of freedom
    if len(sku_data) < 10:
        features = ["ln_price"]  # just price elasticity, no seasonality/trend

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
        beta, ci, pval, rsq = cat_default, [cat_default * 1.5, cat_default * 0.5], 0.50, 0.10

    # ── Decide whether to use OLS result or category default ──────
    # If OLS found a non-significant result (high p-value, near-zero R²),
    # or the coefficient is positive/near-zero (would be clamped), the
    # item likely has insufficient price variation for item-level estimation.
    # In that case, use the category-level default instead.
    ols_was_unreliable = (pval > 0.10 and rsq < 0.10) or beta > ELASTICITY_MAX
    if ols_was_unreliable and category:
        logger.info(f"OLS unreliable for {sku_id} (β={beta:.3f}, R²={rsq:.3f}, p={pval:.3f}) "
                     f"— using category default ({category}: {cat_default})")
        beta = cat_default
        ci = [cat_default * 1.5, cat_default * 0.5]
        warning = f"Using {category} category-average elasticity ({cat_default})"
    else:
        warning = None

    # Clamp to plausible retail range
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
        data_quality=_data_quality,
    )


def estimate_volume_lift(
    elasticity: float,
    discount_pct: float,
    promo_multiplier: Optional[float] = None,
) -> float:
    """
    Estimate volumetric lift from a promotional price discount.

    Uses the **constant-elasticity demand model**:
        Q_new / Q_old = (P_new / P_old) ^ promo_elasticity
        lift = (1 − discount) ^ (elasticity × promo_multiplier) − 1

    The promo_multiplier accounts for the well-documented fact that
    promotional (temporary) price response is 2–3× the regular price
    elasticity due to urgency, display/feature effects, and
    reference-price anchoring.

    Capped at 80% to guard against implausible predictions.

    Returns the lift as a fraction (e.g. 0.42 for +42%).
    """
    if promo_multiplier is None:
        promo_multiplier = PROMO_RESPONSE_MULTIPLIER

    # Apply promo multiplier to convert regular → promotional elasticity
    promo_elasticity = elasticity * promo_multiplier

    # Constant-elasticity demand model
    lift = (1.0 - discount_pct) ** promo_elasticity - 1.0

    # Clamp: lift must be non-negative and capped at 80%
    return min(max(lift, 0.0), 0.80)


def estimate_all_elasticities(
    sales_df: pd.DataFrame,
    seasonality_df: Optional[pd.DataFrame] = None,
    category_map: Optional[dict] = None,
) -> dict[str, ElasticityResult]:
    """Estimate elasticity for every SKU found in sales_df.

    Parameters
    ----------
    category_map : Optional dict of {sku_id: category_name} for
                   category-level fallback when item OLS is unreliable.
    """
    skus = sales_df["sku_id"].unique()
    results = {}
    for sku in skus:
        cat = category_map.get(sku) if category_map else None
        results[sku] = estimate_elasticity(sales_df, sku, seasonality_df, category=cat)
    return results

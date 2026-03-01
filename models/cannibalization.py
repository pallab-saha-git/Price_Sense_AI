"""
models/cannibalization.py
──────────────────────────
Cross-elasticity matrix estimation and cannibalization impact calculation.

For a focal SKU going on promo, this module:
  1. Computes how much each related SKU's volume drops.
  2. Translates volume drops to margin loss (cannibalization cost).

Method: multivariate log-log regression per affected SKU.
Fallback: lookup table from embedded cross-elasticity estimates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from loguru import logger

# Fallback cross-elasticities (sku_a price cut → sku_b volume drop)
# Positive = substitutes (cannibalization), Negative = complements (halo)
# Values calibrated to IRI/Nielsen benchmarks for specialty food categories.
# Within-subcategory (e.g. Pistachios 16oz ↔ Pistachios 32oz): 0.20–0.30
# Cross-subcategory same category (Pistachios ↔ Almonds):        0.12–0.20
# Cross-category (Nuts ↔ Beverages): negligible, not listed here.
#
# NOTE: These are only used as a static fallback for synthetic data.
#       For dunnhumby / real data, dynamic fallback is built at runtime
#       based on same-category product pairs (see _dynamic_fallback_cross_elasticity).
FALLBACK_CROSS_ELASTICITIES: dict[tuple[str, str], float] = {
    ("NUT-PIST-16", "NUT-ALMD-16"): 0.22,
    ("NUT-PIST-16", "NUT-MIXD-16"): 0.14,
    ("NUT-ALMD-16", "NUT-PIST-16"): 0.20,
    ("NUT-ALMD-16", "NUT-MIXD-16"): 0.12,
    ("NUT-MIXD-16", "NUT-PIST-16"): 0.13,
    ("NUT-MIXD-16", "NUT-ALMD-16"): 0.11,
    ("NUT-PIST-08", "NUT-ALMD-08"): 0.18,
    ("NUT-ALMD-08", "NUT-PIST-08"): 0.17,
    ("NUT-PIST-32", "NUT-MIXD-32"): 0.16,
    ("NUT-PIST-08", "NUT-PIST-16"): 0.28,   # size-pack substitution
    ("BEV-COLA-12", "BEV-COLA-24"): 0.25,
    ("BEV-COLA-24", "BEV-COLA-12"): 0.22,
    ("BEV-WTER-06", "BEV-WTER-12"): 0.23,
    ("BEV-WTER-12", "BEV-WTER-06"): 0.20,
}


def _dynamic_fallback_cross_elasticity(focal_sku: str, affected_sku: str, products_df: pd.DataFrame = None) -> float:
    """
    Dynamic fallback: if the pair exists in the static table, use that.
    Otherwise, if both SKUs share the same category, assign a default
    cross-elasticity based on whether they share a subcategory too.

    This ensures dunnhumby data (DH-xxx, LGSR-xxx) gets plausible
    fallback values instead of always returning 0.0.
    """
    # Try static table first
    static = FALLBACK_CROSS_ELASTICITIES.get((focal_sku, affected_sku))
    if static is not None:
        return static

    # If no products_df provided, return a conservative default
    if products_df is None or products_df.empty:
        return 0.12

    focal_info    = products_df[products_df["sku_id"] == focal_sku]
    affected_info = products_df[products_df["sku_id"] == affected_sku]
    if focal_info.empty or affected_info.empty:
        return 0.0

    focal_cat = focal_info.iloc[0]["category"]
    focal_sub = focal_info.iloc[0]["subcategory"]
    aff_cat   = affected_info.iloc[0]["category"]
    aff_sub   = affected_info.iloc[0]["subcategory"]

    if focal_cat != aff_cat:
        return 0.0  # cross-category: negligible

    if focal_sub == aff_sub:
        return 0.22  # same subcategory: moderate cannibalization

    return 0.14  # same category, different subcategory: lower cannibalization


@dataclass
class CannibalizationImpact:
    affected_sku_id:       str
    affected_product_name: str
    cross_elasticity:      float
    volume_loss_units:     float     # units lost per week
    margin_loss_dollars:   float     # $ margin lost per week
    pct_volume_depressed:  float     # % of affected SKU's baseline volume


@dataclass
class CannibalizationResult:
    focal_sku_id:  str
    discount_pct:  float
    impacts:       list[CannibalizationImpact]
    total_margin_loss: float         # sum of all affected SKU margin losses

    @property
    def has_cannibalization(self) -> bool:
        return bool(self.impacts)

    @property
    def worst_affected(self) -> Optional[CannibalizationImpact]:
        return max(self.impacts, key=lambda x: x.margin_loss_dollars) if self.impacts else None


def _estimate_cross_elasticity(
    sales_df: pd.DataFrame,
    focal_sku_id: str,
    affected_sku_id: str,
    products_df: pd.DataFrame = None,
) -> float:
    """
    Estimate cross-price elasticity via regression:
      ln(qty_affected) = α + γ·ln(price_focal) + δ·ln(price_affected) + trend + ε
    Returns γ (positive = substitutes, cannibalization).
    Falls back to dynamic lookup if insufficient data or regression fails.
    """
    focal_df    = sales_df[sales_df["sku_id"] == focal_sku_id][["date", "price_paid", "units_sold"]].copy()
    affected_df = sales_df[sales_df["sku_id"] == affected_sku_id][["date", "price_paid", "units_sold"]].copy()

    focal_df    = focal_df.groupby("date").agg(price_paid=("price_paid", "mean"), units_sold=("units_sold", "sum")).reset_index()
    affected_df = affected_df.groupby("date").agg(price_paid=("price_paid", "mean"), units_sold=("units_sold", "sum")).reset_index()

    merged = focal_df.merge(affected_df, on="date", suffixes=("_focal", "_affected"))
    merged = merged[(merged["units_sold_affected"] > 0) & (merged["price_paid_focal"] > 0) & (merged["price_paid_affected"] > 0)]

    if len(merged) < 15:
        return _dynamic_fallback_cross_elasticity(focal_sku_id, affected_sku_id, products_df)

    merged["ln_qty_affected"]   = np.log(merged["units_sold_affected"].clip(lower=1))
    merged["ln_price_focal"]    = np.log(merged["price_paid_focal"])
    merged["ln_price_affected"] = np.log(merged["price_paid_affected"])
    merged["trend"]             = np.arange(len(merged)) / len(merged)

    X = sm.add_constant(merged[["ln_price_focal", "ln_price_affected", "trend"]])
    y = merged["ln_qty_affected"]

    try:
        model = sm.OLS(y, X).fit()
        cross_e = float(model.params["ln_price_focal"])
        # Clamp to plausible range
        return float(np.clip(cross_e, -0.3, 1.5))
    except Exception:
        return _dynamic_fallback_cross_elasticity(focal_sku_id, affected_sku_id, products_df)


def compute_cannibalization(
    focal_sku_id: str,
    discount_pct: float,
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
    use_regression: bool = True,
) -> CannibalizationResult:
    """
    Calculate cannibalization impact on all related SKUs when focal_sku goes on promo.

    Parameters
    ----------
    focal_sku_id   : The SKU being promoted
    discount_pct   : Promotional discount (e.g. 0.25 for 25%)
    sales_df       : Weekly sales data
    products_df    : Product catalog with cost_price
    use_regression : If True, try regression; fall back to lookup table
    """
    # Identify related SKUs (same category + subcategory prefix match, excluding focal)
    focal_info = products_df[products_df["sku_id"] == focal_sku_id]
    if focal_info.empty:
        return CannibalizationResult(focal_sku_id=focal_sku_id, discount_pct=discount_pct, impacts=[], total_margin_loss=0.0)

    focal_cat    = focal_info.iloc[0]["category"]
    focal_sub    = focal_info.iloc[0]["subcategory"]

    related_skus = products_df[
        (products_df["category"] == focal_cat) &
        (products_df["sku_id"] != focal_sku_id)
    ]["sku_id"].tolist()

    if not related_skus:
        return CannibalizationResult(focal_sku_id=focal_sku_id, discount_pct=discount_pct, impacts=[], total_margin_loss=0.0)

    # Baseline weekly volume for each related SKU (non-promo weeks, last 52 weeks)
    # Sum across stores per date first, THEN average over weeks — consistent with P&L baseline.
    sales_non_promo = sales_df[(sales_df["is_promo"] == False) | (sales_df["is_promo"].isna())]
    recent_sales    = sales_non_promo[
        pd.to_datetime(sales_non_promo["date"]) >= (pd.to_datetime(sales_non_promo["date"]).max() - pd.Timedelta(weeks=52))
    ]
    baseline_weekly = (
        recent_sales.groupby(["sku_id", "date"])["units_sold"]
        .sum()                    # total across all stores for each week
        .groupby(level="sku_id")
        .mean()                   # mean of weekly totals → consistent with forecast baseline
        .to_dict()
    )

    impacts = []
    for affected_sku_id in related_skus:
        if use_regression:
            cross_e = _estimate_cross_elasticity(sales_df, focal_sku_id, affected_sku_id, products_df)
        else:
            cross_e = _dynamic_fallback_cross_elasticity(focal_sku_id, affected_sku_id, products_df)

        if abs(cross_e) < 0.10:
            continue  # negligible cross-effect — below 10% threshold

        baseline_vol = baseline_weekly.get(affected_sku_id, 0.0)
        if baseline_vol <= 0:
            continue

        pct_drop     = float(np.clip(cross_e * discount_pct * 0.88, 0, 0.70))
        volume_loss  = baseline_vol * pct_drop

        # Get margin for affected SKU
        affected_info  = products_df[products_df["sku_id"] == affected_sku_id]
        affected_name  = affected_info.iloc[0]["product_name"] if not affected_info.empty else affected_sku_id
        affected_cost  = float(affected_info.iloc[0]["cost_price"]) if not affected_info.empty else 0.0
        affected_price = float(affected_info.iloc[0]["regular_price"]) if not affected_info.empty else 0.0
        affected_margin_per_unit = max(0.0, affected_price - affected_cost)

        margin_loss = volume_loss * affected_margin_per_unit

        impacts.append(CannibalizationImpact(
            affected_sku_id=affected_sku_id,
            affected_product_name=affected_name,
            cross_elasticity=round(cross_e, 4),
            volume_loss_units=round(volume_loss, 1),
            margin_loss_dollars=round(margin_loss, 2),
            pct_volume_depressed=round(pct_drop * 100, 1),
        ))

    # Sort by margin impact descending
    impacts.sort(key=lambda x: x.margin_loss_dollars, reverse=True)
    total_margin_loss = sum(i.margin_loss_dollars for i in impacts)

    return CannibalizationResult(
        focal_sku_id=focal_sku_id,
        discount_pct=discount_pct,
        impacts=impacts,
        total_margin_loss=round(total_margin_loss, 2),
    )


def build_cross_elasticity_matrix(
    sales_df: pd.DataFrame,
    sku_ids: list[str],
) -> pd.DataFrame:
    """
    Build a full cross-elasticity matrix for a list of SKUs.
    Rows = focal SKU (price changes), Columns = affected SKU (volume response).
    """
    matrix = pd.DataFrame(index=sku_ids, columns=sku_ids, dtype=float)

    for focal in sku_ids:
        for affected in sku_ids:
            if focal == affected:
                matrix.loc[focal, affected] = np.nan  # own-price not shown here
            else:
                cross_e = _estimate_cross_elasticity(sales_df, focal, affected)
                matrix.loc[focal, affected] = round(cross_e, 3)

    return matrix

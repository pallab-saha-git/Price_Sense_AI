"""
models/profit_calculator.py
────────────────────────────
Full promotion P&L model.

Computes:
  • Baseline profit (no promo)
  • Promo profit (with discount + lift)
  • Net incremental profit
  • Promo ROI
  • Cannibalization-adjusted totals
  • Forward-buy discount (pantry loading adjustment)
  
New:
  • estimate_forward_buy_factor() — analyzes post-promo dips to estimate pantry loading
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PromoPnL:
    # Inputs
    sku_id:               str
    product_name:         str
    regular_price:        float
    cost_price:           float
    discount_pct:         float
    baseline_weekly_units: float

    # Derived
    promo_price:          float = field(init=False)
    regular_margin:       float = field(init=False)
    promo_margin:         float = field(init=False)
    margin_erosion_per_unit: float = field(init=False)

    # Results (populated by calculate())
    promo_weekly_units:      float = 0.0
    incremental_units:       float = 0.0

    baseline_revenue:        float = 0.0
    promo_revenue:           float = 0.0
    incremental_revenue:     float = 0.0

    baseline_margin_total:   float = 0.0
    promo_margin_total:      float = 0.0
    margin_on_incremental:   float = 0.0
    margin_loss_on_base:     float = 0.0
    net_margin_impact:       float = 0.0

    cannibalization_cost:    float = 0.0
    net_incremental_profit:  float = 0.0

    promo_roi:               float = 0.0
    promo_weeks:             int = 1

    forward_buy_adjustment:  float = 0.0   # post-promo demand dip adjustment
    data_quality:            str = "good"  # 'good' | 'limited' | 'insufficient'

    def __post_init__(self):
        self.promo_price             = round(self.regular_price * (1 - self.discount_pct), 2)
        self.regular_margin          = round(self.regular_price - self.cost_price, 2)
        self.promo_margin            = round(self.promo_price   - self.cost_price, 2)
        self.margin_erosion_per_unit = round(self.regular_margin - self.promo_margin, 2)

    @property
    def recommendation_tier(self) -> str:
        """Promotion tier based on net incremental profit, ROI, and data quality.

        INSUFFICIENT_DATA — not enough historical data to make a reliable assessment
        RECOMMENDED       — positive net incremental profit (lift revenue exceeds margin erosion)
        MARGINAL          — small loss: ROI between -0.30 and 0 (worth reviewing)
        NOT_RECOMMENDED   — net loss deeper than 30% of discount cost, not worth running
        """
        if self.data_quality == "insufficient":
            return "INSUFFICIENT_DATA"
        if self.net_incremental_profit > 0:
            return "RECOMMENDED"
        elif self.promo_roi >= -0.30:
            return "MARGINAL"
        else:
            return "NOT_RECOMMENDED"

    @property
    def promo_margin_pct(self) -> float:
        return round(self.promo_margin / self.promo_price * 100, 1) if self.promo_price > 0 else 0.0

    @property
    def regular_margin_pct(self) -> float:
        return round(self.regular_margin / self.regular_price * 100, 1) if self.regular_price > 0 else 0.0


def calculate_promo_pnl(
    sku_id:                str,
    product_name:          str,
    regular_price:         float,
    cost_price:            float,
    discount_pct:          float,
    baseline_weekly_units: float,
    volume_lift_pct:       float,       # e.g. 0.42 for +42%
    promo_weeks:           int = 1,
    cannibalization_cost:  float = 0.0,
    forward_buy_factor:    float = 0.0,  # pantry loading adj (default 0 — enable if data supports)
) -> PromoPnL:
    """
    Calculate the full promotion P&L.

    Parameters
    ----------
    volume_lift_pct     : Expected fractional lift (0.0–0.80)
    cannibalization_cost: Total margin loss from related SKUs (from cannibalization model)
    forward_buy_factor  : Fraction of incremental volume that is pull-forward (reduces net)
    """
    pnl = PromoPnL(
        sku_id=sku_id,
        product_name=product_name,
        regular_price=regular_price,
        cost_price=cost_price,
        discount_pct=discount_pct,
        baseline_weekly_units=baseline_weekly_units,
    )

    pnl.promo_weeks = promo_weeks

    # Volume calculations (aggregate over promo period)
    weeks_base = baseline_weekly_units * promo_weeks
    pnl.promo_weekly_units  = round(baseline_weekly_units * (1 + volume_lift_pct), 1)
    promo_total_units       = pnl.promo_weekly_units * promo_weeks
    pnl.incremental_units   = round(promo_total_units - weeks_base, 1)

    # Revenue
    pnl.baseline_revenue    = round(weeks_base * regular_price, 2)
    pnl.promo_revenue       = round(promo_total_units * pnl.promo_price, 2)
    pnl.incremental_revenue = round(pnl.promo_revenue - pnl.baseline_revenue, 2)

    # Margin analysis
    pnl.baseline_margin_total = round(weeks_base * pnl.regular_margin, 2)
    pnl.promo_margin_total    = round(promo_total_units * pnl.promo_margin, 2)
    pnl.margin_on_incremental = round(pnl.incremental_units * pnl.promo_margin, 2)
    pnl.margin_loss_on_base   = round(-weeks_base * pnl.margin_erosion_per_unit, 2)
    pnl.net_margin_impact     = round(pnl.promo_margin_total - pnl.baseline_margin_total, 2)

    # Cannibalization (total across all affected SKUs × promo_weeks)
    pnl.cannibalization_cost = round(cannibalization_cost * promo_weeks, 2)

    # Forward buy (pantry loading) adjustment — reduces true net benefit
    incremental_non_fb = pnl.incremental_units * (1 - forward_buy_factor)
    fb_units_lost      = pnl.incremental_units * forward_buy_factor
    pnl.forward_buy_adjustment = round(-fb_units_lost * pnl.promo_margin, 2)

    # Net incremental profit
    pnl.net_incremental_profit = round(
        pnl.net_margin_impact
        - pnl.cannibalization_cost
        + pnl.forward_buy_adjustment,
        2,
    )

    # ROI: incremental profit / cost of discount on baseline volume
    discount_cost = weeks_base * pnl.margin_erosion_per_unit
    if discount_cost > 0:
        pnl.promo_roi = round(pnl.net_incremental_profit / discount_cost, 2)
    else:
        pnl.promo_roi = 0.0

    return pnl


def find_optimal_discount(
    sku_id:                str,
    product_name:          str,
    regular_price:         float,
    cost_price:            float,
    baseline_weekly_units: float,
    elasticity:            float,
    cannibalization_cost_per_pct: float = 0.0,  # marginal cannibal cost per 1% discount
    discount_levels: list[float] | None = None,
) -> tuple[float, PromoPnL]:
    """
    Find the discount level that maximises net incremental profit.
    Returns (optimal_discount_pct, best_pnl).
    """
    from models.elasticity import estimate_volume_lift

    if discount_levels is None:
        discount_levels = [0.10, 0.15, 0.20, 0.25, 0.30]

    best_pnl      = None
    best_discount = discount_levels[0]

    for disc in discount_levels:
        lift = estimate_volume_lift(elasticity, disc)
        cannibal_cost = cannibalization_cost_per_pct * disc
        pnl = calculate_promo_pnl(
            sku_id=sku_id,
            product_name=product_name,
            regular_price=regular_price,
            cost_price=cost_price,
            discount_pct=disc,
            baseline_weekly_units=baseline_weekly_units,
            volume_lift_pct=lift,
            cannibalization_cost=cannibal_cost,
        )
        if best_pnl is None or pnl.net_incremental_profit > best_pnl.net_incremental_profit:
            best_pnl      = pnl
            best_discount = disc

    return best_discount, best_pnl


def estimate_forward_buy_factor(
    sales_df: pd.DataFrame,
    sku_id: str,
    promo_weeks: int = 4,
) -> float:
    """
    Estimate forward-buy (pantry loading) factor by analyzing post-promo dips.
    
    Forward-buy occurs when customers stockpile during promotions, causing
    a demand dip in the weeks following the promotion end.
    
    Returns the estimated fraction of incremental volume that is pull-forward
    (0.0 = no pantry loading, 0.3 = 30% of lift is borrowed from future).
    
    Method:
    1. Identify historical promotions for this SKU
    2. Measure the post-promo dip (weeks 1-4 after promo end)
    3. Average the dip magnitude across all past promos
    4. Return as a fraction of the baseline
    
    Parameters
    ----------
    sales_df : Sales DataFrame with columns [date, sku_id, units_sold, is_promo]
    sku_id   : The SKU to analyze
    promo_weeks : Number of weeks to look after promo for dips
    
    Returns
    -------
    forward_buy_factor : float in [0.0, 0.5]
        0.0 = no pantry loading detected
        0.3 = 30% of incremental volume is borrowed from future periods
    """
    sku_sales = sales_df[sales_df["sku_id"] == sku_id].copy()
    if sku_sales.empty or "is_promo" not in sku_sales.columns:
        return 0.0
    
    sku_sales = sku_sales.sort_values("date")
    sku_sales["date"] = pd.to_datetime(sku_sales["date"])
    
    # Find promo end dates
    promo_rows = sku_sales[sku_sales["is_promo"] == True]
    if promo_rows.empty:
        return 0.0
    
    # Group consecutive promo weeks
    promo_rows["promo_group"] = (promo_rows["date"].diff() > pd.Timedelta(days=8)).cumsum()
    promo_ends = promo_rows.groupby("promo_group")["date"].max()
    
    # Baseline (non-promo weeks' average)
    baseline = sku_sales[~sku_sales["is_promo"]]["units_sold"].mean()
    if pd.isna(baseline) or baseline <= 0:
        return 0.0
    
    # Measure post-promo dips
    dips = []
    for end_date in promo_ends:
        post_promo_start = end_date + pd.Timedelta(days=1)
        post_promo_end   = end_date + pd.Timedelta(weeks=promo_weeks)
        post_promo_sales = sku_sales[
            (sku_sales["date"] >= post_promo_start) &
            (sku_sales["date"] <= post_promo_end) &
            (~sku_sales["is_promo"])
        ]
        
        if len(post_promo_sales) >= 2:
            avg_post = post_promo_sales["units_sold"].mean()
            # Dip is measured as % below baseline
            dip_pct = (baseline - avg_post) / baseline if baseline > 0 else 0.0
            if dip_pct > 0:  # Only count actual dips, not increases
                dips.append(dip_pct)
    
    if not dips:
        return 0.0
    
    # Average dip across all promos
    avg_dip = float(np.mean(dips))
    
    # Clamp to [0.0, 0.5] — extreme pantry loading is 50% pull-forward
    return min(max(avg_dip, 0.0), 0.5)

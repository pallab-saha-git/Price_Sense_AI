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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


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

    def __post_init__(self):
        self.promo_price             = round(self.regular_price * (1 - self.discount_pct), 2)
        self.regular_margin          = round(self.regular_price - self.cost_price, 2)
        self.promo_margin            = round(self.promo_price   - self.cost_price, 2)
        self.margin_erosion_per_unit = round(self.regular_margin - self.promo_margin, 2)

    @property
    def recommendation_tier(self) -> str:
        """Promotion tier based on net incremental profit and ROI.

        RECOMMENDED   — positive net profit AND ROI ≥ 1.0x (cleared cost of discount)
        MARGINAL      — profitable but ROI < 1.0, OR small loss (ROI > -0.15)
        NOT_RECOMMENDED — net loss deeper than 15% of discount cost
        """
        if self.net_incremental_profit > 0 and self.promo_roi >= 1.0:
            return "RECOMMENDED"
        elif self.net_incremental_profit > 0 or self.promo_roi > -0.15:
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
    forward_buy_factor:    float = 0.02,  # 2% of incremental attributed to pull-forward
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

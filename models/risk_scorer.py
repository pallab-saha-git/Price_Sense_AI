"""
models/risk_scorer.py
──────────────────────
Composite risk score (0.0–1.0) for a promotion decision.

Factors (weighted composite):
  1. Elasticity confidence   25%  — model R²  and p-value
  2. Data recency            20%  — age of most recent sales observation
  3. Cannibalization breadth 20%  — number of affected SKUs
  4. Discount depth history  15%  — is requested discount within tested range?
  5. Seasonal anomaly risk   10%  — holiday / peak period uncertainty
  6. Category volatility     10%  — demand variability (CV of weekly sales)

Score bands:
  0.0–0.3 → LOW    (Green)
  0.3–0.6 → MEDIUM (Yellow)
  0.6–1.0 → HIGH   (Red)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RiskFactor:
    name:        str
    weight:      float
    raw_score:   float    # 0 (low risk) → 1 (high risk)
    description: str

    @property
    def weighted_score(self) -> float:
        return self.raw_score * self.weight


@dataclass
class RiskResult:
    total_score:   float             # 0.0–1.0
    band:          str               # 'LOW' | 'MEDIUM' | 'HIGH'
    factors:       list[RiskFactor]
    dominant_risk: Optional[str] = None  # name of the highest-weighted factor

    @property
    def color(self) -> str:
        return {"LOW": "success", "MEDIUM": "warning", "HIGH": "danger"}.get(self.band, "secondary")

    @property
    def label(self) -> str:
        return f"{self.band} ({self.total_score:.2f}/1.0)"


def score_risk(
    sku_id:             str,
    discount_pct:       float,
    elasticity_rsq:     float,
    elasticity_pvalue:  float,
    n_cannibal_skus:    int,
    sales_df:           pd.DataFrame,
    promotions_df:      pd.DataFrame,
    target_date:        Optional[date] = None,
    seasonality_index:  Optional[dict] = None,    # {week_of_year: multiplier}
) -> RiskResult:
    """
    Compute the composite risk score.

    Parameters
    ----------
    sku_id            : Focal SKU
    discount_pct      : Proposed discount (0.0–1.0)
    elasticity_rsq    : R² from the elasticity model
    elasticity_pvalue : p-value of β₁ in elasticity model
    n_cannibal_skus   : Number of SKUs materially affected by cannibalization
    sales_df          : Full sales DataFrame (to compute volatility + recency)
    promotions_df     : Historical promotions (to check tested discount range)
    target_date       : Planned promo start date (for seasonality check)
    seasonality_index : Pre-computed {week_of_year: multiplier}
    """
    factors: list[RiskFactor] = []

    # ── 1. Elasticity confidence (25%) ────────────────────────────────────────
    if elasticity_pvalue > 0.10 or elasticity_rsq < 0.10:
        e_score = 1.0
        e_desc  = f"Low confidence (R²={elasticity_rsq:.2f}, p={elasticity_pvalue:.3f})"
    elif elasticity_pvalue < 0.05 and elasticity_rsq > 0.40:
        e_score = 0.1
        e_desc  = f"High confidence (R²={elasticity_rsq:.2f}, p={elasticity_pvalue:.3f})"
    else:
        e_score = 0.4
        e_desc  = f"Moderate confidence (R²={elasticity_rsq:.2f}, p={elasticity_pvalue:.3f})"
    factors.append(RiskFactor("Elasticity confidence", 0.25, e_score, e_desc))

    # ── 2. Data recency (20%) ─────────────────────────────────────────────────
    sku_sales = sales_df[sales_df["sku_id"] == sku_id]
    if sku_sales.empty:
        r_score = 1.0
        r_desc  = "No sales data found"
    else:
        most_recent = pd.to_datetime(sku_sales["date"]).max().date()
        today       = target_date or date.today()
        age_weeks   = max(0, (today - most_recent).days // 7)
        if age_weeks <= 4:
            r_score = 0.05
        elif age_weeks <= 13:
            r_score = 0.30
        elif age_weeks <= 26:
            r_score = 0.60
        else:
            r_score = 1.0
        r_desc = f"Most recent data: {most_recent} ({age_weeks} weeks ago)"
    factors.append(RiskFactor("Data recency", 0.20, r_score, r_desc))

    # ── 3. Cannibalization breadth (20%) ──────────────────────────────────────
    if n_cannibal_skus == 0:
        c_score = 0.05
        c_desc  = "No material cannibalization detected"
    elif n_cannibal_skus <= 2:
        c_score = 0.30
        c_desc  = f"Affects {n_cannibal_skus} related SKU(s)"
    elif n_cannibal_skus <= 4:
        c_score = 0.65
        c_desc  = f"Affects {n_cannibal_skus} related SKUs — moderate portfolio risk"
    else:
        c_score = 1.0
        c_desc  = f"Affects {n_cannibal_skus}+ SKUs — high portfolio risk"
    factors.append(RiskFactor("Cannibalization breadth", 0.20, c_score, c_desc))

    # ── 4. Discount depth vs. history (15%) ───────────────────────────────────
    sku_promos = promotions_df[promotions_df["sku_id"] == sku_id] if not promotions_df.empty else pd.DataFrame()
    if sku_promos.empty:
        d_score = 0.80
        d_desc  = "No historical promotions to validate this discount depth"
    else:
        max_hist_disc = float(sku_promos["discount_pct"].max())
        if discount_pct <= max_hist_disc * 0.80:
            d_score = 0.10
            d_desc  = f"Within well-tested range (max historical: {max_hist_disc*100:.0f}%)"
        elif discount_pct <= max_hist_disc * 1.10:
            d_score = 0.30
            d_desc  = f"Near edge of tested range (max historical: {max_hist_disc*100:.0f}%)"
        else:
            d_score = 0.85
            d_desc  = f"Deeper than any historical promo — untested territory"
    factors.append(RiskFactor("Discount depth vs history", 0.15, d_score, d_desc))

    # ── 5. Seasonal anomaly risk (10%) ────────────────────────────────────────
    if target_date is not None and seasonality_index:
        week_of_year    = target_date.isocalendar().week
        seas_multiplier = seasonality_index.get(int(week_of_year), 1.0)
        if seas_multiplier >= 2.5:
            s_score = 0.85
            s_desc  = f"Peak holiday period (×{seas_multiplier:.1f} baseline) — high estimation risk"
        elif seas_multiplier >= 1.5:
            s_score = 0.50
            s_desc  = f"Elevated seasonal demand (×{seas_multiplier:.1f} baseline)"
        elif seas_multiplier <= 0.70:
            s_score = 0.40
            s_desc  = f"Off-peak period (×{seas_multiplier:.1f} baseline) — lower absolute impact"
        else:
            s_score = 0.10
            s_desc  = f"Normal seasonal period (×{seas_multiplier:.1f} baseline)"
    else:
        s_score = 0.20
        s_desc  = "No seasonal context provided — using default"
    factors.append(RiskFactor("Seasonal anomaly risk", 0.10, s_score, s_desc))

    # ── 6. Category volatility (10%) ──────────────────────────────────────────
    if sku_sales.empty:
        v_score = 0.70
        v_desc  = "No data to assess volatility"
    else:
        non_promo = sku_sales[(sku_sales["is_promo"] == False) | (sku_sales["is_promo"].isna())]
        weekly_vol = non_promo.groupby("date")["units_sold"].sum()
        if len(weekly_vol) < 8:
            cv = 0.30
        else:
            mean = weekly_vol.mean()
            std  = weekly_vol.std()
            cv   = float(std / mean) if mean > 0 else 0.30
        if cv <= 0.15:
            v_score = 0.05
            v_desc  = f"Very stable demand (CV={cv:.2f})"
        elif cv <= 0.30:
            v_score = 0.30
            v_desc  = f"Moderate demand variability (CV={cv:.2f})"
        elif cv <= 0.50:
            v_score = 0.65
            v_desc  = f"High demand variability (CV={cv:.2f})"
        else:
            v_score = 0.90
            v_desc  = f"Very volatile demand (CV={cv:.2f}) — forecast uncertainty is high"
    factors.append(RiskFactor("Category volatility", 0.10, v_score, v_desc))

    # ── Composite ─────────────────────────────────────────────────────────────
    total = round(sum(f.weighted_score for f in factors), 3)
    total = float(np.clip(total, 0.0, 1.0))

    if total <= 0.30:
        band = "LOW"
    elif total <= 0.60:
        band = "MEDIUM"
    else:
        band = "HIGH"

    dominant = max(factors, key=lambda f: f.raw_score * f.weight).name

    return RiskResult(
        total_score=total,
        band=band,
        factors=factors,
        dominant_risk=dominant,
    )

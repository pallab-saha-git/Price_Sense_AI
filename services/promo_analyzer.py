"""
services/promo_analyzer.py
───────────────────────────
Orchestrates all 5 ML models into a single unified result dict.

Input:  sku_id, discount_pct, start_date, end_date, channels
Output: PromoAnalysisResult (dataclass with all metrics)

This is the single entry point called by Dash callbacks.
All models are called here; results are assembled and returned.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd
from loguru import logger

from models.cannibalization import CannibalizationResult, compute_cannibalization
from models.demand_forecast import ForecastResult, forecast_baseline
from models.elasticity import ElasticityResult, estimate_elasticity, estimate_volume_lift
from models.profit_calculator import PromoPnL, calculate_promo_pnl, find_optimal_discount
from models.risk_scorer import RiskResult, score_risk


@dataclass
class PromoAnalysisResult:
    # Inputs
    sku_id:       str
    discount_pct: float
    start_date:   date
    end_date:     date

    # Sub-model results
    elasticity:      ElasticityResult
    cannibalization: CannibalizationResult
    forecast:        ForecastResult
    pnl:             PromoPnL
    risk:            RiskResult

    # Top-level derived
    recommendation:       str    # 'RECOMMENDED' | 'MARGINAL' | 'NOT_RECOMMENDED'
    recommendation_label: str    # Human-readable label
    alt_discount_pct:     Optional[float] = None   # Better discount if not recommended
    alt_pnl:              Optional[PromoPnL] = None

    @property
    def lift_pct(self) -> float:
        return round(estimate_volume_lift(self.elasticity.elasticity, self.discount_pct) * 100, 1)

    @property
    def lift_units(self) -> float:
        return self.pnl.incremental_units

    @property
    def net_incremental_profit(self) -> float:
        return self.pnl.net_incremental_profit

    @property
    def promo_roi(self) -> float:
        return self.pnl.promo_roi

    @property
    def risk_score(self) -> float:
        return self.risk.total_score

    @property
    def risk_band(self) -> str:
        return self.risk.band


# ── In-process data cache (loaded once, reused across callbacks) ───────────────
_cache: dict = {}


def _load_data() -> dict:
    """Load all data tables once and cache them."""
    global _cache
    if _cache:
        return _cache

    from data.database import get_session
    from data.database import (
        Product, Store, Sale, Promotion,
        CalendarEvent, SeasonalityIndex, CompetitorEvent,
    )
    from sqlalchemy import func

    session = get_session()
    try:
        products_rows = session.query(Product).all()
        promos_rows   = session.query(Promotion).all()
        sales_rows    = session.query(Sale).limit(500_000).all()
        calendar_rows = session.query(CalendarEvent).all()
        seas_rows     = session.query(SeasonalityIndex).all()

        def _to_df(rows, cls):
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame([{c.key: getattr(r, c.key) for c in cls.__table__.columns} for r in rows])

        products_df  = _to_df(products_rows, Product)
        promos_df    = _to_df(promos_rows,   Promotion)
        sales_df     = _to_df(sales_rows,    Sale)
        calendar_df  = _to_df(calendar_rows, CalendarEvent)
        seas_df      = _to_df(seas_rows,     SeasonalityIndex)

        # Type coercions
        if not sales_df.empty:
            sales_df["date"]     = pd.to_datetime(sales_df["date"])
            sales_df["is_promo"] = sales_df["is_promo"].astype(bool)
        if not promos_df.empty:
            promos_df["start_date"] = pd.to_datetime(promos_df["start_date"])
            promos_df["end_date"]   = pd.to_datetime(promos_df["end_date"])
        if not calendar_df.empty:
            calendar_df["date"] = pd.to_datetime(calendar_df["date"])

        _cache = {
            "products":  products_df,
            "promos":    promos_df,
            "sales":     sales_df,
            "calendar":  calendar_df,
            "seas":      seas_df,
        }
        logger.info("Data loaded into analyzer cache")
    finally:
        session.close()

    return _cache


def invalidate_cache():
    """Call this if the underlying data changes."""
    global _cache
    _cache = {}


def analyze_promotion(
    sku_id:       str,
    discount_pct: float,
    start_date:   date,
    end_date:     date,
    channels:     list[str] | None = None,
    store_ids:    list[str] | None = None,
) -> PromoAnalysisResult:
    """
    Full promotion analysis pipeline.

    Steps:
      1. Load / fetch data
      2. Estimate price elasticity
      3. Forecast demand baseline
      4. Compute volume lift
      5. Compute cannibalization
      6. Calculate full P&L
      7. Score risk
      8. Find alternative (better) discount if current is not recommended

    Returns PromoAnalysisResult with all outputs.
    """
    data        = _load_data()
    sales_df    = data["sales"]
    products_df = data["products"]
    promos_df   = data["promos"]
    calendar_df = data["calendar"]
    seas_df     = data["seas"]

    promo_weeks = max(1, (end_date - start_date).days // 7 + 1)

    # Filter by store if requested
    if store_ids:
        sales_for_model = sales_df[sales_df["store_id"].isin(store_ids)]
    else:
        sales_for_model = sales_df

    # ── 1. Elasticity ─────────────────────────────────────────────────────────
    logger.info(f"Computing elasticity for {sku_id}")
    elasticity_result = estimate_elasticity(sales_for_model, sku_id, seas_df)

    # ── 2. Demand forecast (baseline) ─────────────────────────────────────────
    logger.info(f"Forecasting baseline for {sku_id}")
    forecast_result = forecast_baseline(sales_for_model, sku_id, periods=promo_weeks + 4, calendar_df=calendar_df)

    # Get seasonality multiplier for the promo start week
    target_week = start_date.isocalendar().week
    seas_index  = forecast_result.seasonality_index
    seas_mult   = seas_index.get(int(target_week), 1.0)

    # Baseline volume (seasonality-adjusted)
    baseline = forecast_result.baseline_weekly * seas_mult

    # ── 3. Volume lift ────────────────────────────────────────────────────────
    lift_pct = estimate_volume_lift(elasticity_result.elasticity, discount_pct)

    # ── 4. Cannibalization ────────────────────────────────────────────────────
    logger.info(f"Computing cannibalization for {sku_id}")
    cannibal_result = compute_cannibalization(
        focal_sku_id=sku_id,
        discount_pct=discount_pct,
        sales_df=sales_for_model,
        products_df=products_df,
        use_regression=True,
    )

    # ── 5. P&L ────────────────────────────────────────────────────────────────
    product_info = products_df[products_df["sku_id"] == sku_id].iloc[0] if not products_df.empty else None
    regular_price = float(product_info["regular_price"]) if product_info is not None else 10.0
    cost_price    = float(product_info["cost_price"]) if product_info is not None else 5.0
    product_name  = str(product_info["product_name"]) if product_info is not None else sku_id

    pnl = calculate_promo_pnl(
        sku_id=sku_id,
        product_name=product_name,
        regular_price=regular_price,
        cost_price=cost_price,
        discount_pct=discount_pct,
        baseline_weekly_units=baseline,
        volume_lift_pct=lift_pct,
        promo_weeks=promo_weeks,
        cannibalization_cost=cannibal_result.total_margin_loss,
    )

    # ── 6. Risk ───────────────────────────────────────────────────────────────
    risk_result = score_risk(
        sku_id=sku_id,
        discount_pct=discount_pct,
        elasticity_rsq=elasticity_result.r_squared,
        elasticity_pvalue=elasticity_result.p_value,
        n_cannibal_skus=len(cannibal_result.impacts),
        sales_df=sales_for_model,
        promotions_df=promos_df,
        target_date=start_date,
        seasonality_index=seas_index,
    )

    # ── 7. Recommendation ─────────────────────────────────────────────────────
    recommendation = pnl.recommendation_tier
    if recommendation == "RECOMMENDED":
        label = "✅ RECOMMENDED"
    elif recommendation == "MARGINAL":
        label = "⚠️ MARGINAL — review before running"
    else:
        label = "❌ NOT RECOMMENDED — see alternative"

    # ── 8. Alternative discount ───────────────────────────────────────────────
    alt_discount = None
    alt_pnl_obj  = None

    if recommendation != "RECOMMENDED":
        # Find the best discount level
        from config.settings import SCENARIO_DISCOUNTS
        cannibal_per_pct = cannibal_result.total_margin_loss / (discount_pct + 1e-9)
        alt_discount, alt_pnl_obj = find_optimal_discount(
            sku_id=sku_id,
            product_name=product_name,
            regular_price=regular_price,
            cost_price=cost_price,
            baseline_weekly_units=baseline,
            elasticity=elasticity_result.elasticity,
            cannibalization_cost_per_pct=cannibal_per_pct,
            discount_levels=SCENARIO_DISCOUNTS,
        )
        if alt_discount == discount_pct:
            alt_discount = None  # no better alternative found
            alt_pnl_obj  = None

    return PromoAnalysisResult(
        sku_id=sku_id,
        discount_pct=discount_pct,
        start_date=start_date,
        end_date=end_date,
        elasticity=elasticity_result,
        cannibalization=cannibal_result,
        forecast=forecast_result,
        pnl=pnl,
        risk=risk_result,
        recommendation=recommendation,
        recommendation_label=label,
        alt_discount_pct=alt_discount,
        alt_pnl=alt_pnl_obj,
    )

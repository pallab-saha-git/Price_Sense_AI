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

    # Segment intelligence
    segment_summary:      list   = field(default_factory=list)  # per-segment share/response
    seg_multiplier:       float  = 1.0    # weighted promo response multiplier

    # Channel/store scope applied
    channels_used:        Optional[list] = None
    store_ids_used:       Optional[list] = None

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
        CalendarEvent, SeasonalityIndex, CompetitorEvent, CustomerSegment,
    )
    from sqlalchemy import func

    session = get_session()
    try:
        products_rows  = session.query(Product).all()
        promos_rows    = session.query(Promotion).all()
        sales_rows     = session.query(Sale).limit(500_000).all()
        calendar_rows  = session.query(CalendarEvent).all()
        seas_rows      = session.query(SeasonalityIndex).all()
        stores_rows    = session.query(Store).all()
        segments_rows  = session.query(CustomerSegment).all()

        def _to_df(rows, cls):
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame([{c.key: getattr(r, c.key) for c in cls.__table__.columns} for r in rows])

        products_df  = _to_df(products_rows, Product)
        promos_df    = _to_df(promos_rows,   Promotion)
        sales_df     = _to_df(sales_rows,    Sale)
        calendar_df  = _to_df(calendar_rows, CalendarEvent)
        seas_df      = _to_df(seas_rows,     SeasonalityIndex)
        stores_df    = _to_df(stores_rows,   Store)
        segments_df  = _to_df(segments_rows, CustomerSegment)

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
            "stores":    stores_df,
            "segments":  segments_df,
        }
        logger.info("Data loaded into analyzer cache (products={}, stores={}, segments={})",
                    len(products_df), len(stores_df), len(segments_df))
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
    stores_df   = data.get("stores", pd.DataFrame())
    segments_df = data.get("segments", pd.DataFrame())

    promo_weeks = max(1, (end_date - start_date).days // 7 + 1)

    # ── Channel-specific configuration ─────────────────────────────────────────
    # Online shoppers are typically more price-elastic and have a different
    # demand baseline than physical store customers.
    CHANNEL_ELASTICITY_FACTORS = {
        "online":   1.18,   # online customers are ~18% more price-sensitive
        "physical": 1.00,   # physical is the reference baseline
        "mixed":    1.06,   # blended when both channels are active
    }
    CHANNEL_BASELINE_FACTORS = {
        "online":   0.08,   # online drives ~8% of total retail volume (1 virtual store)
        "physical": 0.92,   # physical stores dominate foot-traffic volume
        "mixed":    1.00,   # combined — use full baseline
    }

    channels_set  = set(channels) if channels else {"physical", "online"}
    if channels_set == {"online"}:
        ch_mode = "online"
    elif channels_set == {"physical"}:
        ch_mode = "physical"
    else:
        ch_mode = "mixed"

    elasticity_ch_factor = CHANNEL_ELASTICITY_FACTORS[ch_mode]
    baseline_ch_factor   = CHANNEL_BASELINE_FACTORS[ch_mode]

    # Apply channel filter to sales FIRST, then store filter
    sales_for_model = sales_df
    if ch_mode != "mixed":
        if "channel" in sales_df.columns:
            sales_for_model = sales_df[sales_df["channel"] == ch_mode]
            if sales_for_model.empty:
                # Fallback: use all data but apply the factor adjustment only
                logger.warning(f"No sales rows for channel='{ch_mode}', using all stores with factor adjustment")
                sales_for_model = sales_df

    # Store filter applied AFTER channel filter (channel takes precedence)
    if store_ids:
        store_filtered = sales_for_model[sales_for_model["store_id"].isin(store_ids)]
        # Only apply store filter if it produces data; otherwise keep channel-filtered set
        if not store_filtered.empty:
            sales_for_model = store_filtered
        else:
            logger.warning(f"store_ids {store_ids} returned no rows for channel={ch_mode}; using channel-only filter")

    # Compute segment-weighted promo response multiplier for selected stores
    seg_multiplier = 1.0
    segment_summary: list[dict] = []
    if not segments_df.empty:
        seg_scope = segments_df
        if store_ids:
            seg_scope = segments_df[segments_df["store_id"].isin(store_ids)]
        if not seg_scope.empty:
            for seg_name, grp in seg_scope.groupby("segment_name"):
                avg_share  = grp["segment_share_pct"].mean()
                avg_resp   = grp["promo_response_multiplier"].mean()
                avg_elast  = grp["price_elasticity"].mean()
                avg_cann   = grp["cannibalization_susceptibility"].mean()
                segment_summary.append({
                    "segment":    seg_name,
                    "share_pct":  round(avg_share, 1),
                    "response":   round(avg_resp, 2),
                    "elasticity": round(avg_elast, 2),
                    "cann_risk":  round(avg_cann, 2),
                })
            # Weighted response multiplier (share-weighted)
            total_share = sum(s["share_pct"] for s in segment_summary)
            if total_share > 0:
                seg_multiplier = sum(
                    s["share_pct"] * s["response"] for s in segment_summary
                ) / total_share

    # ── 1. Elasticity ─────────────────────────────────────────────────────────
    logger.info(f"Computing elasticity for {sku_id} (channel={ch_mode})")
    elasticity_result = estimate_elasticity(sales_for_model, sku_id, seas_df)

    # Apply channel-specific elasticity adjustment
    # Online customers are more price-sensitive; physical shoppers less so
    if elasticity_ch_factor != 1.0:
        import dataclasses
        elasticity_result = dataclasses.replace(
            elasticity_result,
            elasticity=elasticity_result.elasticity * elasticity_ch_factor,
        )

    # ── 2. Demand forecast (baseline) ─────────────────────────────────────────
    logger.info(f"Forecasting baseline for {sku_id}")
    forecast_result = forecast_baseline(sales_for_model, sku_id, periods=promo_weeks + 4, calendar_df=calendar_df)

    # Get seasonality multiplier for the promo start week
    target_week = start_date.isocalendar().week
    seas_index  = forecast_result.seasonality_index
    seas_mult   = seas_index.get(int(target_week), 1.0)

    # Baseline volume (seasonality-adjusted + channel-adjusted)
    baseline = forecast_result.baseline_weekly * seas_mult
    # Scale baseline to reflect the channel scope (online-only is a fraction of total)
    if ch_mode == "online" and baseline_ch_factor < 1.0:
        # Online store has 1.8x per-store factor but is 1 store vs 25 physical
        # baseline_ch_factor captures this proportionality
        baseline = max(baseline, forecast_result.baseline_weekly / 25 * 1.8)

    # ── 3. Volume lift ────────────────────────────────────────────────────────
    lift_pct = estimate_volume_lift(elasticity_result.elasticity, discount_pct)
    # Apply segment-weighted promo response multiplier (scales lift by customer mix)
    lift_pct = lift_pct * seg_multiplier

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
        label = "RECOMMENDED"
    elif recommendation == "MARGINAL":
        label = "MARGINAL — review before running"
    else:
        label = "NOT RECOMMENDED — see alternative"

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
        segment_summary=segment_summary,
        seg_multiplier=seg_multiplier,
        channels_used=channels,
        store_ids_used=store_ids,
    )

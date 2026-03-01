"""
services/scenario_engine.py
────────────────────────────
Runs the full analyzer across multiple discount levels and returns
a side-by-side comparison — used by the scenario comparison page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from loguru import logger

from config.settings import SCENARIO_DISCOUNTS
from services.promo_analyzer import PromoAnalysisResult, analyze_promotion


@dataclass
class ScenarioRow:
    discount_pct:          float
    discount_label:        str        # "25% off"
    lift_pct:              float      # +42%
    lift_units:            float
    incremental_revenue:   float
    net_incremental_profit: float
    promo_roi:             float
    risk_band:             str
    risk_score:            float
    cannibalization_cost:  float
    recommendation:        str
    is_optimal:            bool       # highest net_incremental_profit among positive scenarios


@dataclass
class ScenarioComparisonResult:
    sku_id:            str
    product_name:      str
    scenarios:         list[ScenarioRow]
    optimal_discount:  Optional[float]
    optimal_row:       Optional[ScenarioRow]
    full_results:      dict[float, PromoAnalysisResult]   # keyed by discount_pct


def compare_scenarios(
    sku_id:        str,
    start_date:    date,
    end_date:      date,
    discount_levels: list[float] | None = None,
    channels:      list[str] | None = None,
    store_ids:     list[str] | None = None,
) -> ScenarioComparisonResult:
    """
    Run the full promotion analyzer for each discount level and return
    a structured comparison.

    OPTIMIZED: Elasticity and forecast are computed only once (they don't
    depend on discount level), then P&L and risk are recomputed per scenario.

    Parameters
    ----------
    sku_id          : Focal SKU
    start_date      : Promo start date
    end_date        : Promo end date
    discount_levels : List of discount fractions (e.g. [0.10, 0.15, 0.20, 0.25, 0.30])
    """
    if discount_levels is None:
        discount_levels = SCENARIO_DISCOUNTS

    from services.promo_analyzer import _load_data
    from services.promo_analyzer import analyze_promotion
    from models.elasticity import estimate_volume_lift
    from models.profit_calculator import calculate_promo_pnl
    from models.risk_scorer import score_risk
    from models.cannibalization import compute_cannibalization
    
    import pandas as pd
    
    data        = _load_data()
    products_df = data["products"]

    product_info = products_df[products_df["sku_id"] == sku_id]
    product_name = product_info.iloc[0]["product_name"] if not product_info.empty else sku_id

    # ── Run full analysis ONCE for the first discount to get elasticity/forecast ──
    logger.info(f"Scenario comparison: computing base models for {sku_id}")
    base_result = analyze_promotion(
        sku_id=sku_id,
        discount_pct=discount_levels[0],
        start_date=start_date,
        end_date=end_date,
        channels=channels,
        store_ids=store_ids,
    )
    
    # Extract reusable components (discount-independent)
    elasticity_result = base_result.elasticity
    forecast_result   = base_result.forecast
    segment_summary   = base_result.segment_summary
    seg_multiplier    = base_result.seg_multiplier
    data_quality      = base_result.data_quality
    
    # Product info for P&L
    if not product_info.empty:
        regular_price = float(product_info.iloc[0]["regular_price"])
        cost_price    = float(product_info.iloc[0]["cost_price"])
    else:
        regular_price = 10.0
        cost_price    = 5.0
    
    promo_weeks = max(1, (end_date - start_date).days // 7 + 1)
    baseline_weekly = forecast_result.baseline_weekly
    
    # Get seasonality multiplier for the promo start week
    target_week = start_date.isocalendar().week
    seas_index  = forecast_result.seasonality_index
    seas_mult   = seas_index.get(int(target_week), 1.0)
    baseline_adjusted = baseline_weekly * seas_mult

    # ── Now loop over discount levels — only recompute P&L, risk, cannibalization ──
    rows: list[ScenarioRow] = []
    full: dict[float, PromoAnalysisResult] = {}
    
    sales_df = data["sales"]
    promos_df = data["promos"]

    for disc in discount_levels:
        logger.info(f"Scenario: {sku_id} @ {disc*100:.0f}% off")
        try:
            # Recompute volume lift for this discount
            lift_pct = estimate_volume_lift(elasticity_result.elasticity, disc) * seg_multiplier
            
            # Recompute cannibalization for this discount
            cannibal_result = compute_cannibalization(
                focal_sku_id=sku_id,
                discount_pct=disc,
                sales_df=sales_df,
                products_df=products_df,
                use_regression=True,
            )
            
            # Compute P&L
            pnl = calculate_promo_pnl(
                sku_id=sku_id,
                product_name=product_name,
                regular_price=regular_price,
                cost_price=cost_price,
                discount_pct=disc,
                baseline_weekly_units=baseline_adjusted,
                volume_lift_pct=lift_pct,
                promo_weeks=promo_weeks,
                cannibalization_cost=cannibal_result.total_margin_loss,
            )
            pnl.data_quality = data_quality
            
            # Compute risk
            risk_result = score_risk(
                sku_id=sku_id,
                discount_pct=disc,
                elasticity_rsq=elasticity_result.r_squared,
                elasticity_pvalue=elasticity_result.p_value,
                n_cannibal_skus=len(cannibal_result.impacts),
                sales_df=sales_df,
                promotions_df=promos_df,
                target_date=start_date,
                seasonality_index=seas_index,
            )
            
            # Build full result object for this scenario
            from services.promo_analyzer import PromoAnalysisResult
            result = PromoAnalysisResult(
                sku_id=sku_id,
                discount_pct=disc,
                start_date=start_date,
                end_date=end_date,
                elasticity=elasticity_result,
                cannibalization=cannibal_result,
                forecast=forecast_result,
                pnl=pnl,
                risk=risk_result,
                recommendation=pnl.recommendation_tier,
                recommendation_label=pnl.recommendation_tier,
                segment_summary=segment_summary,
                seg_multiplier=seg_multiplier,
                data_quality=data_quality,
                channels_used=channels,
                store_ids_used=store_ids,
            )
            
            full[disc] = result
            rows.append(ScenarioRow(
                discount_pct=disc,
                discount_label=f"{disc*100:.0f}% off",
                lift_pct=lift_pct * 100,  # convert to percentage
                lift_units=pnl.incremental_units,
                incremental_revenue=pnl.incremental_revenue,
                net_incremental_profit=pnl.net_incremental_profit,
                promo_roi=pnl.promo_roi,
                risk_band=risk_result.band,
                risk_score=risk_result.total_score,
                cannibalization_cost=cannibal_result.total_margin_loss,
                recommendation=pnl.recommendation_tier,
                is_optimal=False,  # set below
            ))
        except Exception as exc:
            logger.error(f"Scenario analysis failed for {disc}: {exc}")

    # Mark optimal (best positive net_incremental_profit)
    positive_rows = [r for r in rows if r.net_incremental_profit > 0]
    optimal_disc  = None
    optimal_row   = None

    if positive_rows:
        optimal_row  = max(positive_rows, key=lambda r: r.net_incremental_profit)
        optimal_disc = optimal_row.discount_pct
        for r in rows:
            r.is_optimal = (r.discount_pct == optimal_disc)

    return ScenarioComparisonResult(
        sku_id=sku_id,
        product_name=product_name,
        scenarios=rows,
        optimal_discount=optimal_disc,
        optimal_row=optimal_row,
        full_results=full,
    )


def scenarios_to_dataframe(comparison: ScenarioComparisonResult) -> "pd.DataFrame":
    """Convert ScenarioComparisonResult to a flat DataFrame for Dash AgGrid."""
    import pandas as pd

    def _badge(rec: str) -> str:
        return {"RECOMMENDED": "OK", "MARGINAL": "MARG", "NOT_RECOMMENDED": "NO", "INSUFFICIENT_DATA": "N/A"}.get(rec, "")

    data = []
    for r in comparison.scenarios:
        data.append({
            "Discount":         r.discount_label,
            "Volume Lift":      f"+{r.lift_pct:.0f}%",
            "Incremental Units": f"{r.lift_units:,.0f}",
            "Incr. Revenue":    f"${r.incremental_revenue:,.0f}",
            "Net Profit":       f"${r.net_incremental_profit:,.0f}",
            "ROI":              f"{r.promo_roi:.1f}x",
            "Cannibal. Cost":   f"${r.cannibalization_cost:,.0f}",
            "Risk":             r.risk_band,
            "Decision":         _badge(r.recommendation) + " " + r.recommendation.replace("_", " ").title(),
            "Optimal?":         "Best" if r.is_optimal else "",
            # Raw values for sorting / styling
            "_profit_raw":      r.net_incremental_profit,
            "_discount_raw":    r.discount_pct,
            "_roi_raw":         r.promo_roi,
        })

    return pd.DataFrame(data)

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
    data        = _load_data()
    products_df = data["products"]

    product_info = products_df[products_df["sku_id"] == sku_id]
    product_name = product_info.iloc[0]["product_name"] if not product_info.empty else sku_id

    rows: list[ScenarioRow] = []
    full: dict[float, PromoAnalysisResult] = {}

    for disc in discount_levels:
        logger.info(f"Scenario: {sku_id} @ {disc*100:.0f}% off")
        try:
            result = analyze_promotion(
                sku_id=sku_id,
                discount_pct=disc,
                start_date=start_date,
                end_date=end_date,
                channels=channels,
                store_ids=store_ids,
            )
            full[disc] = result
            rows.append(ScenarioRow(
                discount_pct=disc,
                discount_label=f"{disc*100:.0f}% off",
                lift_pct=result.lift_pct,
                lift_units=result.pnl.incremental_units,
                incremental_revenue=result.pnl.incremental_revenue,
                net_incremental_profit=result.pnl.net_incremental_profit,
                promo_roi=result.pnl.promo_roi,
                risk_band=result.risk.band,
                risk_score=result.risk.total_score,
                cannibalization_cost=result.cannibalization.total_margin_loss,
                recommendation=result.recommendation,
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
        return {"RECOMMENDED": "✅", "MARGINAL": "⚠️", "NOT_RECOMMENDED": "❌"}.get(rec, "")

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
            "Optimal?":         "⭐ Best" if r.is_optimal else "",
            # Raw values for sorting / styling
            "_profit_raw":      r.net_incremental_profit,
            "_discount_raw":    r.discount_pct,
            "_roi_raw":         r.promo_roi,
        })

    return pd.DataFrame(data)

"""
components/recommendation_card.py
───────────────────────────────────
Dash card showing Go/No-Go headline + key metrics.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import dash_bootstrap_components as dbc
from dash import html

if TYPE_CHECKING:
    from services.promo_analyzer import PromoAnalysisResult


_REC_STYLES = {
    "RECOMMENDED":     ("success", "RECOMMENDED"),
    "MARGINAL":        ("warning", "MARGINAL"),
    "NOT_RECOMMENDED": ("danger",  "NOT RECOMMENDED"),
}


def _metric_col(label: str, value: str, sub: str = "", color: str = "text-dark") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.P(label, className="text-muted mb-1", style={"fontSize": "12px"}),
                    html.H4(value, className=f"fw-bold mb-0 {color}"),
                    html.Small(sub, className="text-muted") if sub else None,
                ],
                className="text-center p-2",
            ),
            className="h-100 border-0 bg-light",
        ),
        xs=6, sm=4, md=2,
    )


def recommendation_card(result: "PromoAnalysisResult") -> dbc.Card:
    rec_color, rec_label = _REC_STYLES.get(result.recommendation, ("secondary", result.recommendation))

    # Format metrics
    lift_str    = f"+{result.lift_pct:.0f}%  (+{result.pnl.incremental_units:,.0f} units)"
    profit_str  = f"${result.pnl.net_incremental_profit:,.0f}"
    profit_col  = "text-success" if result.pnl.net_incremental_profit >= 0 else "text-danger"
    roi_str     = f"{result.pnl.promo_roi:.1f}x"
    roi_col     = "text-success" if result.pnl.promo_roi >= 1.0 else "text-danger"
    cannibal    = f"-${result.cannibalization.total_margin_loss:,.0f}" if result.cannibalization.has_cannibalization else "$0"
    risk_str    = f"{result.risk.band}  ({result.risk.total_score:.2f})"
    risk_col    = {"LOW": "text-success", "MEDIUM": "text-warning", "HIGH": "text-danger"}.get(result.risk.band, "")

    # Confidence interval on elasticity → volume lift range
    el          = result.elasticity
    lift_lo     = round(abs(el.conf_int_low)  * result.discount_pct * 100, 0)
    lift_hi     = round(abs(el.conf_int_high) * result.discount_pct * 100, 0)
    if lift_lo > lift_hi:
        lift_lo, lift_hi = lift_hi, lift_lo
    ci_str      = f"+{lift_lo:.0f}% – +{lift_hi:.0f}%"
    ci_note     = "95% CI" if el.is_reliable else "est. (low data)"
    ci_col      = "text-success" if el.is_reliable else "text-warning"

    # Segment multiplier badge
    seg_mult    = getattr(result, "seg_multiplier", 1.0)
    seg_str     = f"{seg_mult:.2f}x" if seg_mult != 1.0 else "1.00x (all stores)"
    seg_col     = "text-success" if seg_mult >= 1.0 else "text-warning"

    # Scope badge — shows exactly what store/channel scope was analysed
    channels_used = result.channels_used or ["physical", "online"]
    ch_label = " + ".join(c.title() for c in sorted(channels_used))
    store_ids_used = getattr(result, "store_ids_used", None)
    if store_ids_used:
        store_label = f"{len(store_ids_used)} store(s): {', '.join(store_ids_used)}"
    else:
        store_label = "All Stores"
    scope_badge = html.Div(
        [
            dbc.Badge(f"📍 {store_label}", color="light", text_color="dark", className="me-2"),
            dbc.Badge(f"📡 {ch_label}", color="light", text_color="dark", className="me-2"),
            dbc.Badge(
                f"Baseline: {result.forecast.baseline_weekly:,.0f} units/wk",
                color="light", text_color="dark",
            ),
        ],
        className="mt-2 mb-1",
    )

    # Alternative suggestion row
    alt_block = html.Div()
    if result.alt_discount_pct and result.alt_pnl:
        alt_block = dbc.Alert(
            [
                html.Strong("Suggestion: "),
                f"Try {result.alt_discount_pct*100:.0f}% off instead — "
                f"projected net profit: ${result.alt_pnl.net_incremental_profit:,.0f} "
                f"(ROI: {result.alt_pnl.promo_roi:.1f}x) with less margin erosion.",
            ],
            color="info",
            className="mt-3 mb-0 py-2 px-3",
            style={"fontSize": "14px"},
        )

    return dbc.Card(
        [
            # Header: recommendation badge
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(
                            html.H4(rec_label, className="mb-0 text-white fw-bold"),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Badge(result.risk.band + " RISK", color=rec_color, className="ms-2 align-self-center"),
                            width="auto",
                        ),
                        dbc.Col(
                            html.Small(
                                f"{result.pnl.product_name}  ·  "
                                f"{result.discount_pct*100:.0f}% off  ·  "
                                f"{result.start_date} → {result.end_date}",
                                className="text-white-50",
                            ),
                            className="ms-auto align-self-center text-end",
                        ),
                    ],
                    align="center",
                ),
                style={
                    "background": {
                        "RECOMMENDED": "linear-gradient(135deg, #1a5276, #27ae60)",
                        "MARGINAL":    "linear-gradient(135deg, #7d6608, #f39c12)",
                        "NOT_RECOMMENDED": "linear-gradient(135deg, #7b241c, #e74c3c)",
                    }.get(result.recommendation, "#333"),
                },
            ),

            # Metrics row
            dbc.CardBody(
                [
                    scope_badge,
                    html.Hr(className="my-2"),
                    dbc.Row(
                        [
                            _metric_col("Volume Lift",          lift_str),
                            _metric_col("Lift Range (95% CI)",  ci_str,    ci_note,           ci_col),
                            _metric_col("Cannibalization",      cannibal,  "margin cost",      "text-warning"),
                            _metric_col("Net Incr. Profit",     profit_str, "",                profit_col),
                            _metric_col("Promo ROI",            roi_str,   "",                 roi_col),
                            _metric_col("Risk Score",           risk_str,  "",                 risk_col),
                            _metric_col("Segment Response",     seg_str,   "customer mix adj", seg_col),
                            _metric_col("Net Incr. Revenue",    f"${result.pnl.incremental_revenue:,.0f}"),
                        ],
                        className="g-2",
                    ),
                    alt_block,
                ]
            ),
        ],
        className="shadow mb-3",
    )


def empty_recommendation_card() -> dbc.Card:
    """Placeholder card before any analysis has been run."""
    return dbc.Card(
        dbc.CardBody(
            html.Div(
                [
                    html.H5("Configure a promotion and click 'Analyze' to see results.",
                            className="text-muted text-center mt-5"),
                    html.P("Results will appear here.", className="text-muted text-center"),
                ],
                className="py-5",
            )
        ),
        className="shadow-sm",
    )

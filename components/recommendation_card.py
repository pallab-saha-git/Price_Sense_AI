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
    "RECOMMENDED":       ("success", "RECOMMENDED"),
    "MARGINAL":          ("warning", "MARGINAL"),
    "NOT_RECOMMENDED":   ("danger",  "NOT RECOMMENDED"),
    "INSUFFICIENT_DATA": ("secondary", "NOT ENOUGH DATA"),
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

    # ── Insufficient data → show a clear, distinct card ────────────────────────
    if result.recommendation == "INSUFFICIENT_DATA":
        return _insufficient_data_card(result, rec_color, rec_label)

    # Format metrics
    lift_str    = f"+{result.lift_pct:.0f}%  (+{result.pnl.incremental_units:,.0f} units)"
    profit_str  = f"${result.pnl.net_incremental_profit:,.0f}"
    profit_col  = "text-success" if result.pnl.net_incremental_profit >= 0 else "text-danger"
    roi_str     = f"{result.pnl.promo_roi:.1f}x"
    roi_col     = "text-success" if result.pnl.promo_roi >= 0.0 else "text-danger"
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

    # Limited-data warning banner (when data_quality="limited" but not insufficient)
    data_quality = getattr(result, "data_quality", "good")
    limited_data_banner = html.Div()
    if data_quality == "limited":
        limited_data_banner = dbc.Alert(
            [
                html.I(className="fas fa-info-circle me-2"),
                html.Strong("Limited data: "),
                "Estimates are based on limited historical data. "
                "Metrics carry higher uncertainty than usual. "
                f"({result.elasticity.n_observations} elasticity obs, "
                f"{getattr(result.forecast, 'n_weeks_used', '?')} forecast weeks)",
            ],
            color="info",
            className="mt-2 mb-0 py-2 px-3",
            style={"fontSize": "13px"},
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
                        "INSUFFICIENT_DATA": "linear-gradient(135deg, #4a5568, #718096)",
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
                    limited_data_banner,
                ]
            ),
        ],
        className="shadow mb-3",
    )


def _insufficient_data_card(result: "PromoAnalysisResult", rec_color: str, rec_label: str) -> dbc.Card:
    """Card displayed when there is not enough historical data for a reliable assessment."""
    channels_used = result.channels_used or ["physical", "online"]
    ch_label = " + ".join(c.title() for c in sorted(channels_used))
    store_ids_used = getattr(result, "store_ids_used", None)
    if store_ids_used:
        store_label = f"{len(store_ids_used)} store(s): {', '.join(store_ids_used)}"
    else:
        store_label = "All Stores"

    elast_obs = result.elasticity.n_observations
    forecast_weeks = getattr(result.forecast, "n_weeks_used", 0)
    model_used = result.forecast.model_used

    details = []
    if elast_obs < 12:
        details.append(f"Only {elast_obs} sales observations found for elasticity (need 12+)")
    if forecast_weeks < 12:
        details.append(f"Only {forecast_weeks} non-promo weeks available for baseline forecast (need 12+)")
    if not details:
        details.append("Insufficient variation in historical prices or sales volume")

    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(
                            html.H4(rec_label, className="mb-0 text-white fw-bold"),
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
                style={"background": "linear-gradient(135deg, #4a5568, #718096)"},
            ),
            dbc.CardBody([
                html.Div(
                    [
                        dbc.Badge(f"📍 {store_label}", color="light", text_color="dark", className="me-2"),
                        dbc.Badge(f"📡 {ch_label}", color="light", text_color="dark"),
                    ],
                    className="mb-3",
                ),
                dbc.Alert(
                    [
                        html.H5([
                            html.I(className="fas fa-exclamation-triangle me-2"),
                            "Insufficient Data for Reliable Assessment",
                        ], className="alert-heading mb-2"),
                        html.P(
                            "There is not enough historical sales data for this SKU "
                            "in the selected channel/store scope to produce reliable "
                            "promotion metrics. The numbers below are rough estimates only.",
                            className="mb-2",
                        ),
                        html.Ul([html.Li(d) for d in details], className="mb-0"),
                    ],
                    color="warning",
                    className="mb-3",
                ),
                html.H6("Rough Estimates (low confidence)", className="text-muted mb-2"),
                dbc.Row(
                    [
                        _metric_col("Baseline",      f"{result.forecast.baseline_weekly:,.0f} u/wk", model_used, "text-muted"),
                        _metric_col("Est. Lift",      f"+{result.lift_pct:.0f}%",  "very uncertain", "text-muted"),
                        _metric_col("Elasticity Obs", f"{elast_obs}",              "observations",   "text-muted"),
                        _metric_col("Forecast Wks",   f"{forecast_weeks}",         "non-promo weeks","text-muted"),
                    ],
                    className="g-2",
                ),
                html.Hr(),
                html.P(
                    [
                        html.Strong("What to do: "),
                        "Wait for more sales history to accumulate, broaden the store scope "
                        "(e.g. include all stores instead of online-only), or check that the "
                        "selected channel actually has transaction data for this SKU.",
                    ],
                    className="text-muted mb-0",
                    style={"fontSize": "14px"},
                ),
            ]),
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

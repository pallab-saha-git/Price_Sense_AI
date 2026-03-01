"""
pages/home.py
──────────────
Dashboard home page — summary metrics and recent analyses.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from dash import dcc, html, register_page

register_page(__name__, path="/", name="Home", title="Price Sense AI — Home")


def _kpi_card(title: str, value: str, delta: str = "", color: str = "primary", icon: str = "") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.P([html.Span(icon + " ", style={"marginRight": 4}), title],
                           className="text-muted mb-1", style={"fontSize": "12px"}),
                    html.H3(value, className=f"fw-bold text-{color} mb-0"),
                    html.Small(delta, className="text-muted") if delta else None,
                ],
                className="p-3",
            ),
            className="shadow-sm h-100",
        ),
        xs=12, sm=6, md=3,
    )


def layout() -> html.Div:
    return html.Div(
        [
            # Page header
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H2("🏪 Promotion Intelligence Dashboard",
                                    className="fw-bold mb-1 mt-3"),
                            html.P(
                                "AI-powered promotion analysis for mid-market retailers. "
                                "Run an analysis on the Analyze tab to see your results.",
                                className="text-muted",
                            ),
                        ]
                    )
                )
            ),
            html.Hr(),

            # KPI row
            dbc.Row(
                [
                    _kpi_card("Avg Promo ROI",       "2.1×",    "vs 1.8× last quarter", "success",  "📈"),
                    _kpi_card("Profitable Promos",   "68%",     "+8pp vs baseline",      "primary",  "✅"),
                    _kpi_card("Avg Lift Accuracy",   "±8%",     "MAPE across 60 promos", "info",     "🎯"),
                    _kpi_card("SKUs Analyzed",       "15",      "2 categories",          "secondary","📦"),
                ],
                className="g-3 mb-4",
            ),

            # Charts row
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("📊 Category Volume Trend", className="mb-0")),
                                dbc.CardBody(dcc.Graph(
                                    figure=_sample_trend_chart(),
                                    config={"displayModeBar": False},
                                    style={"height": "260px"},
                                )),
                            ],
                            className="shadow-sm",
                        ),
                        md=8,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("🗂 Recent Analyses", className="mb-0")),
                                dbc.CardBody(_recent_analyses_table()),
                            ],
                            className="shadow-sm",
                        ),
                        md=4,
                    ),
                ],
                className="g-3 mb-4",
            ),

            # Callout
            dbc.Row(
                dbc.Col(
                    dbc.Alert(
                        [
                            html.H5("👉 Ready to analyze a promotion?", className="alert-heading"),
                            html.P(
                                "Click 'Analyze' in the navigation bar to run a full promo analysis "
                                "— including elasticity, cannibalization, P&L, and risk scoring. "
                                "Results appear instantly with actionable insights.",
                                className="mb-0",
                            ),
                        ],
                        color="primary",
                    )
                )
            ),
        ],
        className="container-fluid px-4",
    )


def _sample_trend_chart():
    """Demo weekly volume trend chart."""
    weeks = pd.date_range("2025-01-01", periods=52, freq="W")
    import numpy as np
    np.random.seed(0)
    nuts_vol  = 8000 + np.sin(np.linspace(0, 4 * np.pi, 52)) * 2000 + np.random.normal(0, 300, 52)
    bev_vol   = 5000 + np.cos(np.linspace(0, 2 * np.pi, 52)) * 1500 + np.random.normal(0, 200, 52)

    df = pd.DataFrame({
        "Week": list(weeks) * 2,
        "Units": list(nuts_vol.clip(min=0)) + list(bev_vol.clip(min=0)),
        "Category": ["Nuts"] * 52 + ["Beverages"] * 52,
    })

    fig = px.line(
        df, x="Week", y="Units", color="Category",
        color_discrete_map={"Nuts": "#0f3460", "Beverages": "#e94560"},
        template="plotly_white",
    )
    fig.update_layout(
        margin=dict(l=30, r=10, t=10, b=30),
        legend=dict(orientation="h", y=1.05),
        hovermode="x unified",
    )
    return fig


def _recent_analyses_table():
    data = [
        ("NUT-PIST-16", "25% off",  "❌ No",   "0.65"),
        ("NUT-ALMD-16", "15% off",  "✅ Yes",  "2.1×"),
        ("BEV-COLA-12", "20% off",  "✅ Yes",  "1.8×"),
        ("NUT-MIXD-16", "30% off",  "⚠️ Marg", "0.9×"),
        ("BEV-WTER-12", "10% off",  "✅ Yes",  "1.4×"),
    ]
    rows = [
        html.Tr([html.Td(sku, style={"fontSize": "12px"}),
                 html.Td(disc, style={"fontSize": "12px"}),
                 html.Td(rec),
                 html.Td(roi, style={"fontSize": "12px"})])
        for sku, disc, rec, roi in data
    ]
    return dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("SKU", style={"fontSize": "12px"}),
                html.Th("Discount"),
                html.Th("Rec."),
                html.Th("ROI"),
            ])),
            html.Tbody(rows),
        ],
        bordered=False, hover=True, responsive=True, size="sm",
    )

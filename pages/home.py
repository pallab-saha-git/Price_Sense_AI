"""
pages/home.py
──────────────
Dashboard home page — summary metrics and recent analyses.

All data fetching happens in Dash callbacks so the page shell renders
instantly.  The heavy category-trend query is limited to the most recent
52 weeks to keep SQLite response < 2 s.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dash import dcc, html, register_page, callback, Output, Input
from loguru import logger

register_page(__name__, path="/", name="Home", title="Price Sense AI — Home")


# ── Layout (renders immediately — no DB calls) ────────────────────────────────

def layout() -> html.Div:
    return html.Div(
        [
            # Page header
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H2("Promotion Intelligence Dashboard",
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

            # KPI row — populated by callback
            dcc.Loading(
                dbc.Row(id="kpi-row", className="g-3 mb-4"),
                type="dot",
            ),

            # Charts row — populated by callbacks
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("Category Volume Trend",
                                                       className="mb-0")),
                                dbc.CardBody(dcc.Loading(
                                    dcc.Graph(
                                        id="home-trend-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "260px"},
                                    ),
                                    type="dot",
                                )),
                            ],
                            className="shadow-sm",
                        ),
                        md=8,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("Recent Analyses",
                                                       className="mb-0")),
                                dbc.CardBody(dcc.Loading(
                                    html.Div(id="home-recent-analyses"),
                                    type="dot",
                                )),
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
                            html.H5("Ready to analyze a promotion?",
                                    className="alert-heading"),
                            html.P(
                                "Click Analyze in the navigation bar to run a full "
                                "promo analysis — including elasticity, "
                                "cannibalization, P&L, and risk scoring. "
                                "Results appear instantly with actionable insights.",
                                className="mb-0",
                            ),
                        ],
                        color="primary",
                    )
                )
            ),

            # Hidden trigger so callbacks fire once on page load
            dcc.Store(id="home-page-loaded", data=True),
        ],
        className="container-fluid px-4",
    )


# ── Callbacks (data loads asynchronously after page shell renders) ─────────────

@callback(Output("kpi-row", "children"),
          Input("home-page-loaded", "data"))
def _update_kpi_row(_trigger):
    """Populate KPI cards from the database."""
    try:
        from data.database import get_session, Product, Sale, Promotion
        session = get_session()
        n_products   = session.query(Product).count()
        n_categories = session.query(Product.category).distinct().count()
        n_promos     = session.query(Promotion).count()
        n_sales      = session.query(Sale).count()
        session.close()
    except Exception as e:
        logger.warning(f"KPI query error: {e}")
        n_products = n_categories = n_promos = n_sales = 0

    return [
        _kpi_card("SKUs in Database",  str(n_products),
                  f"{n_categories} categories", "primary"),
        _kpi_card("Promotions Loaded", str(n_promos),
                  "historical promotions",      "success"),
        _kpi_card("Sales Records",
                  f"{n_sales:,}" if n_sales else "0",
                  "transaction rows",           "info"),
        _kpi_card("Categories",        str(n_categories),
                  "product categories",         "secondary"),
    ]


@callback(Output("home-trend-chart", "figure"),
          Input("home-page-loaded", "data"))
def _update_trend_chart(_trigger):
    """Category volume trend — limited to the last 52 weeks for speed."""
    try:
        from data.database import get_session, Sale, Product
        from sqlalchemy import func
        session = get_session()

        cutoff = (datetime.now() - timedelta(weeks=52)).strftime("%Y-%m-%d")

        # Top 5 categories by recent volume
        cat_volumes = (
            session.query(Product.category, func.sum(Sale.units_sold))
            .join(Sale, Sale.sku_id == Product.sku_id)
            .filter(Sale.date >= cutoff)
            .group_by(Product.category)
            .order_by(func.sum(Sale.units_sold).desc())
            .limit(5)
            .all()
        )
        top_cats = [c[0] for c in cat_volumes] if cat_volumes else []

        if not top_cats:
            session.close()
            return _empty_trend_chart()

        # Weekly aggregation for those categories
        weekly_data = (
            session.query(
                Sale.date, Product.category, func.sum(Sale.units_sold))
            .join(Product, Product.sku_id == Sale.sku_id)
            .filter(Product.category.in_(top_cats), Sale.date >= cutoff)
            .group_by(Sale.date, Product.category)
            .all()
        )
        session.close()

        if not weekly_data:
            return _empty_trend_chart()

        df = pd.DataFrame(weekly_data,
                          columns=["Week", "Category", "Units"])
        df["Week"] = pd.to_datetime(df["Week"])
        df = df.sort_values("Week")

        fig = px.line(df, x="Week", y="Units", color="Category",
                      template="plotly_white")
        fig.update_layout(
            margin=dict(l=30, r=10, t=10, b=30),
            legend=dict(orientation="h", y=1.05),
            hovermode="x unified",
        )
        return fig
    except Exception as e:
        logger.warning(f"Trend chart error: {e}")
        return _empty_trend_chart()


@callback(Output("home-recent-analyses", "children"),
          Input("home-page-loaded", "data"))
def _update_recent_analyses(_trigger):
    """Product snapshot table."""
    try:
        from data.database import get_session, Product
        session = get_session()
        products = session.query(Product).limit(5).all()
        session.close()

        if not products:
            return html.P("No products loaded yet.", className="text-muted")

        rows = [
            html.Tr([
                html.Td(html.Div([
                    html.Span(p.sku_id,
                              style={"fontSize": "11px", "color": "#888",
                                     "display": "block"}),
                    html.Span(p.product_name[:30],
                              style={"fontSize": "12px", "fontWeight": 500}),
                ])),
                html.Td(p.category, style={"fontSize": "12px"}),
                html.Td(f"${p.regular_price:.2f}",
                         style={"fontSize": "12px"}),
                html.Td(f"{p.margin_pct:.0f}%" if p.margin_pct else "—",
                         style={"fontSize": "12px"}),
            ])
            for p in products
        ]
        return dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Product",  style={"fontSize": "12px"}),
                    html.Th("Category", style={"fontSize": "12px"}),
                    html.Th("Price",    style={"fontSize": "12px"}),
                    html.Th("Margin",   style={"fontSize": "12px"}),
                ])),
                html.Tbody(rows),
            ],
            bordered=False, hover=True, responsive=True, size="sm",
        )
    except Exception as e:
        logger.warning(f"Recent analyses error: {e}")
        return html.P("Loading product data…", className="text-muted")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _kpi_card(title: str, value: str, delta: str = "",
              color: str = "primary") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.P(title, className="text-muted mb-1",
                           style={"fontSize": "12px",
                                  "textTransform": "uppercase",
                                  "letterSpacing": "0.04em"}),
                    html.H3(value, className=f"fw-bold text-{color} mb-0"),
                    html.Small(delta, className="text-muted") if delta else None,
                ],
                className="p-3",
            ),
            className="shadow-sm h-100",
        ),
        xs=12, sm=6, md=3,
    )


def _empty_trend_chart():
    """Fallback empty chart."""
    fig = go.Figure()
    fig.add_annotation(
        text="No sales data loaded yet",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=14, color="gray"),
    )
    fig.update_layout(margin=dict(l=30, r=10, t=10, b=30),
                      template="plotly_white")
    return fig

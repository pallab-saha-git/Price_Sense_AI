"""
callbacks/analyze_callbacks.py
───────────────────────────────
Dash callbacks for the Analyze page.
Triggers the full ML pipeline on form submit and populates the result panels.
"""

from __future__ import annotations

from datetime import date

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html
from loguru import logger


def register(app):
    """Register all analyze-page callbacks on the Dash app instance."""

    # ── Update discount label when slider moves ────────────────────────────────
    @app.callback(
        Output("lbl-discount", "children"),
        Input("sl-discount", "value"),
    )
    def update_discount_label(val):
        return f"Discount: {val}%"

    # ── Filter product dropdown by category ───────────────────────────────────
    @app.callback(
        Output("dd-product", "options"),
        Input("dd-category",  "value"),
    )
    def filter_products_by_category(category):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            df   = data["products"]
            if category and category != "ALL":
                df = df[df["category"] == category]
            return [
                {"label": f"{row['product_name']} ({row['category']})", "value": row["sku_id"]}
                for _, row in df.iterrows()
            ]
        except Exception as exc:
            logger.error(f"filter_products_by_category error: {exc}")
            return []

    # ── Main analysis callback ─────────────────────────────────────────────────
    @app.callback(
        Output("div-recommendation", "children"),
        Output("div-charts",          "children"),
        Input("btn-analyze",  "n_clicks"),
        State("dd-product",        "value"),
        State("sl-discount",       "value"),
        State("dp-promo-range",    "start_date"),
        State("dp-promo-range",    "end_date"),
        State("chk-channels",      "value"),
        State("dd-store",          "value"),
        prevent_initial_call=True,
    )
    def run_analysis(n_clicks, sku_id, discount_pct_int, start_date_str, end_date_str, channels, store_id):
        if not n_clicks:
            from components.recommendation_card import empty_recommendation_card
            return empty_recommendation_card(), html.Div()

        try:
            discount_pct = discount_pct_int / 100.0
            start_date   = date.fromisoformat(start_date_str[:10])
            end_date     = date.fromisoformat(end_date_str[:10])
            store_ids    = None if store_id == "ALL" else [store_id]

            logger.info(f"Running analysis: {sku_id} @ {discount_pct_int}% off {start_date}→{end_date}")

            from services.promo_analyzer import analyze_promotion
            result = analyze_promotion(
                sku_id=sku_id,
                discount_pct=discount_pct,
                start_date=start_date,
                end_date=end_date,
                channels=channels,
                store_ids=store_ids,
            )

            from services.insight_generator import generate_insights
            insights = generate_insights(result)

            # Build UI components
            from components.recommendation_card import recommendation_card
            from components.elasticity_chart import elasticity_chart
            from components.cannibalization_heatmap import cannibalization_bar
            from components.risk_gauge import risk_gauge, risk_factor_bars
            from components.insight_panel import insight_panel
            from services.promo_analyzer import _load_data

            data        = _load_data()
            products_df = data["products"]
            product_row = products_df[products_df["sku_id"] == sku_id]
            reg_price   = float(product_row.iloc[0]["regular_price"]) if not product_row.empty else 10.0

            rec_card       = recommendation_card(result)
            elast_chart    = elasticity_chart(result.elasticity, reg_price, result.forecast.baseline_weekly)
            cannibal_chart = cannibalization_bar(result.cannibalization.impacts, result.pnl.product_name)
            risk_g         = risk_gauge(result.risk)
            risk_bars      = risk_factor_bars(result.risk)
            insight_cards  = insight_panel(insights)

            charts_layout = dbc.Row(
                [
                    # Row 1: Elasticity + Cannibalization
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("📈 Elasticity Curve", className="mb-0")),
                                  dbc.CardBody(elast_chart)], className="shadow-sm"),
                        md=6, className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("🔄 Cannibalization Impact", className="mb-0")),
                                  dbc.CardBody(cannibal_chart)], className="shadow-sm"),
                        md=6, className="mb-3",
                    ),
                    # Row 2: Risk gauge + Risk breakdown
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("⚠️ Risk Score", className="mb-0")),
                                  dbc.CardBody(risk_g)], className="shadow-sm"),
                        md=4, className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("⚖️ Risk Factor Breakdown", className="mb-0")),
                                  dbc.CardBody(risk_bars)], className="shadow-sm"),
                        md=5, className="mb-3",
                    ),
                    # Row 3: Insights
                    dbc.Col(
                        insight_cards,
                        md=12, className="mb-3",
                    ),
                ],
                className="g-2",
            )

            return rec_card, charts_layout

        except Exception as exc:
            logger.exception(f"Analysis failed: {exc}")
            error_card = dbc.Alert(
                [
                    html.H5("⚠️ Analysis Error", className="alert-heading"),
                    html.P(str(exc)),
                    html.P("Please check your inputs and try again.", className="mb-0"),
                ],
                color="danger",
            )
            return error_card, html.Div()

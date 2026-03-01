"""
callbacks/scenario_callbacks.py
────────────────────────────────
Callbacks for the Scenario Comparison page.
"""

from __future__ import annotations

from datetime import date

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html
from loguru import logger


def register(app):

    # ── Populate product dropdown on compare page load ────────────────────────
    @app.callback(
        Output("dd-cmp-product", "options"),
        Input("dd-cmp-product",  "id"),   # fires on page load
    )
    def populate_cmp_products(_):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            df   = data["products"]
            return [
                {"label": f"{row['product_name']} ({row['category']})", "value": row["sku_id"]}
                for _, row in df.iterrows()
            ]
        except Exception as exc:
            logger.error(f"populate_cmp_products error: {exc}")
            return []

    # ── Run scenario comparison ────────────────────────────────────────────────
    @app.callback(
        Output("div-cmp-results", "children"),
        Input("btn-compare",      "n_clicks"),
        State("dd-cmp-product",   "value"),
        State("dp-cmp-range",     "start_date"),
        State("dp-cmp-range",     "end_date"),
        State("dd-cmp-discounts", "value"),
        prevent_initial_call=True,
    )
    def run_comparison(n_clicks, sku_id, start_str, end_str, discounts):
        if not n_clicks or not sku_id:
            return html.Div("Select a product and click Compare.", className="text-muted text-center py-4")

        try:
            start_date = date.fromisoformat(start_str[:10])
            end_date   = date.fromisoformat(end_str[:10])
            discounts  = sorted(discounts or [0.10, 0.15, 0.20, 0.25, 0.30])

            from services.scenario_engine import compare_scenarios, scenarios_to_dataframe
            comparison = compare_scenarios(
                sku_id=sku_id,
                start_date=start_date,
                end_date=end_date,
                discount_levels=discounts,
            )

            df = scenarios_to_dataframe(comparison)

            if df.empty:
                return dbc.Alert(
                    [
                        html.H5("No scenarios could be computed", className="alert-heading"),
                        html.P("All discount scenarios failed during modelling. "
                               "This is usually a forecasting issue — try a different product or date range."),
                    ],
                    color="warning",
                )

            from components.scenario_table import scenario_table
            from components.elasticity_chart import scenario_bar_chart
            from components.insight_panel import scenario_insight_panel

            table      = scenario_table(df)
            bar_chart  = scenario_bar_chart(df)
            ins_panel  = scenario_insight_panel(comparison)

            return html.Div(
                [
                    ins_panel,
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H6("Side-by-Side Discount Comparison", className="mb-0")),
                            dbc.CardBody(table),
                        ],
                        className="shadow-sm mb-3",
                    ),
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H6("Net Profit by Discount Level", className="mb-0")),
                            dbc.CardBody(bar_chart),
                        ],
                        className="shadow-sm",
                    ),
                ]
            )

        except Exception as exc:
            logger.exception(f"Scenario comparison failed: {exc}")
            return dbc.Alert(f"Error running comparison: {exc}", color="danger")

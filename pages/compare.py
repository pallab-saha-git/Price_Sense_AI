"""
pages/compare.py
─────────────────
Scenario comparison page — see how 10%/15%/20%/25%/30% off compare for a SKU.
"""

from __future__ import annotations

from datetime import date, timedelta

import dash_bootstrap_components as dbc
from dash import dcc, html, register_page

register_page(__name__, path="/compare", name="Compare", title="Price Sense AI — Compare Scenarios")


def layout() -> html.Div:
    today         = date.today()
    default_start = today + timedelta(days=(7 - today.weekday()))
    default_end   = default_start + timedelta(weeks=1)

    return html.Div(
        [
            dbc.Row(
                dbc.Col(html.H3("Scenario Comparison", className="fw-bold mt-3 mb-0"))
            ),
            html.Hr(),

            # Configuration row
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Product", html_for="dd-cmp-product"),
                                    dcc.Dropdown(
                                        id="dd-cmp-product",
                                        options=[],    # populated by callback on page load
                                        value=None,
                                        clearable=False,
                                    ),
                                ],
                                md=4,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Promotion Window"),
                                    dcc.DatePickerRange(
                                        id="dp-cmp-range",
                                        start_date=str(default_start),
                                        end_date=str(default_end),
                                        display_format="YYYY-MM-DD",
                                    ),
                                ],
                                md=4,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Discount levels"),
                                    dcc.Dropdown(
                                        id="dd-cmp-discounts",
                                        options=[
                                            {"label": "5%",  "value": 0.05},
                                            {"label": "10%", "value": 0.10},
                                            {"label": "15%", "value": 0.15},
                                            {"label": "20%", "value": 0.20},
                                            {"label": "25%", "value": 0.25},
                                            {"label": "30%", "value": 0.30},
                                            {"label": "35%", "value": 0.35},
                                            {"label": "40%", "value": 0.40},
                                        ],
                                        value=[0.10, 0.15, 0.20, 0.25, 0.30],
                                        multi=True,
                                    ),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Compare →",
                                    id="btn-compare",
                                    color="primary",
                                    className="w-100 mt-4",
                                ),
                                md=1,
                            ),
                        ],
                        align="end",
                    ),
                    className="py-2",
                ),
                className="shadow-sm mb-3",
            ),

            # Results
            dcc.Loading(
                type="circle",
                children=html.Div(
                    id="div-cmp-results",
                    children=html.Div(
                        "Select a product and click Compare to see scenarios.",
                        className="text-muted text-center py-5",
                    ),
                ),
            ),
        ],
        className="container-fluid px-4",
    )

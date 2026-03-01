"""
pages/profit_buckets.py
────────────────────────
Discount Opportunity Scanner — surfaces which products would profit from
discounts and at what depth, across the entire SKU catalog.

This page fulfils the "horizontal product" brief: it works for any retailer
(nuts, beverages, grocery) and instantly answers: "Which of my SKUs should
I promote, and at what discount?"
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html, register_page

register_page(
    __name__,
    path="/profit-opportunities",
    name="Opportunities",
    title="Price Sense AI — Profit Opportunities",
)


def layout() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                dbc.Col(
                    [
                        html.H3("Discount Opportunity Scanner", className="fw-bold mt-3 mb-0"),
                        html.P(
                            "Scans your entire catalog to identify which products generate positive "
                            "incremental profit at each discount depth — ranked and bucketed so you know "
                            "exactly where to invest your promo budget.",
                            className="text-muted mb-0",
                        ),
                    ]
                )
            ),
            html.Hr(),

            # Controls row
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Category Filter"),
                                    dcc.Dropdown(
                                        id="pb-dd-category",
                                        options=[{"label": "All Categories", "value": "ALL"}],
                                        value="ALL",
                                        clearable=False,
                                        style={"fontSize": "14px"},
                                    ),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Promotion Window (weeks)"),
                                    dcc.Slider(
                                        id="pb-sl-weeks",
                                        min=1, max=4, step=1,
                                        value=1,
                                        marks={1: "1w", 2: "2w", 3: "3w", 4: "4w"},
                                    ),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Min. ROI threshold"),
                                    dcc.Slider(
                                        id="pb-sl-roi",
                                        min=0, max=2, step=0.25,
                                        value=0,
                                        marks={0: "Any", 0.5: "0.5x", 1: "1x", 1.5: "1.5x", 2: "2x"},
                                    ),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                dbc.Button(
                                    [html.I(className="fa fa-search me-2"), "Scan All SKUs"],
                                    id="pb-btn-scan",
                                    color="primary",
                                    size="lg",
                                    className="w-100 mt-4",
                                ),
                                md=3,
                            ),
                        ],
                    ),
                ),
                className="shadow-sm mb-3",
            ),

            # Results area
            dcc.Loading(
                type="circle",
                children=html.Div(id="pb-div-results",
                                  children=_empty_state()),
            ),
        ],
        className="container-fluid px-4",
    )


def _empty_state() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.I(className="fa fa-chart-bar fa-3x text-primary opacity-50 mb-3"),
                    html.H5("Click 'Scan All SKUs' to discover discount opportunities", className="text-muted"),
                    html.P(
                        "The scanner runs your P&L model across every product × every discount level "
                        "and buckets results by profit potential.",
                        className="text-muted small",
                    ),
                ],
                className="text-center py-5",
            )
        ]
    )

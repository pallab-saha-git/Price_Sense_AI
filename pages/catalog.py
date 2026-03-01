"""
pages/catalog.py
─────────────────
Product catalog browser + historical promo performance view.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html, register_page

register_page(__name__, path="/catalog", name="Catalog", title="Price Sense AI — Catalog")


def layout() -> html.Div:
    return html.Div(
        [
            dbc.Row(
                dbc.Col(html.H3("📦 Product Catalog & Promo History", className="fw-bold mt-3 mb-0"))
            ),
            html.Hr(),

            # Filter row
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Category", html_for="dd-cat-filter"),
                                    dcc.Dropdown(
                                        id="dd-cat-filter",
                                        options=[
                                            {"label": "All", "value": "ALL"},
                                            {"label": "Nuts", "value": "Nuts"},
                                            {"label": "Beverages", "value": "Beverages"},
                                        ],
                                        value="ALL",
                                        clearable=False,
                                    ),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Search product name"),
                                    dbc.Input(id="inp-cat-search", placeholder="e.g. Pistachio", debounce=True),
                                ],
                                md=4,
                            ),
                        ]
                    ),
                    className="py-2",
                ),
                className="shadow-sm mb-3",
            ),

            # Products grid
            dcc.Loading(
                type="dot",
                children=html.Div(id="div-catalog-grid"),
            ),

            html.Hr(className="my-4"),

            # Promo history
            dbc.Row(
                dbc.Col(html.H5("📅 Historical Promotion Performance", className="fw-semibold"))
            ),
            dcc.Loading(
                type="dot",
                children=html.Div(id="div-promo-history"),
            ),
        ],
        className="container-fluid px-4",
    )

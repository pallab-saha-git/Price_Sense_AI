"""
pages/analyze.py
─────────────────
Main promotion analysis page.
Form → Analyze → Recommendation + Charts + Insights
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html, register_page

from components.promo_input_form import promo_input_form
from components.recommendation_card import empty_recommendation_card

register_page(__name__, path="/analyze", name="Analyze", title="Price Sense AI — Analyze")


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="store-analysis-result"),     # stores PromoAnalysisResult as dict
            dcc.Store(id="store-products-data"),       # products DataFrame as JSON
            dcc.Store(id="store-stores-data"),         # stores DataFrame as JSON

            dbc.Row(
                dbc.Col(html.H3("⚡ Promotion Analyzer", className="fw-bold mt-3 mb-0"))
            ),
            html.Hr(),

            dbc.Row(
                [
                    # ── Left column: input form ────────────────────────────────
                    dbc.Col(
                        html.Div(id="div-input-form", children=[promo_input_form()]),
                        md=3,
                        className="mb-3",
                    ),

                    # ── Right column: results ──────────────────────────────────
                    dbc.Col(
                        [
                            # Recommendation headline card
                            html.Div(
                                id="div-recommendation",
                                children=[empty_recommendation_card()],
                            ),

                            # Loading wrapper for charts
                            dcc.Loading(
                                id="loading-charts",
                                type="circle",
                                children=html.Div(
                                    id="div-charts",
                                    children=html.Div(
                                        "Run an analysis to see detailed charts.",
                                        className="text-muted text-center py-4",
                                    ),
                                ),
                            ),
                        ],
                        md=9,
                    ),
                ],
                className="g-3",
            ),
        ],
        className="container-fluid px-4",
    )

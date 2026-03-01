"""
components/promo_input_form.py
───────────────────────────────
Dash layout for the promotion input form panel.
Provides product selector, discount slider, date range picker, channel toggles.
"""

from __future__ import annotations

from datetime import date, timedelta

import dash_bootstrap_components as dbc
from dash import dcc, html


def get_product_options(products_df=None) -> list[dict]:
    """Build dropdown options from the products table."""
    if products_df is None or products_df.empty:
        return [{"label": "Loading…", "value": "NUT-PIST-16"}]
    return [
        {
            "label": f"{row['product_name']} ({row['category']})",
            "value": row["sku_id"],
        }
        for _, row in products_df.iterrows()
    ]


def get_store_options(stores_df=None) -> list[dict]:
    if stores_df is None or stores_df.empty:
        return [{"label": "All Stores", "value": "ALL"}]
    opts = [{"label": "All Stores", "value": "ALL"}]
    for _, row in stores_df.iterrows():
        opts.append({"label": f"{row['store_name']} ({row['region']})", "value": row["store_id"]})
    return opts


def promo_input_form(products_df=None, stores_df=None) -> dbc.Card:
    today       = date.today()
    default_start = today + timedelta(days=(7 - today.weekday()))   # next Monday
    default_end   = default_start + timedelta(weeks=1)

    return dbc.Card(
        [
            dbc.CardHeader(
                html.H5("Configure Promotion", className="mb-0 fw-bold"),
                className="card-header-dark",
            ),
            dbc.CardBody(
                [
                    # Category filter — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("Category Filter", html_for="dd-category"),
                            dcc.Dropdown(
                                id="dd-category",
                                options=[{"label": "All Categories", "value": "ALL"}],
                                value="ALL",
                                clearable=False,
                                style={"fontSize": "14px"},
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # Product (subcategory) — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("Product", html_for="dd-analyze-product"),
                            dcc.Dropdown(
                                id="dd-analyze-product",
                                options=[{"label": "All Products", "value": "ALL"}],
                                value="ALL",
                                clearable=False,
                                placeholder="All Products",
                                style={"fontSize": "14px"},
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # SKU — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("SKU", html_for="dd-product"),
                            dcc.Dropdown(
                                id="dd-product",
                                options=get_product_options(products_df),
                                value="NUT-PIST-16",
                                clearable=False,
                                style={"fontSize": "14px"},
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # Discount slider — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label(id="lbl-discount", children="Discount: 25%"),
                            dcc.Slider(
                                id="sl-discount",
                                min=5, max=40, step=5,
                                value=25,
                                marks={v: f"{v}%" for v in range(5, 45, 5)},
                                tooltip={"placement": "bottom", "always_visible": False},
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # Promotion window — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("Promotion Window"),
                            dcc.DatePickerRange(
                                id="dp-promo-range",
                                min_date_allowed=str(date(2024, 1, 1)),
                                max_date_allowed=str(date(2027, 12, 31)),
                                start_date=str(default_start),
                                end_date=str(default_end),
                                display_format="YYYY-MM-DD",
                                style={"fontSize": "14px"},
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # Channels — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("Sales Channels"),
                            dbc.Checklist(
                                id="chk-channels",
                                options=[
                                    {"label": "  In-store", "value": "physical"},
                                    {"label": "  Online",   "value": "online"},
                                ],
                                value=["physical", "online"],
                                inline=False,
                                switch=True,
                                className="mt-1",
                            ),
                        ]),
                        className="mb-3",
                    ),

                    # Store scope — own row
                    dbc.Row(
                        dbc.Col([
                            dbc.Label("Store Scope"),
                            dcc.Dropdown(
                                id="dd-store",
                                options=get_store_options(stores_df),
                                value="ALL",
                                clearable=False,
                                style={"fontSize": "13px"},
                            ),
                            html.Small(
                                "Store list updates based on selected channels.",
                                className="text-muted mt-1 d-block",
                                style={"fontSize": "11px"},
                            ),
                        ]),
                        className="mb-4",
                    ),

                    # Analyze button
                    dbc.Button(
                        "Run Analysis",
                        id="btn-analyze",
                        color="primary",
                        size="lg",
                        className="w-100 fw-semibold",
                    ),

                    # Loading indicator
                    dbc.Spinner(
                        html.Div(id="spinner-placeholder"),
                        color="primary",
                        size="sm",
                        spinner_style={"display": "none"},
                    ),
                ]
            ),
        ],
        className="shadow-sm",
    )

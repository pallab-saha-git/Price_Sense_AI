"""
callbacks/catalog_callbacks.py
───────────────────────────────
Callbacks for the Catalog page.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px
import pandas as pd
from dash import Input, Output, html, dcc
from loguru import logger


def register(app):

    # ── Populate category filter dynamically ──────────────────────────────────
    @app.callback(
        Output("dd-cat-filter", "options"),
        Input("dd-cat-filter",  "id"),
    )
    def populate_catalog_categories(_):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            cats = sorted(data["products"]["category"].dropna().unique())

            opts = [{"label": "All Categories", "value": "ALL"}]
            for c in cats:
                opts.append({"label": c, "value": c})
            return opts
        except Exception as exc:
            logger.error(f"populate_catalog_categories error: {exc}")
            return [{"label": "All", "value": "ALL"}]

    # ── Product grid ──────────────────────────────────────────────────────────
    @app.callback(
        Output("div-catalog-grid",    "children"),
        Output("div-promo-history",   "children"),
        Input("dd-cat-filter",        "value"),
        Input("inp-cat-search",       "value"),
    )
    def update_catalog(category, search_term):
        from services.promo_analyzer import _load_data
        try:
            data        = _load_data()
            products_df = data["products"].copy()
            promos_df   = data["promos"].copy()
            sales_df    = data["sales"].copy()

            # Filter products
            if category and category != "ALL":
                products_df = products_df[products_df["category"] == category]
            if search_term:
                products_df = products_df[
                    products_df["product_name"].str.contains(search_term, case=False, na=False)
                ]

            # Product cards
            product_grid = _product_cards(products_df)

            # Promo history for filtered SKUs
            sku_ids = products_df["sku_id"].tolist()
            if promos_df.empty or not sku_ids:
                history = html.P("No promotion history available.", className="text-muted")
            else:
                hist_df = promos_df[promos_df["sku_id"].isin(sku_ids)].copy()
                hist_df["product_name"] = hist_df["sku_id"].map(
                    products_df.set_index("sku_id")["product_name"]
                )
                hist_df["discount_pct"] = (hist_df["discount_pct"] * 100).round(0).astype(int).astype(str) + "%"
                history = _promo_history_table(hist_df)

            return product_grid, history

        except Exception as exc:
            logger.exception(f"Catalog callback error: {exc}")
            return dbc.Alert(str(exc), color="danger"), html.Div()


_CAT_COLORS = {
    "Nuts": "primary", "Beverages": "info", "Snacks": "warning",
    "Grocery": "secondary", "Dairy": "success", "Produce": "success",
    "Bakery": "danger",
}



def _product_cards(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return html.P("No products found.", className="text-muted")

    cards = []
    for _, row in df.iterrows():
        cat    = row.get("category", "")
        color  = _CAT_COLORS.get(cat, "secondary")
        rp     = float(row.get("regular_price", 0))
        cp     = float(row.get("cost_price",    0))
        margin = round((rp - cp) / rp * 100, 1) if rp > 0 else 0.0
        card = dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.Span(cat, className=f"badge bg-{color}"),
                    ),
                    dbc.CardBody(
                        [
                            html.H6(row["product_name"], className="fw-bold mb-1"),
                            html.P(f"SKU: {row['sku_id']}", className="text-muted mb-1", style={"fontSize": "12px"}),
                            html.Hr(className="my-1"),
                            dbc.Row([
                                dbc.Col([html.Small("Price", className="text-muted d-block"),
                                         html.Strong(f"${rp:.2f}")], width=6),
                                dbc.Col([html.Small("Gross Margin", className="text-muted d-block"),
                                         html.Strong(f"{margin:.0f}%")], width=6),
                            ]),
                            html.Small(
                                "🗓 Seasonal" if row.get("is_seasonal") else "",
                                className="text-info mt-1",
                            ),
                        ],
                        className="p-2",
                    ),
                ],
                className="h-100 shadow-sm",
            ),
            xs=12, sm=6, md=4, lg=3,
            className="mb-3",
        )
        cards.append(card)

    return dbc.Row(cards, className="g-2")


def _promo_history_table(df: pd.DataFrame) -> html.Div:
    display_cols = ["product_name", "start_date", "end_date", "discount_pct", "promo_type", "funding_type"]
    col_defs = [
        {"field": "product_name",  "headerName": "Product",    "width": 200},
        {"field": "start_date",    "headerName": "Start",      "width": 120},
        {"field": "end_date",      "headerName": "End",        "width": 120},
        {"field": "discount_pct",  "headerName": "Discount",   "width": 100},
        {"field": "promo_type",    "headerName": "Type",       "width": 110},
        {"field": "funding_type",  "headerName": "Funding",    "width": 130},
    ]
    return dag.AgGrid(
        rowData=df[display_cols].to_dict("records"),
        columnDefs=col_defs,
        defaultColDef={"sortable": True, "filter": True, "resizable": True},
        dashGridOptions={"suppressCellFocus": True, "domLayout": "autoHeight"},
        style={"height": None},
        className="ag-theme-alpine",
    )

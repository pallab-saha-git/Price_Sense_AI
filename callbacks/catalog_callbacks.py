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
from dash import Input, Output, State, html, dcc, ctx
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
            return [{"label": "All Categories", "value": "ALL"}]

    # ── Populate Product filter when category changes ────────────────────────
    @app.callback(
        Output("dd-product-filter", "options"),
        Output("dd-product-filter", "value"),
        Input("dd-cat-filter",      "value"),
    )
    def populate_product_options(category):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            df   = data["products"].copy()
            if category and category != "ALL":
                df = df[df["category"] == category]
            subcats = sorted(df["subcategory"].dropna().unique())
            opts = [{"label": "All Products", "value": "ALL"}]
            for s in subcats:
                opts.append({"label": s, "value": s})
            return opts, "ALL"
        except Exception as exc:
            logger.error(f"populate_product_options error: {exc}")
            return [{"label": "All Products", "value": "ALL"}], "ALL"

    # ── Populate SKU filter when category OR product changes ─────────────────
    @app.callback(
        Output("dd-sku-filter", "options"),
        Output("dd-sku-filter", "value"),
        Input("dd-cat-filter",     "value"),
        Input("dd-product-filter", "value"),
    )
    def populate_sku_options(category, product):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            df   = data["products"].copy()
            if category and category != "ALL":
                df = df[df["category"] == category]
            if product and product != "ALL":
                df = df[df["subcategory"] == product]
            sort_cols = [c for c in ["subcategory"] if c in df.columns]
            if "size" in df.columns and df["size"].notna().any():
                sort_cols.append("size")
            df = df.sort_values(sort_cols) if sort_cols else df
            opts = [{"label": "All SKUs", "value": "ALL"}]
            for _, row in df.iterrows():
                size_label = ""
                if pd.notna(row.get("size")):
                    size_label = f" — {int(row['size'])}{row.get('size_unit', '')}"
                opts.append({
                    "label": f"{row['subcategory']}{size_label}  [{row['sku_id']}]",
                    "value": row["sku_id"],
                })
            return opts, "ALL"
        except Exception as exc:
            logger.error(f"populate_sku_options error: {exc}")
            return [{"label": "All SKUs", "value": "ALL"}], "ALL"

    # ── Clear all filters — resets category; cascade auto-resets product & SKU ──
    @app.callback(
        Output("dd-cat-filter",  "value"),
        Output("inp-cat-search", "value"),
        Input("btn-cat-clear",   "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_filters(_):
        return "ALL", ""

    # ── Product grid ──────────────────────────────────────────────────────────
    @app.callback(
        Output("div-catalog-grid",  "children"),
        Output("div-promo-history", "children"),
        Input("dd-cat-filter",      "value"),
        Input("dd-product-filter",  "value"),
        Input("dd-sku-filter",      "value"),
        Input("inp-cat-search",     "value"),
    )
    def update_catalog(category, product_filter, sku_filter, search_term):
        from services.promo_analyzer import _load_data
        try:
            data        = _load_data()
            products_df = data["products"].copy()
            promos_df   = data["promos"].copy()

            # Filter products — Category → Product → SKU cascade
            if category and category != "ALL":
                products_df = products_df[products_df["category"] == category]
            if product_filter and product_filter != "ALL":
                products_df = products_df[products_df["subcategory"] == product_filter]
            if sku_filter and sku_filter != "ALL":
                products_df = products_df[products_df["sku_id"] == sku_filter]
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
                    data["products"].set_index("sku_id")["product_name"]
                )
                hist_df["discount_pct"] = (hist_df["discount_pct"] * 100).round(0).astype(int).astype(str) + "%"
                history = _promo_history_table(hist_df)

            return product_grid, history

        except Exception as exc:
            logger.exception(f"Catalog callback error: {exc}")
            return dbc.Alert(str(exc), color="danger"), html.Div()


_CAT_COLORS = {
    # Synthetic data categories
    "Nuts": "primary", "Beverages": "info", "Snacks": "warning",
    "Grocery": "secondary", "Dairy": "success", "Produce": "success",
    "Bakery": "danger", "Frozen": "info", "Meat": "danger",
    "Deli": "warning", "Seafood": "primary", "Household": "secondary",
    "Health": "success", "Baby": "warning", "Personal Care": "info",
    "Floral": "success", "Fuel": "secondary",
    # Dunnhumby categories
    "Kiosk-Gas": "dark", "Misc Sales Tran": "secondary",
    "Pastry": "warning", "Salad Bar": "success",
    "Drug Gm": "info", "Meat-Pckgd": "danger",
}



def _product_cards(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return html.P("No products found.", className="text-muted")

    # Group by subcategory so variants (8oz / 16oz / 32oz) share one card
    groups = df.sort_values(["category", "subcategory", "size"]).groupby(
        ["category", "subcategory"], sort=False
    )

    cards = []
    for (cat, subcat), group in groups:
        color   = _CAT_COLORS.get(cat, "secondary")
        brand   = group.iloc[0].get("brand", "")
        is_seas = group["is_seasonal"].any() if "is_seasonal" in group.columns else False

        # Build one row per SKU variant
        variant_rows = []
        for _, row in group.iterrows():
            rp     = float(row.get("regular_price", 0))
            cp     = float(row.get("cost_price",    0))
            margin = round((rp - cp) / rp * 100, 1) if rp > 0 else 0.0
            size_label = (
                f"{int(row['size'])}{row.get('size_unit','')}"
                if pd.notna(row.get("size")) else ""
            )
            variant_rows.append(
                html.Tr([
                    html.Td(
                        dbc.Badge(size_label, color="secondary", pill=True, className="me-1"),
                        style={"width": "60px"},
                    ),
                    html.Td(
                        html.Code(row["sku_id"],
                                  style={"fontSize": "10px", "color": "#6366f1"}),
                    ),
                    html.Td(f"${rp:.2f}", className="text-end fw-semibold"),
                    html.Td(f"{margin:.0f}%", className="text-end text-muted",
                            style={"fontSize": "11px"}),
                ])
            )

        card = dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Row([
                            dbc.Col(html.Span(cat, className=f"badge bg-{color}"), width="auto"),
                            dbc.Col(
                                html.Small(brand, className="text-muted"),
                                width="auto", className="ms-auto pe-0",
                            ),
                        ], align="center", className="g-0"),
                    ),
                    dbc.CardBody(
                        [
                            html.H6(subcat, className="fw-bold mb-1"),
                            html.Small(
                                "🗓 Seasonal" if is_seas else "",
                                className="text-info d-block mb-2",
                            ),
                            html.Hr(className="my-1"),
                            dbc.Table(
                                [html.Tbody(variant_rows)],
                                size="sm", bordered=False,
                                className="mb-0 table-striped",
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
        className="ag-theme-balham",
    )

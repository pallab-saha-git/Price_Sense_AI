"""
callbacks/profit_buckets_callbacks.py
──────────────────────────────────────
Callbacks for the Discount Opportunity Scanner page (/profit-opportunities).

Scans every SKU x every discount level, computes P&L, and groups results
into three tiers:
  High Opportunity  — positive net profit at optimal discount
  Moderate          — small loss but ROI trend acceptable
  Avoid             — consistently negative across all tested discounts
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dash import Input, Output, State, dcc, html
from loguru import logger

DISCOUNT_LEVELS  = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
_BUCKET_ORDER    = {"High Opportunity": 0, "Moderate": 1, "Avoid": 2}
_BUCKET_COLORS   = {"High Opportunity": "success", "Moderate": "warning", "Avoid": "danger"}


def register(app):

    # ── Populate category dropdown ─────────────────────────────────────────────
    @app.callback(
        Output("pb-dd-category", "options"),
        Input("pb-dd-category",  "id"),
    )
    def populate_pb_categories(_):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            cats = sorted(data["products"]["category"].dropna().unique())

            opts = [{"label": "All Categories", "value": "ALL"}]
            for c in cats:
                opts.append({"label": c, "value": c})
            return opts
        except Exception as exc:
            logger.error(f"pb populate categories error: {exc}")
            return [{"label": "All Categories", "value": "ALL"}]

    # ── Populate Product dropdown (cascade from category) ─────────────────────
    @app.callback(
        Output("pb-dd-product", "options"),
        Output("pb-dd-product", "value"),
        Input("pb-dd-category", "value"),
    )
    def populate_pb_products(category):
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
            logger.error(f"pb populate products error: {exc}")
            return [{"label": "All Products", "value": "ALL"}], "ALL"

    # ── Populate SKU dropdown (cascade from category + product) ───────────────
    @app.callback(
        Output("pb-dd-sku", "options"),
        Output("pb-dd-sku", "value"),
        Input("pb-dd-category", "value"),
        Input("pb-dd-product",  "value"),
    )
    def populate_pb_skus(category, product):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            df   = data["products"].copy()
            if category and category != "ALL":
                df = df[df["category"] == category]
            if product and product != "ALL":
                df = df[df["subcategory"] == product]
            df = df.sort_values(["subcategory", "size"] if "size" in df.columns else ["subcategory"])
            opts = [{"label": "All SKUs", "value": "ALL"}]
            for _, row in df.iterrows():
                size_label = ""
                if "size" in row and pd.notna(row.get("size")):
                    size_label = f" — {int(row['size'])}{row.get('size_unit', '')}"
                opts.append({
                    "label": f"{row['subcategory']}{size_label}  [{row['sku_id']}]",
                    "value": row["sku_id"],
                })
            return opts, "ALL"
        except Exception as exc:
            logger.error(f"pb populate skus error: {exc}")
            return [{"label": "All SKUs", "value": "ALL"}], "ALL"

    # ── Main scan callback ─────────────────────────────────────────────────────
    @app.callback(
        Output("pb-div-results", "children"),
        Input("pb-btn-scan",      "n_clicks"),
        State("pb-dd-category",  "value"),
        State("pb-dd-product",   "value"),
        State("pb-dd-sku",       "value"),
        State("pb-sl-weeks",     "value"),
        State("pb-sl-roi",       "value"),
        prevent_initial_call=True,
    )
    def run_scan(n_clicks, category, product, sku, promo_weeks, min_roi):
        if not n_clicks:
            return html.Div()

        try:
            from services.promo_analyzer  import _load_data
            from models.profit_calculator import calculate_promo_pnl
            from models.elasticity        import estimate_volume_lift, estimate_elasticity

            data        = _load_data()
            products_df = data["products"].copy()
            sales_df    = data["sales"]
            seas_df     = data.get("seas", pd.DataFrame())

            if category and category != "ALL":
                products_df = products_df[products_df["category"] == category]
            if product and product != "ALL":
                products_df = products_df[products_df["subcategory"] == product]
            if sku and sku != "ALL":
                products_df = products_df[products_df["sku_id"] == sku]

            # Estimate elasticity per SKU (reuse cached estimates)
            records = []
            for _, prod in products_df.iterrows():
                sku_id = prod["sku_id"]
                rp     = float(prod.get("regular_price", 10.0))
                cp     = float(prod.get("cost_price",    5.0))

                # Estimate elasticity
                try:
                    el_result = estimate_elasticity(sales_df, sku_id, seas_df)
                    elasticity = el_result.elasticity
                    # Get per-week baseline from forecast fallback
                    sku_sales  = sales_df[sales_df["sku_id"] == sku_id]
                    baseline   = float(sku_sales["units_sold"].mean()) if len(sku_sales) > 0 else 50.0
                except Exception:
                    elasticity = -1.8  # safe default
                    baseline   = 50.0

                best_profit = None
                best_disc   = None

                for d in DISCOUNT_LEVELS:
                    lift = estimate_volume_lift(elasticity, d)
                    pnl  = calculate_promo_pnl(
                        sku_id=sku_id,
                        product_name=prod["product_name"],
                        regular_price=rp,
                        cost_price=cp,
                        discount_pct=d,
                        baseline_weekly_units=baseline,
                        volume_lift_pct=lift,
                        promo_weeks=promo_weeks,
                    )
                    if best_profit is None or pnl.net_incremental_profit > best_profit:
                        best_profit = pnl.net_incremental_profit
                        best_disc   = d
                    records.append({
                        "sku_id":        sku_id,
                        "product_name":  prod["product_name"],
                        "category":      prod.get("category", ""),
                        "regular_price": rp,
                        "gross_margin":  round((rp - cp) / rp * 100, 1) if rp > 0 else 0,
                        "elasticity":    round(elasticity, 2),
                        "discount":      d,
                        "discount_label": f"{int(d*100)}%",
                        "lift_pct":      round(lift * 100, 1),
                        "net_profit":    round(pnl.net_incremental_profit, 2),
                        "promo_roi":     round(pnl.promo_roi, 2),
                        "tier":          pnl.recommendation_tier,
                        "best_profit":   best_profit,
                        "optimal_disc":  best_disc,
                    })

            df = pd.DataFrame(records)

            if df.empty:
                return dbc.Alert("No products found for the selected category.", color="warning")

            # Apply min ROI filter
            if min_roi and min_roi > 0:
                df = df[df["promo_roi"] >= min_roi]

            if df.empty:
                return dbc.Alert(
                    f"No SKUs meet the minimum ROI threshold of {min_roi}x. "
                    "Try lowering the threshold or selecting 'Any'.",
                    color="warning",
                )

            return _build_results(df, promo_weeks)

        except Exception as exc:
            logger.exception(f"Profit bucket scan failed: {exc}")
            return dbc.Alert(
                [html.H5("Scan Error"), html.P(str(exc))],
                color="danger",
            )


# ── Results builder ────────────────────────────────────────────────────────────

def _build_results(df: pd.DataFrame, promo_weeks: int) -> html.Div:
    """Build the buckets display from the scan results DataFrame."""

    # Summary per SKU (take best discount row)
    best_per_sku = (
        df.sort_values("net_profit", ascending=False)
          .drop_duplicates(subset=["sku_id"])
          .reset_index(drop=True)
    )

    def _bucket(row):
        # High Opportunity: positive net profit at optimal discount
        if row["net_profit"] > 0:
            return "High Opportunity"
        # Moderate: small negative ROI (between -0.30 and 0) — worth reviewing at lower discount
        elif row["promo_roi"] >= -0.30:
            return "Moderate"
        else:
            return "Avoid"

    best_per_sku["bucket"] = best_per_sku.apply(_bucket, axis=1)

    # KPI counts
    n_high = (best_per_sku["bucket"] == "High Opportunity").sum()
    n_mod  = (best_per_sku["bucket"] == "Moderate").sum()
    n_avoid= (best_per_sku["bucket"] == "Avoid").sum()
    total  = len(best_per_sku)
    total_potential = best_per_sku[best_per_sku["net_profit"] > 0]["net_profit"].sum()

    kpi_row = dbc.Row([
        dbc.Col(_kpi("SKUs Scanned",       str(total),                  "secondary"), md=2, className="mb-3"),
        dbc.Col(_kpi("High Opportunity",   str(n_high),                 "success"),   md=2, className="mb-3"),
        dbc.Col(_kpi("Moderate",           str(n_mod),                  "warning"),   md=2, className="mb-3"),
        dbc.Col(_kpi("Avoid",              str(n_avoid),                "danger"),    md=2, className="mb-3"),
        dbc.Col(_kpi("Total Profit Pool",  f"${total_potential:,.0f}",  "primary"),   md=4, className="mb-3"),
    ], className="g-2 mb-2")

    # Heatmap: products × discounts → profit
    pivot = df.pivot_table(index="product_name", columns="discount_label", values="net_profit", aggfunc="mean")
    # Sort columns numerically
    col_order = [f"{int(d*100)}%" for d in sorted(set(df["discount"].tolist()))]
    pivot = pivot.reindex(columns=[c for c in col_order if c in pivot.columns])
    # Guard: only sort if pivot is non-empty and has columns
    if not pivot.empty and len(pivot.columns) > 0:
        sort_col = col_order[0] if col_order and col_order[0] in pivot.columns else pivot.columns[0]
        pivot = pivot.sort_values(sort_col, ascending=False)

    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[
            [0.0, "#ef4444"],   # red – big loss
            [0.4, "#f59e0b"],   # amber – marginal
            [0.6, "#10b981"],   # green – profitable
            [1.0, "#059669"],   # deep green – highly profitable
        ],
        zmid=0,
        colorbar=dict(title="Net Profit ($)", tickformat="$,.0f"),
        hovertemplate="%{y}<br>%{x}: $%{z:,.0f}<extra></extra>",
    ))
    fig_heat.update_layout(
        xaxis_title="Discount Depth",
        yaxis_title="",
        height=max(300, len(pivot) * 28 + 80),
        margin=dict(l=180, r=30, t=30, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
        yaxis=dict(tickfont=dict(size=11)),
    )

    heatmap_card = dbc.Card([
        dbc.CardHeader(html.H6("Profit Heatmap — All SKUs x All Discount Levels", className="mb-0")),
        dbc.CardBody(dcc.Graph(figure=fig_heat, config={"displayModeBar": False})),
    ], className="shadow-sm mb-3")

    # Bucket tables
    bucket_sections = []
    for bucket_name in ["High Opportunity", "Moderate", "Avoid"]:
        bucket_df   = best_per_sku[best_per_sku["bucket"] == bucket_name].sort_values("net_profit", ascending=False)
        if bucket_df.empty:
            continue
        color_map   = {"High Opportunity": "success", "Moderate": "warning", "Avoid": "danger"}
        badge_color = color_map.get(bucket_name, "secondary")

        rows = []
        for _, row in bucket_df.iterrows():
            profit_cls = "text-success fw-bold" if row["net_profit"] > 0 else "text-danger fw-bold"
            rows.append(html.Tr([
                html.Td(row["product_name"]),
                html.Td(row["category"]),
                html.Td(f"${row['regular_price']:.2f}"),
                html.Td(f"{row['gross_margin']:.0f}%"),
                html.Td(f"{row['elasticity']:.2f}"),
                html.Td(dbc.Badge(f"{int(row['optimal_disc']*100)}% off", color="primary", pill=True)),
                html.Td(f"${row['net_profit']:,.0f}", className=profit_cls),
                html.Td(f"{row['promo_roi']:.2f}x"),
                html.Td(dbc.Button(
                    "Analyze →",
                    href=f"/analyze",
                    color="outline-primary",
                    size="sm",
                    external_link=False,
                )),
            ]))

        table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Product"), html.Th("Category"), html.Th("Price"),
                html.Th("Margin"), html.Th("Elasticity"), html.Th("Best Discount"),
                html.Th(f"Net Profit ({promo_weeks}w)"), html.Th("ROI"), html.Th(""),
            ])),
            html.Tbody(rows)],
            bordered=True, hover=True, responsive=True, size="sm",
        )

        bucket_sections.append(
            dbc.Card([
                dbc.CardHeader(
                    dbc.Row([
                        dbc.Col(html.H6(f"{bucket_name}  ({len(bucket_df)} SKUs)", className="mb-0 fw-bold"), width="auto"),
                        dbc.Col(
                            dbc.Badge(f"Total: ${bucket_df['net_profit'].sum():,.0f}", color=badge_color, className="ms-2"),
                            width="auto",
                        ),
                    ], align="center"),
                ),
                dbc.CardBody(table),
            ], className="shadow-sm mb-3")
        )

    # Elasticity vs Gross Margin scatter
    fig_scatter = go.Figure(go.Scatter(
        x=best_per_sku["gross_margin"],
        y=best_per_sku["elasticity"],
        mode="markers+text",
        text=best_per_sku["product_name"].str.split().str[0],  # first word
        textposition="top center",
        marker=dict(
            size=12,
            color=best_per_sku["net_profit"],
            colorscale="RdYlGn",
            cmid=0,
            showscale=True,
            colorbar=dict(title="Best Net Profit ($)", tickformat="$,.0f"),
        ),
        hovertemplate="%{text}<br>Margin: %{x:.0f}%<br>Elasticity: %{y:.2f}<br>Profit: $%{marker.color:,.0f}<extra></extra>",
    ))
    fig_scatter.update_layout(
        xaxis_title="Gross Margin %",
        yaxis_title="Price Elasticity",
        height=320,
        margin=dict(l=55, r=30, t=30, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
        yaxis=dict(gridcolor="#e2e8f0"),
        xaxis=dict(gridcolor="#e2e8f0"),
    )
    scatter_card = dbc.Card([
        dbc.CardHeader(html.H6("Elasticity vs Margin — colour = best net profit", className="mb-0")),
        dbc.CardBody(dcc.Graph(figure=fig_scatter, config={"displayModeBar": False})),
    ], className="shadow-sm mb-3")

    return html.Div([
        kpi_row,
        dbc.Row([
            dbc.Col(heatmap_card, md=8),
            dbc.Col(scatter_card, md=4),
        ], className="g-3"),
        *bucket_sections,
    ])


def _kpi(label: str, value: str, color: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([
            html.P(label, className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H4(value, className=f"fw-bold mb-0 text-{color}"),
        ], className="text-center p-2"),
        className="border-0 bg-light h-100",
    )

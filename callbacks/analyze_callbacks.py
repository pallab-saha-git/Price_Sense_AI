"""
callbacks/analyze_callbacks.py
───────────────────────────────
Dash callbacks for the Analyze page.
Triggers the full ML pipeline on form submit and populates the result panels.
"""

from __future__ import annotations

from datetime import date

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
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

    # ── Populate store dropdown — filtered by channel selection ───────────────
    @app.callback(
        Output("dd-store", "options"),
        Output("dd-store", "value"),
        Output("dd-store", "disabled"),
        Input("chk-channels", "value"),
    )
    def populate_store_dropdown(channels):
        from services.promo_analyzer import _load_data
        try:
            data      = _load_data()
            stores_df = data.get("stores")
            if stores_df is None or stores_df.empty:
                return [{"label": "All Stores", "value": "ALL"}], "ALL", False

            channels = channels or []

            # Determine which store channels are active
            want_physical = "physical" in channels
            want_online   = "online"   in channels

            filtered = stores_df.copy()
            if want_physical and not want_online:
                filtered = filtered[filtered["channel"] == "physical"]
            elif want_online and not want_physical:
                filtered = filtered[filtered["channel"] == "online"]
            # if both or neither selected — show all

            filtered = filtered.sort_values("store_name")
            opts = [{"label": "All Stores", "value": "ALL"}]
            for _, row in filtered.iterrows():
                ch_label = " [Online]" if row.get("channel") == "online" else ""
                opts.append({
                    "label": f"{row['store_name']} ({row.get('region', '')}){ch_label}",
                    "value": row["store_id"],
                })

            # Auto-select + disable when only online (single store)
            if want_online and not want_physical:
                online_stores = filtered[filtered["channel"] == "online"]
                auto_val  = online_stores.iloc[0]["store_id"] if not online_stores.empty else "ALL"
                return opts, auto_val, True

            return opts, "ALL", False
        except Exception as exc:
            logger.error(f"populate_store_dropdown error: {exc}")
            return [{"label": "All Stores", "value": "ALL"}], "ALL", False

    # ── Populate category dropdown dynamically from the products table ────────
    @app.callback(
        Output("dd-category", "options"),
        Input("dd-category",  "id"),   # fires once on page load
    )
    def populate_category_options(_):
        from services.promo_analyzer import _load_data
        try:
            data = _load_data()
            cats = sorted(data["products"]["category"].dropna().unique())
            opts = [{"label": "All Categories", "value": "ALL"}]
            for c in cats:
                opts.append({"label": c, "value": c})
            return opts
        except Exception as exc:
            logger.error(f"populate_category_options error: {exc}")
            return [{"label": "All Categories", "value": "ALL"}]

    # ── Populate Product (subcategory) dropdown by category ───────────────────
    @app.callback(
        Output("dd-analyze-product", "options"),
        Output("dd-analyze-product", "value"),
        Input("dd-category", "value"),
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

    # ── Populate SKU dropdown by category + product ────────────────────────────
    @app.callback(
        Output("dd-product", "options"),
        Output("dd-product", "value"),
        Input("dd-category",        "value"),
        Input("dd-analyze-product", "value"),
    )
    def populate_sku_options(category, product):
        from services.promo_analyzer import _load_data
        import pandas as _pd
        try:
            data = _load_data()
            df   = data["products"].copy()
            if category and category != "ALL":
                df = df[df["category"] == category]
            if product and product != "ALL":
                df = df[df["subcategory"] == product]
            sort_cols = [c for c in ["category", "subcategory", "size"] if c in df.columns]
            df = df.sort_values(sort_cols) if sort_cols else df
            options = []
            for _, row in df.iterrows():
                size_label = ""
                if "size" in row and _pd.notna(row.get("size")):
                    size_label = f" — {int(row['size'])}{row.get('size_unit', '')}"
                cat_prefix = "" if (category and category != "ALL") else f"[{row.get('category', '')}] "
                options.append({
                    "label": f"{cat_prefix}{row['subcategory']}{size_label}  [{row['sku_id']}]",
                    "value": row["sku_id"],
                })
            default_val = options[0]["value"] if options else "NUT-PIST-16"
            return options, default_val
        except Exception as exc:
            logger.error(f"populate_sku_options error: {exc}")
            return [], "NUT-PIST-16"

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

        # ── Guard: at least one channel must be selected ───────────────────────
        if not channels:
            warn = dbc.Alert(
                [
                    html.I(className="fa fa-wifi-slash me-2"),
                    html.Strong("No channel selected. "),
                    "Please enable at least one channel (In-store or Online) to run the analysis.",
                ],
                color="warning",
                className="mt-2",
            )
            from components.recommendation_card import empty_recommendation_card
            return empty_recommendation_card(), warn

        try:
            discount_pct = discount_pct_int / 100.0
            start_date   = date.fromisoformat(start_date_str[:10])
            end_date     = date.fromisoformat(end_date_str[:10])
            store_ids    = None if store_id == "ALL" else [store_id]

            logger.info(f"Running analysis: {sku_id} @ {discount_pct_int}% off {start_date}→{end_date} channels={channels} store={store_id}")

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

            import pandas as _pd
            data        = _load_data()
            products_df = data["products"]
            _s = data.get("stores");  stores_df  = _s  if _s  is not None else _pd.DataFrame()
            _g = data.get("segments"); segments_df = _g if _g is not None else _pd.DataFrame()
            promos_df   = data["promos"]
            product_row = products_df[products_df["sku_id"] == sku_id]
            reg_price   = float(product_row.iloc[0]["regular_price"]) if not product_row.empty else 10.0
            cost_price  = float(product_row.iloc[0]["cost_price"])    if not product_row.empty else 5.0

            rec_card       = recommendation_card(result)
            elast_chart    = elasticity_chart(result.elasticity, reg_price, result.forecast.baseline_weekly)
            cannibal_chart = cannibalization_bar(result.cannibalization.impacts, result.pnl.product_name)
            risk_g         = risk_gauge(result.risk)
            risk_bars      = risk_factor_bars(result.risk)
            insight_cards  = insight_panel(insights)

            # ── Historical promo performance for this SKU ──────────────────
            hist_sku_promos = (
                promos_df[promos_df["sku_id"] == sku_id].copy()
                if not promos_df.empty and "sku_id" in promos_df.columns
                else __import__("pandas").DataFrame()
            )
            hist_chart_panel = _build_historical_promo_chart(hist_sku_promos, sku_id)

            # ── Store-level breakdown (top stores by expected lift) ─────────
            store_breakdown_panel = _build_store_breakdown(
                stores_df, segments_df, result, store_ids
            )

            # ── Customer segment panel ─────────────────────────────────────
            segment_panel = _build_segment_panel(result)

            # Tab 1 — Overview (existing charts)
            overview_tab_content = dbc.Row(
                [
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("Elasticity Curve", className="mb-0")),
                                  dbc.CardBody(elast_chart)], className="shadow-sm"),
                        md=6, className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("Cannibalization Impact", className="mb-0")),
                                  dbc.CardBody(cannibal_chart)], className="shadow-sm"),
                        md=6, className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("Risk Score", className="mb-0")),
                                  dbc.CardBody(risk_g)], className="shadow-sm"),
                        md=4, className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card([dbc.CardHeader(html.H6("Risk Factor Breakdown", className="mb-0")),
                                  dbc.CardBody(risk_bars)], className="shadow-sm"),
                        md=5, className="mb-3",
                    ),
                    dbc.Col(segment_panel, md=3, className="mb-3"),
                    dbc.Col(hist_chart_panel, md=6, className="mb-3"),
                    dbc.Col(store_breakdown_panel, md=6, className="mb-3"),
                    dbc.Col(insight_cards, md=12, className="mb-3"),
                ],
                className="g-2",
            )

            # Tab 2 — Seasonality
            seasonality_tab_content = _build_seasonality_tab(result, start_date, end_date)

            # Tab 3 — Discount waterfall
            discount_tab_content = _build_discount_analysis_tab(
                result, sku_id, result.pnl.product_name, reg_price, cost_price,
                result.forecast.baseline_weekly,
            )

            tabs_layout = dbc.Tabs(
                [
                    dbc.Tab(overview_tab_content,      label="Overview",          tab_id="tab-overview",     className="pt-3"),
                    dbc.Tab(seasonality_tab_content,   label="Seasonality",        tab_id="tab-season",       className="pt-3"),
                    dbc.Tab(discount_tab_content,      label="Discount Analysis",  tab_id="tab-discount",     className="pt-3"),
                ],
                id="analyze-tabs",
                active_tab="tab-overview",
                className="mt-3",
            )

            return rec_card, tabs_layout

        except Exception as exc:
            logger.exception(f"Analysis failed: {exc}")
            error_card = dbc.Alert(
                [
                    html.H5("Analysis Error", className="alert-heading"),
                    html.P(str(exc)),
                    html.P("Please check your inputs and try again.", className="mb-0"),
                ],
                color="danger",
            )
            return error_card, html.Div()


# ── Helper builders ────────────────────────────────────────────────────────────

def _build_historical_promo_chart(hist_df, sku_id: str):
    """Bar chart of historical promotions + their discount depths for a SKU."""
    import pandas as pd
    import plotly.graph_objects as go

    if hist_df.empty:
        content = html.P("No historical promotions found for this SKU.",
                          className="text-muted text-center mt-3")
    else:
        hist_df = hist_df.sort_values("start_date").tail(20)
        labels  = [str(r["start_date"])[:10] for _, r in hist_df.iterrows()]
        discounts = [float(r.get("discount_pct", 0)) * 100 for _, r in hist_df.iterrows()]

        # Try to get actual lift if column exists
        lift_col = None
        for col in ["actual_lift_pct", "lift_pct", "realized_lift"]:
            if col in hist_df.columns:
                lift_col = col
                break

        bars = [go.Bar(
            x=labels,
            y=discounts,
            name="Discount %",
            marker_color="#3b82f6",
            text=[f"{d:.0f}%" for d in discounts],
            textposition="outside",
        )]
        if lift_col:
            lifts = [float(r.get(lift_col, 0)) * 100 for _, r in hist_df.iterrows()]
            bars.append(go.Bar(
                x=labels,
                y=lifts,
                name="Actual Lift %",
                marker_color="#10b981",
                text=[f"+{l:.0f}%" for l in lifts],
                textposition="outside",
            ))

        fig = go.Figure(bars)
        fig.update_layout(
            barmode="group",
            height=260,
            margin=dict(l=30, r=10, t=20, b=60),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.35),
            xaxis=dict(tickangle=-40, tickfont=dict(size=11)),
            yaxis=dict(title="Percentage", gridcolor="#e2e8f0"),
            font=dict(family="Inter, sans-serif", size=12),
        )
        from dash import dcc as _dcc
        content = _dcc.Graph(figure=fig, config={"displayModeBar": False})

    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Historical Promo Performance (This SKU)", className="mb-0")),
            dbc.CardBody(content),
        ],
        className="shadow-sm h-100",
    )


def _build_store_breakdown(stores_df, segments_df, result, store_ids):
    """Rank stores by expected promo lift using segment response multipliers."""
    import pandas as pd

    if stores_df.empty or segments_df.empty:
        content = html.P("Store or segment data not available.",
                          className="text-muted text-center mt-3")
        return dbc.Card([
            dbc.CardHeader(html.H6("Store-Level Breakdown (Top 10)", className="mb-0")),
            dbc.CardBody(content),
        ], className="shadow-sm h-100")

    # Aggregate segment response per store (weighted average)
    resp_by_store = (
        segments_df
        .groupby("store_id")
        .apply(lambda g: (g["promo_response_multiplier"] * g["segment_share_pct"]).sum() / g["segment_share_pct"].sum())
        .reset_index(name="weighted_response")
    )

    merged = stores_df.merge(resp_by_store, on="store_id", how="left")
    merged["weighted_response"] = merged["weighted_response"].fillna(1.0)

    # If a specific store scope was selected, highlight those stores
    if store_ids:
        merged = merged[merged["store_id"].isin(store_ids) | ~merged["store_id"].isin(store_ids)]

    base_lift_pct = result.lift_pct  # already in percentage points
    merged["expected_lift_pct"] = (base_lift_pct * merged["weighted_response"]).round(1)
    merged = merged.sort_values("expected_lift_pct", ascending=False).head(10)

    rows = []
    rank_colors = ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd",
                   "#bfdbfe", "#dbeafe", "#eff6ff", "#f0f9ff", "#f8fafc"]
    for i, (_, row) in enumerate(merged.iterrows()):
        color = rank_colors[i] if i < len(rank_colors) else "#f8fafc"
        lift_pct_val = row["expected_lift_pct"]
        lift_badge_color = "success" if lift_pct_val >= base_lift_pct else "warning"
        rows.append(
            html.Tr([
                html.Td(html.Strong(f"#{i+1}"), style={"width": "36px"}),
                html.Td(
                    [html.Div(row["store_name"], style={"fontWeight": 600, "fontSize": "13px"}),
                     html.Small(f"{row.get('city', '')} · {row.get('region', '')}", className="text-muted")],
                ),
                html.Td(
                    dbc.Badge(f"+{lift_pct_val:.1f}%", color=lift_badge_color, pill=True),
                    className="text-end",
                ),
            ])
        )

    table = dbc.Table(
        [html.Thead(html.Tr([html.Th(""), html.Th("Store"), html.Th("Expected Lift", className="text-end")])),
         html.Tbody(rows)],
        bordered=False, hover=True, size="sm",
    )
    scope_note = html.Small(
        f"Based on customer segment mix · Showing top 10 out of {len(stores_df)} stores",
        className="text-muted d-block mt-2",
    )

    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Store-Level Breakdown (Top 10)", className="mb-0")),
            dbc.CardBody([table, scope_note], style={"overflowY": "auto", "maxHeight": "300px"}),
        ],
        className="shadow-sm h-100",
    )


def _build_segment_panel(result):
    """Customer segment signals panel showing share & promo response per segment."""
    segments = getattr(result, "segment_summary", [])
    seg_mult = getattr(result, "seg_multiplier", 1.0)

    if not segments:
        content = html.P("Segment data not available.", className="text-muted text-center mt-3")
    else:
        seg_order = {"price_sensitive": 0, "occasional": 1, "loyalist": 2}
        segments  = sorted(segments, key=lambda s: seg_order.get(s["segment"], 9))
        seg_colors = {"price_sensitive": "#ef4444", "loyalist": "#10b981", "occasional": "#f59e0b"}

        rows = []
        for s in segments:
            color = seg_colors.get(s["segment"], "#64748b")
            rows.append(html.Tr([
                html.Td(html.Span(
                    s["segment"].replace("_", " ").title(),
                    style={"color": color, "fontWeight": 600, "fontSize": "12.5px"},
                )),
                html.Td(f"{s['share_pct']:.0f}%", className="text-center"),
                html.Td(f"{s['response']:.2f}x", className="text-center"),
                html.Td(html.Small(f"{s['elasticity']:.2f}", className="text-muted"), className="text-center"),
            ]))

        mult_color = "#10b981" if seg_mult >= 1.0 else "#ef4444"
        mult_badge = dbc.Badge(
            f"Multiplier: {seg_mult:.2f}x",
            color="success" if seg_mult >= 1.0 else "danger",
            pill=True,
            className="mb-2",
        )

        table = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Segment", style={"fontSize": "11px"}),
                html.Th("Share", className="text-center", style={"fontSize": "11px"}),
                html.Th("Resp.", className="text-center", style={"fontSize": "11px"}),
                html.Th("Elast.", className="text-center", style={"fontSize": "11px"}),
            ])),
             html.Tbody(rows)],
            bordered=False, size="sm",
        )
        content = html.Div([mult_badge, table])

    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Customer Segment Signals", className="mb-0")),
            dbc.CardBody(content),
        ],
        className="shadow-sm h-100",
    )


# ── Seasonality Tab ────────────────────────────────────────────────────────────

def _build_seasonality_tab(result, start_date, end_date):
    """Builds the Seasonality tab showing weekly demand index and promo timing quality."""
    from dash import dcc as _dcc
    import plotly.graph_objects as go

    seas_idx = result.forecast.seasonality_index
    if not seas_idx:
        return html.P("No seasonality data available — insufficient sales history.", className="text-muted p-3")

    weeks  = sorted(seas_idx.keys())
    values = [seas_idx[w] for w in weeks]
    target_week = int(start_date.isocalendar().week)

    # Colour bars by value bucket
    def _bar_color(w, v):
        if w == target_week:
            return "#7c3aed"   # purple → selected promotion week
        if v >= 1.15:          return "#10b981"   # high season
        if v >= 1.0:            return "#3b82f6"   # above average
        if v >= 0.85:           return "#94a3b8"   # below average
        return "#ef4444"       # low season

    colors  = [_bar_color(w, v) for w, v in zip(weeks, values)]
    texts   = [f"{v:.2f}x" if w == target_week else "" for w, v in zip(weeks, values)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weeks, y=values,
        marker_color=colors,
        text=texts,
        textposition="outside",
        hovertemplate="Week %{x}: %{y:.2f}x demand<extra></extra>",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#94a3b8", line_width=1,
                  annotation_text="avg (1.00x)", annotation_position="right")

    promo_seas = seas_idx.get(target_week, 1.0)
    if promo_seas != 1.0:
        fig.add_annotation(
            x=target_week, y=promo_seas,
            text=f"Wk {target_week}: {promo_seas:.2f}x",
            showarrow=True, arrowhead=2,
            bgcolor="#1e293b", font=dict(color="white", size=11),
            yshift=10,
        )

    # Shade Q4 peaks (weeks 44-52)
    fig.add_vrect(x0=43.5, x1=52.5, fillcolor="#fef08a", opacity=0.15,
                  annotation_text="Q4 Peak", annotation_position="top left")

    fig.update_layout(
        xaxis=dict(title="Week of Year", tickmode="linear", dtick=4, gridcolor="#e2e8f0"),
        yaxis=dict(title="Demand Multiplier", gridcolor="#e2e8f0"),
        height=300,
        margin=dict(l=45, r=20, t=30, b=45),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
    )

    # Seasonal timing KPIs
    peak_week = max(seas_idx, key=seas_idx.get)
    peak_val  = seas_idx[peak_week]
    low_week  = min(seas_idx, key=seas_idx.get)
    low_val   = seas_idx[low_week]

    if promo_seas >= 1.15:
        timing_label, timing_color = "Peak Season", "success"
        timing_note = "Excellent timing — high demand amplifies promo lift."
    elif promo_seas >= 1.0:
        timing_label, timing_color = "Good Timing", "primary"
        timing_note = "Above-average demand — solid promotion window."
    elif promo_seas >= 0.85:
        timing_label, timing_color = "Off-Peak", "warning"
        timing_note = f"Below-average demand. Consider shifting to week {peak_week} ({peak_val:.2f}x)."
    else:
        timing_label, timing_color = "Low Season", "danger"
        timing_note = f"Lowest demand period. Strong against-trend promo cost. Best week: {peak_week}."

    kpi_row = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P("Promo Week Demand", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H4(f"{promo_seas:.2f}x", className=f"fw-bold mb-0 {'text-success' if promo_seas >= 1.0 else 'text-danger'}"),
            html.Small(f"Week {target_week}", className="text-muted"),
        ]), className="text-center border-0 bg-light"), md=3, className="mb-2"),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P("Peak Demand Week", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H4(f"Week {peak_week}", className="fw-bold mb-0 text-success"),
            html.Small(f"{peak_val:.2f}x demand", className="text-muted"),
        ]), className="text-center border-0 bg-light"), md=3, className="mb-2"),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P("Lowest Demand Week", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H4(f"Week {low_week}", className="fw-bold mb-0 text-danger"),
            html.Small(f"{low_val:.2f}x demand", className="text-muted"),
        ]), className="text-center border-0 bg-light"), md=3, className="mb-2"),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.P("Timing Quality", className="text-muted mb-1", style={"fontSize": "12px"}),
            dbc.Badge(timing_label, color=timing_color, className="fs-6 py-1 px-2"),
            html.Div(html.Small(timing_note, className="text-muted mt-1 d-block"), style={"fontSize": "11px"}),
        ]), className="text-center border-0 bg-light"), md=3, className="mb-2"),
    ], className="g-2 mb-3")

    # Peak seasons bar (sparklines for seasonal products)
    from services.promo_analyzer import _load_data as _ld
    try:
        data = _ld()
        prow = data["products"][data["products"]["sku_id"] == result.sku_id]
        peak_seasons = prow.iloc[0].get("peak_seasons", []) if not prow.empty else []
        if isinstance(peak_seasons, str):
            import json
            try: peak_seasons = json.loads(peak_seasons)
            except: peak_seasons = []
        is_seasonal = prow.iloc[0].get("is_seasonal", False) if not prow.empty else False
    except Exception:
        peak_seasons, is_seasonal = [], False

    season_badges = html.Div()
    if is_seasonal and peak_seasons:
        badges = [dbc.Badge(s.replace("_", " ").title(), color="warning", className="me-1 mb-1 text-dark")
                  for s in peak_seasons]
        season_badges = dbc.Alert(
            [html.Strong("Peak Sale Events: "), html.Span(badges)],
            color="warning", className="py-2 px-3 mb-3",
        )

    return html.Div([kpi_row, season_badges, _dcc.Graph(figure=fig, config={"displayModeBar": False})])


# ── Discount Analysis Tab ──────────────────────────────────────────────────────

def _build_discount_analysis_tab(result, sku_id, product_name, regular_price, cost_price, baseline_weekly):
    """Waterfall chart + table comparing profitability at different discount levels."""
    from dash import dcc as _dcc
    import plotly.graph_objects as go
    from models.profit_calculator import calculate_promo_pnl
    from models.elasticity import estimate_volume_lift

    discount_levels = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    rows = []

    # Scale cannibalization proportionally to discount depth
    # (deeper discounts cause more cross-SKU volume diversion)
    base_cannibal = result.cannibalization.total_margin_loss
    base_disc     = result.discount_pct if result.discount_pct > 0 else 0.10

    for d in discount_levels:
        lift = estimate_volume_lift(result.elasticity.elasticity, d)
        scaled_cannibal = base_cannibal * (d / base_disc) if base_disc > 0 else 0.0
        pnl  = calculate_promo_pnl(
            sku_id=sku_id,
            product_name=product_name,
            regular_price=regular_price,
            cost_price=cost_price,
            discount_pct=d,
            baseline_weekly_units=baseline_weekly,
            volume_lift_pct=lift,
            cannibalization_cost=scaled_cannibal,
        )
        rows.append({
            "label":  f"{int(d*100)}% off",
            "disc":   d,
            "lift":   round(lift * 100, 1),
            "units":  round(pnl.incremental_units, 0),
            "profit": pnl.net_incremental_profit,
            "roi":    pnl.promo_roi,
            "margin": round(pnl.promo_margin_pct, 1),
            "tier":   pnl.recommendation_tier,
        })

    labels  = [r["label"]  for r in rows]
    profits = [r["profit"] for r in rows]
    tier_colors = {
        "RECOMMENDED":     "#10b981",
        "MARGINAL":        "#f59e0b",
        "NOT_RECOMMENDED": "#ef4444",
    }
    bar_colors = [tier_colors.get(r["tier"], "#94a3b8") for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=profits,
        marker_color=bar_colors,
        text=[f"${p:,.0f}" for p in profits],
        textposition=["outside" if p >= 0 else "outside" for p in profits],
        hovertemplate="%{x}<br>Net profit: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="solid", line_color="#1e293b", line_width=1.5)

    # Mark currently-selected discount
    selected_d = result.discount_pct
    for r in rows:
        if abs(r["disc"] - selected_d) < 0.01:
            fig.add_annotation(
                x=r["label"], y=r["profit"],
                text="← selected",
                showarrow=False,
                font=dict(color="#7c3aed", size=11, family="Inter"),
                xshift=55, yshift=5,
            )

    fig.update_layout(
        xaxis_title="Discount Level",
        yaxis_title="Net Incremental Profit ($)",
        height=280,
        margin=dict(l=55, r=20, t=20, b=45),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#e2e8f0", zeroline=False),
        font=dict(family="Inter, sans-serif", size=12),
    )

    # Legend pills
    legend_pills = html.Div([
        dbc.Badge("● Recommended", color="success", className="me-2 text-white"),
        dbc.Badge("● Marginal",    color="warning", className="me-2 text-white"),
        dbc.Badge("● Not Recommended", color="danger", className="me-2 text-white"),
    ], className="mb-2")

    # Detailed table
    _rec_badge = {"RECOMMENDED": "success", "MARGINAL": "warning", "NOT_RECOMMENDED": "danger"}
    _rec_icon  = {"RECOMMENDED": "Rec", "MARGINAL": "Marginal", "NOT_RECOMMENDED": "Not Rec"}
    table_rows = []
    for r in rows:
        is_selected  = abs(r["disc"] - selected_d) < 0.01
        row_style    = {"background": "#ede9fe"} if is_selected else {}
        profit_class = "text-success fw-bold" if r["profit"] > 0 else "text-danger fw-bold"
        table_rows.append(html.Tr([
            html.Td(html.Strong(r["label"]) if is_selected else r["label"],
                    style={"fontWeight": 700 if is_selected else "normal"}),
            html.Td(f"{r['margin']:.1f}%"),
            html.Td(f"+{r['lift']:.0f}%"),
            html.Td(f"+{int(r['units']):,}"),
            html.Td(f"${r['profit']:,.0f}", className=profit_class),
            html.Td(f"{r['roi']:.2f}x"),
            html.Td(dbc.Badge(
                f"{_rec_icon[r['tier']]} {r['tier'].replace('_', ' ').title()}",
                color=_rec_badge.get(r["tier"], "secondary"),
                className="text-white",
            )),
        ], style=row_style))

    table = dbc.Table(
        [html.Thead(html.Tr([
            html.Th("Discount"), html.Th("Promo Margin"), html.Th("Vol. Lift"),
            html.Th("Incr. Units"), html.Th("Net Profit"), html.Th("ROI"),
            html.Th("Decision"),
        ])),
        html.Tbody(table_rows)],
        bordered=True, hover=True, responsive=True, size="sm", className="mt-3",
    )

    # Best-discount call-out
    best = max(rows, key=lambda r: r["profit"])
    callout_color = "success" if best["profit"] > 0 else ("warning" if best["profit"] > -100 else "danger")
    if best["profit"] > 0:
        callout_msg = f"Optimal discount: {best['label']} — projected net profit ${best['profit']:,.0f} with {best['lift']:.0f}% volume lift."
    else:
        callout_msg = f"No discount level achieves positive profit at current elasticity. Nearest: {best['label']} (${best['profit']:,.0f}). Consider traffic & basket value."

    callout = dbc.Alert([html.Strong("Insight: "), callout_msg], color=callout_color, className="py-2 px-3 mb-3")

    return html.Div([callout, legend_pills, _dcc.Graph(figure=fig, config={"displayModeBar": False}), table])

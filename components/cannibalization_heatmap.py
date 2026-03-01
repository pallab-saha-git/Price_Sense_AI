"""
components/cannibalization_heatmap.py
──────────────────────────────────────
Plotly heatmap of the cross-elasticity matrix.
Shows how a price change in one SKU affects volumes of related SKUs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc


def cannibalization_heatmap(cross_matrix: pd.DataFrame) -> dcc.Graph:
    """
    Renders the cross-elasticity matrix as a heatmap.
    Rows = focal SKU price change, Columns = affected SKU volume response.
    Color scale: red = high cannibalization, white = independent, blue = halo.
    """
    if cross_matrix.empty:
        return _empty_heatmap("No cross-elasticity data available")

    z_vals  = cross_matrix.values.astype(float)
    row_labels = [_shorten(s) for s in cross_matrix.index.tolist()]
    col_labels = [_shorten(s) for s in cross_matrix.columns.tolist()]

    # Replace NaN (own-price diagonal) with 0 for display
    z_display = np.where(np.isnan(z_vals), 0.0, z_vals)

    hover_text = []
    for i, row_name in enumerate(cross_matrix.index):
        row_hover = []
        for j, col_name in enumerate(cross_matrix.columns):
            v = z_vals[i, j]
            if np.isnan(v):
                row_hover.append(f"<b>{row_name}</b><br>Own-price")
            elif v > 0.1:
                row_hover.append(f"<b>{col_name}</b> loses<br>{v:.2f} vol per 1% price cut in<br><b>{row_name}</b>")
            else:
                row_hover.append(f"Independent<br>{row_name} ↔ {col_name}")
        hover_text.append(row_hover)

    fig = go.Figure(go.Heatmap(
        z=z_display,
        x=col_labels,
        y=row_labels,
        text=[[f"{v:.2f}" if not np.isnan(v) else "" for v in row] for row in z_vals],
        texttemplate="%{text}",
        colorscale=[
            [0.0,  "#2980b9"],   # blue = complement (halo)
            [0.45, "#ecf0f1"],
            [0.5,  "#ffffff"],
            [0.55, "#f8d7da"],
            [1.0,  "#c0392b"],   # red = strong cannibalization
        ],
        zmin=-0.5,
        zmax=1.0,
        showscale=True,
        colorbar=dict(
            title="Cross-Elasticity",
            tickvals=[-0.5, 0, 0.5, 1.0],
            ticktext=["Complement", "Neutral", "Moderate", "Strong Substitute"],
        ),
        hoverinfo="text",
        hovertext=hover_text,
    ))

    fig.update_layout(
        title=dict(text="🔄 Cannibalization Matrix (Cross-Elasticity)", font=dict(size=14)),
        xaxis_title="Affected SKU (volume response)",
        yaxis_title="Focal SKU (price change)",
        template="plotly_white",
        height=360,
        margin=dict(l=150, r=20, t=60, b=120),
        xaxis=dict(tickangle=-35),
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def cannibalization_bar(impacts, product_name: str) -> dcc.Graph:
    """
    Horizontal bar chart of cannibalization margin loss per affected SKU.
    """
    if not impacts:
        return _empty_heatmap("No significant cannibalization detected for this promotion.")

    names   = [i.affected_product_name for i in impacts]
    losses  = [i.margin_loss_dollars for i in impacts]
    vols    = [i.pct_volume_depressed for i in impacts]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=losses,
        y=names,
        orientation="h",
        marker_color="#e74c3c",
        text=[f"${v:,.0f}  ({p:.0f}% vol drop)" for v, p in zip(losses, vols)],
        textposition="outside",
        hovertemplate="%{y}<br>Margin loss: $%{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"🔄 Cannibalization from promoting {product_name}", font=dict(size=14)),
        xaxis_title="Margin Loss ($)",
        yaxis_title="",
        template="plotly_white",
        height=max(200, 100 + len(impacts) * 40),
        margin=dict(l=20, r=60, t=60, b=40),
        showlegend=False,
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _empty_heatmap(msg: str) -> dcc.Graph:
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="gray"))
    fig.update_layout(template="plotly_white", height=240,
                      margin=dict(l=20, r=20, t=40, b=20))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _shorten(name: str, max_len: int = 18) -> str:
    return name if len(name) <= max_len else name[:max_len - 1] + "…"

"""
components/elasticity_chart.py
───────────────────────────────
Plotly demand curve (price vs. volume) and elasticity waterfall.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dash import dcc

if TYPE_CHECKING:
    from models.elasticity import ElasticityResult

CHART_TEMPLATE = "plotly_white"


def elasticity_chart(result: "ElasticityResult", regular_price: float, baseline_units: float) -> dcc.Graph:
    """
    Render the price–demand curve for a SKU.
    Shows the expected volume at each discount level.
    """
    from models.elasticity import estimate_volume_lift

    discounts   = np.linspace(0, 0.40, 40)
    prices      = regular_price * (1 - discounts)
    volumes     = baseline_units * (1 + np.array([estimate_volume_lift(result.elasticity, d) for d in discounts]))

    fig = go.Figure()

    # Demand curve
    fig.add_trace(go.Scatter(
        x=prices,
        y=volumes,
        mode="lines",
        name="Demand curve",
        line=dict(color="#0f3460", width=3),
        hovertemplate="Price: $%{x:.2f}<br>Volume: %{y:,.0f} units<extra></extra>",
    ))

    # Base price marker
    fig.add_trace(go.Scatter(
        x=[regular_price],
        y=[baseline_units],
        mode="markers",
        name="Regular price",
        marker=dict(color="#27ae60", size=12, symbol="circle"),
        hovertemplate=f"Regular price: ${regular_price:.2f}<br>Baseline: {baseline_units:,.0f} units<extra></extra>",
    ))

    # Elasticity annotation
    fig.add_annotation(
        x=regular_price * 0.6,
        y=volumes.max() * 0.85,
        text=f"Elasticity: {result.elasticity:.2f}<br>R² = {result.r_squared:.2f}",
        showarrow=False,
        bgcolor="rgba(15,52,96,0.1)",
        bordercolor="#0f3460",
        borderwidth=1,
        font=dict(size=12),
    )

    fig.update_layout(
        title=dict(text="Price-Demand Elasticity Curve", font=dict(size=13)),
        xaxis_title="Price ($)",
        yaxis_title="Projected Weekly Units",
        template=CHART_TEMPLATE,
        height=320,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", y=-0.15),
        hovermode="x unified",
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def scenario_bar_chart(scenarios_df: pd.DataFrame) -> dcc.Graph:
    """
    Bar chart: Net Incremental Profit across discount scenarios.
    Highlights the optimal scenario in green.
    """
    df = scenarios_df.copy()

    if df.empty or "Discount" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="No scenario data available", template=CHART_TEMPLATE, height=320)
        return dcc.Graph(figure=fig, config={"displayModeBar": False})

    colors = []
    for _, row in df.iterrows():
        if row.get("Optimal?", "") and "Best" in str(row.get("Optimal?", "")):
            colors.append("#27ae60")
        elif float(str(row.get("_profit_raw", 0)).replace(",", "").replace("$", "") or 0) > 0:
            colors.append("#0f3460")
        else:
            colors.append("#e74c3c")

    fig = go.Figure(go.Bar(
        x=df["Discount"],
        y=df["_profit_raw"],
        marker_color=colors,
        text=[f"${v:,.0f}" for v in df["_profit_raw"]],
        textposition="outside",
        hovertemplate="Discount: %{x}<br>Net Profit: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Net Incremental Profit by Discount Level", font=dict(size=13)),
        xaxis_title="Discount Level",
        yaxis_title="Net Incremental Profit ($)",
        template=CHART_TEMPLATE,
        height=320,
        margin=dict(l=40, r=20, t=50, b=40),
        showlegend=False,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    return dcc.Graph(figure=fig, config={"displayModeBar": False})

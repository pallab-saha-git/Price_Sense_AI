"""
components/risk_gauge.py
─────────────────────────
Plotly gauge chart for the risk score (0.0–1.0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go
from dash import dcc

if TYPE_CHECKING:
    from models.risk_scorer import RiskResult


def risk_gauge(risk: "RiskResult") -> dcc.Graph:
    score = risk.total_score

    color = {
        "LOW":    "#27ae60",
        "MEDIUM": "#f39c12",
        "HIGH":   "#e74c3c",
    }.get(risk.band, "#95a5a6")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        number={"valueformat": ".2f", "font": {"size": 28}},
        delta={"reference": 0.30, "valueformat": ".2f"},
        gauge={
            "axis": {"range": [0, 1], "tickwidth": 1, "tickcolor": "darkgray"},
            "bar":  {"color": color, "thickness": 0.3},
            "steps": [
                {"range": [0.0, 0.3], "color": "#d5f5e3"},
                {"range": [0.3, 0.6], "color": "#fef9e7"},
                {"range": [0.6, 1.0], "color": "#fadbd8"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.85,
                "value": score,
            },
        },
        title={"text": f"Risk Score<br><span style='font-size:14px;color:{color}'>{risk.band}</span>"},
    ))

    fig.update_layout(
        height=240,
        margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_white",
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def risk_factor_bars(risk: "RiskResult") -> dcc.Graph:
    """Horizontal bar showing contribution of each risk factor."""
    factors     = risk.factors
    names       = [f.name for f in factors]
    weighted    = [f.weighted_score for f in factors]
    colors      = [
        "#27ae60" if f.raw_score < 0.3
        else "#f39c12" if f.raw_score < 0.6
        else "#e74c3c"
        for f in factors
    ]
    hover_texts = [f.description for f in factors]

    fig = go.Figure(go.Bar(
        x=weighted,
        y=names,
        orientation="h",
        marker_color=colors,
        text=[f"{f.raw_score:.2f}" for f in factors],
        textposition="inside",
        hovertext=hover_texts,
        hoverinfo="text+x",
    ))

    fig.add_vline(x=0, line_color="gray", opacity=0.3)

    fig.update_layout(
        title=dict(text="Risk Factor Breakdown", font=dict(size=13)),
        xaxis_title="Weighted contribution to total risk",
        yaxis_title="",
        template="plotly_white",
        height=280,
        margin=dict(l=10, r=20, t=50, b=30),
        showlegend=False,
    )

    return dcc.Graph(figure=fig, config={"displayModeBar": False})

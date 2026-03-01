"""
components/insight_panel.py
────────────────────────────
Renders AI or template-based insight strings as styled Dash Alert blocks.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def insight_panel(insights: list[str], title: str = "💡 AI Insights") -> dbc.Card:
    """
    Render a list of markdown insight strings as styled alert panels.
    Supports markdown bold via **text** → <strong>text</strong> conversion.
    """
    if not insights:
        return html.Div()

    def _parse_md(text: str) -> list:
        """Very lightweight markdown → dash children converter (bold + newlines)."""
        import re
        parts  = re.split(r"(\*\*.*?\*\*)", text)
        result = []
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                result.append(html.Strong(part[2:-2]))
            else:
                # Handle newlines as <br>
                lines = part.split("\n\n")
                for i, line in enumerate(lines):
                    result.append(line)
                    if i < len(lines) - 1:
                        result.append(html.Br())
        return result

    alert_colors = ["info", "secondary", "light"]

    children = [
        dbc.Alert(
            _parse_md(insight),
            color=alert_colors[i % len(alert_colors)],
            className="mb-2 py-2 px-3",
            style={"fontSize": "13.5px", "lineHeight": "1.55"},
        )
        for i, insight in enumerate(insights)
    ]

    return dbc.Card(
        [
            dbc.CardHeader(html.H6(title, className="mb-0 text-white"),
                           style={"background": "#1a1a2e"}),
            dbc.CardBody(children, className="p-2"),
        ],
        className="shadow-sm",
    )


def scenario_insight_panel(comparison) -> dbc.Card:
    """Render a single insight card for the scenario comparison page."""
    if comparison.optimal_row is None:
        msg = "No profitable discount level found for this SKU. Consider a vendor-funded deal or merchandising strategy instead."
        children = [dbc.Alert(msg, color="warning", className="mb-0")]
    else:
        r = comparison.optimal_row
        msg = (
            f"The optimal discount for **{comparison.product_name}** is "
            f"**{r.discount_label}**, which yields the highest net profit of "
            f"**${r.net_incremental_profit:,.0f}** at a **{r.promo_roi:.1f}x ROI**. "
            f"Risk is rated **{r.risk_band}**."
        )
        import re
        parts = re.split(r"(\*\*.*?\*\*)", msg)
        parsed = []
        for p in parts:
            if p.startswith("**") and p.endswith("**"):
                parsed.append(html.Strong(p[2:-2]))
            else:
                parsed.append(p)
        children = [dbc.Alert(parsed, color="success", className="mb-0")]

    return dbc.Card(
        [
            dbc.CardHeader(html.H6("💡 Scenario Insight", className="mb-0 text-white"),
                           style={"background": "#1a1a2e"}),
            dbc.CardBody(children, className="p-2"),
        ],
        className="shadow-sm mb-3",
    )

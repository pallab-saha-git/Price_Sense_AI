"""
components/scenario_table.py
──────────────────────────────
Dash AgGrid table for scenario comparison.
"""

from __future__ import annotations

import pandas as pd
import dash_ag_grid as dag
from dash import html
import dash_bootstrap_components as dbc


def scenario_table(df: pd.DataFrame) -> dag.AgGrid:
    """
    Renders a styled AgGrid scenario comparison table.
    Highlights optimal row in green, negative-profit rows in red.
    """
    display_cols = [c for c in df.columns if not c.startswith("_")]

    col_defs = [
        {"field": "Discount",          "pinned": "left", "width": 110},
        {"field": "Volume Lift",        "width": 110},
        {"field": "Incremental Units",  "width": 140},
        {"field": "Incr. Revenue",      "width": 130},
        {"field": "Net Profit",         "width": 130},
        {"field": "ROI",                "width": 80},
        {"field": "Cannibal. Cost",     "width": 130},
        {"field": "Risk",               "width": 90},
        {"field": "Decision",           "width": 200},
        {"field": "Optimal?",           "width": 100},
    ]

    row_class_rules = {
        "ag-row-green":  "params.data['Optimal?'] && params.data['Optimal?'].includes('Best')",
        "ag-row-red":    "params.data['Net Profit'] && params.data['Net Profit'].startsWith('$-')",
    }

    grid = dag.AgGrid(
        id="tbl-scenarios",
        rowData=df[display_cols].to_dict("records"),
        columnDefs=col_defs,
        defaultColDef={
            "sortable": True,
            "filter": False,
            "resizable": True,
        },
        rowClassRules=row_class_rules,
        dashGridOptions={
            "suppressCellFocus": True,
            "animateRows": True,
            "domLayout": "autoHeight",
        },
        style={"height": None},
        className="ag-theme-alpine",
    )

    return grid

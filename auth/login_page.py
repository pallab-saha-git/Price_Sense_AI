"""
auth/login_page.py
───────────────────
Dash pages for Login and Register — rendered before the NavBar (session-gated).
URL  /login    → login form
URL  /register → registration form (can be disabled via REGISTRATION_DISABLED)
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html



# ── Shared card wrapper ────────────────────────────────────────────────────────

def _auth_card(title: str, body: html.Div) -> html.Div:
    return html.Div(
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H4(title, className="mb-0 text-center fw-bold"),
                            className="py-3",
                        ),
                        dbc.CardBody(body, className="p-4"),
                    ],
                    className="shadow",
                ),
                width={"size": 4, "offset": 4},
                lg={"size": 4, "offset": 4},
                md={"size": 6, "offset": 3},
                sm={"size": 8, "offset": 2},
                xs=12,
            ),
            className="justify-content-center align-items-center",
            style={"minHeight": "80vh"},
        ),
        className="mt-5",
    )


# ── Login page ────────────────────────────────────────────────────────────────

def layout(**kwargs):
    """Login page layout (registered as /login)."""
    from config.settings import REGISTRATION_DISABLED
    return _auth_card(
        "💡 Price Sense AI",
        html.Div(
            [
                dbc.Label("Username"),
                dbc.Input(id="login-username", type="text", placeholder="Enter username",
                          autoFocus=True, className="mb-3"),

                dbc.Label("Password"),
                dbc.Input(id="login-password", type="password",
                          placeholder="Enter password", className="mb-3"),

                dbc.Button("Log In", id="btn-login", color="primary",
                           className="w-100 mb-2", n_clicks=0),

                html.Div(id="login-message", className="mt-2"),

                html.Hr(className="my-3"),

                html.Div(
                    [] if REGISTRATION_DISABLED else [
                        html.Small("Don't have an account? "),
                        dcc.Link("Register here", href="/register",
                                 className="text-decoration-none"),
                    ],
                    className="text-center",
                ),

                dcc.Location(id="login-redirect"),
                dcc.Store(id="login-store"),
            ]
        ),
    )


# ── Register page layout ─────────────────────────────────────────────────────

import sys


def _register_layout(**kwargs):
    from config.settings import REGISTRATION_DISABLED
    if REGISTRATION_DISABLED:
        return dbc.Alert(
            "Registration is currently disabled. Please contact an administrator.",
            color="warning",
            className="mt-5 mx-auto",
            style={"maxWidth": "500px"},
        )
    return _auth_card(
        "Create Account",
        html.Div(
            [
                dbc.Label("Username *"),
                dbc.Input(id="reg-username", type="text",
                          placeholder="At least 3 characters", autoFocus=True,
                          className="mb-2"),

                dbc.Label("Email (optional)"),
                dbc.Input(id="reg-email", type="email",
                          placeholder="you@example.com", className="mb-2"),

                dbc.Label("Password *"),
                dbc.Input(id="reg-password", type="password",
                          placeholder="At least 8 characters", className="mb-2"),

                dbc.Label("Confirm Password *"),
                dbc.Input(id="reg-confirm", type="password",
                          placeholder="Repeat password", className="mb-3"),

                dbc.Button("Create Account", id="btn-register", color="success",
                           className="w-100 mb-2", n_clicks=0),

                html.Div(id="reg-message", className="mt-2"),

                html.Hr(className="my-3"),
                html.Div(
                    [
                        html.Small("Already have an account? "),
                        dcc.Link("Log in", href="/login",
                                 className="text-decoration-none"),
                    ],
                    className="text-center",
                ),

                dcc.Location(id="reg-redirect"),
            ]
        ),
    )


# Register both pages now that layout callables are fully defined
dash.register_page("login",    path="/login",    title="Login — Price Sense AI",    layout=layout)
dash.register_page("register", path="/register", title="Register — Price Sense AI", layout=_register_layout)

"""
auth/auth_callbacks.py
───────────────────────
Dash callbacks for Login, Register, and Logout.
Sessions are stored server-side in a signed Flask cookie (flask.session).
"""

from __future__ import annotations

import flask
from dash import Input, Output, State, callback, dcc, html, no_update
import dash_bootstrap_components as dbc
from loguru import logger


# ── Session helpers ────────────────────────────────────────────────────────────

def get_session_user() -> dict | None:
    """Return the currently logged-in user dict from the Flask session, or None."""
    try:
        return flask.session.get("user")
    except RuntimeError:
        return None


def is_authenticated() -> bool:
    return get_session_user() is not None


def logout_user() -> None:
    flask.session.pop("user", None)


# ── Register callbacks on the app instance ─────────────────────────────────────

def register(app):

    # ── Login ──────────────────────────────────────────────────────────────────
    @app.callback(
        Output("login-message",  "children"),
        Output("login-redirect", "href"),
        Input("btn-login",       "n_clicks"),
        State("login-username",  "value"),
        State("login-password",  "value"),
        prevent_initial_call=True,
    )
    def handle_login(n_clicks, username, password):
        if not n_clicks:
            return no_update, no_update
        if not username or not password:
            return dbc.Alert("Please enter username and password.", color="warning"), no_update

        from auth.users import verify_user
        user = verify_user(username.strip(), password)
        if user is None:
            logger.warning(f"Failed login for username='{username}'")
            return dbc.Alert("Invalid username or password.", color="danger"), no_update

        flask.session["user"] = user
        flask.session.permanent = True
        logger.info(f"User '{username}' logged in.")
        return no_update, "/"     # redirect to dashboard after login

    # ── Register ───────────────────────────────────────────────────────────────
    @app.callback(
        Output("reg-message",  "children"),
        Output("reg-redirect", "href"),
        Input("btn-register",  "n_clicks"),
        State("reg-username",  "value"),
        State("reg-email",     "value"),
        State("reg-password",  "value"),
        State("reg-confirm",   "value"),
        prevent_initial_call=True,
    )
    def handle_register(n_clicks, username, email, password, confirm):
        if not n_clicks:
            return no_update, no_update

        from config.settings import REGISTRATION_DISABLED
        if REGISTRATION_DISABLED:
            return dbc.Alert("Registration is disabled.", color="danger"), no_update

        username = (username or "").strip()
        email    = (email    or "").strip()
        password = password or ""
        confirm  = confirm  or ""

        if not username or not password:
            return dbc.Alert("Username and password are required.", color="warning"), no_update
        if password != confirm:
            return dbc.Alert("Passwords do not match.", color="warning"), no_update

        from auth.users import create_user
        ok, msg = create_user(username=username, password=password, email=email)
        if not ok:
            return dbc.Alert(msg, color="danger"), no_update

        return (
            dbc.Alert("Account created! Redirecting to login…", color="success"),
            "/login",
        )

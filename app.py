"""
app.py — Price Sense AI entry point
=====================================
Run with:  python app.py
Docs at:   http://localhost:8050
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flask
import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html, no_update
from loguru import logger

from config.settings import (
    DATA_DIR,
    DEBUG,
    HOST,
    PORT,
    SECRET_KEY,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)

# ── Suppress verbose Prophet/Stan logging ─────────────────────────────────────
import logging
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

# ── Bootstrap database — prefer dunnhumby real data, fall back to synthetic ────
logger.info("Booting database ...")
try:
    # Try loading real dunnhumby data first (from pre-placed zips in data/zip/)
    from data.load_dunnhumby import load_dunnhumby
    load_dunnhumby(force=False)
except Exception as exc:
    logger.info(f"Dunnhumby load skipped or unavailable: {exc}")

try:
    from data.seed_data import seed_database
    seed_database(force=False)
    logger.success("Database ready.")
except Exception as exc:
    logger.warning(f"DB seed skipped: {exc}")

# ── Seed admin user (first-run only) ──────────────────────────────────────────
try:
    from auth.users import seed_admin_user
    seed_admin_user()
except Exception as exc:
    logger.warning(f"Admin seed skipped: {exc}")

# ── Pre-warm the in-memory data cache ─────────────────────────────────────────
logger.info("Pre-warming data cache ...")
try:
    from services.promo_analyzer import _load_data
    _load_data()
    logger.success("Data cache ready.")
except Exception as exc:
    logger.warning(f"Cache warm-up skipped: {exc}")

# ── Initialise Dash app ────────────────────────────────────────────────────────
app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    title="Price Sense AI",
    update_title=None,
)
server = app.server  # expose Flask server for gunicorn / production

# ── Configure Flask session ────────────────────────────────────────────────────
server.config["SECRET_KEY"]            = SECRET_KEY
server.config["SESSION_COOKIE_SECURE"] = not DEBUG          # HTTPS-only in prod
server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
server.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# ── Import auth pages so Dash registers /login and /register ──────────────────
import auth.login_page  # noqa: F401  (side-effect: registers pages)

# ── Routes that do NOT require authentication ──────────────────────────────────
PUBLIC_PATHS = {"/login", "/register", "/_dash-update-component",
                "/_dash-layout", "/_dash-dependencies", "/_dash-component-suites"}

# ── Auth guard — redirects to /login when not authenticated ───────────────────
@server.before_request
def require_login():
    path = flask.request.path
    # Allow static assets, public pages, and Dash internals
    if path.startswith(("/_dash", "/assets", "/_reload", "/favicon")):
        return
    if path in PUBLIC_PATHS:
        return
    if flask.session.get("user"):
        return
    return flask.redirect("/login")


# ── Logout route ──────────────────────────────────────────────────────────────
@server.route("/logout")
def logout():
    user = flask.session.pop("user", None)
    if user:
        logger.info(f"User '{user.get('username')}' logged out.")
    return flask.redirect("/login")


# ── Navigation bar ─────────────────────────────────────────────────────────────
NAV_LINKS = [
    ("/",                    "Dashboard"),
    ("/analyze",             "Analyze"),
    ("/compare",             "Compare"),
    ("/catalog",             "Catalog"),
    ("/profit-opportunities", "Profit Buckets"),
]

navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarBrand(
                [
                    html.Span("Price", style={"color": "#60a5fa", "fontWeight": 700}),
                    html.Span(" Sense ", style={"color": "#ffffff", "fontWeight": 400}),
                    html.Span("AI",     style={"color": "#fbbf24", "fontWeight": 700}),
                ],
                href="/",
                className="me-4 fs-5",
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavLink(label, href=href, active="exact",
                                    className="px-3 fw-semibold")
                        for href, label in NAV_LINKS
                    ]
                    + [
                        dbc.NavItem(
                            html.Span(id="nav-user-badge", className="navbar-text text-light px-2 small"),
                        ),
                        # Plain <a> so the browser always issues a full GET /logout to Flask
                        html.A(
                            "Logout",
                            href="/logout",
                            className="nav-link px-3 fw-semibold text-warning",
                        ),
                    ],
                    navbar=True,
                    className="ms-auto align-items-center",
                ),
                id="navbar-collapse",
                navbar=True,
            ),
        ],
        fluid=True,
    ),
    color="dark",
    dark=True,
    sticky="top",
    className="mb-0 shadow-sm",
)

# ── Footer ─────────────────────────────────────────────────────────────────────
footer = html.Footer(
    dbc.Container(
        html.Small(
            f"Price Sense AI · Powered by Trinamix · v0.1",
            className="text-muted",
        ),
        fluid=True,
    ),
    className="py-2 mt-4 border-top bg-light text-center",
)

# ── App layout ─────────────────────────────────────────────────────────────────
app.layout = html.Div(
    [
        # Auth guard — fires on every client-side URL change and forces a full
        # page reload to /login when the Flask session has no authenticated user.
        dcc.Location(id="_url-auth-guard", refresh=True),
        navbar,
        dbc.Container(
            dash.page_container,
            fluid=True,
            className="py-4",
        ),
        footer,
        html.Div(id="toast-container",
                 style={"position": "fixed", "top": "70px", "right": "20px", "zIndex": 9999}),
    ]
)

# ── Client-side auth guard ────────────────────────────────────────────────────
# Dash uses HTML5 client-side routing so clicking nav links never hits Flask's
# before_request.  This callback re-checks session on every URL change and
# forces a full page reload to /login when the session is unauthenticated.
_PUBLIC_DASH_PATHS = {"/login", "/register", "/logout"}

@app.callback(
    Output("_url-auth-guard", "href"),
    Input("_url-auth-guard",  "pathname"),
)
def enforce_auth(pathname):
    if not pathname:
        return no_update
    # Dash internals and public pages pass through
    if pathname in _PUBLIC_DASH_PATHS or pathname.startswith(("/_", "/assets", "/favicon")):
        return no_update
    if flask.session.get("user"):
        return no_update
    return "/login"

# ── Show current user in navbar ────────────────────────────────────────────────
@app.callback(
    Output("nav-user-badge", "children"),
    Input("nav-user-badge",  "id"),   # fires on every page load
)
def update_nav_user(_):
    from auth.auth_callbacks import get_session_user
    user = get_session_user()
    if user:
        return f"{user['username']}  ·  {user['role']}"
    return ""

# ── Navbar collapse toggle (mobile) ───────────────────────────────────────────
@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler",   "n_clicks"),
    State("navbar-collapse",  "is_open"),
    prevent_initial_call=True,
)
def toggle_navbar(n, is_open):
    return not is_open

# ── Register page-level callbacks ──────────────────────────────────────────────
from callbacks import analyze_callbacks, scenario_callbacks, catalog_callbacks, profit_buckets_callbacks
from auth     import auth_callbacks

analyze_callbacks.register(app)
scenario_callbacks.register(app)
catalog_callbacks.register(app)
profit_buckets_callbacks.register(app)
auth_callbacks.register(app)

logger.success("All callbacks registered.")

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"Starting Price Sense AI at http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)


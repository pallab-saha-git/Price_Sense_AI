"""
auth/users.py
──────────────
User management: create, verify, update.
Uses Werkzeug's PBKDF2-SHA256 hashing (no extra deps — bundled with Flask).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.orm import Session

from data.database import SessionLocal, User
from loguru import logger


# ── Public API ─────────────────────────────────────────────────────────────────

def create_user(
    username: str,
    password: str,
    email: str = "",
    role: str = "analyst",
) -> tuple[bool, str]:
    """
    Create a new user with a hashed password.

    Returns:
        (True, "ok") on success
        (False, "error message") on failure
    """
    username = username.strip()
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    with SessionLocal() as db:
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            if existing.username == username:
                return False, f"Username '{username}' is already taken."
            return False, f"Email '{email}' is already registered."

        user = User(
            username=username,
            email=email or None,
            password_hash=generate_password_hash(password),
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        logger.info(f"Created user '{username}' (role={role})")
        return True, "ok"


def verify_user(username: str, password: str) -> Optional[dict]:
    """
    Verify credentials.

    Returns user dict on success, None on failure.
    """
    with SessionLocal() as db:
        user = db.query(User).filter(
            User.username == username,
            User.is_active == True,
        ).first()

        if not user:
            return None
        if not check_password_hash(user.password_hash, password):
            return None

        # Update last_login
        user.last_login = datetime.now(timezone.utc)
        db.commit()

        return {
            "id":       user.id,
            "username": user.username,
            "email":    user.email,
            "role":     user.role,
        }


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetch user info (no password) by username."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        return {
            "id":         user.id,
            "username":   user.username,
            "email":      user.email,
            "role":       user.role,
            "is_active":  user.is_active,
            "created_at": str(user.created_at),
            "last_login": str(user.last_login),
        }


def seed_admin_user() -> None:
    """
    Ensure at least one admin account exists.

    Priority order:
      1. If ADMIN_USERNAME + ADMIN_PASSWORD are set → create/keep that account.
      2. If NO env vars are set AND no users exist → auto-generate a random
         password for user 'admin', create the account, and print the
         credentials prominently to stdout so Docker / CI users can retrieve
         them with:  docker logs <container> | grep 'FIRST-RUN'
    Safe to call on every startup.
    """
    import secrets as _secrets
    from config.settings import ADMIN_USERNAME, ADMIN_PASSWORD

    username = ADMIN_USERNAME or "admin"
    password = ADMIN_PASSWORD

    # ── Check whether any users exist at all ──────────────────────────────────
    with SessionLocal() as db:
        total_users = db.query(User).count()
        already_exists = db.query(User).filter(User.username == username).first() is not None

    if already_exists:
        return  # nothing to do

    # ── If no password configured and no users exist → auto-generate ──────────
    if not password:
        if total_users > 0:
            # Other users exist; no need to seed an admin automatically.
            return
        # First-run with no env vars — generate a secure temporary password.
        password = _secrets.token_urlsafe(16)
        banner = (
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║          PRICE SENSE AI — FIRST-RUN CREDENTIALS             ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
           f"║  Username : {username:<49}║\n"
           f"║  Password : {password:<49}║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  Change this via ADMIN_USERNAME / ADMIN_PASSWORD in .env    ║\n"
            "║  or set them as Docker / platform environment variables.     ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        )
        # Use print() so it always appears in Docker logs, even if loguru is
        # configured to filter INFO.  Tag with FIRST-RUN for easy grepping.
        print(f"[FIRST-RUN] {banner}", flush=True)
        logger.warning(f"FIRST-RUN: auto-created admin '{username}'. Check logs for password.")

    ok, msg = create_user(username=username, password=password, role="admin")
    if ok:
        logger.success(f"Admin user '{username}' created.")
    else:
        logger.warning(f"Admin seed skipped: {msg}")


def list_users() -> list[dict]:
    """Return all users (for admin panel)."""
    with SessionLocal() as db:
        users = db.query(User).order_by(User.created_at).all()
        return [
            {
                "id":         u.id,
                "username":   u.username,
                "email":      u.email or "",
                "role":       u.role,
                "is_active":  u.is_active,
                "created_at": str(u.created_at)[:10],
                "last_login": str(u.last_login)[:10] if u.last_login else "—",
            }
            for u in users
        ]

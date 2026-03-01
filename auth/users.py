"""
auth/users.py
──────────────
User management: create, verify, update.
Uses Werkzeug's PBKDF2-SHA256 hashing (no extra deps — bundled with Flask).
"""

from __future__ import annotations

from datetime import datetime
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
            created_at=datetime.utcnow(),
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
        user.last_login = datetime.utcnow()
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
    Create the initial admin user from ADMIN_USERNAME / ADMIN_PASSWORD env vars.
    Safe to call on every startup — skips if already exists or vars are unset.
    """
    from config.settings import ADMIN_USERNAME, ADMIN_PASSWORD
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return

    with SessionLocal() as db:
        if db.query(User).filter(User.username == ADMIN_USERNAME).first():
            return  # already exists

    ok, msg = create_user(
        username=ADMIN_USERNAME,
        password=ADMIN_PASSWORD,
        role="admin",
    )
    if ok:
        logger.success(f"Admin user '{ADMIN_USERNAME}' created.")
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

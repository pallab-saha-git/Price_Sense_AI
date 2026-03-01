"""
tests/test_auth.py
──────────────────
Unit tests for authentication and user management.
Run with:  pytest tests/test_auth.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import pytest
from datetime import datetime, timezone


class TestUserManagement:
    """Test user creation and verification."""
    
    def test_create_user_success(self):
        """Test creating a valid user."""
        from auth.users import create_user
        # Use unique username to avoid conflicts
        username = f"testuser_{datetime.now(timezone.utc).timestamp()}"
        ok, msg = create_user(username=username, password="testpass123", email=f"{username}@test.com")
        assert ok is True or "already taken" in msg  # OK if user exists from previous run
    
    def test_create_user_short_password(self):
        """Test that short passwords are rejected."""
        from auth.users import create_user
        ok, msg = create_user(username="testuser", password="short", email="test@test.com")
        assert ok is False
        assert "at least 8 characters" in msg
    
    def test_create_user_short_username(self):
        """Test that short usernames are rejected."""
        from auth.users import create_user
        ok, msg = create_user(username="ab", password="testpass123", email="test@test.com")
        assert ok is False
        assert "at least 3 characters" in msg
    
    def test_verify_user_success(self):
        """Test successful user verification."""
        from auth.users import create_user, verify_user
        username = f"verifytest_{datetime.now(timezone.utc).timestamp()}"
        password = "testpass123"
        create_user(username=username, password=password, email=f"{username}@test.com")
        
        user = verify_user(username, password)
        assert user is not None
        assert user["username"] == username
        assert "role" in user
    
    def test_verify_user_wrong_password(self):
        """Test that wrong password returns None."""
        from auth.users import create_user, verify_user
        username = f"wrongpass_{datetime.now(timezone.utc).timestamp()}"
        create_user(username=username, password="correctpass", email=f"{username}@test.com")
        
        user = verify_user(username, "wrongpass")
        assert user is None
    
    def test_verify_user_nonexistent(self):
        """Test that nonexistent user returns None."""
        from auth.users import verify_user
        user = verify_user("nonexistent_user_12345", "anypass")
        assert user is None


class TestPasswordHashing:
    """Test password hashing security."""
    
    def test_password_not_stored_plaintext(self):
        """Ensure passwords are hashed, not stored plaintext."""
        from auth.users import create_user
        from data.database import SessionLocal, User
        
        username = f"hashtest_{datetime.now(timezone.utc).timestamp()}"
        password = "mysecretpass"
        create_user(username=username, password=password)
        
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username).first()
            assert user is not None
            # Hashed password should not match plaintext
            assert user.password_hash != password
            # Should contain hash prefix
            assert "pbkdf2:sha256" in user.password_hash or "scrypt:" in user.password_hash

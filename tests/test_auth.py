"""Tests for auth module."""
import json
import time
from pathlib import Path

import pytest

from dsviewer.auth import (
    hash_password,
    verify_password,
    login,
    logout,
    authenticate,
    change_password,
    load_users,
    load_sessions,
    save_sessions,
    set_config,
)
from dsviewer.config import AppConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    cfg = AppConfig(data_dir=tmp_path / "data")
    cfg.ensure_data_dir()
    set_config(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_and_verify():
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)


def test_hash_produces_different_salts():
    h1 = hash_password("password")
    h2 = hash_password("password")
    assert h1 != h2  # different salts


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def test_default_admin_created(tmp_config):
    users = load_users()
    assert "admin" in users
    assert verify_password("admin123", users["admin"]["password"])


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

def test_login_success(tmp_config):
    result = login("admin", "admin123")
    assert "token" in result
    assert result["username"] == "admin"
    assert result["expires_at"] > int(time.time())


def test_login_wrong_password(tmp_config):
    with pytest.raises(ValueError, match="Invalid credentials"):
        login("admin", "wrong")


def test_login_unknown_user(tmp_config):
    with pytest.raises(ValueError, match="Invalid credentials"):
        login("nobody", "pass")


def test_session_stored_after_login(tmp_config):
    result = login("admin", "admin123")
    sessions = load_sessions()
    assert result["token"] in sessions


def test_expired_sessions_cleaned_on_load(tmp_config):
    # Inject an expired session
    sessions = {
        "expired_token": {"username": "admin", "expires_at": int(time.time()) - 1},
        "valid_token": {"username": "admin", "expires_at": int(time.time()) + 3600},
    }
    from dsviewer.config import safe_write_json
    safe_write_json(tmp_config.sessions_file, sessions)

    loaded = load_sessions()
    assert "expired_token" not in loaded
    assert "valid_token" in loaded

    # File should also be cleaned up
    on_disk = json.loads(tmp_config.sessions_file.read_text())
    assert "expired_token" not in on_disk


# ---------------------------------------------------------------------------
# change_password
# ---------------------------------------------------------------------------

def test_change_password(tmp_config):
    change_password("admin", "admin123", "newpass456")
    users = load_users()
    assert verify_password("newpass456", users["admin"]["password"])


def test_change_password_wrong_old(tmp_config):
    with pytest.raises(ValueError, match="Invalid current password"):
        change_password("admin", "wrongold", "newpass")


def test_change_password_unknown_user(tmp_config):
    with pytest.raises(ValueError, match="User not found"):
        change_password("ghost", "x", "y")

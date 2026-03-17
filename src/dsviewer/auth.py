from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING

import bcrypt as _bcrypt_lib
from fastapi import Request

from dsviewer.config import safe_write_json

if TYPE_CHECKING:
    from dsviewer.config import AppConfig

TOKEN_EXPIRY = 7 * 24 * 60 * 60  # 7 days in seconds

# Module-level config reference (set by server.py on startup)
_config: "AppConfig | None" = None


def set_config(config: "AppConfig") -> None:
    global _config
    _config = config


def _cfg() -> "AppConfig":
    if _config is None:
        raise RuntimeError("Auth module not initialised — call set_config() first")
    return _config


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _bcrypt_lib.hashpw(password.encode(), _bcrypt_lib.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return _bcrypt_lib.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def load_users() -> dict:
    cfg = _cfg()
    if not cfg.users_file.exists():
        default_users = {"admin": {"password": hash_password("admin123")}}
        safe_write_json(cfg.users_file, default_users)
        return default_users
    return json.loads(cfg.users_file.read_text(encoding="utf-8")) or {}


def save_users(users: dict) -> None:
    safe_write_json(_cfg().users_file, users)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def load_sessions() -> dict:
    """Read sessions.json, filter expired entries, write back, return clean dict."""
    cfg = _cfg()
    if not cfg.sessions_file.exists():
        return {}

    now = int(time.time())
    raw = json.loads(cfg.sessions_file.read_text(encoding="utf-8")) or {}
    clean = {k: v for k, v in raw.items() if v.get("expires_at", 0) > now}

    if len(clean) != len(raw):
        safe_write_json(cfg.sessions_file, clean)

    return clean


def save_sessions(sessions: dict) -> None:
    """Filter expired entries, then write sessions.json (thread-safe)."""
    now = int(time.time())
    clean = {k: v for k, v in sessions.items() if v.get("expires_at", 0) > now}
    safe_write_json(_cfg().sessions_file, clean)


# ---------------------------------------------------------------------------
# Public-link tokens
# ---------------------------------------------------------------------------

TOKEN_LENGTH = 8  # hex chars → 8-char token
TOKEN_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def load_tokens() -> dict:
    cfg = _cfg()
    if not cfg.tokens_file.exists():
        return {}
    return json.loads(cfg.tokens_file.read_text(encoding="utf-8")) or {}


def save_tokens(tokens: dict) -> None:
    cutoff = int(time.time()) - TOKEN_MAX_AGE
    clean = {k: v for k, v in tokens.items() if v.get("created_at", 0) > cutoff}
    safe_write_json(_cfg().tokens_file, clean)


def generate_short_token(path: str) -> str:
    token = secrets.token_hex(TOKEN_LENGTH // 2)
    tokens = load_tokens()
    tokens[token] = {"path": path, "created_at": int(time.time())}
    save_tokens(tokens)
    return token


def get_path_from_token(token: str) -> str:
    tokens = load_tokens()
    if token not in tokens:
        raise ValueError("Invalid or expired token")
    return tokens[token]["path"]


# ---------------------------------------------------------------------------
# Login / Logout / Authenticate
# ---------------------------------------------------------------------------

def login(username: str, password: str) -> dict:
    users = load_users()

    if username not in users:
        raise ValueError("Invalid credentials")

    if not verify_password(password, users[username]["password"]):
        raise ValueError("Invalid credentials")

    token = secrets.token_hex(32)
    expires_at = int(time.time()) + TOKEN_EXPIRY

    sessions = load_sessions()
    sessions[token] = {"username": username, "expires_at": expires_at}
    save_sessions(sessions)

    return {"token": token, "username": username, "expires_at": expires_at}


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    # Fall back to query param
    return request.query_params.get("token")


def authenticate(request: Request) -> dict:
    """Validate Bearer token, return session data, or raise HTTP 401."""
    token = _extract_token(request)
    if not token:
        raise _unauthorized("Authentication required")

    sessions = load_sessions()
    if token not in sessions:
        raise _unauthorized("Invalid token")

    session = sessions[token]
    if session.get("expires_at", 0) < int(time.time()):
        del sessions[token]
        save_sessions(sessions)
        raise _unauthorized("Token expired")

    return session


def logout(request: Request) -> None:
    token = _extract_token(request)
    if token:
        sessions = load_sessions()
        sessions.pop(token, None)
        save_sessions(sessions)


def change_password(username: str, old_password: str, new_password: str) -> None:
    users = load_users()

    if username not in users:
        raise ValueError("User not found")

    if not verify_password(old_password, users[username]["password"]):
        raise ValueError("Invalid current password")

    users[username]["password"] = hash_password(new_password)
    save_users(users)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _unauthorized(msg: str) -> _HTTPException:
    return _HTTPException(status_code=401, detail=msg)

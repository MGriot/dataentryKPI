# src/user_management/crud.py
"""
User accounts: password-based login (required to use the React app / REST API) plus
API keys (a separate, longer-lived secret) used to authenticate MCP HTTP requests.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib `hashlib`, no extra dependency) --
260,000 iterations, a random 16-byte salt per user. Sessions are opaque random tokens;
only their SHA-256 hash is ever stored, same pattern as API keys.
"""
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from src.config.settings import get_database_path

API_KEY_PREFIX = "kpi_mcp_"
SESSION_TTL_DAYS = 30
PBKDF2_ITERATIONS = 260_000


def _get_db() -> sqlite3.Connection:
    return sqlite3.connect(get_database_path("db_users.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(raw_password: str, salt: Optional[str] = None) -> tuple:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return digest.hex(), salt


# --- Users ---

def add_user(name: str, password: str, email: str = "", color: str = "#3b82f6") -> int:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    password_hash, salt = _hash_password(password)
    with _get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, color, password_hash, password_salt, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (name, email, color, password_hash, salt, _now()),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError(f"A user named '{name}' already exists.") from e


def update_user(user_id: int, name: str, email: str = "", color: str = "#3b82f6", is_active: bool = True):
    with _get_db() as conn:
        try:
            conn.execute(
                "UPDATE users SET name=?, email=?, color=?, is_active=? WHERE id=?",
                (name, email, color, 1 if is_active else 0, user_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"A user named '{name}' already exists.") from e


def get_all_users(active_only: bool = False) -> list:
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT id, name, email, color, is_active, created_at FROM users"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        return [dict(r) for r in conn.execute(query).fetchall()]


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, email, color, is_active, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


# --- Password auth ---

def verify_password(name: str, raw_password: str) -> Optional[dict]:
    """Returns the public user dict if name+password match an active user, else None."""
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, email, color, is_active, password_hash, password_salt FROM users WHERE name = ?",
            (name,),
        ).fetchone()
        if not row or not row["is_active"] or not row["password_hash"]:
            return None
        computed_hash, _ = _hash_password(raw_password, row["password_salt"])
        if not secrets.compare_digest(computed_hash, row["password_hash"]):
            return None
        return {"id": row["id"], "name": row["name"], "email": row["email"], "color": row["color"]}


def set_password(user_id: int, raw_password: str):
    if not raw_password or len(raw_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    password_hash, salt = _hash_password(raw_password)
    with _get_db() as conn:
        conn.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (password_hash, salt, user_id))
        conn.commit()


def change_password(user_id: int, current_password: str, new_password: str):
    """Verifies current_password before setting new_password. Raises ValueError on mismatch."""
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT password_hash, password_salt FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not row["password_hash"]:
            raise ValueError("User not found or has no password set.")
        computed_hash, _ = _hash_password(current_password, row["password_salt"])
        if not secrets.compare_digest(computed_hash, row["password_hash"]):
            raise ValueError("Current password is incorrect.")
    set_password(user_id, new_password)


# --- Sessions (React app / REST API login) ---

def create_session(user_id: int) -> dict:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    created_at = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    with _get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at, is_active) VALUES (?, ?, ?, ?, 1)",
            (user_id, token_hash, created_at, expires_at),
        )
        conn.commit()
    return {"token": raw_token, "expires_at": expires_at}


def validate_session(raw_token: str) -> Optional[dict]:
    """Resolves a raw session token to its owning user (only if session+user are active and not expired)."""
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT user_id, expires_at, is_active FROM sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not row or not row["is_active"]:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return None

        user_row = conn.execute(
            "SELECT id, name, email, color, is_active FROM users WHERE id = ?", (row["user_id"],)
        ).fetchone()
        if not user_row or not user_row["is_active"]:
            return None
        return {"id": user_row["id"], "name": user_row["name"], "email": user_row["email"], "color": user_row["color"]}


def revoke_session(raw_token: str):
    if not raw_token:
        return
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with _get_db() as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE token_hash = ?", (token_hash,))
        conn.commit()


# --- API Keys (MCP authentication) ---

def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_api_key(user_id: int, label: str) -> dict:
    """Generates a new API key. The raw key is returned ONCE and never stored in plaintext."""
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[: len(API_KEY_PREFIX) + 8]

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO api_keys (user_id, label, key_prefix, key_hash, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, label, key_prefix, key_hash, _now()),
        )
        conn.commit()
        key_id = cursor.lastrowid

    return {"id": key_id, "label": label, "key_prefix": key_prefix, "raw_key": raw_key}


def list_api_keys(user_id: Optional[int] = None) -> list:
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        if user_id is not None:
            rows = conn.execute(
                "SELECT id, user_id, label, key_prefix, created_at, last_used_at, is_active FROM api_keys WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, label, key_prefix, created_at, last_used_at, is_active FROM api_keys ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def revoke_api_key(key_id: int):
    with _get_db() as conn:
        conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
        conn.commit()


def validate_api_key(raw_key: str) -> Optional[dict]:
    """Resolves a raw API key to its owning user (only if key and user are active). Updates last_used_at."""
    if not raw_key:
        return None
    key_hash = _hash_key(raw_key)
    with _get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, user_id, is_active FROM api_keys WHERE key_hash = ?", (key_hash,)
        ).fetchone()
        if not row or not row["is_active"]:
            return None

        user_row = conn.execute(
            "SELECT id, name, email, is_active FROM users WHERE id = ?", (row["user_id"],)
        ).fetchone()
        if not user_row or not user_row["is_active"]:
            return None

        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (_now(), row["id"]))
        conn.commit()
        return {"id": user_row["id"], "name": user_row["name"], "email": user_row["email"], "api_key_id": row["id"]}

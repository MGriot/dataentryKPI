# src/user_management/crud.py
"""
User accounts: password login (React app / REST API), an admin role, and API keys (a
separate, longer-lived secret) for MCP HTTP requests.

Passwords: PBKDF2-HMAC-SHA256, 260k iterations, random 16-byte salt per user. Sessions and
API keys are random tokens; only their SHA-256 hash is stored.

Roles: the first account ever created becomes admin. Admins manage users, everyone's API
keys and backup restores; everyone else manages only their own password and keys.
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.data_access import db

API_KEY_PREFIX = "kpi_mcp_"
SESSION_TTL_DAYS = 30
PBKDF2_ITERATIONS = 260_000
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256

_PUBLIC_COLUMNS = "id, name, email, color, is_active, is_admin, created_at"
# Hash computed for unknown user names so a failed login costs the same either way.
_DUMMY_SALT = secrets.token_hex(16)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(raw_password: str, salt: Optional[str] = None) -> tuple:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def _check_password_policy(password: str):
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")


def _public(row) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    for flag in ("is_active", "is_admin"):
        if flag in d:
            d[flag] = bool(d[flag])
    return d


# --- Users ---

def count_users() -> int:
    with db.connect(db.USERS) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def add_user(name: str, password: str, email: str = "", color: str = "#3b82f6", is_admin: Optional[bool] = None) -> int:
    """Creates a user. is_admin=None means: admin only if this is the very first account."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Name cannot be empty.")
    _check_password_policy(password)
    password_hash, salt = _hash_password(password)
    with db.connect(db.USERS) as conn:
        conn.execute("BEGIN IMMEDIATE")  # serialize the "first user becomes admin" check
        if is_admin is None:
            is_admin = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        try:
            return conn.execute(
                "INSERT INTO users (name, email, color, password_hash, password_salt, is_active, is_admin, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (name, email or "", color or "#3b82f6", password_hash, salt, 1 if is_admin else 0, _now()),
            ).lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError(f"A user named '{name}' already exists.") from e


def update_user(user_id: int, name: str, email: str = "", color: str = "#3b82f6", is_active: bool = True,
                is_admin: Optional[bool] = None) -> bool:
    """Updates a profile. Deactivating a user also revokes their sessions and API keys.

    Refuses (ValueError) to remove the last active admin.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Name cannot be empty.")
    with db.connect(db.USERS) as conn:
        current = conn.execute("SELECT is_admin, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if not current:
            return False
        new_admin = bool(current["is_admin"]) if is_admin is None else bool(is_admin)
        if current["is_admin"] and current["is_active"] and (not new_admin or not is_active):
            others = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND is_active = 1 AND id != ?", (user_id,)
            ).fetchone()[0]
            if others == 0:
                raise ValueError("Can't remove the last active admin.")
        try:
            conn.execute(
                "UPDATE users SET name=?, email=?, color=?, is_active=?, is_admin=? WHERE id=?",
                (name, email or "", color or "#3b82f6", 1 if is_active else 0, 1 if new_admin else 0, user_id),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(f"A user named '{name}' already exists.") from e
        if not is_active:
            conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
            conn.execute("UPDATE api_keys SET is_active = 0 WHERE user_id = ?", (user_id,))
    return True


def get_all_users(active_only: bool = False) -> list:
    query = f"SELECT {_PUBLIC_COLUMNS} FROM users" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY name"
    with db.connect(db.USERS) as conn:
        return [_public(r) for r in conn.execute(query)]


def get_user_by_id(user_id: int) -> Optional[dict]:
    with db.connect(db.USERS) as conn:
        return _public(conn.execute(f"SELECT {_PUBLIC_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone())


# --- Password auth ---

def verify_password(name: str, raw_password: str) -> Optional[dict]:
    """The public user dict if name+password match an active user, else None (constant-ish time)."""
    raw_password = (raw_password or "")[:MAX_PASSWORD_LENGTH]
    with db.connect(db.USERS) as conn:
        row = conn.execute(
            f"SELECT {_PUBLIC_COLUMNS}, password_hash, password_salt FROM users WHERE name = ?", ((name or "").strip(),)
        ).fetchone()
    if not row or not row["password_hash"]:
        _hash_password(raw_password, _DUMMY_SALT)
        return None
    computed, _ = _hash_password(raw_password, row["password_salt"])
    if not secrets.compare_digest(computed, row["password_hash"]) or not row["is_active"]:
        return None
    user = _public(row)
    user.pop("password_hash", None)
    user.pop("password_salt", None)
    return user


def set_password(user_id: int, raw_password: str):
    _check_password_policy(raw_password)
    password_hash, salt = _hash_password(raw_password)
    with db.connect(db.USERS) as conn:
        conn.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (password_hash, salt, user_id))


def change_password(user_id: int, current_password: str, new_password: str, keep_session_token: Optional[str] = None):
    """Verifies current_password, sets new_password, and revokes every other session of the user."""
    with db.connect(db.USERS) as conn:
        row = conn.execute("SELECT password_hash, password_salt FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not row["password_hash"]:
        raise ValueError("User not found or has no password set.")
    computed, _ = _hash_password((current_password or "")[:MAX_PASSWORD_LENGTH], row["password_salt"])
    if not secrets.compare_digest(computed, row["password_hash"]):
        raise ValueError("Current password is incorrect.")
    set_password(user_id, new_password)
    keep_hash = _hash_token(keep_session_token) if keep_session_token else ""
    with db.connect(db.USERS) as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ? AND token_hash != ?", (user_id, keep_hash))


def admin_reset_password(user_id: int, new_password: str) -> bool:
    """Admin-initiated reset: sets the password and signs the user out everywhere."""
    if not get_user_by_id(user_id):
        return False
    set_password(user_id, new_password)
    with db.connect(db.USERS) as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
    return True


# --- Sessions ---

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> dict:
    raw_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    with db.connect(db.USERS) as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at, is_active) VALUES (?, ?, ?, ?, 1)",
            (user_id, _hash_token(raw_token), _now(), expires_at),
        )
    return {"token": raw_token, "expires_at": expires_at}


def validate_session(raw_token: str) -> Optional[dict]:
    """The owning user (if session and user are active and unexpired), else None."""
    if not raw_token:
        return None
    with db.connect(db.USERS) as conn:
        row = conn.execute(
            "SELECT s.expires_at, s.is_active AS session_active, u.id, u.name, u.email, u.color, u.is_active, u.is_admin, u.created_at "
            "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (_hash_token(raw_token),),
        ).fetchone()
    if not row or not row["session_active"] or not row["is_active"]:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return None
    user = _public(row)
    user.pop("expires_at", None)
    user.pop("session_active", None)
    return user


def revoke_session(raw_token: str):
    if not raw_token:
        return
    with db.connect(db.USERS) as conn:
        conn.execute("UPDATE sessions SET is_active = 0 WHERE token_hash = ?", (_hash_token(raw_token),))


def purge_expired_sessions():
    with db.connect(db.USERS) as conn:
        conn.execute("DELETE FROM sessions WHERE is_active = 0 OR expires_at < ?", (_now(),))


# --- API keys (MCP) ---

def create_api_key(user_id: int, label: str) -> dict:
    """Generates a key. The raw key is returned ONCE and only its hash is stored."""
    label = (label or "").strip()
    if not label:
        raise ValueError("Label cannot be empty.")
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[: len(API_KEY_PREFIX) + 8]
    with db.connect(db.USERS) as conn:
        key_id = conn.execute(
            "INSERT INTO api_keys (user_id, label, key_prefix, key_hash, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, label, key_prefix, _hash_token(raw_key), _now()),
        ).lastrowid
    return {"id": key_id, "label": label, "key_prefix": key_prefix, "raw_key": raw_key}


def get_api_key(key_id: int) -> Optional[dict]:
    with db.connect(db.USERS) as conn:
        row = conn.execute(
            "SELECT id, user_id, label, key_prefix, created_at, last_used_at, is_active FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()
    return _public(row)


def list_api_keys(user_id: Optional[int] = None) -> list:
    query = "SELECT id, user_id, label, key_prefix, created_at, last_used_at, is_active FROM api_keys"
    params: tuple = ()
    if user_id is not None:
        query += " WHERE user_id = ?"
        params = (user_id,)
    with db.connect(db.USERS) as conn:
        return [_public(r) for r in conn.execute(query + " ORDER BY id DESC", params)]


def revoke_api_key(key_id: int) -> bool:
    with db.connect(db.USERS) as conn:
        return conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,)).rowcount > 0


def validate_api_key(raw_key: str) -> Optional[dict]:
    """The owning user (if key and user are active), else None. Updates last_used_at."""
    if not raw_key or not raw_key.startswith(API_KEY_PREFIX):
        return None
    with db.connect(db.USERS) as conn:
        row = conn.execute(
            "SELECT k.id AS api_key_id, k.is_active AS key_active, u.id, u.name, u.email, u.is_active, u.is_admin "
            "FROM api_keys k JOIN users u ON u.id = k.user_id WHERE k.key_hash = ?",
            (_hash_token(raw_key),),
        ).fetchone()
        if not row or not row["key_active"] or not row["is_active"]:
            return None
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (_now(), row["api_key_id"]))
    return {"id": row["id"], "name": row["name"], "email": row["email"], "is_admin": bool(row["is_admin"]),
            "api_key_id": row["api_key_id"]}

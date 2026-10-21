# src/user_management/access.py
"""
Who may manage which accounts and API keys. Shared by the REST API and the MCP server so the
two enforce exactly the same rules.

`actor` is the authenticated user ({"id", "name", "is_admin", ...}). The local stdio MCP
operator has id None (it isn't an account) and is admin unless MCP_STDIO_ADMIN=false.

Raises AccessDenied (REST: 403), LookupError for a missing user/key (REST: 404) and
ValueError for invalid input (REST: 400/409).
"""
from typing import Optional

from src.user_management import crud as user_crud


class AccessDenied(PermissionError):
    """The actor isn't allowed to do this (a dedicated type, so OS permission errors aren't 403s)."""


def _is_admin(actor: dict) -> bool:
    return bool(actor.get("is_admin"))


def require_admin(actor: dict):
    if not _is_admin(actor):
        raise AccessDenied("Admin rights required.")


def require_self_or_admin(actor: dict, user_id: int):
    if actor.get("id") != user_id and not _is_admin(actor):
        raise AccessDenied("You can only manage your own account.")


def list_users(actor: dict, active_only: bool = False) -> list:
    """Admins get full profiles; everyone else gets id/name/color/is_active only."""
    users = user_crud.get_all_users(active_only=active_only)
    if _is_admin(actor):
        return users
    return [{"id": u["id"], "name": u["name"], "color": u["color"], "is_active": u["is_active"]} for u in users]


def create_user(actor: dict, name: str, password: str, email: str = "", color: str = "#3b82f6",
                is_admin: bool = False) -> int:
    require_admin(actor)
    return user_crud.add_user(name, password, email or "", color or "#3b82f6", is_admin=is_admin)


def update_user(actor: dict, user_id: int, name: str, email: str = "", color: str = "#3b82f6",
                is_active: bool = True, is_admin: Optional[bool] = None):
    """Admins can edit anyone (incl. is_active / is_admin); users only their own name, email and color."""
    require_self_or_admin(actor, user_id)
    target = user_crud.get_user_by_id(user_id)
    if not target:
        raise LookupError("User not found")
    if not _is_admin(actor):
        if is_active is False:
            raise AccessDenied("Only admins can deactivate accounts.")
        if is_admin is not None and is_admin != target["is_admin"]:
            raise AccessDenied("Only admins can change roles.")
        is_active, is_admin = target["is_active"], None
    user_crud.update_user(user_id, name, email or "", color or "#3b82f6", is_active, is_admin)


def reset_password(actor: dict, user_id: int, new_password: str):
    """Admin only: sets a new password and signs the user out everywhere."""
    require_admin(actor)
    if not user_crud.admin_reset_password(user_id, new_password):
        raise LookupError("User not found")


def list_api_keys(actor: dict, user_id: int) -> list:
    require_self_or_admin(actor, user_id)
    return user_crud.list_api_keys(user_id=user_id)


def create_api_key(actor: dict, user_id: int, label: str) -> dict:
    """Your own key (admins: anyone's). The raw key is in the result ONCE."""
    require_self_or_admin(actor, user_id)
    target = user_crud.get_user_by_id(user_id)
    if not target or not target["is_active"]:
        raise LookupError("User not found")
    return user_crud.create_api_key(user_id, label)


def revoke_api_key(actor: dict, key_id: int):
    key = user_crud.get_api_key(key_id)
    if not key:
        raise LookupError("API key not found")
    require_self_or_admin(actor, key["user_id"])
    user_crud.revoke_api_key(key_id)

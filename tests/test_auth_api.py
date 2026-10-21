from tests.helpers import auth as _auth


def test_first_account_is_admin_then_registration_closes(client):
    assert client.get("/auth/status").json() == {"has_users": False, "registration_open": True}
    first = client.post("/auth/register", json={"name": "boss", "password": "password-1"})
    assert first.status_code == 200 and first.json()["user"]["is_admin"] is True
    second = client.post("/auth/register", json={"name": "eve", "password": "password-2"})
    assert second.status_code == 403
    assert client.get("/auth/status").json()["registration_open"] is False


def test_allow_registration_opens_signup_as_regular_user(client, admin, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    res = client.post("/auth/register", json={"name": "bob", "password": "password-2"})
    assert res.status_code == 200 and res.json()["user"]["is_admin"] is False


def test_routes_require_a_session(client, admin):
    assert client.get("/kpis").status_code == 401
    assert client.get("/kpis", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/kpis", headers=admin).status_code == 200
    assert client.get("/health").status_code == 200


def test_login_rate_limit(client, admin):
    for _ in range(8):
        assert client.post("/auth/login", json={"name": "admin", "password": "wrong-pass"}).status_code == 401
    assert client.post("/auth/login", json={"name": "admin", "password": "wrong-pass"}).status_code == 429
    assert client.post("/auth/login", json={"name": "admin", "password": "admin-password"}).status_code == 429


def test_change_password_revokes_other_sessions(client, admin):
    other = _auth(client.post("/auth/login", json={"name": "admin", "password": "admin-password"}).json()["token"])
    res = client.post("/auth/change-password", json={"current_password": "admin-password", "new_password": "new-password-1"}, headers=admin)
    assert res.status_code == 200
    assert client.get("/auth/me", headers=admin).status_code == 200  # this session survives
    assert client.get("/auth/me", headers=other).status_code == 401  # others are signed out
    assert client.post("/auth/login", json={"name": "admin", "password": "new-password-1"}).status_code == 200


def test_authorization_matrix(client, admin, user):
    me = client.get("/auth/me", headers=user).json()
    admin_me = client.get("/auth/me", headers=admin).json()
    assert me["is_admin"] is False

    # admin-only
    assert client.post("/users", json={"name": "mallory", "password": "password-3"}, headers=user).status_code == 403
    assert client.post(f"/users/{admin_me['id']}/reset-password", json={"new_password": "hijacked-1"}, headers=user).status_code == 403
    assert client.post("/import/restore", files={"file": ("b.zip", b"PK", "application/zip")}, headers=user).status_code == 403

    # can't touch other accounts or their keys
    assert client.put(f"/users/{admin_me['id']}", json={"name": "pwned", "is_active": False}, headers=user).status_code == 403
    assert client.post(f"/users/{admin_me['id']}/api-keys", json={"label": "steal"}, headers=user).status_code == 403
    assert client.get(f"/users/{admin_me['id']}/api-keys", headers=user).status_code == 403
    admin_key = client.post(f"/users/{admin_me['id']}/api-keys", json={"label": "mine"}, headers=admin).json()
    assert client.delete(f"/api-keys/{admin_key['id']}", headers=user).status_code == 403

    # self-service works
    own = client.post(f"/users/{me['id']}/api-keys", json={"label": "laptop"}, headers=user)
    assert own.status_code == 200 and own.json()["raw_key"].startswith("kpi_mcp_")
    assert client.delete(f"/api-keys/{own.json()['id']}", headers=user).status_code == 200
    assert client.put(f"/users/{me['id']}", json={"name": "alice2"}, headers=user).status_code == 200
    assert client.put(f"/users/{me['id']}", json={"name": "alice2", "is_admin": True}, headers=user).status_code == 403
    assert client.put(f"/users/{me['id']}", json={"name": "alice2", "is_active": False}, headers=user).status_code == 403

    # non-admins only see names
    listed = client.get("/users", headers=user).json()
    assert all("email" not in u for u in listed)
    assert "email" in client.get("/users", headers=admin).json()[0]


def test_deactivation_revokes_sessions_and_keys(client, admin, user):
    from src.user_management import crud as user_crud

    me = client.get("/auth/me", headers=user).json()
    key = client.post(f"/users/{me['id']}/api-keys", json={"label": "k"}, headers=user).json()["raw_key"]
    assert user_crud.validate_api_key(key)
    assert client.put(f"/users/{me['id']}", json={"name": "alice", "is_active": False}, headers=admin).status_code == 200
    assert client.get("/auth/me", headers=user).status_code == 401
    assert user_crud.validate_api_key(key) is None


def test_last_admin_cannot_be_demoted(client, admin):
    admin_me = client.get("/auth/me", headers=admin).json()
    res = client.put(f"/users/{admin_me['id']}", json={"name": "admin", "is_admin": False}, headers=admin)
    assert res.status_code == 409

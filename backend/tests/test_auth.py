"""Authentification, cookie de session et limitation de débit."""
from sqlalchemy import select

from app.config import get_settings
from app.models import AuditEvent
from tests.conftest import login


def test_login_sets_httponly_cookie_and_me_works(client):
    r = client.post("/api/auth/login", json={"email": "user@aihub-demo.local", "password": "User!2026"})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "USER"


def test_wrong_password_is_rejected_and_logged_without_password(client, db):
    r = client.post("/api/auth/login", json={"email": "user@aihub-demo.local", "password": "mauvais-mdp-123"})
    assert r.status_code == 401
    event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "LOGIN_FAILED"))
    assert event is not None and "mauvais-mdp-123" not in str(event.details)


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(client):
    login(client, "USER")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_login_per_minute", 3)
    codes = [client.post("/api/auth/login", json={"email": "x@y.z", "password": "bad"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_demo_accounts_only_exposed_in_demo_mode(client, monkeypatch):
    assert client.get("/api/config/public").json()["demo_accounts"]
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    body = client.get("/api/config/public").json()
    assert body == {"demo_mode": False, "demo_accounts": []}

"""Contrôle des rôles côté backend (test 5)."""
import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.conftest import login

ADMIN_PREFIXES = ("/api/security", "/api/policy", "/api/audit", "/api/classify")


def admin_routes() -> list[tuple[str, str]]:
    """Découverte automatique : toute nouvelle route sous ces préfixes est testée d'office."""
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(ADMIN_PREFIXES):
            path = route.path.replace("{term_id}", "1")
            routes += [(method, path) for method in route.methods]
    assert len(routes) >= 9
    return routes


@pytest.mark.parametrize("role", ["USER", "DEVELOPER", "MANAGER"])
def test_05_non_admin_gets_403_on_all_admin_routes(client, role):
    login(client, role)
    for method, path in admin_routes():
        r = client.request(method, path, json={})
        assert r.status_code == 403, f"{role} {method} {path} -> {r.status_code}"


def test_05b_anonymous_gets_401_on_admin_routes(client):
    for method, path in admin_routes():
        assert client.request(method, path, json={}).status_code == 401, f"{method} {path}"


def test_05c_admin_can_access_admin_routes(client):
    login(client, "ADMIN")
    assert client.get("/api/audit").status_code == 200
    assert client.get("/api/security/events").status_code == 200
    assert client.get("/api/policy").status_code == 200

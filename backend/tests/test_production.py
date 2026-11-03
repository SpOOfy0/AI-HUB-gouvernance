"""Comportement en mode réel (DEMO_MODE=false) : pas de faux modèle, pas de compte de démo."""
import pytest
from sqlalchemy import select, text

from app.config import Settings, get_settings
from app.db import engine
from app.models import AuditEvent, User
from app.providers import factory
from app.seed import seed as seed_module
from tests.conftest import TABLES, chat, login

FOB = "Explique-moi la différence entre FOB et CIF."


@pytest.fixture
def real_mode(monkeypatch):
    """Mode réel, sans aucune clé API et sans Ollama joignable."""
    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", False)
    for key in ("openai_api_key", "anthropic_api_key", "deepseek_api_key", "gemini_api_key"):
        monkeypatch.setattr(s, key, "")
    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(factory, "ollama_available", lambda: False)
    return s


@pytest.mark.parametrize("raw,expected", [
    ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgresql://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
    ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
])
def test_database_url_from_hosting_providers_is_normalized(raw, expected):
    assert Settings(database_url=raw).database_url == expected


def test_unconfigured_providers_are_skipped_without_any_call(client, providers, real_mode, db):
    login(client, "USER")
    r = chat(client, FOB)
    assert r.status_code == 503
    assert r.json()["code"] == "NO_CONFIGURED_PROVIDER"
    assert providers.calls == []  # aucun appel, même pas vers un fournisseur sans clé
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "PROVIDER_ERROR")) is None


def test_only_configured_provider_is_used(client, providers, real_mode, monkeypatch):
    monkeypatch.setattr(real_mode, "gemini_api_key", "cle-de-test")
    login(client, "USER")
    body = chat(client, FOB).json()
    assert body["status"] == "SUCCESS" and body["routing"]["model"] == "gemini/gemini-2.5-flash"
    # Gemini (offre gratuite) est plafonné à PUBLIC : une requête INTERNAL ne peut pas y aller.
    r = chat(client, "Résume la procédure interne d'ouverture d'un dossier export au site de Fos.")
    assert r.status_code == 503 and r.json()["code"] == "NO_CONFIGURED_PROVIDER"
    assert [c["model"] for c in providers.calls] == ["gemini/gemini-2.5-flash"]


def test_private_model_never_mocked_in_real_mode(real_mode, db):
    from app.models import LlmModel

    llama = db.scalar(select(LlmModel).where(LlmModel.litellm_name == "ollama/llama3.1:8b"))
    with pytest.raises(Exception, match="non configuré"):
        factory.default_provider_factory(llama).complete(llama, [{"role": "user", "content": "x"}])


def _empty_db():
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        conn.execute(text("SET session_replication_role = DEFAULT"))


def test_production_bootstrap_creates_admin_and_no_demo_account(real_mode, monkeypatch, db):
    _empty_db()
    monkeypatch.setattr(real_mode, "admin_email", "dsi@exemple.fr")
    monkeypatch.setattr(real_mode, "admin_password", "UnMotDePasseLong!2026")
    seed_module.run()
    users = db.scalars(select(User)).all()
    assert [u.email for u in users] == ["dsi@exemple.fr"] and users[0].role == "ADMIN"


def test_production_bootstrap_refuses_weak_admin_password(real_mode, monkeypatch):
    _empty_db()
    monkeypatch.setattr(real_mode, "admin_email", "dsi@exemple.fr")
    monkeypatch.setattr(real_mode, "admin_password", "court")
    with pytest.raises(SystemExit):
        seed_module.run()


def test_demo_accounts_disabled_when_switching_to_real_mode(client, real_mode):
    seed_module.run()  # base de test = données de référence avec comptes de démo
    r = client.post("/api/auth/login", json={"email": "admin@aihub-demo.local", "password": "Admin!2026"})
    assert r.status_code == 401


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"


def test_switching_demo_database_to_real_mode_creates_admin(client, real_mode, monkeypatch):
    """Base de démo passée en mode réel : comptes démo désactivés ET administrateur réel créé (pas de blocage)."""
    monkeypatch.setattr(real_mode, "admin_email", "dsi@exemple.fr")
    monkeypatch.setattr(real_mode, "admin_password", "UnMotDePasseLong!2026")
    seed_module.run()
    seed_module.run()  # idempotent : pas de doublon au redémarrage
    r = client.post("/api/auth/login", json={"email": "dsi@exemple.fr", "password": "UnMotDePasseLong!2026"})
    assert r.status_code == 200 and r.json()["role"] == "ADMIN"
    assert client.post("/api/auth/login", json={"email": "user@aihub-demo.local", "password": "User!2026"}).status_code == 401

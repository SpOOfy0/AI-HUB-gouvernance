"""Configuration pytest : base PostgreSQL de test isolée (jamais la base de démo).

La base est recréée au début de la session (migrations Alembic rejouées, ce qui teste
aussi les migrations et le trigger d'audit), puis vidée et ré-amorcée avec les données
de référence avant chaque test.
"""
import os

# Les variables doivent être fixées AVANT l'import de l'application.
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://rdt:rdt@localhost:5432/rdt_test")
os.environ.update({
    "DATABASE_URL": TEST_DB_URL,
    "DEMO_MODE": "true",
    "COOKIE_SECURE": "false",  # TestClient parle en http://testserver
    "MOCK_LATENCY_MIN_MS": "0",
    "MOCK_LATENCY_MAX_MS": "0",
    "RATE_LIMIT_LOGIN_PER_MINUTE": "1000",
    "RATE_LIMIT_CHAT_PER_MINUTE": "1000",
    "OLLAMA_BASE_URL": "http://127.0.0.1:9",  # injoignable : les modèles privés passent par le mock
    "JWT_SECRET": "test-secret-0123456789abcdef0123456789",
})

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.seed.data import DEMO_ACCOUNTS  # noqa: E402
from app.seed.seed import seed_reference  # noqa: E402

get_settings.cache_clear()
PASSWORDS = {a["role"]: (a["email"], a["password"]) for a in DEMO_ACCOUNTS if a["email"] != "quota@aihub-demo.local"}
TABLES = ["audit_events", "quota_alerts", "llm_requests", "messages", "conversations", "model_prices", "models",
          "providers", "dlp_lexicon_terms", "policy_settings", "users", "departments"]


def _create_database() -> None:
    url = make_url(TEST_DB_URL)
    assert url.database and "test" in url.database, "Sécurité : la base de test doit contenir 'test' dans son nom"
    admin = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
            conn.execute(f'CREATE DATABASE "{url.database}"')


@pytest.fixture(scope="session", autouse=True)
def database():
    _create_database()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(database):
    """Vide toutes les tables puis recharge les données de référence.

    session_replication_role=replica désactive les triggers le temps du nettoyage
    (nécessite un rôle superutilisateur : acceptable pour la base de test uniquement).
    """
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        conn.execute(text("SET session_replication_role = DEFAULT"))
    with SessionLocal() as db:
        seed_reference(db)
        db.commit()
    limiter.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class FakeProviders:
    """Fabrique de fournisseurs pour les tests : enregistre chaque appel, peut simuler des pannes."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.failing: set[str] = set()

    def factory(self, model):
        return self

    def complete(self, model, messages):
        from app.providers.base import ProviderError, ProviderResult

        self.calls.append({"model": model.litellm_name, "hosting": model.hosting, "messages": messages})
        if model.litellm_name in self.failing:
            raise ProviderError("panne simulée")
        return ProviderResult("Réponse de test.", 100, 50, False, True, "fake")


@pytest.fixture
def providers(client):
    """Remplace la fabrique de fournisseurs de l'application par un faux qui compte les appels."""
    from app.main import app
    from app.providers.factory import get_provider_factory

    fake = FakeProviders()
    app.dependency_overrides[get_provider_factory] = lambda: fake.factory
    return fake


def chat(client: TestClient, message: str, **kwargs):
    return client.post("/api/chat/completions", json={"message": message, **kwargs})


def model_id(db, litellm_name: str) -> int:
    from app.models import LlmModel

    return db.scalar(select(LlmModel.id).where(LlmModel.litellm_name == litellm_name))


def login(client: TestClient, role: str = "USER") -> None:
    email, password = PASSWORDS[role]
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text

"""Configuration de l'application, lue depuis les variables d'environnement.

Aucune valeur secrète par défaut n'est utilisable en production : JWT_SECRET
doit être défini explicitement (voir .env.example).
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Base de données ---
    database_url: str = "postgresql+psycopg://rdt:rdt@localhost:5432/rdt_ai_hub"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Les hébergeurs (Render, Neon...) fournissent postgres:// ou postgresql:// : on force le pilote psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    # --- Authentification ---
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # une journée de travail
    cookie_name: str = "rdt_session"
    cookie_secure: bool = True  # Secure : cookie envoyé uniquement en HTTPS (localhost toléré par Chrome/Firefox)

    # --- Mode démo ---
    demo_mode: bool = True
    mock_latency_min_ms: int = 300
    mock_latency_max_ms: int = 1500
    # Modèles (litellm_name) que le MockProvider fait échouer : sert à démontrer le fallback.
    mock_failing_models: str = ""

    # --- Compte administrateur initial (mode réel uniquement, DEMO_MODE=false) ---
    admin_email: str = ""
    admin_password: str = ""

    # --- Documentation Swagger (/docs) : toujours en démo, sur option en mode réel ---
    enable_api_docs: bool = False

    # --- Frontend statique servi par FastAPI (déploiement en un seul conteneur) ---
    static_dir: str = ""

    # --- Fournisseurs (clés lues uniquement ici, jamais renvoyées par l'API) ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://ollama:11434"
    provider_timeout_seconds: float = 30.0

    # --- Limitation de débit (fenêtre glissante d'une minute) ---
    rate_limit_login_per_minute: int = 10
    rate_limit_chat_per_minute: int = 30

    # --- Passerelle ---
    max_message_chars: int = 20000
    estimated_output_tokens: int = 800  # hypothèse pessimiste pour l'estimation avant appel

    @property
    def failing_models(self) -> set[str]:
        return {m.strip() for m in self.mock_failing_models.split(",") if m.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Choix du fournisseur concret pour un modèle donné.

- Modèle PRIVATE (Ollama) : appel réel si Ollama est joignable, sinon mock "privé".
- Modèle EXTERNAL : mock en mode démo ; sinon LiteLLM avec la clé lue dans l'environnement.
  En mode démo, AUCUNE requête ne part vers un fournisseur externe.
"""
import os
import time

import httpx

from app.config import get_settings
from app.core.enums import Hosting
from app.models import LlmModel
from app.providers.base import LlmProvider, ProviderError, ProviderResult
from app.providers.litellm_provider import LiteLLMProvider
from app.providers.mock import MockProvider

_ollama_cache: dict[str, float | bool] = {"checked_at": 0.0, "up": False}


def ollama_available() -> bool:
    """Test de joignabilité d'Ollama, mis en cache 30 s."""
    now = time.monotonic()
    if now - float(_ollama_cache["checked_at"]) > 30:
        try:
            httpx.get(f"{get_settings().ollama_base_url}/api/tags", timeout=1.5).raise_for_status()
            _ollama_cache["up"] = True
        except Exception:
            _ollama_cache["up"] = False
        _ollama_cache["checked_at"] = now
    return bool(_ollama_cache["up"])


def api_key_for(model: LlmModel) -> str | None:
    env_var = model.provider.api_key_env_var
    return os.environ.get(env_var) or getattr(get_settings(), env_var.lower(), None) if env_var else None


class _MissingKeyProvider:
    def complete(self, model: LlmModel, messages: list[dict]) -> ProviderResult:
        raise ProviderError("Clé API non configurée")


def default_provider_factory(model: LlmModel) -> LlmProvider:
    settings = get_settings()
    if model.hosting == Hosting.PRIVATE:
        if ollama_available():
            return LiteLLMProvider(api_base=settings.ollama_base_url, backend="ollama")
        return MockProvider(private=True)
    if settings.demo_mode:
        return MockProvider()
    key = api_key_for(model)
    return LiteLLMProvider(api_key=key) if key else _MissingKeyProvider()


def get_provider_factory():
    """Dépendance FastAPI (surchargée dans les tests)."""
    return default_provider_factory

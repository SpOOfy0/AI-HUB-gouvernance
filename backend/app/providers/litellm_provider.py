"""Appel réel via LiteLLM utilisé comme bibliothèque (pas de LiteLLM Proxy).

LiteLLM ne sert qu'à uniformiser l'appel aux différents fournisseurs (OpenAI, Anthropic,
DeepSeek, Ollama). Toute la gouvernance (DLP, routage, quotas, audit) est dans notre code.
"""
import os

from app.config import get_settings
from app.models import LlmModel
from app.providers.base import ProviderError, ProviderResult
from app.services.cost_service import estimate_tokens

# Évite que LiteLLM télécharge sa table de prix sur Internet à l'import.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


class LiteLLMProvider:
    def __init__(self, api_key: str | None = None, api_base: str | None = None, backend: str = "litellm"):
        self.api_key = api_key
        self.api_base = api_base
        self.backend = backend

    def complete(self, model: LlmModel, messages: list[dict]) -> ProviderResult:
        import litellm  # import tardif : la bibliothèque est lourde à charger

        try:
            response = litellm.completion(
                model=model.litellm_name,
                messages=messages,
                api_key=self.api_key,
                api_base=self.api_base,
                timeout=get_settings().provider_timeout_seconds,
                num_retries=0,  # le fallback est géré par notre passerelle, pas par LiteLLM
            )
        except Exception as exc:
            # On ne propage que le type d'erreur : le message peut contenir des extraits de requête.
            raise ProviderError(type(exc).__name__) from None

        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage and usage.prompt_tokens is not None:
            return ProviderResult(text, usage.prompt_tokens, usage.completion_tokens or 0, False, False, self.backend)
        prompt_chars = sum(len(m["content"]) for m in messages)
        return ProviderResult(text, max(1, prompt_chars // 4), estimate_tokens(text), True, False, self.backend)

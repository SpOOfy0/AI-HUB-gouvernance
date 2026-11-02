"""Interface commune à tous les fournisseurs : un seul point d'appel, `complete()`.

C'est le seul endroit par lequel un contenu peut sortir vers un modèle.
Les tests remplacent la fabrique de fournisseurs par un mock qui compte les appels.
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.models import LlmModel


@dataclass
class ProviderResult:
    text: str
    input_tokens: int
    output_tokens: int
    tokens_estimated: bool  # True si les tokens sont estimés (mode simulé)
    simulated: bool         # True si la réponse est générée par un mock
    backend: str            # "mock" | "mock-private" | "litellm" | "ollama"


class ProviderError(Exception):
    """Erreur fournisseur (timeout, indisponibilité, clé absente...) : déclenche le fallback."""


class LlmProvider(Protocol):
    def complete(self, model: LlmModel, messages: list[dict]) -> ProviderResult: ...


ProviderFactory = Callable[[LlmModel], LlmProvider]

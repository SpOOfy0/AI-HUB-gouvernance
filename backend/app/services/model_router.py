"""Sélection du modèle dans l'ensemble éligible, et ordre de fallback.

Mode automatique :
  - complexité estimée par une heuristique déterministe (longueur, mots-clés, code,
    option "raisonnement approfondi") ;
  - SIMPLE  -> modèle le moins cher ;
  - COMPLEX -> tier le plus élevé disponible (à tier égal : le moins cher).
Mode manuel :
  - le modèle demandé n'est utilisé que s'il est éligible ET autorisé pour le rôle ;
  - sinon refus explicite, ou bascule vers un modèle privé si l'utilisateur l'accepte.
Fallback : les autres modèles de la liste, tous issus du MÊME ensemble éligible.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.enums import Hosting, Tier
from app.models import LlmModel
from app.services.cost_service import blended_price
from app.services.dlp_service import normalize

_CODE_HINT = re.compile(r"```|\bdef \w+\(|\bfunction\b|\bclass \w+|\bSELECT\b.+\bFROM\b|=>|;\s*$", re.MULTILINE | re.IGNORECASE)


@dataclass
class Complexity:
    level: str  # SIMPLE | COMPLEX
    score: int
    signals: list[str] = field(default_factory=list)


def estimate_complexity(message: str, deep_reasoning: bool, config: dict) -> Complexity:
    signals: list[str] = []
    score = 0
    if deep_reasoning:
        return Complexity("COMPLEX", 99, ["raisonnement approfondi demandé"])
    if len(message) >= config["very_long_message_chars"]:
        score += 2
        signals.append("message très long")
    elif len(message) >= config["long_message_chars"]:
        score += 1
        signals.append("message long")
    text = normalize(message)
    hits = [k for k in config["keywords"] if normalize(k) in text]
    if hits:
        score += min(2, len(hits))
        signals.append("mots-clés d'analyse")
    if _CODE_HINT.search(message):
        score += 1
        signals.append("présence de code")
    level = "COMPLEX" if score >= config["complex_score_threshold"] else "SIMPLE"
    return Complexity(level, score, signals)


def _price_key(m: LlmModel) -> Decimal:
    p = blended_price(m)
    return p if p is not None else Decimal("Infinity")  # prix inconnu : en dernier


def order_candidates(eligible: list[LlmModel], complexity: Complexity) -> list[LlmModel]:
    if complexity.level == "COMPLEX":
        return sorted(eligible, key=lambda m: (-Tier(m.tier).rank, _price_key(m), m.display_name))
    return sorted(eligible, key=lambda m: (_price_key(m), Tier(m.tier).rank, m.display_name))


class ModelNotEligible(Exception):
    def __init__(self, reason: str, can_fallback_private: bool):
        super().__init__(reason)
        self.reason = reason
        self.can_fallback_private = can_fallback_private


@dataclass
class RouteSelection:
    candidates: list[LlmModel]  # le premier est le choix principal, les suivants le fallback
    mode: str
    explanation: str


def select(
    eligible: list[LlmModel],
    complexity: Complexity,
    requested: LlmModel | None,
    requested_id: int | None,
    role: str,
    accept_private_fallback: bool,
) -> RouteSelection:
    if requested_id is None:
        ordered = order_candidates(eligible, complexity)
        why = "modèle le moins cher" if complexity.level == "SIMPLE" else "tier le plus élevé disponible"
        signals = f" ({', '.join(complexity.signals)})" if complexity.signals else ""
        return RouteSelection(ordered, "auto", f"Mode auto, complexité {complexity.level}{signals} : {why}.")

    eligible_ids = {m.id for m in eligible}
    private_eligible = [m for m in eligible if m.hosting == Hosting.PRIVATE]

    if requested is None or not requested.is_active:
        reason = "Le modèle demandé est inconnu ou désactivé."
    elif role not in (requested.allowed_roles or []):
        reason = f"Le modèle {requested.display_name} n'est pas autorisé pour votre rôle."
    elif requested.id not in eligible_ids:
        reason = f"Le modèle {requested.display_name} n'est pas autorisé pour le niveau de confidentialité de cette requête."
    else:
        others = [m for m in order_candidates(eligible, complexity) if m.id != requested.id]
        return RouteSelection([requested, *others], "manual", f"Mode manuel : {requested.display_name} est éligible.")

    # Modèle demandé refusé : jamais d'envoi forcé.
    if accept_private_fallback and private_eligible:
        ordered = order_candidates(private_eligible, complexity)
        return RouteSelection(ordered, "manual", f"{reason} Bascule acceptée vers un modèle privé.")
    raise ModelNotEligible(reason, can_fallback_private=bool(private_eligible))

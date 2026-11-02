"""Calcul des coûts. Si le prix est absent : None ("coût non disponible"), jamais inventé."""
from decimal import Decimal

from app.models import LlmModel, ModelPrice

MILLION = Decimal(1_000_000)


def estimate_tokens(text: str) -> int:
    """Estimation grossière (~4 caractères par token). Utilisée seulement si le fournisseur
    ne renvoie pas de compte, ou pour l'estimation avant appel. Marquée "estimé"."""
    return max(1, len(text) // 4)


def compute_cost(price: ModelPrice | None, input_tokens: int, output_tokens: int) -> Decimal | None:
    if price is None:
        return None
    cost = (Decimal(input_tokens) * price.input_per_mtok + Decimal(output_tokens) * price.output_per_mtok) / MILLION
    return cost.quantize(Decimal("0.000001"))


def blended_price(model: LlmModel) -> Decimal | None:
    """Indicateur de tri "moins cher" : prix entrée + prix sortie par million de tokens."""
    if model.price is None:
        return None
    return model.price.input_per_mtok + model.price.output_per_mtok


def estimate_max_cost(models: list[LlmModel], input_tokens: int, output_tokens: int) -> Decimal:
    """Estimation pessimiste avant appel : on ne connaît pas encore le modèle (la classification
    vient après), donc on prend le plus cher des modèles fournis."""
    costs = [compute_cost(m.price, input_tokens, output_tokens) for m in models if m.is_active and m.price]
    return max((c for c in costs if c is not None), default=Decimal(0))

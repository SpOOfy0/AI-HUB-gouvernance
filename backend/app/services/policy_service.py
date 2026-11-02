"""Décision de politique et ensemble des modèles éligibles.

Règles (invariants de sécurité, volontairement codées et testées, pas configurables) :
  RESTRICTED   -> BLOCK        : aucun appel fournisseur
  CONFIDENTIAL -> PRIVATE_ONLY : seuls les modèles hébergés en interne (PRIVATE)
  PUBLIC/INTERNAL -> ALLOW     : modèles dont le niveau max >= niveau de la requête
"""
from app.core.enums import Decision, Hosting, Level
from app.models import LlmModel
from app.services.classification_service import ClassificationResult

DETECTION_LABELS = {
    "api_key": "clé API",
    "jwt": "jeton JWT",
    "private_key": "clé privée",
    "password": "mot de passe",
    "connection_string": "chaîne de connexion",
    "api_key_assignment": "secret applicatif",
    "high_entropy_string": "chaîne aléatoire de type secret",
    "payment_card": "numéro de carte bancaire",
    "email": "adresse email",
    "phone": "numéro de téléphone",
    "social_security_number": "numéro de sécurité sociale",
    "iban": "IBAN",
    "lexique:commercial": "lexique commercial confidentiel",
    "lexique:client": "nom de client",
    "lexique:internal_id": "identifiant interne",
    "lexique:site": "nom de site",
    "lexique:procedure": "procédure interne",
    "classification_error": "erreur de classification",
}

LEVEL_LABELS = {
    Level.PUBLIC: "publiques",
    Level.INTERNAL: "internes",
    Level.CONFIDENTIAL: "confidentielles",
    Level.RESTRICTED: "secrètes",
}


def label(detection_type: str) -> str:
    if detection_type.startswith("detector_error:"):
        return "erreur d'un détecteur (niveau relevé par précaution)"
    return DETECTION_LABELS.get(detection_type, detection_type.replace("lexique:", "lexique : "))


def decide(level: Level) -> Decision:
    if level == Level.RESTRICTED:
        return Decision.BLOCK
    if level == Level.CONFIDENTIAL:
        return Decision.PRIVATE_ONLY
    return Decision.ALLOW


def is_model_allowed_for_level(model: LlmModel, level: Level) -> bool:
    """Un modèle peut traiter une requête si son niveau max couvre le niveau de la requête,
    et si la requête est CONFIDENTIAL, seulement s'il est hébergé en interne."""
    decision = decide(level)
    if decision == Decision.BLOCK:
        return False
    if decision == Decision.PRIVATE_ONLY and model.hosting != Hosting.PRIVATE:
        return False
    return Level(model.max_classification).rank >= level.rank


def eligible_models(models: list[LlmModel], level: Level, role: str) -> list[LlmModel]:
    """Modèles actifs, autorisés pour le rôle et compatibles avec le niveau."""
    return [
        m for m in models
        if m.is_active and role in (m.allowed_roles or []) and is_model_allowed_for_level(m, level)
    ]


def explain(result: ClassificationResult, decision: Decision) -> str:
    """Phrase lisible expliquant la décision. Ne cite jamais le contenu."""
    level = result.level
    source = result.dominant_source
    relevant = [d for d in result.detections if d.level == level]
    if source in ("message", "context") and relevant:
        what = ", ".join(sorted({label(d.type) for d in relevant}))
        where = " dans l'historique de la conversation" if source == "context" and result.sources["message"] != level else ""
        cause = f"Données {LEVEL_LABELS[level]} détectées{where} ({what})"
    elif source == "conversation" and level != Level.PUBLIC:
        cause = f"La conversation est déjà classée {level} (le niveau ne redescend jamais)"
    elif source == "declared" and level != Level.PUBLIC:
        cause = f"Niveau {level} déclaré par l'utilisateur"
    else:
        cause = "Aucune donnée sensible détectée"

    if decision == Decision.BLOCK:
        return f"{cause} : requête bloquée, aucun modèle n'a été appelé."
    if decision == Decision.PRIVATE_ONLY:
        return f"{cause} : routage limité aux modèles privés."
    if level == Level.INTERNAL:
        return f"{cause} : modèles autorisés jusqu'au niveau INTERNAL (sous contrat entreprise ou privés)."
    return f"{cause} : tous les modèles autorisés sont éligibles."

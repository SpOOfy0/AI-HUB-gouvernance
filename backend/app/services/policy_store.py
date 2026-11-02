"""Lecture de la politique stockée en base, avec valeurs par défaut documentées.

Ces valeurs sont des hypothèses de démonstration, à valider avec la DSI.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Level
from app.models import LexiconTerm, PolicySetting
from app.services.dlp_service import DEFAULT_DETECTION_LEVELS, LexiconEntry

DEFAULT_POLICY: dict[str, dict] = {
    # Catégorie de détection -> niveau de classification.
    "detection_levels": {k: str(v) for k, v in DEFAULT_DETECTION_LEVELS.items()},
    # Heuristique de complexité (voir model_router.estimate_complexity).
    "complexity": {
        "long_message_chars": 600,
        "very_long_message_chars": 2000,
        "complex_score_threshold": 2,
        "keywords": [
            "analyse", "analyser", "compare", "comparer", "comparaison", "synthese", "synthétise",
            "strategie", "stratégie", "optimise", "optimiser", "rapport", "avantages et inconvenients",
            "avantages et inconvénients", "explique en detail", "explique en détail", "plan d'action",
            "evalue", "évalue", "recommandation",
        ],
    },
    # Rétention des conversations (jours). Valeur démo, à fixer avec le DPO.
    "retention": {"conversation_days": 90},
    # Seuils d'alerte de quota en pourcentage (100 % = blocage, toujours actif).
    "quota": {"alert_thresholds": [70, 90]},
}


def get_policy(db: Session) -> dict[str, dict]:
    policy = {k: dict(v) for k, v in DEFAULT_POLICY.items()}
    for setting in db.scalars(select(PolicySetting)):
        if setting.key in policy:
            policy[setting.key] = {**policy[setting.key], **setting.value}
    return policy


def get_lexicon(db: Session) -> list[LexiconEntry]:
    terms = db.scalars(select(LexiconTerm).where(LexiconTerm.is_active.is_(True)))
    return [LexiconEntry(t.term, t.category, Level(t.level), t.is_regex) for t in terms]

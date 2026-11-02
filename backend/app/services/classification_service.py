"""Classification d'une requête.

Niveau final = MAX de quatre sources :
  1. DLP sur le message courant
  2. DLP sur tout le contexte envoyé au modèle (messages précédents inclus)
  3. niveau déclaré par l'utilisateur (peut relever, jamais abaisser)
  4. niveau déjà atteint par la conversation (ne redescend jamais)
En cas d'erreur inattendue : RESTRICTED (fail closed).
"""
import logging
from dataclasses import dataclass, field

from app.core.enums import Level
from app.services import dlp_service
from app.services.dlp_service import Detection, LexiconEntry

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    level: Level
    detections: list[Detection]
    sources: dict[str, Level] = field(default_factory=dict)

    @property
    def dominant_source(self) -> str:
        """Source qui a fixé le niveau final (priorité : message > contexte > conversation > déclaré)."""
        for name in ("message", "context", "conversation", "declared"):
            if self.sources.get(name) == self.level:
                return name
        return "message"


def classify(
    message: str,
    history: list[str],
    declared_level: Level | None,
    conversation_level: Level | None,
    lexicon: list[LexiconEntry],
    detection_levels: dict[str, str] | None = None,
) -> ClassificationResult:
    try:
        message_detections = dlp_service.scan(message, lexicon, detection_levels)
        context_detections = (
            dlp_service.scan("\n".join([*history, message]), lexicon, detection_levels) if history else message_detections
        )
    except Exception:
        logger.exception("Erreur de classification : fail closed (RESTRICTED)")
        err = Detection("classification_error", "detector_error", Level.RESTRICTED, 1, "classification")
        return ClassificationResult(Level.RESTRICTED, [err], {"message": Level.RESTRICTED})

    sources = {
        "message": dlp_service.max_level(message_detections),
        "context": dlp_service.max_level(context_detections),
        "declared": declared_level or Level.PUBLIC,
        "conversation": conversation_level or Level.PUBLIC,
    }
    level = Level.max(*sources.values())

    # Détections affichées : celles du message, complétées par celles venant uniquement du contexte.
    seen = {d.type for d in message_detections}
    detections = list(message_detections) + [d for d in context_detections if d.type not in seen]
    return ClassificationResult(level, detections, sources)

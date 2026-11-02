"""Passerelle LLM : orchestre le pipeline de gouvernance.

    1. Authentification + rôle            (dépendances FastAPI, avant d'arriver ici)
    2. Quota (estimation avant appel)     quota_service.check_before
    3. Classification                     classification_service.classify
    4. Décision ALLOW/PRIVATE_ONLY/BLOCK  policy_service.decide
    5. Sélection du modèle                policy_service.eligible_models + model_router.select
    6. Appel fournisseur                  provider.complete
    7. Fallback dans le même ensemble     boucle sur les candidats
    8. Coût réel + consommation           cost_service.compute_cost
    9. Journalisation                     audit_service.log_event
   10. Réponse + métadonnées de routage

Règles de contenu :
  - requête BLOQUÉE : le contenu n'est écrit nulle part (ni base, ni journal, ni logs) ;
  - requête ALLOW / PRIVATE_ONLY : le contenu est stocké dans la conversation (historique) ;
  - journal d'audit et llm_requests : métadonnées uniquement.
"""
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import App, Decision, Level, Severity
from app.models import Conversation, LlmModel, LlmRequest, Message, User
from app.providers.base import ProviderFactory
from app.services import (
    audit_service,
    classification_service,
    cost_service,
    model_router,
    policy_service,
    policy_store,
    quota_service,
)

logger = logging.getLogger(__name__)


@dataclass
class ChatInput:
    message: str
    conversation_id: int | None = None
    model_id: int | None = None          # None = mode automatique
    declared_level: Level | None = None
    deep_reasoning: bool = False
    accept_private_fallback: bool = False
    app: App = App.CHAT


class GatewayError(Exception):
    def __init__(self, status_code: int, code: str, message: str, request_id: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id


class InvariantViolation(RuntimeError):
    """Ne doit jamais arriver : un modèle non éligible a failli être appelé."""


def _detections_payload(result: classification_service.ClassificationResult) -> list[dict]:
    return [{**d.to_dict(), "label": policy_service.label(d.type)} for d in result.detections]


def _record_request(db: Session, user: User, inp: ChatInput, request_id: str, **fields) -> LlmRequest:
    row = LlmRequest(request_id=request_id, user_id=user.id, department_id=user.department_id,
                     app=str(inp.app), mode="manual" if inp.model_id else "auto", **fields)
    db.add(row)
    db.flush()
    return row


def handle_chat(db: Session, user: User, inp: ChatInput, provider_factory: ProviderFactory, request_id: str) -> dict:
    settings = get_settings()
    policy = policy_store.get_policy(db)

    message = inp.message.strip()
    if not message:
        raise GatewayError(422, "EMPTY_MESSAGE", "Le message est vide.", request_id)
    if len(message) > settings.max_message_chars:
        raise GatewayError(422, "MESSAGE_TOO_LONG", f"Message limité à {settings.max_message_chars} caractères.", request_id)

    conversation: Conversation | None = None
    history: list[Message] = []
    if inp.conversation_id is not None:
        conversation = db.get(Conversation, inp.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise GatewayError(404, "CONVERSATION_NOT_FOUND", "Conversation introuvable.", request_id)
        history = list(conversation.messages)

    active_models = list(db.scalars(select(LlmModel).where(LlmModel.is_active.is_(True))).unique())

    # --- 2. Quota : estimation pessimiste avant tout traitement --------------------------
    est_input = cost_service.estimate_tokens("".join(m.content for m in history) + message)
    est_output = settings.estimated_output_tokens
    # Le modèle n'est pas encore connu : on prend le plus cher parmi ceux autorisés pour le rôle.
    role_models = [m for m in active_models if user.role in (m.allowed_roles or [])]
    est_cost = cost_service.estimate_max_cost(role_models, est_input, est_output)
    try:
        quota_service.check_before(db, user, est_cost, est_input + est_output)
    except quota_service.QuotaExceeded as exc:
        audit_service.log_event(db, "QUOTA_EXCEEDED", category="quota", severity=Severity.WARNING, status="DENIED",
                                user_id=user.id, request_id=request_id,
                                details={"scope": exc.scope, "estimated_cost_eur": str(est_cost)})
        db.commit()
        raise GatewayError(429, "QUOTA_EXCEEDED", exc.message, request_id) from None

    # --- 3. Classification ----------------------------------------------------------------
    result = classification_service.classify(
        message=message,
        history=[m.content for m in history],
        declared_level=inp.declared_level,
        conversation_level=Level(conversation.max_classification) if conversation else None,
        lexicon=policy_store.get_lexicon(db),
        detection_levels=policy["detection_levels"],
    )

    # --- 4. Décision de politique ----------------------------------------------------------
    decision = policy_service.decide(result.level)
    reason = policy_service.explain(result, decision)
    routing: dict = {
        "classification": str(result.level),
        "sources": {k: str(v) for k, v in result.sources.items()},
        "detections": _detections_payload(result),
        "decision": str(decision),
        "mode": "manual" if inp.model_id else "auto",
        "reason": reason,
    }
    detections_meta = [d.to_dict() for d in result.detections]

    if decision == Decision.BLOCK:
        # Aucun appel fournisseur, aucun stockage du contenu. Métadonnées seulement.
        _record_request(db, user, inp, request_id, conversation_id=conversation.id if conversation else None,
                        classification=str(result.level), detections=detections_meta, decision=str(decision),
                        routing_reason=reason, status="BLOCKED")
        audit_service.log_event(db, "REQUEST_BLOCKED", category="security", severity=Severity.CRITICAL,
                                status="BLOCKED", user_id=user.id, request_id=request_id,
                                details={"classification": str(result.level), "detections": detections_meta,
                                         "app": str(inp.app)})
        db.commit()
        logger.warning("Requête bloquée (classification=%s, détections=%s)",
                       result.level, [d.type for d in result.detections])
        return {"status": "BLOCKED", "request_id": request_id,
                "conversation_id": conversation.id if conversation else None,
                "message": None, "routing": routing, "alerts": [], "can_fallback_private": False}

    # --- 5. Sélection du modèle -------------------------------------------------------------
    eligible = policy_service.eligible_models(active_models, result.level, user.role)
    complexity = model_router.estimate_complexity(message, inp.deep_reasoning, policy["complexity"])
    routing["complexity"] = complexity.level
    requested = db.get(LlmModel, inp.model_id) if inp.model_id else None
    try:
        selection = model_router.select(eligible, complexity, requested, inp.model_id, user.role,
                                        inp.accept_private_fallback)
    except model_router.ModelNotEligible as exc:
        routing["reason"] = f"{reason} {exc.reason}"
        _record_request(db, user, inp, request_id, conversation_id=conversation.id if conversation else None,
                        classification=str(result.level), detections=detections_meta, decision=str(decision),
                        routing_reason=routing["reason"], complexity=complexity.level, status="REFUSED",
                        model=requested.litellm_name if requested else None)
        audit_service.log_event(db, "MANUAL_MODEL_REFUSED", category="security", severity=Severity.WARNING,
                                status="REFUSED", user_id=user.id, request_id=request_id,
                                details={"requested_model": requested.litellm_name if requested else inp.model_id,
                                         "classification": str(result.level), "reason": exc.reason})
        db.commit()
        return {"status": "REFUSED", "request_id": request_id,
                "conversation_id": conversation.id if conversation else None, "message": None,
                "routing": routing, "alerts": [], "can_fallback_private": exc.can_fallback_private}

    if not selection.candidates:
        audit_service.log_event(db, "NO_MODEL_AVAILABLE", category="security", severity=Severity.CRITICAL,
                                status="ERROR", user_id=user.id, request_id=request_id,
                                details={"classification": str(result.level), "cause": "aucun modèle éligible"})
        db.commit()
        raise GatewayError(503, "NO_ELIGIBLE_MODEL",
                           "Aucun modèle n'est disponible pour ce niveau de confidentialité.", request_id)

    # --- 6-7. Appel fournisseur avec fallback dans le même ensemble éligible ---------------
    context_messages = [{"role": m.role, "content": m.content} for m in history] + [{"role": "user", "content": message}]
    attempts: list[dict] = []
    provider_result = None
    used_model: LlmModel | None = None
    latency_ms = 0
    for model in selection.candidates:
        # Défense en profondeur : on revérifie l'invariant juste avant l'envoi.
        if not policy_service.is_model_allowed_for_level(model, result.level):
            raise InvariantViolation(f"Modèle {model.litellm_name} non éligible pour {result.level}")
        started = time.perf_counter()
        try:
            provider_result = provider_factory(model).complete(model, context_messages)
            latency_ms = int((time.perf_counter() - started) * 1000)
            used_model = model
            break
        except Exception as exc:  # ProviderError ou erreur inattendue : on tente le suivant
            error = type(exc).__name__
            attempts.append({"model": model.litellm_name, "error": error})
            audit_service.log_event(db, "PROVIDER_ERROR", category="ai", severity=Severity.WARNING, status="ERROR",
                                    user_id=user.id, request_id=request_id,
                                    details={"model": model.litellm_name, "provider": model.provider.name,
                                             "error": error})
            logger.warning("Erreur fournisseur sur %s (%s), tentative suivante", model.litellm_name, error)

    routing["attempts"] = attempts
    if provider_result is None or used_model is None:
        _record_request(db, user, inp, request_id, conversation_id=conversation.id if conversation else None,
                        classification=str(result.level), detections=detections_meta, decision=str(decision),
                        routing_reason=reason, complexity=complexity.level, status="ERROR", fallback_used=True)
        audit_service.log_event(db, "NO_MODEL_AVAILABLE", category="security", severity=Severity.CRITICAL,
                                status="ERROR", user_id=user.id, request_id=request_id,
                                details={"classification": str(result.level), "attempts": attempts})
        db.commit()
        raise GatewayError(503, "ALL_PROVIDERS_FAILED",
                           "Aucun modèle éligible n'a pu répondre. Réessayez plus tard.", request_id)

    # --- 8. Coût réel ------------------------------------------------------------------------
    cost = cost_service.compute_cost(used_model.price, provider_result.input_tokens, provider_result.output_tokens)
    fallback_used = bool(attempts)
    selection_text = selection.explanation
    if fallback_used:
        selection_text += (f" Fallback vers {used_model.display_name} après {len(attempts)} échec(s),"
                           " dans le même ensemble éligible.")
    routing.update({
        "reason": f"{reason} {selection_text}",
        "mode": selection.mode,
        "provider": used_model.provider.name,
        "model": used_model.litellm_name,
        "model_display": used_model.display_name,
        "hosting": used_model.hosting,
        "fallback_used": fallback_used,
        "latency_ms": latency_ms,
        "input_tokens": provider_result.input_tokens,
        "output_tokens": provider_result.output_tokens,
        "tokens_estimated": provider_result.tokens_estimated,
        "cost_eur": str(cost) if cost is not None else None,
        "cost_available": cost is not None,
        "price_is_demo": bool(used_model.price and used_model.price.is_demo),
        "simulated": provider_result.simulated,
        "backend": provider_result.backend,
    })

    # Stockage de l'échange (autorisé pour ALLOW et PRIVATE_ONLY uniquement).
    now = datetime.now(UTC)
    if conversation is None:
        conversation = Conversation(user_id=user.id, title=message[:60], max_classification=str(result.level))
        db.add(conversation)
        db.flush()
    conversation.max_classification = str(Level.max(Level(conversation.max_classification), result.level))
    conversation.updated_at = now
    db.add(Message(conversation_id=conversation.id, role="user", content=message,
                   classification=str(result.level), request_id=request_id))
    assistant = Message(conversation_id=conversation.id, role="assistant", content=provider_result.text,
                        classification=str(result.level), request_id=request_id, routing=routing)
    db.add(assistant)

    _record_request(db, user, inp, request_id, conversation_id=conversation.id, classification=str(result.level),
                    detections=detections_meta, decision=str(decision), routing_reason=routing["reason"],
                    complexity=complexity.level, provider=used_model.provider.name, model=used_model.litellm_name,
                    hosting=used_model.hosting, fallback_used=fallback_used,
                    input_tokens=provider_result.input_tokens, output_tokens=provider_result.output_tokens,
                    tokens_estimated=provider_result.tokens_estimated, cost_eur=cost, latency_ms=latency_ms,
                    status="SUCCESS", is_simulated=provider_result.simulated)

    # --- 9. Journalisation (métadonnées uniquement) --------------------------------------------
    audit_service.log_event(db, "AI_REQUEST", category="ai", severity=Severity.INFO, status="SUCCESS",
                            user_id=user.id, request_id=request_id,
                            details={"app": str(inp.app), "classification": str(result.level),
                                     "decision": str(decision), "mode": selection.mode, "model": used_model.litellm_name,
                                     "hosting": used_model.hosting, "fallback_used": fallback_used,
                                     "detections": detections_meta, "cost_eur": str(cost) if cost is not None else None,
                                     "simulated": provider_result.simulated})
    alerts = quota_service.record_thresholds(db, user, request_id, policy["quota"]["alert_thresholds"])
    db.commit()
    logger.info("Requête traitée (classification=%s, décision=%s, modèle=%s, latence=%sms)",
                result.level, decision, used_model.litellm_name, latency_ms)

    # --- 10. Réponse ---------------------------------------------------------------------------
    return {"status": "SUCCESS", "request_id": request_id, "conversation_id": conversation.id,
            "message": {"id": assistant.id, "role": "assistant", "content": provider_result.text},
            "routing": routing, "alerts": alerts, "can_fallback_private": False}

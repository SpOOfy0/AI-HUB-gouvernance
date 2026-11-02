"""Sécurité (ADMIN) : bac à sable de classification, événements, politique et lexique."""
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.enums import Level
from app.core.request_context import get_request_id
from app.db import get_db
from app.models import AuditEvent, LexiconTerm, LlmModel, PolicySetting, User
from app.schemas.chat import ClassifyIn
from app.services import audit_service, classification_service, model_router, policy_service, policy_store
from app.services.dlp_service import normalize

router = APIRouter(prefix="/api", tags=["security"], dependencies=[Depends(require_admin)])

# Catégories dont le niveau est figé : un secret ou une carte bancaire reste RESTRICTED (bloqué).
LOCKED_CATEGORIES = {"secret": Level.RESTRICTED, "payment_card": Level.RESTRICTED}
LEXICON_CATEGORIES = {"client", "commercial", "internal_id", "site", "procedure"}


# --- Bac à sable : classification sans appel de modèle -----------------------------------
@router.post("/classify")
def classify_sandbox(body: ClassifyIn, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Affiche la décision qui serait prise. N'appelle aucun modèle, ne stocke pas le texte."""
    policy = policy_store.get_policy(db)
    result = classification_service.classify(body.message, [], body.declared_level, None,
                                             policy_store.get_lexicon(db), policy["detection_levels"])
    decision = policy_service.decide(result.level)
    models = list(db.scalars(select(LlmModel).where(LlmModel.is_active.is_(True))).unique())
    eligible = policy_service.eligible_models(models, result.level, user.role)
    complexity = model_router.estimate_complexity(body.message, False, policy["complexity"])
    ordered = model_router.order_candidates(eligible, complexity)
    return {
        "classification": str(result.level),
        "sources": {k: str(v) for k, v in result.sources.items()},
        "detections": [{**d.to_dict(), "label": policy_service.label(d.type)} for d in result.detections],
        "decision": str(decision),
        "reason": policy_service.explain(result, decision),
        "complexity": complexity.level,
        "eligible_models": [{"display_name": m.display_name, "hosting": m.hosting} for m in ordered],
        "would_select": ordered[0].display_name if ordered and decision != "BLOCK" else None,
    }


# --- Événements de sécurité ----------------------------------------------------------------
@router.get("/security/events")
def security_events(
    db: Session = Depends(get_db),
    severity: str | None = None,
    event_type: str | None = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    q = select(AuditEvent, User.email).outerjoin(User, User.id == AuditEvent.user_id).where(
        AuditEvent.category.in_(["security", "quota"]),
        AuditEvent.ts >= datetime.now(UTC) - timedelta(days=days),
    )
    if severity:
        q = q.where(AuditEvent.severity == severity)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).all()
    by_type = db.execute(
        select(AuditEvent.event_type, func.count()).where(
            AuditEvent.category.in_(["security", "quota"]),
            AuditEvent.ts >= datetime.now(UTC) - timedelta(days=days)).group_by(AuditEvent.event_type)
    ).all()
    return {
        "total": total,
        "by_type": {t: c for t, c in by_type},
        "items": [{"id": e.id, "ts": e.ts.isoformat(), "user_email": email, "event_type": e.event_type,
                   "category": e.category, "severity": e.severity, "status": e.status, "request_id": e.request_id,
                   "details": e.details} for e, email in rows],
    }


# --- Politique -------------------------------------------------------------------------------
class PolicyUpdate(BaseModel):
    detection_levels: dict[str, Level] | None = None
    complexity: dict | None = None
    retention: dict | None = None
    quota: dict | None = None

    @field_validator("complexity")
    @classmethod
    def check_complexity(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        for key in ("long_message_chars", "very_long_message_chars", "complex_score_threshold"):
            if key in v and (not isinstance(v[key], int) or v[key] < 1):
                raise ValueError(f"{key} doit être un entier positif")
        if "keywords" in v and not (isinstance(v["keywords"], list) and all(isinstance(k, str) for k in v["keywords"])):
            raise ValueError("keywords doit être une liste de chaînes")
        return v

    @field_validator("retention")
    @classmethod
    def check_retention(cls, v: dict | None) -> dict | None:
        if v is not None and not (isinstance(v.get("conversation_days"), int) and 1 <= v["conversation_days"] <= 3650):
            raise ValueError("conversation_days doit être compris entre 1 et 3650")
        return v

    @field_validator("quota")
    @classmethod
    def check_quota(cls, v: dict | None) -> dict | None:
        if v is not None:
            t = v.get("alert_thresholds")
            if not (isinstance(t, list) and all(isinstance(x, int) and 1 <= x < 100 for x in t)):
                raise ValueError("alert_thresholds : liste d'entiers entre 1 et 99")
        return v


@router.get("/policy")
def get_policy(db: Session = Depends(get_db)) -> dict:
    return {"policy": policy_store.get_policy(db), "locked_categories": {k: str(v) for k, v in LOCKED_CATEGORIES.items()}}


@router.put("/policy")
def update_policy(body: PolicyUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    current = policy_store.get_policy(db)
    changes = body.model_dump(exclude_none=True, mode="json")
    if "detection_levels" in changes:
        for cat, lvl in changes["detection_levels"].items():
            if cat in LOCKED_CATEGORIES and lvl != LOCKED_CATEGORIES[cat]:
                raise HTTPException(422, f"Le niveau de la catégorie « {cat} » est figé à {LOCKED_CATEGORIES[cat]}.")
    for key, value in changes.items():
        merged = {**current[key], **value}
        setting = db.get(PolicySetting, key)
        if setting is None:
            db.add(PolicySetting(key=key, value=merged))
        else:
            setting.value = merged
        # La politique n'est pas sensible : on journalise l'ancienne et la nouvelle valeur.
        audit_service.log_event(db, "CONFIG_CHANGED", category="config", user_id=user.id, request_id=get_request_id(),
                                details={"target": f"policy.{key}", "old": current[key], "new": merged})
    db.commit()
    return {"policy": policy_store.get_policy(db), "locked_categories": {k: str(v) for k, v in LOCKED_CATEGORIES.items()}}


# --- Lexique métier ------------------------------------------------------------------------------
class LexiconIn(BaseModel):
    term: str = Field(min_length=2, max_length=200)
    category: str
    level: Level
    is_regex: bool = False
    is_active: bool = True

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        if v not in LEXICON_CATEGORIES:
            raise ValueError(f"catégorie inconnue (attendu : {', '.join(sorted(LEXICON_CATEGORIES))})")
        return v

    @field_validator("level")
    @classmethod
    def check_level(cls, v: Level) -> Level:
        if v == Level.PUBLIC:
            raise ValueError("un terme du lexique doit relever le niveau (INTERNAL minimum)")
        return v


def _lexicon_out(t: LexiconTerm) -> dict:
    return {"id": t.id, "term": t.term, "category": t.category, "level": t.level, "is_regex": t.is_regex,
            "is_active": t.is_active}


def _validate_regex(body: LexiconIn) -> None:
    if body.is_regex:
        try:
            re.compile(normalize(body.term))
        except re.error as exc:
            raise HTTPException(422, f"Expression régulière invalide : {exc}") from None


@router.get("/policy/lexicon")
def list_lexicon(db: Session = Depends(get_db)) -> list[dict]:
    return [_lexicon_out(t) for t in db.scalars(select(LexiconTerm).order_by(LexiconTerm.category, LexiconTerm.id))]


@router.post("/policy/lexicon", status_code=201)
def create_lexicon(body: LexiconIn, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    _validate_regex(body)
    term = LexiconTerm(**body.model_dump(mode="json"))
    db.add(term)
    db.flush()
    audit_service.log_event(db, "CONFIG_CHANGED", category="config", user_id=user.id, request_id=get_request_id(),
                            details={"target": "lexicon", "action": "create", "id": term.id, "category": term.category,
                                     "level": term.level})
    db.commit()
    return _lexicon_out(term)


@router.put("/policy/lexicon/{term_id}")
def update_lexicon(term_id: int, body: LexiconIn, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    term = db.get(LexiconTerm, term_id)
    if term is None:
        raise HTTPException(404, "Terme introuvable")
    _validate_regex(body)
    for k, v in body.model_dump(mode="json").items():
        setattr(term, k, v)
    audit_service.log_event(db, "CONFIG_CHANGED", category="config", user_id=user.id, request_id=get_request_id(),
                            details={"target": "lexicon", "action": "update", "id": term.id, "category": term.category,
                                     "level": term.level, "is_active": term.is_active})
    db.commit()
    return _lexicon_out(term)


@router.delete("/policy/lexicon/{term_id}", status_code=204)
def delete_lexicon(term_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    term = db.get(LexiconTerm, term_id)
    if term is None:
        raise HTTPException(404, "Terme introuvable")
    audit_service.log_event(db, "CONFIG_CHANGED", category="config", user_id=user.id, request_id=get_request_id(),
                            details={"target": "lexicon", "action": "delete", "id": term.id, "category": term.category})
    db.delete(term)
    db.commit()

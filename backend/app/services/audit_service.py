"""Journal d'audit : append-only (trigger PostgreSQL) et chaîné par hash.

Chaque événement stocke le hash du précédent :
    hash = SHA-256(prev_hash + représentation canonique de l'événement)
Modifier, supprimer ou insérer un événement au milieu casse la chaîne,
ce que `verify_chain` détecte en recalculant tout.

Règle : métadonnées uniquement. `_sanitize` est un filet de sécurité qui
retire les clés pouvant contenir du contenu et tronque les chaînes longues.
"""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.enums import Severity
from app.models import AuditEvent

GENESIS_HASH = "0" * 64
# Verrou consultatif PostgreSQL : sérialise les insertions pour éviter deux
# événements avec le même prev_hash (fourche dans la chaîne) en cas de concurrence.
_AUDIT_LOCK_ID = 727274
_FORBIDDEN_KEYS = {"content", "prompt", "message", "messages", "response", "text", "completion", "password", "api_key"}
_MAX_STR = 200


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items() if k.lower() not in _FORBIDDEN_KEYS}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str) and len(value) > _MAX_STR:
        return value[:_MAX_STR] + "…"
    return value


def compute_hash(prev_hash: str, ts: datetime, user_id: int | None, event_type: str, category: str,
                 severity: str, status: str, request_id: str | None, details: dict) -> str:
    canonical = json.dumps(
        {
            "ts": ts.astimezone(UTC).isoformat(),
            "user_id": user_id,
            "event_type": event_type,
            "category": category,
            "severity": severity,
            "status": status,
            "request_id": request_id,
            "details": details,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def log_event(
    db: Session,
    event_type: str,
    *,
    category: str,
    severity: Severity = Severity.INFO,
    status: str = "SUCCESS",
    user_id: int | None = None,
    request_id: str | None = None,
    details: dict | None = None,
    ts: datetime | None = None,
) -> AuditEvent:
    """Ajoute un événement (flush, sans commit : l'appelant gère la transaction)."""
    clean = _sanitize(details or {})
    # Normalise via JSON pour que le hash calculé maintenant soit identique à la relecture.
    clean = json.loads(json.dumps(clean, default=str))
    ts = ts or datetime.now(UTC)
    db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _AUDIT_LOCK_ID})
    last = db.scalar(select(AuditEvent.hash).order_by(AuditEvent.id.desc()).limit(1))
    prev_hash = last or GENESIS_HASH
    event = AuditEvent(
        ts=ts, user_id=user_id, event_type=event_type, category=category, severity=str(severity),
        status=status, request_id=request_id, details=clean, prev_hash=prev_hash,
        hash=compute_hash(prev_hash, ts, user_id, event_type, category, str(severity), status, request_id, clean),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Recalcule toute la chaîne. Renvoie le premier événement incohérent s'il y en a un."""
    expected_prev = GENESIS_HASH
    checked = 0
    rows = db.execute(select(AuditEvent).order_by(AuditEvent.id).execution_options(yield_per=1000)).scalars()
    for ev in rows:
        recomputed = compute_hash(ev.prev_hash, ev.ts, ev.user_id, ev.event_type, ev.category,
                                  ev.severity, ev.status, ev.request_id, ev.details)
        if ev.prev_hash != expected_prev or recomputed != ev.hash:
            return {"valid": False, "checked": checked, "first_invalid_id": ev.id,
                    "reason": "chaînage rompu" if ev.prev_hash != expected_prev else "contenu modifié"}
        expected_prev = ev.hash
        checked += 1
    return {"valid": True, "checked": checked, "first_invalid_id": None, "reason": None}

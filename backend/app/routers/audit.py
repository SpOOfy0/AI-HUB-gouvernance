"""Journal d'audit (ADMIN) : consultation filtrable et vérification d'intégrité."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.enums import Severity
from app.core.request_context import get_request_id
from app.db import get_db
from app.models import AuditEvent, User
from app.services import audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("")
def list_events(
    db: Session = Depends(get_db),
    category: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    user_email: str | None = None,
    request_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    q = select(AuditEvent, User.email).outerjoin(User, User.id == AuditEvent.user_id)
    if category:
        q = q.where(AuditEvent.category == category)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    if severity:
        q = q.where(AuditEvent.severity == severity)
    if user_email:
        q = q.where(User.email.ilike(f"%{user_email}%"))
    if request_id:
        q = q.where(AuditEvent.request_id == request_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).all()
    return {
        "total": total,
        "items": [{"id": e.id, "ts": e.ts.isoformat(), "user_email": email, "event_type": e.event_type,
                   "category": e.category, "severity": e.severity, "status": e.status, "request_id": e.request_id,
                   "details": e.details, "hash": e.hash, "prev_hash": e.prev_hash} for e, email in rows],
    }


@router.post("/verify")
def verify(user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Recalcule toute la chaîne de hash. La vérification est elle-même journalisée."""
    result = audit_service.verify_chain(db)
    audit_service.log_event(db, "AUDIT_VERIFIED", category="admin",
                            severity=Severity.INFO if result["valid"] else Severity.CRITICAL,
                            status="VALID" if result["valid"] else "INVALID", user_id=user.id,
                            request_id=get_request_id(), details=result)
    db.commit()
    return result

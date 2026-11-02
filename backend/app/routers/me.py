"""Consommation de l'utilisateur connecté (jauge et notifications du header)."""
from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import QuotaAlert, User
from app.services import quota_service

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/usage")
def my_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    period = quota_service.month_start().strftime("%Y-%m")
    alerts = db.scalars(
        select(QuotaAlert).where(
            QuotaAlert.period == period,
            or_(and_(QuotaAlert.scope == "user", QuotaAlert.scope_id == user.id),
                and_(QuotaAlert.scope == "department", QuotaAlert.scope_id == user.department_id)),
        ).order_by(QuotaAlert.threshold.desc())
    )
    return {
        "user": quota_service.user_usage(db, user).to_dict(),
        "department": quota_service.department_usage(db, user.department).to_dict(),
        "alerts": [{"scope": a.scope, "threshold": a.threshold, "created_at": a.created_at.isoformat()} for a in alerts],
    }

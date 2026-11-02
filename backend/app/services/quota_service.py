"""Quotas mensuels (euros et tokens) par utilisateur et par département.

- Vérification AVANT l'appel avec une estimation pessimiste.
- Mise à jour APRÈS avec le coût réel (la consommation est la somme de llm_requests).
- Alertes à 70 % et 90 % (configurables), blocage à 100 %.

Limite connue : deux requêtes simultanées du même utilisateur peuvent passer la
vérification en même temps (pas de réservation). Le dépassement reste borné à une
requête ; en production on ferait une réservation de budget (voir NOTES-ENTRETIEN).
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import Severity
from app.models import Department, LlmRequest, QuotaAlert, User
from app.services import audit_service


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass
class Usage:
    cost_eur: Decimal
    tokens: int
    budget_eur: Decimal
    token_limit: int | None

    @property
    def pct(self) -> float:
        """Pourcentage le plus élevé entre budget euros et limite de tokens."""
        pcts = []
        if self.budget_eur and self.budget_eur > 0:
            pcts.append(float(self.cost_eur / self.budget_eur * 100))
        if self.token_limit:
            pcts.append(self.tokens / self.token_limit * 100)
        return round(max(pcts, default=0.0), 2)

    def to_dict(self) -> dict:
        return {"cost_eur": str(self.cost_eur), "tokens": self.tokens, "budget_eur": str(self.budget_eur),
                "token_limit": self.token_limit, "pct": self.pct}


def _usage(db: Session, column, scope_id: int) -> tuple[Decimal, int]:
    row = db.execute(
        select(func.coalesce(func.sum(LlmRequest.cost_eur), 0),
               func.coalesce(func.sum(LlmRequest.input_tokens + LlmRequest.output_tokens), 0))
        .where(column == scope_id, LlmRequest.created_at >= month_start())
    ).one()
    return Decimal(row[0]), int(row[1])


def user_usage(db: Session, user: User) -> Usage:
    cost, tokens = _usage(db, LlmRequest.user_id, user.id)
    return Usage(cost, tokens, user.monthly_budget_eur, user.monthly_token_limit)


def department_usage(db: Session, dept: Department) -> Usage:
    cost, tokens = _usage(db, LlmRequest.department_id, dept.id)
    return Usage(cost, tokens, dept.monthly_budget_eur, dept.monthly_token_limit)


class QuotaExceeded(Exception):
    def __init__(self, scope: str, message: str):
        super().__init__(message)
        self.scope = scope
        self.message = message


def _would_exceed(u: Usage, est_cost: Decimal, est_tokens: int) -> bool:
    if u.budget_eur is not None and u.cost_eur + est_cost > u.budget_eur:
        return True
    if u.token_limit is not None and u.tokens + est_tokens > u.token_limit:
        return True
    return False


def check_before(db: Session, user: User, est_cost: Decimal, est_tokens: int) -> None:
    """Lève QuotaExceeded si la requête estimée ferait dépasser 100 % d'un quota."""
    if _would_exceed(user_usage(db, user), est_cost, est_tokens):
        raise QuotaExceeded("user", "Votre quota mensuel est atteint. Contactez votre manager pour l'ajuster.")
    if _would_exceed(department_usage(db, user.department), est_cost, est_tokens):
        raise QuotaExceeded("department", "Le budget mensuel de votre département est atteint.")


def record_thresholds(db: Session, user: User, request_id: str | None, thresholds: list[int]) -> list[dict]:
    """Après l'appel : signale les seuils nouvellement franchis (une fois par mois et par seuil)."""
    period = month_start().strftime("%Y-%m")
    alerts: list[dict] = []
    for scope, scope_id, usage in (
        ("user", user.id, user_usage(db, user)),
        ("department", user.department_id, department_usage(db, user.department)),
    ):
        for threshold in sorted({*thresholds, 100}):
            if usage.pct < threshold:
                continue
            inserted = db.execute(
                insert(QuotaAlert)
                .values(scope=scope, scope_id=scope_id, period=period, threshold=threshold)
                .on_conflict_do_nothing()
                .returning(QuotaAlert.id)
            ).scalar()
            if inserted is None:
                continue  # déjà signalé ce mois-ci
            audit_service.log_event(
                db, "QUOTA_THRESHOLD", category="quota",
                severity=Severity.CRITICAL if threshold >= 100 else Severity.WARNING,
                status="ALERT", user_id=user.id, request_id=request_id,
                details={"scope": scope, "scope_id": scope_id, "threshold": threshold, "pct": usage.pct},
            )
            alerts.append({"scope": scope, "threshold": threshold, "pct": usage.pct})
    return alerts

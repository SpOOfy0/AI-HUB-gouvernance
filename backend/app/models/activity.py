from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Niveau le plus haut atteint : ne redescend jamais (une conversation CONFIDENTIAL le reste).
    max_classification: Mapped[str] = mapped_column(String(20), default="PUBLIC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", cascade="all, delete-orphan"
    )


class Message(Base):
    """Contenu des échanges : stocké uniquement pour les requêtes ALLOW et PRIVATE_ONLY."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Métadonnées de routage (sans contenu) pour réafficher le panneau sous la réponse.
    routing: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class LlmRequest(Base):
    """Une ligne par requête passée par la passerelle. Métadonnées uniquement, jamais de contenu."""

    __tablename__ = "llm_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    app: Mapped[str] = mapped_column(String(20))
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification: Mapped[str] = mapped_column(String(20))
    detections: Mapped[list] = mapped_column(JSON, default=list)  # [{type, level, count}] - jamais la valeur
    decision: Mapped[str] = mapped_column(String(20))
    routing_reason: Mapped[str] = mapped_column(String(500))
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mode: Mapped[str] = mapped_column(String(10), default="auto")  # auto | manual
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    hosting: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tokens_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_eur: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)  # NULL = coût non disponible
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # SUCCESS | BLOCKED | REFUSED | ERROR
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class QuotaAlert(Base):
    """Seuils (70/90/100 %) déjà signalés pour une période : évite d'alerter en boucle."""

    __tablename__ = "quota_alerts"
    __table_args__ = (UniqueConstraint("scope", "scope_id", "period", "threshold"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(20))  # user | department
    scope_id: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    threshold: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    """Journal d'audit append-only (trigger PostgreSQL) et chaîné par hash."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # auth | ai | security | quota | config | admin
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

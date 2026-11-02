"""Politique de classification modifiable par un ADMIN (stockée en base)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PolicySetting(Base):
    """Paramètres clé/valeur : mapping détection→niveau, seuils de complexité, rétention..."""

    __tablename__ = "policy_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LexiconTerm(Base):
    """Terme du lexique métier : nom de client, expression commerciale, format d'identifiant."""

    __tablename__ = "dlp_lexicon_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50))  # client | commercial | internal_id | site | procedure
    level: Mapped[str] = mapped_column(String(20))
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

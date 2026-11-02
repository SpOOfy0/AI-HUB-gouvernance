"""Catalogue fournisseurs / modèles / prix.

Ajouter un modèle = ajouter une ligne dans `models` (+ son prix). Aucun code à modifier.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(30))  # openai | anthropic | deepseek | ollama
    # Nom de la variable d'environnement qui porte la clé. La clé elle-même n'est jamais en base.
    api_key_env_var: Mapped[str | None] = mapped_column(String(100), nullable=True)

    models: Mapped[list["LlmModel"]] = relationship(back_populates="provider")


class LlmModel(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    display_name: Mapped[str] = mapped_column(String(100))
    litellm_name: Mapped[str] = mapped_column(String(150), unique=True)
    hosting: Mapped[str] = mapped_column(String(20))  # EXTERNAL | PRIVATE
    max_classification: Mapped[str] = mapped_column(String(20))  # niveau maximal autorisé
    tier: Mapped[str] = mapped_column(String(20))  # eco | standard | premium
    # Rôles autorisés à utiliser ce modèle (liste de chaînes).
    allowed_roles: Mapped[list[str]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    provider: Mapped[Provider] = relationship(back_populates="models", lazy="joined")
    price: Mapped["ModelPrice | None"] = relationship(back_populates="model", uselist=False, lazy="joined")


class ModelPrice(Base):
    __tablename__ = "model_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"), unique=True)
    input_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    output_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    source: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    model: Mapped[LlmModel] = relationship(back_populates="price")

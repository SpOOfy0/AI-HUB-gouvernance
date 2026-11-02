from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    monthly_budget_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Plafond fixé par l'ADMIN : un MANAGER ne peut pas donner plus que ce budget à un membre.
    manager_quota_cap_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("50"))

    users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # app.core.enums.Role
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    monthly_budget_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    department: Mapped[Department] = relationship(back_populates="users")

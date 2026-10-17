"""Financing and sandbox models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.organization import IdMixin, TimestampMixin, OrgMixin


def generate_uuid() -> str:
    return str(uuid.uuid4())


class FinancingProduct(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "financing_products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    countries: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_amount: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(nullable=True)
    nominal_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    upfront_fee_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    fixed_fee: Mapped[Optional[float]] = mapped_column(nullable=True)
    tenor_months: Mapped[Optional[int]] = mapped_column(nullable=True)
    funding_days: Mapped[int] = mapped_column(default=7)
    min_trading_months: Mapped[int] = mapped_column(default=0)
    min_monthly_revenue: Mapped[Optional[float]] = mapped_column(nullable=True)
    required_documents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_example: Mapped[bool] = mapped_column(default=True)


class ProposedAction(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "proposed_actions"

    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    arguments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    proposed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    decided_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    autonomy_level_required: Mapped[int] = mapped_column(default=2)


class SandboxPayment(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "sandbox_payments"

    action_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SandboxApplication(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "sandbox_applications"

    action_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

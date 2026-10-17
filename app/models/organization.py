"""Organization, user and membership models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)


class OrgMixin:
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-US")
    fiscal_year_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    default_tax_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    tax_label: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    default_payment_terms_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    default_receipt_delay_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    autonomy_level: Mapped[int] = mapped_column(default=2)
    action_limit: Mapped[Optional[float]] = mapped_column(nullable=True)
    second_approver_threshold: Mapped[Optional[float]] = mapped_column(nullable=True)
    approval_expiry_hours: Mapped[int] = mapped_column(default=72)
    demo_loaded: Mapped[bool] = mapped_column(default=False)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_guest: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )


class Membership(Base, IdMixin, TimestampMixin):
    __tablename__ = "memberships"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")

    __table_args__ = (UniqueConstraint("user_id", "org_id", name="ix_memberships_user_org"),)

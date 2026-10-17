"""Security, session, job and audit models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.organization import IdMixin, TimestampMixin


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Session(Base, IdMixin):
    __tablename__ = "sessions"

    id_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class RateLimit(Base, IdMixin):
    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (Index("ix_rate_limits_key_window", "key", "window_start"),)


class Job(Base, IdMixin, TimestampMixin):
    __tablename__ = "jobs"

    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditEvent(Base, IdMixin):
    __tablename__ = "audit_events"

    org_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    seq: Mapped[int] = mapped_column(nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_audit_events_org_timestamp", "org_id", "ts"),
    )


class FxRate(Base, IdMixin):
    __tablename__ = "fx_rates"

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    base: Mapped[str] = mapped_column(String(3), nullable=False)
    quote: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_fx_rates_pair_date", "base", "quote", "date"),)


class SupportTicket(Base, IdMixin, TimestampMixin):
    __tablename__ = "support_tickets"

    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    screenshot_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    org_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

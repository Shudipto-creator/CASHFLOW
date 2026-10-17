"""Alert models."""

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


class AlertRule(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "alert_rules"

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class Alert(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "alerts"

    rule_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

"""Forecast, scenario and goal models."""

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


class ForecastRun(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "forecast_runs"

    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Scenario(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)


class Goal(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "goals"

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[float] = mapped_column(nullable=False)
    current_value: Mapped[float] = mapped_column(default=0)

"""Chat, message and artifact models."""

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


class ChatThread(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "chat_threads"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")


class ChatMessage(Base, IdMixin, TimestampMixin):
    __tablename__ = "chat_messages"

    thread_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class Artifact(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "artifacts"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="answer")

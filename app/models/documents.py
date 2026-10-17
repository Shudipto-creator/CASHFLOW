"""Document and import models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.organization import IdMixin, TimestampMixin, OrgMixin


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    extracted_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ImportBatch(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "import_batches"

    account_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    undone_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

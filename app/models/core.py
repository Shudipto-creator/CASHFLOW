"""Core money models: accounts, transactions, counterparties, invoices, loans, recurring items."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.organization import IdMixin, TimestampMixin, OrgMixin


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Account(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    opening_balance: Mapped[float] = mapped_column(default=0)
    opening_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Transaction(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "transactions"

    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    base_amount: Mapped[float] = mapped_column(nullable=False)
    fx_rate_used: Mapped[Optional[float]] = mapped_column(nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    import_batch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    dedupe_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    __table_args__ = (Index("ix_transactions_org_date", "org_id", "date"),)


class Counterparty(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "counterparties"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    payment_details_encrypted: Mapped[Optional[str]] = mapped_column(nullable=True)
    avg_delay_days: Mapped[int] = mapped_column(default=0)


class Invoice(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "invoices"

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    counterparty_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    discount_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    discount_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (Index("ix_invoices_org_status", "org_id", "status"),)


class Loan(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "loans"

    lender: Mapped[str] = mapped_column(String(255), nullable=False)
    balance: Mapped[float] = mapped_column(nullable=False)
    rate: Mapped[float] = mapped_column(default=0)
    monthly_payment: Mapped[float] = mapped_column(nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class RecurringItem(Base, IdMixin, TimestampMixin, OrgMixin):
    __tablename__ = "recurring_items"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    cadence: Mapped[str] = mapped_column(String(32), nullable=False)
    next_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

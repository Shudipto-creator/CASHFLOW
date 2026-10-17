"""Database models for CASHFLOW."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.utcnow()


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-US")
    fiscal_year_start: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)  # MM-DD
    tax_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    filing_due_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # day of month
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="organization", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="organization", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="organization", cascade="all, delete-orphan")
    counterparts = relationship("Counterparty", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    forecast_runs = relationship("ForecastRun", back_populates="organization", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="organization", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="organization", cascade="all, delete-orphan")
    financing_products = relationship("FinancingProduct", back_populates="organization", cascade="all, delete-orphan")
    financing_recommendations = relationship(
        "FinancingRecommendation", back_populates="organization", cascade="all, delete-orphan"
    )
    proposed_actions = relationship("ProposedAction", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="organization", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="organization", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="organization", cascade="all, delete-orphan")
    support_tickets = relationship("SupportTicket", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization = relationship("Organization", back_populates="users")
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="user")
    artifacts = relationship("Artifact", back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")

    __table_args__ = ()


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")  # owner, finance, viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

    __table_args__ = (Index("ix_memberships_user_org", "user_id", "org_id", unique=True),)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # bank, cash, card, loan
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    opening_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)  # in original currency
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    base_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)  # in base currency
    fx_rate_used: Mapped[Optional[float]] = mapped_column(Numeric(18, 8), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    dedupe_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

    __table_args__ = (Index("ix_transactions_org_date", "org_id", "date"),)


class Counterparty(Base):
    __tablename__ = "counterparties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    saved_payment_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    average_payment_delay_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="counterparts")
    invoices = relationship("Invoice", back_populates="cp")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    counterparty_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # receivable or payable
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False)  # denormalized name
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")  # open, paid, overdue, void
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="invoices")
    cp = relationship("Counterparty", back_populates="invoices")

    __table_args__ = (Index("ix_invoices_org_status", "org_id", "status"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # invoice, bank_statement, financial_report, contract, other
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")  # uploaded, extracting, review, processed, quarantined, error
    doc_metadata: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON text
    injection_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="documents")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    data_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    organization = relationship("Organization", back_populates="forecast_runs")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="alert_rules")
    alerts = relationship("Alert", back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open, acknowledged, resolved
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="alerts")
    rule = relationship("AlertRule", back_populates="alerts")


class FinancingProduct(Base):
    __tablename__ = "financing_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # working_capital_loan, revolving_credit_line, invoice_financing, supplier_early_payment_discount, overdraft
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    min_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    min_months_history: Mapped[int] = mapped_column(Integer, default=0)
    min_monthly_revenue: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    required_documents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    rate_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # fixed, flat
    rate_value: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)  # percent
    fee_value: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    fee_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # flat, percent_of_amount
    funding_time_days: Mapped[int] = mapped_column(Integer, default=7)
    is_example: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="financing_products")
    recommendations = relationship("FinancingRecommendation", back_populates="product")


class FinancingRecommendation(Base):
    __tablename__ = "financing_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    requested_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    requested_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("financing_products.id", ondelete="CASCADE"), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    effective_annual_rate: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    funding_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eligible_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eligibility_fix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="financing_recommendations")
    product = relationship("FinancingProduct", back_populates="recommendations")


class ProposedAction(Base):
    __tablename__ = "proposed_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)  # read, draft, execute
    input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending, approved, rejected, executed
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)  # agent name
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # user id
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_document_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    autonomy_level_required: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="proposed_actions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    organization = relationship("Organization", back_populates="audit_events")

    __table_args__ = (Index("ix_audit_events_org_timestamp", "org_id", "timestamp"),)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)  # min_cash_target, runway_target_months, receivable_days_target
    target_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization = relationship("Organization", back_populates="goals")


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization = relationship("Organization", back_populates="chat_threads")
    user = relationship("User", back_populates="chat_threads")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("ChatThread", back_populates="messages")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="answer")  # answer, lender_pack, scenario
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="artifacts")
    user = relationship("User", back_populates="artifacts")


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(18, 10), nullable=False)
    rate_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_fx_rates_pair_date", "base_currency", "target_currency", "rate_date"),)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reference: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="support_tickets")
    user = relationship("User", back_populates="support_tickets")

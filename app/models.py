"""Database models for CASHFLOW"""

from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


def generate_uuid():
    """Generate UUID string"""
    return str(uuid.uuid4())


class User(Base):
    """User account model"""

    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    business_type = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Document(Base):
    """Document model"""

    __tablename__ = "documents"

    document_id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=True, index=True)
    file_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed = Column(Boolean, default=False, nullable=False)
    doc_metadata = Column(JSON, nullable=True)


class Analysis(Base):
    """Analysis model"""

    __tablename__ = "analyses"

    analysis_id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # processing/completed/failed
    processing_mode = Column(String(20), nullable=True, default="aws")  # aws | local
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


class AnalysisDocument(Base):
    """Many-to-many relationship between analyses and documents"""

    __tablename__ = "analysis_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(36), ForeignKey("analyses.analysis_id"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.document_id"), nullable=False, index=True)


class AgentResult(Base):
    """Agent execution results"""

    __tablename__ = "agent_results"

    result_id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.analysis_id"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False, index=True)
    result_data = Column(JSON, nullable=False)
    execution_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    """Final report model"""

    __tablename__ = "reports"

    report_id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.analysis_id"), unique=True, nullable=False, index=True)
    report_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    """Persist AgentCFO messages for an analysis conversation."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(36), ForeignKey("analyses.analysis_id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="complete")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BillFlowImport(Base):
    """Imported bank CSV metadata for the BillFlow local ledger."""

    __tablename__ = "billflow_imports"

    import_id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    bank = Column(String(50), nullable=True)
    transaction_count = Column(Integer, nullable=False, default=0)
    date_range_start = Column(String(10), nullable=True)
    date_range_end = Column(String(10), nullable=True)
    import_metadata = Column(JSON, nullable=True)
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class BillFlowTransaction(Base):
    """Local bank ledger row — categorized and analyzed on-device by BillFlow."""

    __tablename__ = "billflow_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    import_id = Column(String(36), ForeignKey("billflow_imports.import_id"), nullable=True, index=True)
    date = Column(String(10), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=True, index=True)
    category_confidence = Column(Float, nullable=True)
    categorization_method = Column(String(20), nullable=True)
    bank = Column(String(50), nullable=True)
    source_file = Column(String(255), nullable=True)
    external_key = Column(String(512), nullable=True, index=True)
    is_recurring = Column(Boolean, default=False, nullable=False)
    user_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

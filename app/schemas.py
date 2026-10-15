"""Pydantic schemas for API request/response validation"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# Authentication Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    company_name: str = Field(..., min_length=2, max_length=100)
    business_type: Optional[str] = None

    @validator("password")
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    company_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


# Document Schemas
class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    document_type: Optional[str]
    size_bytes: int
    uploaded_at: datetime
    processed: bool

    class Config:
        from_attributes = True


class DocumentDetail(DocumentResponse):
    metadata: Optional[Dict[str, Any]] = Field(None, alias="doc_metadata")

    class Config:
        from_attributes = True
        populate_by_name = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    limit: int


class DocumentUploadResponse(BaseModel):
    document_ids: List[str]
    uploaded_count: int
    documents: List[DocumentResponse]


# Analysis Schemas
class AnalysisRequest(BaseModel):
    document_ids: Optional[List[str]] = None
    analysis_type: Optional[str] = "full"  # "full" or "quick"


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    estimated_completion: Optional[datetime] = None
    message: str


class AnalysisStatus(BaseModel):
    analysis_id: str
    user_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    document_count: int


class AnalysisListResponse(BaseModel):
    analyses: List[AnalysisStatus]
    total: int
    page: int
    limit: int


class ReportResponse(BaseModel):
    analysis_id: str
    user_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    report: Optional[Dict[str, Any]] = None


# Health Check Schema
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]


# Error Schema
class ErrorDetail(BaseModel):
    field: Optional[str] = None
    reason: Optional[str] = None


class ErrorResponse(BaseModel):
    error: Dict[str, Any]
    timestamp: datetime

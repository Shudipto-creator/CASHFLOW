"""Document endpoints for CASHFLOW."""

import os
import shutil
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf
from app.config import get_settings
from app.security import scan_injection

settings = get_settings()
logger = logging.getLogger("cashflow")

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED = {
    "pdf": ["application/pdf"],
    "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    "xls": ["application/vnd.ms-excel"],
    "csv": ["text/csv"],
}

MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


class DocumentResponse(BaseModel):
    id: str
    filename: str
    stored_name: str
    file_path: str
    size_bytes: int
    mime_type: str
    document_type: Optional[str]
    status: str
    injection_flagged: bool
    created_at: str

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(uploaded|extracting|review|processed|quarantined|error)$")


def _validate_and_store(file: UploadFile, org_id: str, user_id: str) -> dict:
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File type .{ext} not allowed")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    raw = file.file.read()
    file.file.seek(0)

    # Determine MIME from file magic bytes without external lib
    if raw[:4] == b"%PDF":
        mime = "application/pdf"
    elif raw[:4] == b"PK\x03\x04":
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif raw[:8] == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        mime = "application/vnd.ms-excel"
    else:
        mime = "application/octet-stream"

    allowed_mimes = ALLOWED[ext]
    if mime not in allowed_mimes and mime != "application/octet-stream":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"MIME type {mime} not allowed for .{ext}")

    stored_name = f"{uuid.uuid4().hex}_{filename}"
    org_dir = os.path.join(settings.upload_dir, org_id)
    os.makedirs(org_dir, exist_ok=True)
    file_path = os.path.join(org_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(raw)

    return {
        "filename": filename,
        "stored_name": stored_name,
        "file_path": file_path,
        "size_bytes": size,
        "mime_type": mime,
        "ext": ext,
    }


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    request: Request = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    info = _validate_and_store(file, user.organization_id, user.id)
    doc = models.Document(
        org_id=user.organization_id,
        user_id=user.id,
        filename=info["filename"],
        stored_name=info["stored_name"],
        file_path=info["file_path"],
        size_bytes=info["size_bytes"],
        mime_type=info["mime_type"],
        document_type=document_type,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Document).filter(models.Document.org_id == user.organization_id)
    if document_type:
        q = q.filter(models.Document.document_type == document_type)
    if status:
        q = q.filter(models.Document.status == status)
    return q.order_by(models.Document.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == user.organization_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: str,
    data: DocumentUpdate,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == user.organization_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == user.organization_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as exc:
        logger.warning("Failed to delete stored file: %s", exc)
    db.delete(doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

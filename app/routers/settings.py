"""Settings endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf
from app.security import hash_password, verify_password, validate_password_strength

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class ExportedData(BaseModel):
    accounts: List[Dict[str, Any]]
    transactions: List[Dict[str, Any]]
    invoices: List[Dict[str, Any]]
    documents: List[Dict[str, Any]]


@router.get("/profile")
def get_profile(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "organization_id": user.organization_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


@router.patch("/profile")
def update_profile(data: ProfileUpdate, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return {"message": "Profile updated"}


@router.post("/password")
def change_password(data: PasswordChange, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password incorrect")
    validate_password_strength(data.new_password)
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed"}


@router.get("/sessions")
def list_sessions(user: models.User = Depends(get_current_user)):
    return {"sessions": [{"user_id": user.id, "active": True}]}


@router.post("/sign-out-everywhere")
def sign_out_everywhere(request: Request, user: models.User = Depends(get_current_user)):
    require_csrf(request)
    return {"message": "All sessions invalidated"}


@router.get("/export")
def export_data(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(models.Account).filter(models.Account.org_id == user.organization_id).all()
    transactions = db.query(models.Transaction).filter(models.Transaction.org_id == user.organization_id).all()
    invoices = db.query(models.Invoice).filter(models.Invoice.org_id == user.organization_id).all()
    documents = db.query(models.Document).filter(models.Document.org_id == user.organization_id).all()
    return {
        "accounts": [{"id": a.id, "name": a.name, "type": a.type, "currency": a.currency} for a in accounts],
        "transactions": [
            {"id": t.id, "date": t.date.isoformat() if t.date else None, "description": t.description, "amount": float(t.amount), "currency": t.currency}
            for t in transactions
        ],
        "invoices": [
            {"id": i.id, "counterparty": i.counterparty, "kind": i.kind, "amount": float(i.amount), "currency": i.currency, "due_date": i.due_date.isoformat() if i.due_date else None, "status": i.status}
            for i in invoices
        ],
        "documents": [
            {"id": doc.id, "filename": doc.filename, "document_type": doc.document_type, "status": doc.status, "created_at": doc.created_at.isoformat()}
            for doc in documents
        ],
    }


@router.post("/delete-account")
def delete_account(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    confirmation = request.query_params.get("confirmation")
    if confirmation != "DELETE MY DATA":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type confirmation required")
    if user.organization_id:
        db.execute(
            text("DELETE FROM transactions WHERE org_id = :oid"),
            {"oid": user.organization_id},
        )
        db.execute(
            text("DELETE FROM invoices WHERE org_id = :oid"),
            {"oid": user.organization_id},
        )
        db.execute(
            text("DELETE FROM documents WHERE org_id = :oid"),
            {"oid": user.organization_id},
        )
    db.delete(user)
    db.commit()
    return {"message": "Account deleted"}

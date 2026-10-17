"""Invoice endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


class InvoiceBase(BaseModel):
    counterparty_id: Optional[str] = None
    counterparty: str = Field(..., min_length=1, max_length=255)
    kind: str = Field(..., pattern="^(receivable|payable)$")
    amount: float
    currency: str = Field(default="USD", min_length=3, max_length=3)
    issue_date: str
    due_date: str
    status: str = Field(default="open", pattern="^(open|paid|overdue|void)$")
    paid_date: Optional[str] = None
    source_document_id: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: str
    org_id: str
    counterparty_id: Optional[str]
    counterparty: str
    kind: str
    amount: float
    currency: str
    issue_date: str
    due_date: str
    status: str
    paid_date: Optional[str]
    source_document_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


def _parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format")


@router.get("", response_model=List[InvoiceResponse])
def list_invoices(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    kind: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Invoice).filter(models.Invoice.org_id == user.organization_id)
    if kind:
        q = q.filter(models.Invoice.kind == kind)
    if status:
        q = q.filter(models.Invoice.status == status)
    return q.order_by(models.Invoice.due_date.asc()).offset(offset).limit(limit).all()


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: InvoiceBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    inv = models.Invoice(
        org_id=user.organization_id,
        counterparty_id=data.counterparty_id,
        counterparty=data.counterparty,
        kind=data.kind,
        amount=data.amount,
        currency=data.currency,
        issue_date=_parse_date(data.issue_date),
        due_date=_parse_date(data.due_date),
        status=data.status,
        paid_date=_parse_date(data.paid_date) if data.paid_date else None,
        source_document_id=data.source_document_id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    data: InvoiceBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    inv = (
        db.query(models.Invoice)
        .filter(models.Invoice.id == invoice_id, models.Invoice.org_id == user.organization_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("issue_date", "due_date", "paid_date"):
            if value:
                value = _parse_date(value)
            else:
                value = None
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: str,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    inv = (
        db.query(models.Invoice)
        .filter(models.Invoice.id == invoice_id, models.Invoice.org_id == user.organization_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    db.delete(inv)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

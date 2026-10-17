"""Transaction endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf
from app.security import sha256_hex

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionBase(BaseModel):
    account_id: Optional[str] = None
    date: str
    description: str
    amount: float
    currency: str = Field(default="USD", min_length=3, max_length=3)
    category: Optional[str] = None
    source_document_id: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    org_id: str
    account_id: Optional[str]
    date: str
    description: str
    amount: float
    currency: str
    base_amount: float
    fx_rate_used: Optional[float]
    category: Optional[str]
    source_document_id: Optional[str]
    dedupe_hash: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Transaction).filter(models.Transaction.org_id == user.organization_id)
    return q.order_by(models.Transaction.date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    try:
        tx_date = datetime.fromisoformat(data.date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format")

    dedupe_hash = sha256_hex(
        f"{user.organization_id}|{tx_date.isoformat()}|{data.description}|{data.amount}|{data.currency}"
    )

    tx = models.Transaction(
        org_id=user.organization_id,
        account_id=data.account_id,
        date=tx_date,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        base_amount=data.amount,
        category=data.category,
        source_document_id=data.source_document_id,
        dedupe_hash=dedupe_hash,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.org_id == user.organization_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: str,
    data: TransactionBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.org_id == user.organization_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "date":
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format")
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.org_id == user.organization_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    db.delete(tx)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from fastapi import Response

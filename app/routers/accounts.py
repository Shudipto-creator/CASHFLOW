"""Account endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(bank|cash|card|loan)$")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    opening_balance: float = 0
    opening_date: Optional[str] = None


class AccountResponse(BaseModel):
    id: str
    org_id: str
    name: str
    type: str
    currency: str
    opening_balance: float
    opening_date: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


def _org_accounts(db: Session, org_id: str):
    return db.query(models.Account).filter(models.Account.org_id == org_id)


@router.get("", response_model=List[AccountResponse])
def list_accounts(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _org_accounts(db, user.organization_id).all()


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    acct = models.Account(
        org_id=user.organization_id,
        name=data.name,
        type=data.type,
        currency=data.currency,
        opening_balance=data.opening_balance,
        opening_date=data.opening_date,
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: str,
    data: AccountBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    acct = _org_accounts(db, user.organization_id).filter(models.Account.id == account_id).first()
    if not acct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(acct, field, value)
    db.commit()
    db.refresh(acct)
    return acct


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: str, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    acct = _org_accounts(db, user.organization_id).filter(models.Account.id == account_id).first()
    if not acct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    db.delete(acct)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

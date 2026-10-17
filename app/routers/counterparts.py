"""Counterparty endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/counterparties", tags=["counterparties"])


class CounterpartyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    saved_payment_details: Optional[str] = None
    average_payment_delay_days: int = Field(default=0, ge=0)


class CounterpartyResponse(BaseModel):
    id: str
    org_id: str
    name: str
    saved_payment_details: Optional[str]
    average_payment_delay_days: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[CounterpartyResponse])
def list_counterparties(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Counterparty).filter(models.Counterparty.org_id == user.organization_id)
    return q.order_by(models.Counterparty.name.asc()).offset(offset).limit(limit).all()


@router.post("", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
def create_counterparty(
    data: CounterpartyBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    cp = models.Counterparty(
        org_id=user.organization_id,
        name=data.name,
        saved_payment_details=data.saved_payment_details,
        average_payment_delay_days=data.average_payment_delay_days,
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.patch("/{counterparty_id}", response_model=CounterpartyResponse)
def update_counterparty(
    counterparty_id: str,
    data: CounterpartyBase,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    cp = (
        db.query(models.Counterparty)
        .filter(models.Counterparty.id == counterparty_id, models.Counterparty.org_id == user.organization_id)
        .first()
    )
    if not cp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cp, field, value)
    db.commit()
    db.refresh(cp)
    return cp


@router.delete("/{counterparty_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_counterparty(
    counterparty_id: str,
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    cp = (
        db.query(models.Counterparty)
        .filter(models.Counterparty.id == counterparty_id, models.Counterparty.org_id == user.organization_id)
        .first()
    )
    if not cp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty not found")
    db.delete(cp)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

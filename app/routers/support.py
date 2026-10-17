"""Support endpoints for CASHFLOW."""

import itertools
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/support", tags=["support"])

_reference_counter = itertools.count(1000)


class SupportTicketRequest(BaseModel):
    subject: str
    message: str


class SupportTicketResponse(BaseModel):
    id: str
    reference: str
    subject: str
    message: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: SupportTicketRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = f"CF-{next(_reference_counter)}"
    ticket = models.SupportTicket(
        org_id=user.organization_id,
        user_id=user.id,
        subject=data.subject,
        message=data.message,
        status="open",
        reference=ref,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=List[SupportTicketResponse])
def list_tickets(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.SupportTicket)
        .filter(models.SupportTicket.user_id == user.id)
        .order_by(models.SupportTicket.created_at.desc())
        .all()
    )

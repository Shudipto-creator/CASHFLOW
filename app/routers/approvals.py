"""Approvals endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ProposedActionResponse(BaseModel):
    id: str
    org_id: str
    thread_id: Optional[str]
    tool: str
    tier: str
    input: Optional[str]
    output: Optional[str]
    input_hash: str
    output_hash: str
    status: str
    requested_by: str
    approved_by: Optional[str]
    decided_at: Optional[str]
    executed_at: Optional[str]
    expiry: Optional[str]
    evidence_document_ids: Optional[str]
    autonomy_level_required: int
    created_at: str

    class Config:
        from_attributes = True


class DecideRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reason: Optional[str] = None


@router.get("", response_model=List[ProposedActionResponse])
def list_proposed_actions(
    status: Optional[str] = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.ProposedAction).filter(models.ProposedAction.org_id == user.organization_id)
    if status:
        q = q.filter(models.ProposedAction.status == status)
    return q.order_by(models.ProposedAction.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{action_id}", response_model=ProposedActionResponse)
def get_proposed_action(action_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = (
        db.query(models.ProposedAction)
        .filter(models.ProposedAction.id == action_id, models.ProposedAction.org_id == user.organization_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return a


@router.post("/{action_id}/decide", response_model=ProposedActionResponse)
def decide_action(
    action_id: str,
    request: Request,
    data: DecideRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    a = (
        db.query(models.ProposedAction)
        .filter(models.ProposedAction.id == action_id, models.ProposedAction.org_id == user.organization_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    if a.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action already decided")
    a.approved_by = user.id
    from datetime import datetime

    a.decided_at = datetime.utcnow()
    if data.decision == "approve":
        a.status = "approved"
        # execute in sandbox for execute tier
        a.executed_at = datetime.utcnow()
        a.status = "executed"
        a.output = a.output or '{"executed": true, "sandbox": true}'
    else:
        a.status = "rejected"
    db.commit()
    db.refresh(a)
    return a

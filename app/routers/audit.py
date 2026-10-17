"""Audit log endpoints for CASHFLOW."""

import hashlib
import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.dependencies import get_current_user
from app.security import sha256_hex

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: str
    org_id: Optional[str]
    timestamp: str
    actor: str
    action: str
    input_hash: str
    output_hash: str
    prev_hash: str
    hash: str

    class Config:
        from_attributes = True


class VerifyResponse(BaseModel):
    passed: bool
    checked: int
    first_broken: Optional[int]


class AgentSendRequest(BaseModel):
    pass


@router.get("", response_model=List[AuditEventResponse])
def list_audit(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    actor: Optional[str] = None,
    action: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    q = db.query(models.AuditEvent).filter(models.AuditEvent.org_id == user.organization_id)
    if actor:
        q = q.filter(models.AuditEvent.actor.like(f"%{actor}%"))
    if action:
        q = q.filter(models.AuditEvent.action.like(f"%{action}%"))
    if start:
        q = q.filter(models.AuditEvent.timestamp >= datetime.fromisoformat(start))
    if end:
        q = q.filter(models.AuditEvent.timestamp <= datetime.fromisoformat(end))
    return q.order_by(models.AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()


@router.post("/verify", response_model=VerifyResponse)
def verify_audit(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = (
        db.query(models.AuditEvent)
        .filter(models.AuditEvent.org_id == user.organization_id)
        .order_by(models.AuditEvent.timestamp.asc())
        .all()
    )
    prev_hash = "0" * 64
    for idx, ev in enumerate(events):
        computed = sha256_hex(
            f"{ev.id}{ev.timestamp.isoformat() if ev.timestamp else ''}{ev.actor}{ev.action}{ev.input_hash}{ev.output_hash}{prev_hash}"
        )
        if ev.prev_hash != prev_hash:
            return VerifyResponse(passed=False, checked=idx, first_broken=idx)
        if ev.hash != computed:
            return VerifyResponse(passed=False, checked=idx, first_broken=idx)
        prev_hash = ev.hash
    return VerifyResponse(passed=True, checked=len(events), first_broken=None)


def append_audit(db, org_id, actor, action, input_hash, output_hash, prev_hash=None):
    if prev_hash is None:
        last = (
            db.query(models.AuditEvent)
            .filter(models.AuditEvent.org_id == org_id)
            .order_by(models.AuditEvent.timestamp.desc())
            .first()
        )
        prev_hash = last.hash if (last and last.hash) else "0" * 64
    hash_value = sha256_hex(f"{actor}{action}{input_hash}{output_hash}{prev_hash}")
    ev = models.AuditEvent(
        org_id=org_id,
        actor=actor,
        action=action,
        input_hash=input_hash,
        output_hash=output_hash,
        prev_hash=prev_hash,
        hash=hash_value,
    )
    db.add(ev)
    db.commit()
    return ev

from fastapi import Request, Response
from pydantic import BaseModel

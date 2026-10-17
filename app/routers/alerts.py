"""Alert endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str
    params: Optional[str] = None
    enabled: bool = True


class AlertRuleResponse(BaseModel):
    id: str
    org_id: str
    name: str
    type: str
    params: Optional[str]
    enabled: bool
    created_at: str

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: str
    org_id: str
    rule_id: Optional[str]
    type: str
    severity: str
    status: str
    message: str
    data: Optional[str]
    created_at: str
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    status: str = Field(..., pattern="^(acknowledged|resolved)$")


@router.get("/rules", response_model=List[AlertRuleResponse])
def list_rules(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.AlertRule).filter(models.AlertRule.org_id == user.organization_id).all()


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(data: AlertRuleBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    rule = models.AlertRule(
        org_id=user.organization_id,
        name=data.name,
        type=data.type,
        params=data.params,
        enabled=data.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
def update_rule(rule_id: str, data: AlertRuleBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    rule = (
        db.query(models.AlertRule)
        .filter(models.AlertRule.id == rule_id, models.AlertRule.org_id == user.organization_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: str, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    rule = (
        db.query(models.AlertRule)
        .filter(models.AlertRule.id == rule_id, models.AlertRule.org_id == user.organization_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Alert).filter(models.Alert.org_id == user.organization_id)
    if status:
        q = q.filter(models.Alert.status == status)
    if severity:
        q = q.filter(models.Alert.severity == severity)
    return q.order_by(models.Alert.created_at.desc()).offset(offset).limit(limit).all()


@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert(alert_id: str, data: AlertAcknowledge, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    alert = (
        db.query(models.Alert)
        .filter(models.Alert.id == alert_id, models.Alert.org_id == user.organization_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = data.status
    from datetime import datetime
    if data.status == "acknowledged" and not alert.acknowledged_at:
        alert.acknowledged_at = datetime.utcnow()
    if data.status == "resolved":
        alert.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return alert

from fastapi import Response

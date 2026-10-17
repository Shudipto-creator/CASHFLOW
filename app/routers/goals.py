"""Goal endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalBase(BaseModel):
    kind: str = Field(..., pattern="^(min_cash_target|runway_target_months|receivable_days_target)$")
    target_value: float
    current_value: float = 0


class GoalResponse(BaseModel):
    id: str
    org_id: str
    kind: str
    target_value: float
    current_value: float
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[GoalResponse])
def list_goals(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Goal).filter(models.Goal.org_id == user.organization_id).all()


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    goal = models.Goal(org_id=user.organization_id, kind=data.kind, target_value=data.target_value, current_value=data.current_value)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: str, data: GoalBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    g = (
        db.query(models.Goal)
        .filter(models.Goal.id == goal_id, models.Goal.org_id == user.organization_id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(g, field, value)
    db.commit()
    db.refresh(g)
    return g


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: str, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    g = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.org_id == user.organization_id).first()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    db.delete(g)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

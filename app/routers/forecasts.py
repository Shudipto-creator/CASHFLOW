"""Forecast endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


class ForecastRequest(BaseModel):
    weeks: int = Field(default=13, ge=1, le=52)
    min_cash_target: Optional[float] = None


class WeeklyPoint(BaseModel):
    week: str
    base: float
    low: float
    high: float


class ForecastResponse(BaseModel):
    id: str
    org_id: str
    weeks: int
    base_currency: str
    min_cash_target: Optional[float]
    runway_weeks: Optional[float]
    first_shortfall_week: Optional[str]
    weekly: List[WeeklyPoint]
    created_at: str


@router.post("/run", response_model=ForecastResponse)
def run_forecast(
    data: ForecastRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.forecast_engine import run_forecast as compute

    result = compute(db, user.organization_id, weeks=data.weeks, min_cash_target=data.min_cash_target)
    run = models.ForecastRun(
        org_id=user.organization_id,
        base_currency=user.organization.base_currency if user.organization else "USD",
        data_snapshot=result.get("snapshot"),
        results=result.get("results_json"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return ForecastResponse(
        id=run.id,
        org_id=run.org_id,
        weeks=data.weeks,
        base_currency=run.base_currency,
        min_cash_target=data.min_cash_target,
        runway_weeks=result.get("runway_weeks"),
        first_shortfall_week=result.get("first_shortfall_week"),
        weekly=result.get("weekly", []),
        created_at=run.created_at.isoformat(),
    )


@router.get("", response_model=List[ForecastResponse])
def list_forecasts(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 10,
    offset: int = 0,
):
    q = db.query(models.ForecastRun).filter(models.ForecastRun.org_id == user.organization_id)
    return q.order_by(models.ForecastRun.created_at.desc()).offset(offset).limit(limit).all()

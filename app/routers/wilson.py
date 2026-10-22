"""Wilson local ledger & billing API — privacy-first bank CSV analysis."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app import models
from app.services.wilson import WilsonEngine
from app.services.wilson.categories import WILSON_CATEGORIES, CATEGORY_DESCRIPTIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wilson", tags=["wilson"])

ALLOWED_CSV = {".csv", ".txt"}


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    user_verified: Optional[bool] = None
    is_recurring: Optional[bool] = None


class AnomalyRequest(BaseModel):
    types: Optional[List[str]] = Field(
        default=None,
        description="duplicates | spikes | forgotten_subscriptions | all",
    )


class MoneyGoneRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _engine(db: Session, user: models.User) -> WilsonEngine:
    return WilsonEngine(db, user.user_id)


@router.get("/categories")
async def list_categories(current_user: models.User = Depends(get_current_user)):
    return {
        "categories": WILSON_CATEGORIES,
        "descriptions": CATEGORY_DESCRIPTIONS,
    }


@router.get("/overview")
async def wilson_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _engine(db, current_user).overview()


@router.post("/import")
async def import_bank_csv(
    file: UploadFile = File(...),
    auto_categorize: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filename = file.filename or "statement.csv"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_CSV:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV bank statements are supported (.csv)",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        result = _engine(db, current_user).import_csv(
            content, filename=filename, auto_categorize=auto_categorize
        )
    except Exception as exc:
        logger.exception("Wilson CSV import failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse bank CSV: {exc}",
        ) from exc

    return result


@router.get("/transactions")
async def list_transactions(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    uncategorized_only: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _engine(db, current_user).list_transactions(
        category=category,
        start_date=start_date,
        end_date=end_date,
        search=search,
        uncategorized_only=uncategorized_only,
        limit=limit,
        offset=offset,
    )


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    body: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        updated = _engine(db, current_user).update_transaction(
            transaction_id,
            category=body.category,
            user_verified=body.user_verified,
            is_recurring=body.is_recurring,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return updated


@router.post("/categorize")
async def categorize_ledger(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _engine(db, current_user).categorize_uncategorized()


@router.post("/anomalies")
async def run_anomalies(
    body: AnomalyRequest = AnomalyRequest(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _engine(db, current_user).anomalies(types=body.types)


@router.get("/summary")
async def spending_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = Query("category", pattern="^(category|merchant)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _engine(db, current_user).summary(
        start_date=start_date, end_date=end_date, group_by=group_by
    )


@router.post("/ask")
async def where_did_my_money_go(
    body: MoneyGoneRequest = MoneyGoneRequest(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Structured answer for billing / 'where did my money go?' demos."""
    return _engine(db, current_user).where_did_my_money_go(
        start_date=body.start_date, end_date=body.end_date
    )

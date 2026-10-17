"""Financing endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal, ROUND_HALF_UP

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/api/financing", tags=["financing"])


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str
    country: Optional[str] = None
    currency: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    min_months_history: int = 0
    min_monthly_revenue: Optional[float] = None
    required_documents: Optional[str] = None
    rate_type: Optional[str] = None
    rate_value: Optional[float] = None
    fee_value: Optional[float] = None
    fee_type: Optional[str] = None
    funding_time_days: int = 7
    is_example: bool = True


class ProductResponse(BaseModel):
    id: str
    org_id: Optional[str]
    name: str
    type: str
    country: Optional[str]
    currency: Optional[str]
    min_amount: Optional[float]
    max_amount: Optional[float]
    min_months_history: int
    min_monthly_revenue: Optional[float]
    required_documents: Optional[str]
    rate_type: Optional[str]
    rate_value: Optional[float]
    fee_value: Optional[float]
    fee_type: Optional[str]
    funding_time_days: int
    is_example: bool
    created_at: str

    class Config:
        from_attributes = True


class RecommendationRequest(BaseModel):
    amount: float = Field(..., gt=0)
    needed_by_date: str
    purpose: str


class RecommendationResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    total_cost: float
    effective_annual_rate: float
    funding_time_days: int
    eligible: bool
    eligible_reason: Optional[str]
    eligibility_fix: Optional[str]
    rank: int


@router.get("/products", response_model=List[ProductResponse])
def list_products(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_examples: bool = True,
):
    q = db.query(models.FinancingProduct)
    if not include_examples:
        q = q.filter(models.FinancingProduct.is_example == False)  # noqa: E712
    if user.organization_id:
        q = q.filter(
            (models.FinancingProduct.org_id == user.organization_id)
            | (models.FinancingProduct.org_id.is_(None))
        )
    return q.order_by(models.FinancingProduct.name.asc()).all()


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    product = models.FinancingProduct(
        org_id=user.organization_id,
        name=data.name,
        type=data.type,
        country=data.country,
        currency=data.currency,
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        min_months_history=data.min_months_history,
        min_monthly_revenue=data.min_monthly_revenue,
        required_documents=data.required_documents,
        rate_type=data.rate_type,
        rate_value=data.rate_value,
        fee_value=data.fee_value,
        fee_type=data.fee_type,
        funding_time_days=data.funding_time_days,
        is_example=data.is_example,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: str, data: ProductBase, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    product = (
        db.query(models.FinancingProduct)
        .filter(models.FinancingProduct.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.org_id and product.org_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    product = db.query(models.FinancingProduct).filter(models.FinancingProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.org_id and product.org_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _money(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rate(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


@router.post("/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(
    data: RecommendationRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(models.Organization).filter(models.Organization.id == user.organization_id).first()
    base_currency = org.base_currency if org else "USD"

    products = db.query(models.FinancingProduct).all()
    results = []

    # org metrics
    from app.forecast_engine import org_history
    months_history, monthly_revenue = org_history(db, user.organization_id)

    for p in products:
        eligible = True
        reasons = []
        fixes = []

        # currency
        if p.currency and p.currency != base_currency:
            eligible = False
            reasons.append(f"currency mismatch: product supports {p.currency}, org base is {base_currency}")
            fixes.append(f"add a {base_currency} version of this product")
        # amount range
        if p.min_amount is not None and data.amount < p.min_amount:
            eligible = False
            reasons.append(f"amount below minimum {p.min_amount}")
            fixes.append(f"request at least {p.min_amount}")
        if p.max_amount is not None and data.amount > p.max_amount:
            eligible = False
            reasons.append(f"amount above maximum {p.max_amount}")
            fixes.append(f"request at most {p.max_amount}")
        # history
        if months_history < p.min_months_history:
            eligible = False
            reasons.append(f"needs {p.min_months_history} months of history, has {months_history}")
            fixes.append(f"needs {p.min_months_history - months_history} more months of history")
        # revenue
        if p.min_monthly_revenue is not None and monthly_revenue < p.min_monthly_revenue:
            eligible = False
            reasons.append(f"monthly revenue {monthly_revenue:.2f} below required {p.min_monthly_revenue}")
            fixes.append(f"needs monthly revenue of {p.min_monthly_revenue:.2f}")

        # cost calc
        rate = p.rate_value or 0
        fee = p.fee_value or 0
        if p.fee_type == "percent_of_amount":
            fee_total = data.amount * fee / 100
        else:
            fee_total = fee
        interest_total = data.amount * rate / 100 * (p.funding_time_days / 365)
        total_cost = _money(interest_total + fee_total)
        ear = _rate((total_cost / data.amount) * (365 / max(p.funding_time_days, 1)) * 100) if data.amount else 0

        results.append({
            "product": p,
            "total_cost": total_cost,
            "effective_annual_rate": ear,
            "funding_time_days": p.funding_time_days,
            "eligible": eligible,
            "eligible_reason": "; ".join(reasons) if reasons else None,
            "eligibility_fix": "; ".join(fixes) if fixes else None,
        })

    results.sort(key=lambda r: (not r["eligible"], r["total_cost"], r["effective_annual_rate"]))
    out = []
    for idx, r in enumerate(results, start=1):
        rec = models.FinancingRecommendation(
            org_id=user.organization_id,
            requested_amount=data.amount,
            requested_date=datetime.fromisoformat(data.needed_by_date),
            purpose=data.purpose,
            product_id=r["product"].id,
            total_cost=r["total_cost"],
            effective_annual_rate=r["effective_annual_rate"],
            funding_time_days=r["funding_time_days"],
            eligible=r["eligible"],
            eligible_reason=r["eligible_reason"],
            eligibility_fix=r["eligibility_fix"],
            rank=idx,
        )
        db.add(rec)
        db.flush()
        out.append(
            RecommendationResponse(
                id=rec.id,
                product_id=r["product"].id,
                product_name=r["product"].name,
                total_cost=r["total_cost"],
                effective_annual_rate=r["effective_annual_rate"],
                funding_time_days=r["funding_time_days"],
                eligible=r["eligible"],
                eligible_reason=r["eligible_reason"],
                eligibility_fix=r["eligibility_fix"],
                rank=idx,
            )
        )
    db.commit()
    return out


@router.get("/recommendations", response_model=List[RecommendationResponse])
def list_recommendations(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    q = db.query(models.FinancingRecommendation).filter(models.FinancingRecommendation.org_id == user.organization_id)
    return q.order_by(models.FinancingRecommendation.created_at.desc()).offset(offset).limit(limit).all()

from datetime import datetime

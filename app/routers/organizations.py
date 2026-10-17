"""Organization endpoints for CASHFLOW."""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user, require_csrf
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/organizations", tags=["organizations"])


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    country: str = Field(default="US", min_length=2, max_length=2)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    jurisdiction: Optional[str] = None
    timezone: str = "UTC"
    locale: str = "en-US"
    fiscal_year_start: Optional[str] = None
    tax_rate: Optional[float] = None
    filing_due_day: Optional[int] = Field(default=None, ge=1, le=31)
    payment_terms_days: Optional[int] = Field(default=None, ge=0)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    country: str
    base_currency: str
    jurisdiction: Optional[str]
    timezone: str
    locale: str
    fiscal_year_start: Optional[str]
    tax_rate: Optional[float]
    filing_due_day: Optional[int]
    payment_terms_days: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


@router.get("/me", response_model=OrganizationResponse)
def get_my_organization(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(models.Organization).filter(models.Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/me", response_model=OrganizationResponse)
def update_my_organization(
    data: OrganizationBase,
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_csrf(request)
    if user.organization_id:
        membership = (
            db.query(models.Membership)
            .filter(models.Membership.user_id == user.id, models.Membership.org_id == user.organization_id)
            .first()
        )
        if membership.role not in ("owner", "finance"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update organization")
    org = db.query(models.Organization).filter(models.Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org


@router.get("/me/memberships", response_model=List[dict])
def list_memberships(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(models.Membership, models.Organization)
        .join(models.Organization, models.Organization.id == models.Membership.org_id)
        .filter(models.Membership.user_id == user.id)
        .all()
    )
    return [
        {
            "id": m.id,
            "org_id": m.org_id,
            "org_name": o.name,
            "role": m.role,
            "created_at": m.created_at.isoformat(),
        }
        for m, o in rows
    ]


@router.post("/me/invite")
def invite_member(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_csrf(request)
    if not settings.smtp_configured():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member invites require SMTP")
    return {"message": "Invite flow requires SMTP configuration"}

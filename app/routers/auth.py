"""Authentication API endpoints for CASHFLOW."""

import time
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from app.database import get_db
from app import models
from app.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
)
from app.config import get_settings, is_production
from app.dependencies import get_current_user

settings = get_settings()
logger = logging.getLogger("cashflow")

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# In-memory rate limit store: key -> list of attempt timestamps
_RATE_LIMITS: dict = {}
_BACKOFF_UNTIL: dict = {}


def _rate_limit_ok(key: str) -> bool:
    now = time.time()
    blocked_until = _BACKOFF_UNTIL.get(key, 0)
    if now < blocked_until:
        return False
    window = _RATE_LIMITS.get(key, [])
    window = [t for t in window if now - t < 60]
    if len(window) >= settings.login_rate_limit_per_minute:
        _BACKOFF_UNTIL[key] = now + settings.login_backoff_seconds
        return False
    window.append(now)
    _RATE_LIMITS[key] = window
    return True


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = is_production()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="Lax",
        max_age=settings.jwt_access_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="Lax",
        max_age=settings.jwt_refresh_expire_days * 24 * 3600,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite="Lax",
        max_age=settings.jwt_refresh_expire_days * 24 * 3600,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


# ---------- Schemas ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=settings.password_min_length)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    organization_name: str = Field(..., min_length=2, max_length=255)
    country: str = Field(default="US", min_length=2, max_length=2)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC")
    locale: str = Field(default="en-US")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: str
    email: str
    organization_id: Optional[str]
    organization_name: Optional[str]
    role: str
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    organization_id: Optional[str]
    role: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class CsrfResponse(BaseModel):
    csrf_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# ---------- Endpoints ----------

@router.post("/csrf-token", response_model=CsrfResponse)
def csrf_token(response: Response):
    token = generate_csrf_token()
    secure = is_production()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=secure,
        samesite="Lax",
        max_age=settings.jwt_refresh_expire_days * 24 * 3600,
        path="/",
    )
    return {"csrf_token": token}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(response: Response, data: UserRegister, db: Session = Depends(get_db)):
    validate_password_strength(data.password)
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    org = models.Organization(
        name=data.organization_name,
        country=data.country,
        base_currency=data.base_currency,
        timezone=data.timezone,
        locale=data.locale,
    )
    db.add(org)
    db.flush()

    user = models.User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=(data.first_name + " " + data.last_name).strip() if data.first_name or data.last_name else None,
        organization_id=org.id,
    )
    db.add(user)
    db.flush()

    membership = models.Membership(user_id=user.id, org_id=org.id, role="owner")
    db.add(membership)
    db.commit()

    access_token = create_access_token(user.id, extra={"email": user.email, "org_id": org.id})
    refresh_token = create_refresh_token(user.id)
    csrf_token_value = generate_csrf_token()
    _set_auth_cookies(response, access_token, refresh_token, csrf_token_value)

    logger.info("User registered", extra={"user_id": user.id, "org_id": org.id})
    return TokenResponse(
        user_id=user.id,
        email=user.email,
        organization_id=org.id,
        organization_name=org.name,
        role="owner",
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(response: Response, request: Request, data: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{data.email}"
    if not _rate_limit_ok(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        _rate_limit_ok(rate_key)  # count failed attempt
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    membership = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == user.id)
        .order_by(models.Membership.created_at.asc())
        .first()
    )
    org = None
    role = "viewer"
    if membership:
        org = db.query(models.Organization).filter(models.Organization.id == membership.org_id).first()
        role = membership.role

    access_token = create_access_token(user.id, extra={"email": user.email, "org_id": str(org.id) if org else None})
    refresh_token = create_refresh_token(user.id)
    csrf_token_value = generate_csrf_token()
    _set_auth_cookies(response, access_token, refresh_token, csrf_token_value)

    logger.info("User logged in", extra={"user_id": user.id})
    return TokenResponse(
        user_id=user.id,
        email=user.email,
        organization_id=str(org.id) if org else None,
        organization_name=org.name if org else None,
        role=role,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.post("/refresh", response_model=TokenResponse)
def refresh(response: Response, request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access_token = create_access_token(user.id, extra={"email": user.email, "org_id": str(user.organization_id)})
    csrf_token_value = generate_csrf_token()
    _set_auth_cookies(response, access_token, refresh_token, csrf_token_value)
    membership = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == user.id)
        .order_by(models.Membership.created_at.asc())
        .first()
    )
    role = membership.role if membership else "viewer"
    org = db.query(models.Organization).filter(models.Organization.id == user.organization_id).first() if user.organization_id else None
    return TokenResponse(
        user_id=user.id,
        email=user.email,
        organization_id=str(user.organization_id) if user.organization_id else None,
        organization_name=org.name if org else None,
        role=role,
        expires_in=settings.jwt_access_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == user.id)
        .order_by(models.Membership.created_at.asc())
        .first()
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.name,
        last_name=None,
        organization_id=user.organization_id,
        role=membership.role if membership else None,
        is_active=user.is_active,
    )


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    if not settings.smtp_configured():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Password reset is not available")
    # SMTP reset would go here; acknowledge only to avoid user enumeration
    return {"message": "If an account exists, a reset link was sent"}

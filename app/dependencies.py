"""Request dependencies for CASHFLOW."""
from typing import Optional

from fastapi import Depends, HTTPException, status, Request, Cookie, Header
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app import models
from app.security import decode_token
from app.config import get_settings, is_production

settings = get_settings()


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def get_current_user_id(
    request: Request,
    session: Optional[str] = Cookie(default=None, alias=None),
) -> str:
    # Resolved per-router via get_current_user; kept for explicit use.
    raise NotImplementedError("use get_current_user instead")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(session_token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    request.state.user_id = user.id
    request.state.user = user
    return user


def require_csrf(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    csrf_header = request.headers.get(settings.csrf_header_name)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    if not csrf_header or not csrf_cookie:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    from app.security import verify_csrf_token
    if not verify_csrf_token(csrf_header, csrf_cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")


def get_optional_user(request: Request, db: Session = Depends(get_db)):
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def is_production_flag() -> bool:
    return is_production()

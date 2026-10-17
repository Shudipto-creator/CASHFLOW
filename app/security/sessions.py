"""Server-side session management (section 8.1)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings

settings = get_settings()
COOKIE_NAME = "__Host-cf_session" if settings.cookie_secure else "cf_session"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def make_token() -> str:
    return secrets.token_urlsafe(32)


def ip_hash(ip: Optional[str]) -> str:
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    user: models.User,
    ip: Optional[str],
    user_agent: Optional[str],
) -> str:
    """Create a session row and return the raw cookie token."""
    token = make_token()
    now = datetime.now(timezone.utc)
    if user.is_guest:
        expires_at = now + timedelta(days=settings.session_absolute_days_guest)
    else:
        expires_at = now + timedelta(days=settings.session_absolute_days_signed_in)
    row = models.Session(
        id_hash=hash_token(token),
        user_id=user.id,
        csrf_token=make_token(),
        expires_at=expires_at,
        ip_hash=ip_hash(ip),
        user_agent=user_agent,
    )
    db.add(row)
    db.commit()
    return token


def get_session(db: Session, token: str) -> Optional[models.Session]:
    row = db.query(models.Session).filter(models.Session.id_hash == hash_token(token)).first()
    if row is None:
        return None
    if row.expires_at <= datetime.now(timezone.utc):
        return None
    return row


def touch_session(db: Session, row: models.Session) -> None:
    row.last_seen_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def destroy_session(db: Session, row: models.Session) -> None:
    db.delete(row)
    db.commit()


def destroy_all_user_sessions(db: Session, user_id: str) -> int:
    count = db.query(models.Session).filter(models.Session.user_id == user_id).delete()
    db.commit()
    return count


def cleanup_expired_sessions(db: Session) -> int:
    count = (
        db.query(models.Session)
        .filter(models.Session.expires_at <= datetime.now(timezone.utc))
        .delete(synchronize_session=False)
    )
    db.commit()
    return count

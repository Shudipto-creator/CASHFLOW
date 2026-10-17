"""Rate limiting backed by the rate_limits table (section 13.7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_and_consume(
    db: Session,
    key: str,
    limit: int,
    window: timedelta,
) -> tuple[bool, Optional[int]]:
    """Returns (allowed, retry_after_seconds). Uses one row per key/window."""
    now = _now()
    window_start = now - (now - datetime.min.replace(tzinfo=timezone.utc)) % window
    row = (
        db.query(models.RateLimit)
        .filter(models.RateLimit.key == key, models.RateLimit.window_start == window_start)
        .first()
    )
    if row is None:
        row = models.RateLimit(key=key, window_start=window_start, count=0)
        db.add(row)
        db.flush()
    if row.count >= limit:
        retry = int((window_start + window - now).total_seconds()) + 1
        return False, max(retry, 1)
    row.count += 1
    db.add(row)
    db.commit()
    return True, None


def cleanup_rate_limits(db: Session) -> int:
    cutoff = _now() - timedelta(days=7)
    count = (
        db.query(models.RateLimit)
        .filter(models.RateLimit.window_start < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count

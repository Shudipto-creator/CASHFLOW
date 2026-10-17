"""CSRF protection (section 8.2)."""

from __future__ import annotations

import hmac
import secrets

from app.config import get_settings

settings = get_settings()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def verify(sent: str | None, expected: str | None) -> bool:
    if not sent or not expected:
        return False
    return hmac.compare_digest(sent, expected)


def origin_allowed(origin: str | None, referer: str | None) -> bool:
    """Check Origin/Referer host matches SITE_URL host."""
    from urllib.parse import urlparse

    site_host = urlparse(settings.site_url).hostname
    for value in (origin, referer):
        if not value:
            continue
        host = urlparse(value).hostname
        if host and host == site_host:
            return True
    return False

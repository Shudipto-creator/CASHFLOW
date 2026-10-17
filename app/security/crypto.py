"""Field encryption with Fernet (section 13.6)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

settings = get_settings()
_KEYS = [Fernet(key.encode()) for key in settings.encryption_keys()]


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _KEYS[0].encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str | None:
    if token is None:
        return None
    last_error: Exception | None = None
    for fernet in _KEYS:
        try:
            return fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return None

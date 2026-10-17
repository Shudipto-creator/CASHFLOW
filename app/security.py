"""Security utilities for CASHFLOW: passwords, JWT, CSRF, masking, injection scan."""

import re
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


# ---------- Passwords ----------

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "welcome1", "admin123", "letmein", "monkey", "dragon", "master",
    "login", "abc123", "passw0rd", "Password1", "Password123", "123456", "iloveyou",
}


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str) -> str:
    if len(password) < settings.password_min_length:
        raise ValueError(f"Password must be at least {settings.password_min_length} characters")
    low = password.lower()
    if low in COMMON_PASSWORDS:
        raise ValueError("Password is too common. Choose a harder to guess password.")
    if re.fullmatch(r"[a-zA-Z0-9]+", password) and len(set(password)) < 8:
        raise ValueError("Password is too weak. Use a mix of characters.")
    return password


# ---------- JWT ----------

def create_access_token(subject: str, extra: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {"sub": subject, "iat": now, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ---------- CSRF ----------

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(sent: str, expected: str) -> bool:
    if not sent or not expected:
        return False
    return hmac.compare_digest(sent, expected)


# ---------- Hashing ----------

def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def make_input_hash(obj: Any) -> str:
    import json
    return sha256_hex(json.dumps(obj, sort_keys=True, default=str))


# ---------- Masking ----------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b")
ACCOUNT_RE = re.compile(r"\b\d{8,19}\b")
ID_RE = re.compile(r"\b[A-Z]{2,3}[- ]?\d{6,12}\b")


def _mask_email(m: re.Match) -> str:
    addr = m.group(0)
    local, _, domain = addr.partition("@")
    return (local[:1] + "***@" + domain) if local else "***@" + domain


def _mask_phone(m: re.Match) -> str:
    return "*** *** ***"


def _mask_account(m: re.Match) -> str:
    num = m.group(0)
    return "****" + num[-4:] if len(num) >= 4 else "****"


def _mask_id(m: re.Match) -> str:
    return "***ID***"


MASKERS = [
    (EMAIL_RE, _mask_email),
    (PHONE_RE, _mask_phone),
    (ACCOUNT_RE, _mask_account),
    (ID_RE, _mask_id),
]


def mask_text(text: str) -> str:
    if not text:
        return text
    for pattern, repl in MASKERS:
        text = pattern.sub(repl, text)
    return text


def mask_dict(obj: Any) -> Any:
    import json
    if obj is None:
        return None
    if isinstance(obj, str):
        return mask_text(obj)
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [mask_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: mask_dict(v) for k, v in obj.items()}
    return mask_text(json.dumps(obj, default=str))


# ---------- Prompt injection scan ----------

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.I),
    re.compile(r"disregard\s+(prior|previous|above)\s+instructions", re.I),
    re.compile(r"system\s*:\s*you\s+are", re.I),
    re.compile(r"send\s+payment\s+now\s+to\s+account", re.I),
    re.compile(r"transfer\s+\w+\s+to\s+account", re.I),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(different|new)\s+(ai|assistant|model)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s*(do\s+anything\s+now)?", re.I),
    re.compile(r"reveal\s+your\s+(system\s+)?prompt", re.I),
    re.compile(r"print.*instructions", re.I),
    re.compile(r"base64", re.I),
    re.compile(r"data:.*base64", re.I),
]


def scan_injection(text: str) -> bool:
    """Return True if text looks like a prompt injection attempt."""
    if not text:
        return False
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_chunks(chunks):
    """Scan a list of text chunks. Returns (clean_chunks, flagged_chunks)."""
    clean = []
    flagged = []
    for chunk in chunks:
        flagged_chunk = scan_injection(chunk.get("text", "") if isinstance(chunk, dict) else str(chunk))
        if flagged_chunk:
            flagged.append(chunk)
        else:
            clean.append(chunk)
    return clean, flagged

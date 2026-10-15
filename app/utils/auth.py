"""Authentication utilities - JWT handling and password hashing"""

from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from app.config import get_settings
from typing import Optional, Dict

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (truncate to 72 bytes for bcrypt limit)"""
    # Bcrypt has a 72-byte limit, so truncate password if needed
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash (truncate to 72 bytes for bcrypt limit)"""
    try:
        # Bcrypt has a 72-byte limit, so truncate password if needed
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict]:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def get_token_expiration_seconds() -> int:
    """Get token expiration time in seconds"""
    return settings.jwt_expiration_hours * 3600

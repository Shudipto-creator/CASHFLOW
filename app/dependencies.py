"""Shared dependencies for FastAPI routes"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import decode_access_token
from app import models
from typing import Optional
from typing import Literal, Optional

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> models.User:
    """Dependency to get current authenticated user

    Args:
        credentials: JWT token from Authorization header
        db: Database session

    Returns:
        User model instance

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID from payload
    user_id: str = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(models.User).filter(models.User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_admin_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Dependency that requires admin role.

    Raises:
        HTTPException: If user does not have admin role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action",
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: Session = Depends(get_db)
) -> Optional[models.User]:
    """Optional authentication - returns None if no valid token

    Args:
        credentials: JWT token from Authorization header (optional)
        db: Database session

    Returns:
        User model instance or None
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_access_token(token)

        if not payload:
            return None

        user_id: str = payload.get("sub")

        if not user_id:
            return None

        user = db.query(models.User).filter(models.User.user_id == user_id).first()
        return user

    except:
        return None
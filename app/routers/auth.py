"""Authentication API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.utils.auth import hash_password, verify_password, create_access_token, get_token_expiration_seconds
from app.config import get_settings
from app.services.password_recovery import PasswordRecoveryCodes, RecoveryCooldownError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])
password_recovery_codes = PasswordRecoveryCodes()


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If email already exists or validation fails
    """
    logger.info(f"Registration attempt for email: {user_data.email}")

    # Check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create user
    new_user = models.User(
        email=user_data.email,
        password_hash=hashed_password,
        company_name=user_data.company_name,
        business_type=user_data.business_type,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User registered successfully: {new_user.user_id}")

    return new_user


@router.post("/login", response_model=schemas.TokenResponse)
async def login_user(login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and receive JWT token

    Args:
        login_data: Login credentials
        db: Database session

    Returns:
        JWT access token and user information

    Raises:
        HTTPException: If credentials are invalid
    """
    logger.info(f"Login attempt for email: {login_data.email}")

    # Get user by email
    user = db.query(models.User).filter(models.User.email == login_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Create access token
    access_token = create_access_token(data={"sub": user.user_id, "email": user.email})

    logger.info(f"User logged in successfully: {user.user_id}")

    return schemas.TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=get_token_expiration_seconds(),
        user=schemas.UserResponse(
            user_id=user.user_id,
            email=user.email,
            company_name=user.company_name,
            created_at=user.created_at,
        ),
    )


@router.post("/password-recovery/request")
async def request_password_recovery(
    request_data: schemas.PasswordRecoveryRequest,
):
    if get_settings().app_env.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery delivery is not configured for this environment",
        )

    try:
        challenge_id = password_recovery_codes.issue(str(request_data.email))
    except RecoveryCooldownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    return {
        "challenge_id": challenge_id,
        "message": (
            "If that email is registered, a recovery code has been generated. "
            "For this demo, check the backend terminal."
        ),
    }


@router.post("/password-recovery/complete")
async def complete_password_recovery(
    request_data: schemas.PasswordRecoveryComplete,
    db: Session = Depends(get_db),
):
    email = str(request_data.email)
    if not password_recovery_codes.verify(
        email,
        request_data.challenge_id,
        request_data.code,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not complete password recovery. Check the email and code, then try again.",
        )

    user = db.query(models.User).filter(models.User.email.ilike(email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not complete password recovery. Check the email and code, then try again.",
        )

    user.password_hash = hash_password(request_data.new_password)
    db.commit()
    logger.info("Password recovered for user %s", user.user_id)
    return {"message": "Password updated. You can now sign in with your new password."}

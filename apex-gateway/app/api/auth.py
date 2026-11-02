"""Authentication and user management endpoints (Registration, Login, API Keys)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password, verify_password, create_access_token, generate_user_api_key
from app.database.connection import get_db
from app.database.models import User, UserApiKey
from app.dependencies import get_current_user
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileResponse,
    TokenResponse,
    CreateApiKeyRequest,
    ApiKeyCreatedResponse,
    ApiKeyListItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
)
async def register_user(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Create a new user account with hashed credentials."""
    # Check for existing username or email
    stmt = select(User).where(or_(User.username == req.username.strip(), User.email == req.email.strip()))
    res = await db.execute(stmt)
    existing_user = res.scalar_one_or_none()

    if existing_user:
        field = "Username" if existing_user.username == req.username.strip() else "Email address"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": f"{field} is already registered.", "type": "duplicate_user"}},
        )

    # Hash password and create user
    hashed_pwd = hash_password(req.password)
    user = User(
        username=req.username.strip(),
        email=req.email.strip().lower(),
        hashed_password=hashed_pwd,
        role=req.role or "faculty",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"User '{user.username}' successfully registered with role '{user.role}'.")
    return UserProfileResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain JWT access token",
)
async def login_user(
    req: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username/email and password, returning a signed JWT access token."""
    settings = get_settings()
    identifier = req.username_or_email.strip()

    stmt = select(User).where(or_(User.username == identifier, User.email == identifier.lower()))
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Invalid username or password.", "type": "invalid_credentials"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Account has been deactivated.", "type": "account_inactive"}},
        )

    # Generate JWT
    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }
    access_token = create_access_token(token_payload)

    logger.info(f"User '{user.username}' authenticated successfully.")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserProfileResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Return profile details of the requesting user."""
    return UserProfileResponse.model_validate(current_user)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personal API key for IDEs / Antigravity",
)
async def create_personal_api_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    """Issue a new personal API key linked to this user's account."""
    raw_key, key_prefix, key_hash = generate_user_api_key()

    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    api_key_entry = UserApiKey(
        user_id=current_user.id,
        name=req.name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api_key_entry)
    await db.commit()
    await db.refresh(api_key_entry)

    logger.info(f"Issued API key '{req.name}' for user '{current_user.username}'.")
    return ApiKeyCreatedResponse(
        id=api_key_entry.id,
        name=api_key_entry.name,
        raw_key=raw_key,
        key_prefix=key_prefix,
        created_at=api_key_entry.created_at,
        expires_at=api_key_entry.expires_at,
    )


@router.get(
    "/api-keys",
    response_model=List[ApiKeyListItem],
    summary="List active personal API keys",
)
async def list_personal_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ApiKeyListItem]:
    """Retrieve all active API keys issued to the current user."""
    stmt = (
        select(UserApiKey)
        .where(UserApiKey.user_id == current_user.id)
        .order_by(UserApiKey.created_at.desc())
    )
    res = await db.execute(stmt)
    keys = res.scalars().all()
    return [ApiKeyListItem.model_validate(k) for k in keys]


@router.delete(
    "/api-keys/{key_id}",
    summary="Revoke personal API key",
)
async def revoke_personal_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke an existing personal API key."""
    stmt = select(UserApiKey).where(UserApiKey.id == key_id, UserApiKey.user_id == current_user.id)
    res = await db.execute(stmt)
    key_obj = res.scalar_one_or_none()

    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": "API key not found.", "type": "not_found"}},
        )

    await db.delete(key_obj)
    await db.commit()
    logger.info(f"Revoked API key id={key_id} for user '{current_user.username}'.")
    return {"message": f"API key '{key_obj.name}' revoked successfully."}


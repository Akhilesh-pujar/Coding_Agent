"""FastAPI dependencies provider for database sessions, services, and core components."""

import secrets
from datetime import datetime, timezone
from functools import lru_cache
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import jwt

from app.config import get_settings
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.core.authentication import verify_api_key
from app.core.security import decode_access_token, hash_api_key
from app.database.connection import get_db
from app.database.models import User, UserApiKey

# Singleton client instances
_ollama_client = OllamaClient()
_model_router = ModelRouter()

security_bearer = HTTPBearer(auto_error=False)
security_api_key = APIKeyHeader(name="x-api-key", auto_error=False)


def get_ollama_client() -> OllamaClient:
    """Return singleton OllamaClient."""
    return _ollama_client


def get_model_registry(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> ModelRegistry:
    """Return ModelRegistry configured with current OllamaClient."""
    return ModelRegistry(ollama_client)


def get_model_router() -> ModelRouter:
    """Return singleton ModelRouter."""
    return _model_router


async def get_current_user(
    bearer: HTTPAuthorizationCredentials | None = Security(security_bearer),
    api_key_header: str | None = Security(security_api_key),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate request via personal API key, JWT Bearer token, or master system key."""
    settings = get_settings()

    provided_token: str | None = None
    if bearer and bearer.credentials:
        provided_token = bearer.credentials.strip()
    elif api_key_header:
        provided_token = api_key_header.strip()

    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Missing authentication credentials.", "type": "authentication_error"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Master System Key Check (Backwards compatible with tests & root scripts)
    if settings.APEX_API_KEY and secrets.compare_digest(provided_token, settings.APEX_API_KEY):
        stmt = select(User).where(User.username == "admin")
        res = await db.execute(stmt)
        admin_user = res.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@apex.local",
                hashed_password="[SYSTEM_KEY_MANAGED]",
                role="admin",
                is_active=True,
            )
            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)
        return admin_user

    # 2. Personal User API Key Check ('apex_live_...')
    if provided_token.startswith("apex_live_"):
        key_hash = hash_api_key(provided_token)
        stmt = select(UserApiKey).options(selectinload(UserApiKey.user)).where(
            UserApiKey.key_hash == key_hash,
            UserApiKey.is_active == True,
        )
        res = await db.execute(stmt)
        api_key_obj = res.scalar_one_or_none()

        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"message": "Invalid personal API key.", "type": "invalid_api_key"}},
            )

        if api_key_obj.expires_at:
            exp = api_key_obj.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": {"message": "Personal API key has expired.", "type": "api_key_expired"}},
                )

        if not api_key_obj.user or not api_key_obj.user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"message": "User account inactive.", "type": "user_inactive"}},
            )

        return api_key_obj.user

    # 3. Standard JWT Token Validation
    try:
        payload = decode_access_token(provided_token)
        sub_str = payload.get("sub")
        if not sub_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"message": "JWT token missing subject claim.", "type": "invalid_token"}},
            )
        user_id = int(sub_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "Invalid or expired access token.", "type": "invalid_token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id, User.is_active == True)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"message": "User account not found or inactive.", "type": "user_not_found"}},
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Enforce admin privileges."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"message": "Administrative privileges required.", "type": "permission_denied"}},
        )
    return current_user


# Re-export
__all__ = [
    "get_ollama_client",
    "get_model_registry",
    "get_model_router",
    "verify_api_key",
    "get_current_user",
    "get_current_admin",
    "get_db",
]


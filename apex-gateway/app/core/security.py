"""Cryptographic security utilities for password hashing, JWT tokens, and API keys."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import bcrypt
import jwt
from app.config import get_settings


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token containing claims."""
    settings = get_settings()
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"iat": now, "exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.InvalidTokenError: If signature or structure is invalid.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload


def generate_user_api_key() -> Tuple[str, str, str]:
    """Generate a persistent personal API key.

    Returns:
        Tuple of (raw_key, key_prefix, key_hash)
        - raw_key: Full secret key shown only once to user (e.g. 'apex_live_...')
        - key_prefix: Truncated prefix safe for UI display (e.g. 'apex_live_a1b2')
        - key_hash: Cryptographic SHA-256 hash stored in DB
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"apex_live_{random_part}"
    key_prefix = raw_key[:14] + "..."
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    """Compute SHA-256 hash of an API key for constant-time DB lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


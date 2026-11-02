"""Authentication module for APEX API Gateway.

Validates API keys from 'Authorization: Bearer <token>' or 'x-api-key' headers using
constant-time string comparison to prevent timing attacks.
"""

import secrets
import logging
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.config import get_settings

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)
security_api_key = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(
    bearer: HTTPAuthorizationCredentials | None = Security(security_bearer),
    api_key_header: str | None = Security(security_api_key),
) -> str:
    """Validate incoming API key against configured APEX_API_KEY.

    Accepts:
      - Authorization: Bearer <key>
      - x-api-key: <key>
    """
    settings = get_settings()
    configured_key = settings.APEX_API_KEY

    # Extract token
    provided_key: str | None = None
    if bearer and bearer.credentials:
        provided_key = bearer.credentials.strip()
    elif api_key_header:
        provided_key = api_key_header.strip()

    if not provided_key:
        logger.warning("Request rejected: Missing API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Missing API key. Please provide Bearer token or x-api-key header.",
                    "type": "authentication_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant time comparison
    if not secrets.compare_digest(provided_key, configured_key):
        logger.warning("Request rejected: Invalid API key provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "message": "Incorrect API key provided.",
                    "type": "authentication_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_key


"""Authentication module for APEX API Gateway.

Re-exports verify_api_key and get_current_user from app.dependencies for full
multi-tenant user authentication and personal API key support.
"""

from app.dependencies import verify_api_key, get_current_user

__all__ = ["verify_api_key", "get_current_user"]

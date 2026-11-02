"""Pydantic schemas for multi-tenant user authentication and personal API keys."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Unique username")
    email: str = Field(..., min_length=5, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid organizational email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    role: Optional[str] = Field(default="faculty", description="Role: admin, faculty, or student")


class UserLoginRequest(BaseModel):
    username_or_email: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Account password")


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserProfileResponse


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Label for key (e.g. 'Cabin Laptop', 'Antigravity')")
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365, description="Optional lifetime in days")


class ApiKeyCreatedResponse(BaseModel):
    id: int
    name: str
    raw_key: str = Field(..., description="Copy this key now. It will not be shown again.")
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class ApiKeyListItem(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

"""Configuration module for APEX API Gateway.

Uses Pydantic Settings to load and validate environment variables with sane defaults.
"""

from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "apex-gateway/.env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL of local Ollama server"
    )
    APEX_HOST: str = Field(
        default="127.0.0.1",
        description="Local host binding"
    )
    APEX_PORT: int = Field(
        default=8000,
        description="Port for the APEX API Gateway"
    )
    APEX_API_KEY: str = Field(
        default="change-this-key",
        description="Authentication key required to access gateway"
    )
    APEX_DEFAULT_MODEL: str = Field(
        default="apex-fast:latest",
        description="Default fallback model"
    )
    APEX_PRO_MODEL: str = Field(
        default="apex-pro:latest",
        description="High-tier model for complex reasoning and architecture"
    )
    APEX_FAST_MODEL: str = Field(
        default="apex-fast:latest",
        description="Lightweight fast model for simple queries and docs"
    )
    APEX_REQUEST_TIMEOUT: float = Field(
        default=300.0,
        description="Timeout for Ollama requests in seconds"
    )
    APEX_LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    APEX_DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./apex.db",
        description="Async SQLAlchemy SQLite database connection string"
    )
    APEX_VERSION: str = "1.0.0"
    MAX_REQUEST_BODY_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(
        default="apex-jwt-secret-key-change-in-production-2026",
        description="Cryptographic secret key for signing JWT tokens"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT encoding algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="Token expiration duration in minutes (default 24 hours)"
    )

    @field_validator("APEX_DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Convert standard sqlite:/// or postgresql:/// to async drivers."""
        if isinstance(v, str):
            if v.startswith("sqlite:///") and not v.startswith("sqlite+aiosqlite:///"):
                return v.replace("sqlite:///", "sqlite+aiosqlite:///")
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    @property
    def ollama_tags_url(self) -> str:
        return f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/tags"

    @property
    def ollama_version_url(self) -> str:
        return f"{self.OLLAMA_BASE_URL.rstrip('/')}/api/version"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


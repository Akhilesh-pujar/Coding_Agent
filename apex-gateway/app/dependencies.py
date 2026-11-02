"""FastAPI dependencies provider for database sessions, services, and core components."""

from functools import lru_cache
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.core.authentication import verify_api_key
from app.database.connection import get_db

# Singleton client instances
_ollama_client = OllamaClient()
_model_router = ModelRouter()


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


# Re-export verify_api_key and get_db for clean route injections
__all__ = [
    "get_ollama_client",
    "get_model_registry",
    "get_model_router",
    "verify_api_key",
    "get_db",
]


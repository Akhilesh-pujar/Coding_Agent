"""Pytest fixtures and configuration for testing APEX API Gateway."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

# Ensure apex-gateway directory is in python path
GATEWAY_DIR = Path(__file__).resolve().parent.parent
if str(GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(GATEWAY_DIR))

from app.main import app
from app.config import Settings, get_settings
from app.dependencies import get_ollama_client, get_model_registry
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.database.connection import init_db

TEST_API_KEY = get_settings().APEX_API_KEY


@pytest.fixture(autouse=True)
async def initialize_test_database():
    """Ensure database schema is created in memory."""
    await init_db()


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient with default successful responses."""
    client = AsyncMock(spec=OllamaClient)

    # Default healthy check
    client.check_health.return_value = {"connected": True, "version": "0.5.1"}

    # Default installed models
    client.list_models.return_value = [
        {
            "name": "apex-fast:latest",
            "model": "apex-fast:latest",
            "modified_at": "2026-10-30T10:00:00Z",
            "size": 4700000000,
            "details": {"family": "qwen2", "parameter_size": "7B"},
        },
        {
            "name": "apex-pro:latest",
            "model": "apex-pro:latest",
            "modified_at": "2026-10-30T10:00:00Z",
            "size": 9000000000,
            "details": {"family": "qwen2", "parameter_size": "14B"},
        },
    ]

    # Default non-streaming response
    client.chat_completion.return_value = {
        "model": "apex-fast:latest",
        "created_at": "2026-10-30T10:01:00Z",
        "message": {"role": "assistant", "content": "Hello! I am APEX."},
        "done": True,
        "prompt_eval_count": 15,
        "eval_count": 25,
    }

    # Default streaming generator
    async def mock_stream_chat(payload):
        yield {"message": {"role": "assistant", "content": "Hello"}, "done": False}
        yield {"message": {"role": "assistant", "content": " world!"}, "done": False}
        yield {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 20,
        }

    client.stream_chat_completion = mock_stream_chat
    return client


@pytest.fixture
async def async_client(mock_ollama_client):
    """Authenticated AsyncClient with mocked Ollama dependency."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_client
    app.dependency_overrides[get_model_registry] = lambda: ModelRegistry(mock_ollama_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def unauthed_client(mock_ollama_client):
    """Unauthenticated AsyncClient."""
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama_client
    app.dependency_overrides[get_model_registry] = lambda: ModelRegistry(mock_ollama_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


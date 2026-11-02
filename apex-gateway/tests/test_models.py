"""Tests for /v1/models endpoint."""

import pytest
from app.core.ollama_client import OllamaConnectionError
from tests.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_list_models_authenticated(async_client):
    """Test authenticated retrieval of OpenAI-formatted model list."""
    response = await async_client.get("/v1/models")
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 2

    model_ids = [m["id"] for m in data["data"]]
    assert "apex-fast:latest" in model_ids
    assert "apex-pro:latest" in model_ids

    first_model = data["data"][0]
    assert first_model["object"] == "model"
    assert first_model["owned_by"] == "apex-local"


@pytest.mark.asyncio
async def test_list_models_unauthenticated(unauthed_client):
    """Test model listing rejection without API key."""
    response = await unauthed_client.get("/v1/models")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_list_models_invalid_key(async_client):
    """Test model listing rejection with invalid API key."""
    response = await async_client.get(
        "/v1/models",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_list_models_x_api_key_header(unauthed_client):
    """Test model listing with x-api-key header instead of Bearer token."""
    response = await unauthed_client.get(
        "/v1/models",
        headers={"x-api-key": TEST_API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["object"] == "list"


@pytest.mark.asyncio
async def test_list_models_ollama_unavailable(async_client, mock_ollama_client):
    """Test 503 response when Ollama is unreachable."""
    mock_ollama_client.list_models.side_effect = OllamaConnectionError("Connection refused")
    response = await async_client.get("/v1/models")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ollama_unavailable"


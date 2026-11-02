"""Tests for /health endpoint and Ollama connectivity status."""

import pytest


@pytest.mark.asyncio
async def test_health_healthy(async_client, mock_ollama_client):
    """Test health endpoint when Ollama is reachable and models are verified."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["gateway_status"] == "healthy"
    assert data["gateway_version"] == "1.0.0"

    # Ollama connectivity
    assert data["ollama_connectivity"]["connected"] is True
    assert data["ollama_connectivity"]["version"] == "0.5.1"

    # Model verification
    model_status = data["model_status"]
    assert model_status["apex_fast_verified"] is True
    assert model_status["apex_pro_verified"] is True
    assert model_status["installed_models_count"] == 2


@pytest.mark.asyncio
async def test_health_ollama_down(async_client, mock_ollama_client):
    """Test health endpoint when Ollama is unreachable."""
    mock_ollama_client.check_health.return_value = {
        "connected": False,
        "error": "Connection refused",
    }
    mock_ollama_client.list_models.return_value = []

    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "degraded" in data["gateway_status"]
    assert data["ollama_connectivity"]["connected"] is False
    assert data["ollama_connectivity"]["error"] == "Connection refused"
    assert data["model_status"]["apex_fast_verified"] is False


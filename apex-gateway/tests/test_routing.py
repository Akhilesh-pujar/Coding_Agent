"""Tests for automatic model routing logic and /api/route endpoint."""

import pytest


@pytest.mark.asyncio
async def test_route_simple_task(async_client):
    """Test routing of a simple explanation request to apex-fast."""
    payload = {
        "messages": [
            {"role": "user", "content": "What is the difference between a list and a tuple in Python?"}
        ]
    }

    response = await async_client.post("/api/route", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["selected_model"] == "apex-fast:latest"
    assert data["classification"] == "simple"
    assert data["confidence"] > 0.6


@pytest.mark.asyncio
async def test_route_complex_task(async_client):
    """Test routing of a complex architecture / debugging request to apex-pro."""
    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Please analyze this distributed architecture deadlock and race condition across multiple files. "
                    "We need to refactor the concurrency model and fix a memory leak in our asyncio background tasks."
                ),
            }
        ]
    }

    response = await async_client.post("/api/route", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["selected_model"] == "apex-pro:latest"
    assert data["classification"] == "complex"
    assert data["confidence"] > 0.6


@pytest.mark.asyncio
async def test_route_explicit_hint(async_client):
    """Test routing using explicit task_hint parameter."""
    payload = {
        "prompt": "Review this small function.",
        "task_hint": "architecture",
    }

    response = await async_client.post("/api/route", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["selected_model"] == "apex-pro:latest"


@pytest.mark.asyncio
async def test_route_explicit_model_selection(async_client):
    """Test that explicit model selection is strictly respected."""
    payload = {
        "prompt": "Simple question",
        "model": "apex-pro:latest",
    }

    response = await async_client.post("/api/route", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["selected_model"] == "apex-pro:latest"
    assert data["classification"] == "explicit"


@pytest.mark.asyncio
async def test_chat_auto_routing_dispatch(async_client, mock_ollama_client):
    """Test that omitting model in /v1/chat/completions triggers auto-routing."""
    # Complex query should dispatch to apex-pro
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Design an event-driven microservice system architecture with zero downtime migration.",
            }
        ]
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.json()["model"] == "apex-pro:latest"


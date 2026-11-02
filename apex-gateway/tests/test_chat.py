"""Tests for /v1/chat/completions endpoint (streaming, non-streaming, routing, timeouts)."""

import json
import pytest
from app.core.ollama_client import OllamaConnectionError, OllamaTimeoutError


@pytest.mark.asyncio
async def test_chat_completion_valid_fast_model(async_client, mock_ollama_client):
    """Test standard non-streaming chat completion with apex-fast."""
    payload = {
        "model": "apex-fast:latest",
        "messages": [{"role": "user", "content": "How do I reverse a list in Python?"}],
        "temperature": 0.5,
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "apex-fast:latest"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello! I am APEX."
    assert data["usage"]["prompt_tokens"] == 15
    assert data["usage"]["completion_tokens"] == 25
    assert data["usage"]["total_tokens"] == 40


@pytest.mark.asyncio
async def test_chat_completion_valid_pro_model(async_client, mock_ollama_client):
    """Test standard non-streaming chat completion with apex-pro."""
    mock_ollama_client.chat_completion.return_value = {
        "model": "apex-pro:latest",
        "created_at": "2026-10-30T10:02:00Z",
        "message": {"role": "assistant", "content": "Architectural recommendation: use event queues."},
        "done": True,
        "prompt_eval_count": 50,
        "eval_count": 80,
    }

    payload = {
        "model": "apex-pro:latest",
        "messages": [{"role": "user", "content": "Design an event-driven microservices architecture."}],
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "apex-pro:latest"
    assert "Architectural" in data["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_chat_completion_invalid_model(async_client):
    """Test 404 rejection when requesting a non-existent model."""
    payload = {
        "model": "non-existent-model-xyz:latest",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_chat_completion_streaming(async_client):
    """Test streaming Server-Sent Events (SSE) completion."""
    payload = {
        "model": "apex-fast:latest",
        "messages": [{"role": "user", "content": "Count to 5."}],
        "stream": True,
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    chunks = []
    lines = response.text.split("\n\n")
    for block in lines:
        block = block.strip()
        if not block:
            continue
        if block == "data: [DONE]":
            chunks.append("[DONE]")
            continue
        if block.startswith("data: "):
            json_str = block[6:]
            chunk_data = json.loads(json_str)
            chunks.append(chunk_data)

    assert len(chunks) >= 3
    assert chunks[-1] == "[DONE]"
    # Verify first content chunk
    first_chunk = chunks[0]
    assert first_chunk["object"] == "chat.completion.chunk"


@pytest.mark.asyncio
async def test_chat_completion_unauthenticated(unauthed_client):
    """Test chat completion rejection when unauthenticated."""
    payload = {
        "model": "apex-fast:latest",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    response = await unauthed_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_completion_ollama_unavailable(async_client, mock_ollama_client):
    """Test 503 response when Ollama fails to respond during chat."""
    mock_ollama_client.chat_completion.side_effect = OllamaConnectionError("Connection refused")

    payload = {
        "model": "apex-fast:latest",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ollama_unavailable"


@pytest.mark.asyncio
async def test_chat_completion_timeout(async_client, mock_ollama_client):
    """Test 504 gateway timeout when Ollama execution exceeds limit."""
    mock_ollama_client.chat_completion.side_effect = OllamaTimeoutError("Timed out")

    payload = {
        "model": "apex-fast:latest",
        "messages": [{"role": "user", "content": "Heavy processing"}],
    }

    response = await async_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "ollama_timeout"


@pytest.mark.asyncio
async def test_text_completion_valid(async_client, mock_ollama_client):
    """Test legacy /v1/completions endpoint."""
    payload = {
        "model": "apex-fast:latest",
        "prompt": "Write a python function to add two numbers.",
    }

    response = await async_client.post("/v1/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "text_completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["text"] == "Hello! I am APEX."


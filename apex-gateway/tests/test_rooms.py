"""Tests for Multi-Room Chat, Context Preservation, and Tenant Isolation."""

import uuid
import pytest
from httpx import AsyncClient


async def create_user_and_token(client: AsyncClient, prefix: str = "u") -> tuple[str, dict]:
    uid = uuid.uuid4().hex[:6]
    username = f"{prefix}_{uid}"
    email = f"{username}@apex.edu"
    password = "TestPassword123!"

    await client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    res = await client.post(
        "/v1/auth/login",
        json={"username_or_email": username, "password": password},
    )
    token = res.json()["access_token"]
    return username, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_room_lifecycle_and_chat(async_client: AsyncClient, mock_ollama_client):
    """Test creating a room, chatting with history persistence, and sliding context."""
    _, auth_headers = await create_user_and_token(async_client, "prof")

    # 1. Create a room
    room_resp = await async_client.post(
        "/v1/rooms",
        headers=auth_headers,
        json={
            "title": "Compiler Project",
            "default_model": "apex-fast:latest",
            "system_prompt": "You are a compiler design expert.",
        },
    )
    assert room_resp.status_code == 200
    room_data = room_resp.json()
    room_id = room_data["id"]
    assert room_data["title"] == "Compiler Project"
    assert len(room_data["messages"]) == 1  # System prompt seeded
    assert room_data["messages"][0]["role"] == "system"

    # 2. List rooms
    list_resp = await async_client.get("/v1/rooms", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
    assert any(r["id"] == room_id for r in list_resp.json())

    # 3. Chat in the room (Turn 1)
    mock_ollama_client.chat_completion.return_value = {
        "model": "apex-fast:latest",
        "message": {"role": "assistant", "content": "An AST represents hierarchical syntax."},
        "prompt_eval_count": 25,
        "eval_count": 30,
    }

    chat_resp = await async_client.post(
        f"/v1/rooms/{room_id}/chat",
        headers=auth_headers,
        json={"message": "What is an AST?"},
    )
    assert chat_resp.status_code == 200
    msg_data = chat_resp.json()
    assert msg_data["role"] == "assistant"
    assert "AST" in msg_data["content"]

    # 4. Verify message history in the room
    detail_resp = await async_client.get(f"/v1/rooms/{room_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    history = detail_resp.json()["messages"]
    # Should have system + user + assistant = 3 messages
    assert len(history) == 3
    assert history[0]["role"] == "system"
    assert history[1]["role"] == "user"
    assert history[1]["content"] == "What is an AST?"
    assert history[2]["role"] == "assistant"

    # 5. Update room title
    patch_resp = await async_client.patch(
        f"/v1/rooms/{room_id}",
        headers=auth_headers,
        json={"title": "Compiler AST Study"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Compiler AST Study"

    # 6. Delete room
    del_resp = await async_client.delete(f"/v1/rooms/{room_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # 7. Access after delete returns 404
    get_after_del = await async_client.get(f"/v1/rooms/{room_id}", headers=auth_headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_room_tenant_isolation(async_client: AsyncClient):
    """Test that User B cannot view, chat in, or delete User A's room."""
    _, user_a_headers = await create_user_and_token(async_client, "alice")
    _, user_b_headers = await create_user_and_token(async_client, "bob")

    # User A creates a private room
    room_resp = await async_client.post(
        "/v1/rooms",
        headers=user_a_headers,
        json={"title": "Alice Private Research"},
    )
    room_id = room_resp.json()["id"]

    # User B attempts to access User A's room -> 404
    b_view = await async_client.get(f"/v1/rooms/{room_id}", headers=user_b_headers)
    assert b_view.status_code == 404

    # User B attempts to chat in User A's room -> 404
    b_chat = await async_client.post(
        f"/v1/rooms/{room_id}/chat",
        headers=user_b_headers,
        json={"message": "Can I spy?"},
    )
    assert b_chat.status_code == 404

    # User B attempts to delete User A's room -> 404
    b_del = await async_client.delete(f"/v1/rooms/{room_id}", headers=user_b_headers)
    assert b_del.status_code == 404


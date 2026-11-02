"""Tests for User Authentication, JWT Tokens, and Personal API Keys."""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login_flow(async_client: AsyncClient):
    """Test user registration followed by successful JWT login."""
    unique_id = uuid.uuid4().hex[:6]
    username = f"user_{unique_id}"
    email = f"{username}@apex.edu"
    password = "SuperSecretPassword123!"

    reg_payload = {
        "username": username,
        "email": email,
        "password": password,
        "role": "faculty",
    }

    # 1. Register
    reg_resp = await async_client.post("/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["username"] == username
    assert user_data["role"] == "faculty"
    assert "password" not in user_data

    # 2. Duplicate registration rejected
    dup_resp = await async_client.post("/v1/auth/register", json=reg_payload)
    assert dup_resp.status_code == 400

    # 3. Login with wrong password rejected
    bad_login = await async_client.post(
        "/v1/auth/login",
        json={"username_or_email": username, "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # 4. Successful login returns JWT
    login_resp = await async_client.post(
        "/v1/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    jwt_token = token_data["access_token"]

    # 5. Access /v1/auth/me using JWT Bearer token
    me_resp = await async_client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == username


@pytest.mark.asyncio
async def test_personal_api_key_lifecycle(async_client: AsyncClient):
    """Test generation, usage, and revocation of personal API keys."""
    unique_id = uuid.uuid4().hex[:6]
    username = f"dev_{unique_id}"
    email = f"{username}@apex.edu"
    password = "PasswordDev123!"

    # Register & login
    await async_client.post(
        "/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    login_resp = await async_client.post(
        "/v1/auth/login",
        json={"username_or_email": username, "password": password},
    )
    jwt_token = login_resp.json()["access_token"]
    jwt_headers = {"Authorization": f"Bearer {jwt_token}"}

    # 1. Create personal API key
    key_resp = await async_client.post(
        "/v1/auth/api-keys",
        headers=jwt_headers,
        json={"name": "Cabin Desktop IDE", "expires_in_days": 30},
    )
    assert key_resp.status_code == 201
    key_data = key_resp.json()
    raw_key = key_data["raw_key"]
    key_id = key_data["id"]
    assert raw_key.startswith("apex_live_")

    # 2. Query /v1/auth/me using the personal API key
    api_key_headers = {"Authorization": f"Bearer {raw_key}"}
    me_via_key = await async_client.get("/v1/auth/me", headers=api_key_headers)
    assert me_via_key.status_code == 200
    assert me_via_key.json()["username"] == username

    # 3. List API keys
    list_resp = await async_client.get("/v1/auth/api-keys", headers=jwt_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 4. Revoke API key
    del_resp = await async_client.delete(f"/v1/auth/api-keys/{key_id}", headers=jwt_headers)
    assert del_resp.status_code == 200

    # 5. Access with revoked key is rejected
    rejected_resp = await async_client.get("/v1/auth/me", headers=api_key_headers)
    assert rejected_resp.status_code == 401

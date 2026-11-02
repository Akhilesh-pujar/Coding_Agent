"""Quickstart script: Registers a user, logs in, creates an API key and chat room, and chats."""

import sys
from pathlib import Path
import httpx

# Ensure gateway path is in sys.path
sys.path.insert(0, "apex-gateway")
from app.config import get_settings

settings = get_settings()
BASE_URL = f"http://127.0.0.1:{settings.APEX_PORT}"


def main():
    print(f"Connecting to APEX Gateway at {BASE_URL}...")

    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
        # 1. Health check
        health = client.get("/health")
        if health.status_code != 200:
            print("ERROR: APEX Gateway is not running. Start it with start_gateway.bat first!")
            return
        print("[✓] Gateway is online and healthy.")

        # 2. Register user
        reg_payload = {
            "username": "faculty_demo",
            "email": "faculty_demo@apex.edu",
            "password": "PasswordDemo2026!",
            "role": "faculty",
        }
        r = client.post("/v1/auth/register", json=reg_payload)
        if r.status_code == 201:
            print(f"[✓] Created user account: {reg_payload['username']}")
        elif r.status_code == 400:
            print(f"[i] User {reg_payload['username']} already exists, proceeding to login...")
        else:
            print(f"Registration failed: {r.text}")
            return

        # 3. Log in & get JWT
        login_resp = client.post(
            "/v1/auth/login",
            json={"username_or_email": "faculty_demo", "password": "PasswordDemo2026!"},
        )
        if login_resp.status_code != 200:
            print(f"Login failed: {login_resp.text}")
            return

        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[✓] Successfully authenticated and received JWT access token.")

        # 4. Generate personal API key for cabin IDE / Antigravity
        key_resp = client.post(
            "/v1/auth/api-keys",
            headers=headers,
            json={"name": "Cabin Laptop Key", "expires_in_days": 60},
        )
        if key_resp.status_code == 201:
            raw_key = key_resp.json()["raw_key"]
            print(f"[✓] Created personal API key: {raw_key}")
            print("    (Use this key in Antigravity or VS Code Continue extension)")

        # 5. Create a persistent Chat Room
        room_resp = client.post(
            "/v1/rooms",
            headers=headers,
            json={
                "title": "Faculty Research & Code",
                "default_model": "auto",
                "system_prompt": "You are a concise programming and architecture assistant.",
            },
        )
        room_id = room_resp.json()["id"]
        print(f"[✓] Created Chat Room: {room_id} ('{room_resp.json()['title']}')")

        # 6. Send a message to the room
        print("\nSending prompt to Chat Room (Model: auto)...")
        chat_resp = client.post(
            f"/v1/rooms/{room_id}/chat",
            headers=headers,
            json={"message": "Write a 3-line Python function to calculate factorial."},
        )
        if chat_resp.status_code == 200:
            data = chat_resp.json()
            print(f"\n[Model: {data.get('model_used')}] responded:")
            print("-" * 50)
            print(data.get("content"))
            print("-" * 50)
            print(f"Tokens: Prompt={data.get('prompt_tokens')}, Completion={data.get('completion_tokens')}")
            print("\n[✓] Everything is working end-to-end!")
        else:
            print(f"Chat failed: {chat_resp.text}")


if __name__ == "__main__":
    main()


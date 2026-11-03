"""Universal Database Inspector: Views tables and rows in PostgreSQL or SQLite."""

import asyncio
import sys
from pathlib import Path

# Add gateway path
sys.path.insert(0, "apex-gateway")
from sqlalchemy import select, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.database.models import User, UserApiKey, ChatRoom, ChatMessage, RequestLog


async def inspect_db():
    settings = get_settings()
    url = settings.APEX_DATABASE_URL
    print("=" * 65)
    print(f" DATABASE INSPECTOR: {url}")
    print("=" * 65)

    is_sqlite = "sqlite" in url
    engine = create_async_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )

    models = [
        ("users", User),
        ("user_api_keys", UserApiKey),
        ("chat_rooms", ChatRoom),
        ("chat_messages", ChatMessage),
        ("request_logs", RequestLog),
    ]

    async with engine.connect() as conn:
        for name, model_cls in models:
            print(f"\n--- TABLE: {name} ---")
            res = await conn.execute(select(model_cls).limit(5))
            rows = res.fetchall()
            if not rows:
                print("  (Empty table - 0 rows)")
            else:
                for r in rows:
                    print(f"  {r}")

    await engine.dispose()
    print("\n" + "=" * 65)


if __name__ == "__main__":
    asyncio.run(inspect_db())

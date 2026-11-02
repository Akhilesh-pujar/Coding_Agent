"""Data migration script: Transfers all tables and rows from SQLite (apex.db) to PostgreSQL."""

import asyncio
import sys
from pathlib import Path

# Add gateway path
sys.path.insert(0, "apex-gateway")
from sqlalchemy import select, inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import get_settings
from app.database.models import Base, User, UserApiKey, ChatRoom, ChatMessage, RequestLog


async def migrate():
    settings = get_settings()

    if "postgres" not in settings.APEX_DATABASE_URL:
        print("ERROR: APEX_DATABASE_URL in .env is not pointing to PostgreSQL.")
        print(f"Current URL: {settings.APEX_DATABASE_URL}")
        print("Please set: APEX_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/apex_db")
        return

    sqlite_path = Path("apex.db")
    if not sqlite_path.exists():
        sqlite_path = Path("apex-gateway/apex.db")

    if not sqlite_path.exists():
        print(f"No existing SQLite database found at {sqlite_path}. Initializing clean PostgreSQL schema.")
        pg_engine = create_async_engine(settings.APEX_DATABASE_URL)
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("PostgreSQL tables created successfully!")
        return

    print(f"Connecting to SQLite: {sqlite_path}")
    print(f"Connecting to PostgreSQL: {settings.APEX_DATABASE_URL}")

    sqlite_engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite_path}")
    pg_engine = create_async_engine(settings.APEX_DATABASE_URL)

    # 1. Initialize PostgreSQL Schema
    print("\n[1/5] Creating PostgreSQL tables...")
    async with pg_engine.begin() as pg_conn:
        await pg_conn.run_sync(Base.metadata.create_all)

    SqliteSession = async_sessionmaker(bind=sqlite_engine)
    PgSession = async_sessionmaker(bind=pg_engine)

    async with SqliteSession() as src, PgSession() as dest:
        # 2. Migrate Users
        print("[2/5] Migrating Users...")
        users = (await src.execute(select(User))).scalars().all()
        for u in users:
            dest.add(User(
                id=u.id,
                username=u.username,
                email=u.email,
                hashed_password=u.hashed_password,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
            ))
        await dest.commit()
        print(f"      Transferred {len(users)} users.")

        # 3. Migrate UserApiKeys
        print("[3/5] Migrating User API Keys...")
        keys = (await src.execute(select(UserApiKey))).scalars().all()
        for k in keys:
            dest.add(UserApiKey(
                id=k.id,
                user_id=k.user_id,
                name=k.name,
                key_prefix=k.key_prefix,
                key_hash=k.key_hash,
                is_active=k.is_active,
                created_at=k.created_at,
                expires_at=k.expires_at,
            ))
        await dest.commit()
        print(f"      Transferred {len(keys)} API keys.")

        # 4. Migrate ChatRooms & Messages
        print("[4/5] Migrating Chat Rooms...")
        rooms = (await src.execute(select(ChatRoom))).scalars().all()
        for r in rooms:
            dest.add(ChatRoom(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                default_model=r.default_model,
                system_prompt=r.system_prompt,
                created_at=r.created_at,
                updated_at=r.updated_at,
            ))
        await dest.commit()
        print(f"      Transferred {len(rooms)} chat rooms.")

        print("      Migrating Chat Messages...")
        msgs = (await src.execute(select(ChatMessage))).scalars().all()
        for m in msgs:
            dest.add(ChatMessage(
                id=m.id,
                room_id=m.room_id,
                role=m.role,
                content=m.content,
                model_used=m.model_used,
                prompt_tokens=m.prompt_tokens,
                completion_tokens=m.completion_tokens,
                created_at=m.created_at,
            ))
        await dest.commit()
        print(f"      Transferred {len(msgs)} chat messages.")

        # 5. Migrate Request Logs
        print("[5/5] Migrating Request Logs...")
        logs = (await src.execute(select(RequestLog))).scalars().all()
        for l in logs:
            dest.add(RequestLog(
                id=l.id,
                request_id=l.request_id,
                timestamp=l.timestamp,
                endpoint=l.endpoint,
                selected_model=l.selected_model,
                is_stream=l.is_stream,
                duration_ms=l.duration_ms,
                http_status=l.http_status,
                prompt_tokens=l.prompt_tokens,
                completion_tokens=l.completion_tokens,
                total_tokens=l.total_tokens,
                success=l.success,
                error_message=l.error_message,
            ))
        await dest.commit()
        print(f"      Transferred {len(logs)} audit log entries.")

    print("\n[✓] Full migration completed successfully! You can now view all data in pgAdmin.")


if __name__ == "__main__":
    asyncio.run(migrate())


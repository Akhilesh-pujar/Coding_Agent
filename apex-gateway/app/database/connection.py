"""Database connection and session management using SQLAlchemy 2.x async engine."""

import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings
from app.database.models import Base, RequestLog

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.APEX_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.APEX_DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


_db_initialized: bool = False


async def init_db() -> None:
    """Initialize database tables asynchronously."""
    global _db_initialized
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _db_initialized = True
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions to request handlers."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def record_audit_log(
    request_id: str,
    endpoint: str,
    selected_model: str,
    is_stream: bool,
    duration_ms: float,
    http_status: int,
    success: bool,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    error_message: str | None = None,
) -> None:
    """Safely log request performance and status metrics to SQLite."""
    global _db_initialized
    try:
        if not _db_initialized:
            await init_db()
        async with AsyncSessionLocal() as session:
            async with session.begin():
                log_entry = RequestLog(
                    request_id=request_id,
                    endpoint=endpoint,
                    selected_model=selected_model,
                    is_stream=is_stream,
                    duration_ms=duration_ms,
                    http_status=http_status,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    success=success,
                    error_message=error_message[:500] if error_message else None,
                )
                session.add(log_entry)
            await session.commit()
    except Exception as e:
        # DB audit logging failure should not crash the gateway or client request
        logger.warning(f"Could not write request audit log: {e}")


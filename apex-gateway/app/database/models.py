"""SQLAlchemy 2.x models for request audit and performance metrics."""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(128), default="/v1/chat/completions", nullable=False)
    selected_model: Mapped[str] = mapped_column(String(128), nullable=False)
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return f"<RequestLog id={self.id} req_id={self.request_id} model={self.selected_model} status={self.http_status}>"


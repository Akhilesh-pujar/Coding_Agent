"""Structured and secure logging configuration for APEX Gateway."""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.config import get_settings


class SensitiveDataFilter(logging.Filter):
    """Filter out or mask sensitive information such as Bearer tokens and API keys."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            # Mask potential bearer tokens or api keys in log messages
            settings = get_settings()
            if settings.APEX_API_KEY and len(settings.APEX_API_KEY) > 4:
                record.msg = record.msg.replace(settings.APEX_API_KEY, "[MASKED_API_KEY]")
        return True


def setup_logging() -> None:
    """Initialize structured logging to stdout and rotating log file."""
    settings = get_settings()
    log_level = getattr(logging, settings.APEX_LOG_LEVEL.upper(), logging.INFO)

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "apex_gateway.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)

    # Rotating File Handler (max 10MB per file, up to 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(file_handler)

    # Reduce verbosity of noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


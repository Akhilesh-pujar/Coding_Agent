"""APEX API Gateway main application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.core.logging_config import setup_logging
from app.database.connection import init_db
from app.dependencies import get_ollama_client
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.chat import router as chat_router
from app.api.routing import router as routing_router
from app.api.auth import router as auth_router
from app.api.rooms import router as rooms_router

logger = logging.getLogger("apex.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup setup and graceful shutdown."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Initializing APEX API Gateway v{settings.APEX_VERSION} on {settings.APEX_HOST}:{settings.APEX_PORT}")

    # Initialize SQLite database
    try:
        await init_db()
        logger.info("SQLite audit database initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

    # Probe Ollama on startup
    ollama_client = get_ollama_client()
    health = await ollama_client.check_health()
    if health.get("connected"):
        logger.info(f"Ollama server connected at {settings.OLLAMA_BASE_URL} (version: {health.get('version')})")
    else:
        logger.warning(
            f"Ollama is not reachable at {settings.OLLAMA_BASE_URL}. Gateway will run in degraded mode until Ollama starts."
        )

    yield

    logger.info("Shutting down APEX API Gateway...")
    await ollama_client.close()
    logger.info("Ollama client connection pool closed.")


def create_app() -> FastAPI:
    """Application factory for APEX API Gateway."""
    settings = get_settings()

    application = FastAPI(
        title="APEX API Gateway",
        description="Unified OpenAI-compatible gateway for local AI models with intelligent routing.",
        version=settings.APEX_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration for local IDE tools (VS Code, Antigravity, MCP Clients)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request size limiter middleware
    @application.middleware("http")
    async def limit_request_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_REQUEST_BODY_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": {
                        "message": f"Request body exceeds maximum allowed size of {settings.MAX_REQUEST_BODY_SIZE} bytes.",
                        "type": "invalid_request_error",
                        "code": "request_too_large",
                    }
                },
            )
        return await call_next(request)

    # Exception Handlers formatted to OpenAI error schema
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": str(detail),
                    "type": "invalid_request_error" if exc.status_code < 500 else "api_error",
                    "code": str(exc.status_code),
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Invalid request parameters.",
                    "type": "invalid_request_error",
                    "details": exc.errors(),
                    "code": "parameter_validation_failed",
                }
            },
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": "An internal server error occurred.",
                    "type": "internal_server_error",
                    "code": "internal_error",
                }
            },
        )

    # Register Routers
    application.include_router(health_router)
    application.include_router(models_router)
    application.include_router(chat_router)
    application.include_router(routing_router)
    application.include_router(auth_router)
    application.include_router(rooms_router)

    return application


app = create_app()


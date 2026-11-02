"""Health monitoring endpoint for APEX API Gateway."""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends
from app.config import get_settings
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.dependencies import get_ollama_client, get_model_registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Gateway health check")
async def health_check(
    ollama_client: OllamaClient = Depends(get_ollama_client),
    model_registry: ModelRegistry = Depends(get_model_registry),
) -> Dict[str, Any]:
    """Inspect status of gateway, Ollama connectivity, and locally available models."""
    settings = get_settings()

    # 1. Probe Ollama health
    ollama_health = await ollama_client.check_health()
    ollama_connected = ollama_health.get("connected", False)

    # 2. Probe available models
    available_models = []
    apex_fast_verified = False
    apex_pro_verified = False

    if ollama_connected:
        try:
            available_models = await model_registry.get_installed_model_names()
            apex_fast_verified = any(settings.APEX_FAST_MODEL in m for m in available_models)
            apex_pro_verified = any(settings.APEX_PRO_MODEL in m for m in available_models)
        except Exception as e:
            logger.warning(f"Error checking model list in health check: {e}")

    # Determine overall gateway status
    if not ollama_connected:
        gateway_status = "degraded (ollama unreachable)"
    elif not apex_fast_verified and not apex_pro_verified:
        gateway_status = "degraded (configured apex models missing)"
    else:
        gateway_status = "healthy"

    return {
        "gateway_status": gateway_status,
        "gateway_version": settings.APEX_VERSION,
        "ollama_connectivity": {
            "connected": ollama_connected,
            "base_url": settings.OLLAMA_BASE_URL,
            "version": ollama_health.get("version"),
            "error": ollama_health.get("error"),
        },
        "model_status": {
            "apex_fast_model": settings.APEX_FAST_MODEL,
            "apex_fast_verified": apex_fast_verified,
            "apex_pro_model": settings.APEX_PRO_MODEL,
            "apex_pro_verified": apex_pro_verified,
            "installed_models_count": len(available_models),
            "installed_models": available_models,
        },
    }


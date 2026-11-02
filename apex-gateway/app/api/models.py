"""OpenAI-compatible model listing endpoint."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.model_registry import ModelRegistry
from app.core.ollama_client import OllamaConnectionError
from app.dependencies import get_model_registry, verify_api_key
from app.schemas.models import ModelListResponse, ModelCard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Models"])


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List available models (OpenAI compatible)",
)
async def list_models(
    model_registry: ModelRegistry = Depends(get_model_registry),
    _: str = Depends(verify_api_key),
) -> ModelListResponse:
    """Discover available models from the local Ollama instance."""
    try:
        models = await model_registry.get_all_models_openai_format()
        cards = [ModelCard(**m) for m in models]
        return ModelListResponse(object="list", data=cards)
    except OllamaConnectionError as e:
        logger.error(f"Ollama connection error during model discovery: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "message": "Local Ollama service is unreachable.",
                    "type": "service_unavailable",
                    "code": "ollama_unavailable",
                }
            },
        )
    except Exception as e:
        logger.error(f"Error fetching models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": str(e), "type": "internal_server_error"}},
        )


"""Routing service orchestrating model selection decisions and model validation."""

import logging
from typing import Any, Dict, List
from app.config import get_settings
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.schemas.models import RouteRequest, RouteResponse

logger = logging.getLogger(__name__)


class RoutingService:
    """Evaluates requests to choose between fast and pro models."""

    def __init__(self, model_router: ModelRouter, model_registry: ModelRegistry) -> None:
        self.router = model_router
        self.registry = model_registry
        self.settings = get_settings()

    async def determine_route(self, route_req: RouteRequest) -> RouteResponse:
        """Analyze prompt/messages and return optimal model routing."""
        messages: List[Dict[str, Any]] = []

        if route_req.messages:
            messages = [m.model_dump() for m in route_req.messages]
        elif route_req.prompt:
            messages = [{"role": "user", "content": route_req.prompt}]

        selected_model, reason, confidence, classification = self.router.route(
            messages=messages,
            requested_model=route_req.model,
            task_hint=route_req.task_hint,
        )

        # Retrieve available models
        try:
            available_models = await self.registry.get_installed_model_names()
        except Exception as e:
            logger.warning(f"Unable to query Ollama for model list in router: {e}")
            available_models = [self.settings.APEX_FAST_MODEL, self.settings.APEX_PRO_MODEL]

        return RouteResponse(
            selected_model=selected_model,
            routing_reason=reason,
            confidence=confidence,
            classification=classification,
            available_models=available_models,
        )


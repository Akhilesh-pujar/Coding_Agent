"""Routing diagnostic and decision endpoint for APEX."""

import logging
from fastapi import APIRouter, Depends
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.dependencies import (
    get_model_registry,
    get_model_router,
    verify_api_key,
)
from app.schemas.models import RouteRequest, RouteResponse
from app.services.routing_service import RoutingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Routing"])


def get_routing_service(
    router_inst: ModelRouter = Depends(get_model_router),
    registry: ModelRegistry = Depends(get_model_registry),
) -> RoutingService:
    return RoutingService(router_inst, registry)


@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Evaluate task and recommend optimal model",
)
async def route_task(
    req: RouteRequest,
    service: RoutingService = Depends(get_routing_service),
    _: str = Depends(verify_api_key),
) -> RouteResponse:
    """Analyze messages or prompt to determine whether to use apex-fast or apex-pro."""
    return await service.determine_route(req)


"""API routers for persistent multi-room chat sessions."""

from typing import List, Union
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import User
from app.dependencies import (
    get_ollama_client,
    get_model_registry,
    get_model_router,
    get_current_user,
)
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.schemas.rooms import (
    CreateRoomRequest,
    UpdateRoomRequest,
    RoomSummaryResponse,
    RoomDetailResponse,
    RoomMessageResponse,
    RoomChatRequest,
)
from app.services.room_service import RoomService

router = APIRouter(prefix="/v1/rooms", tags=["Chat Rooms"])


def get_room_service(
    db: AsyncSession = Depends(get_db),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    model_registry: ModelRegistry = Depends(get_model_registry),
    model_router: ModelRouter = Depends(get_model_router),
) -> RoomService:
    return RoomService(db, ollama_client, model_registry, model_router)


@router.post(
    "",
    response_model=RoomDetailResponse,
    summary="Create a new chat room",
)
async def create_room(
    req: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomDetailResponse:
    """Create a new isolated chat room with optional title and system prompt."""
    return await service.create_room(current_user.id, req)


@router.get(
    "",
    response_model=List[RoomSummaryResponse],
    summary="List all chat rooms for current user",
)
async def list_rooms(
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> List[RoomSummaryResponse]:
    """Retrieve list of user's active chat rooms with message counts."""
    return await service.list_rooms(current_user.id)


@router.get(
    "/{room_id}",
    response_model=RoomDetailResponse,
    summary="Get room details and full conversation history",
)
async def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomDetailResponse:
    """Retrieve full conversation history for a specific room."""
    return await service.get_room_detail(current_user.id, room_id)


@router.patch(
    "/{room_id}",
    response_model=RoomDetailResponse,
    summary="Update room title or configuration",
)
async def update_room(
    room_id: str,
    req: UpdateRoomRequest,
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomDetailResponse:
    """Update title, default model, or system prompt for a chat room."""
    return await service.update_room(current_user.id, room_id, req)


@router.delete(
    "/{room_id}",
    summary="Delete room and conversation history",
)
async def delete_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> dict:
    """Permanently delete a chat room and all messages."""
    return await service.delete_room(current_user.id, room_id)


@router.post(
    "/{room_id}/chat",
    response_model=None,
    summary="Send message in chat room (with automatic context & history persistence)",
)
async def chat_in_room(
    room_id: str,
    req: RoomChatRequest,
    current_user: User = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> Union[RoomMessageResponse, StreamingResponse]:
    """Send message to room.

    Gateway automatically retrieves previous conversation turns, applies sliding window context,
    routes to optimal model, records user and assistant turns in the database, and returns response.
    """
    if req.stream:
        return StreamingResponse(
            service.stream_room_chat(current_user.id, room_id, req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream; charset=utf-8",
                "X-Accel-Buffering": "no",
            },
        )

    return await service.execute_room_chat(current_user.id, room_id, req)


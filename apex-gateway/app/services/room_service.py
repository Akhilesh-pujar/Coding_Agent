"""Room service managing persistent chat rooms, sliding-window context, and history."""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.database.models import ChatRoom, ChatMessage
from app.schemas.rooms import (
    CreateRoomRequest,
    UpdateRoomRequest,
    RoomSummaryResponse,
    RoomDetailResponse,
    RoomMessageResponse,
    RoomChatRequest,
)

logger = logging.getLogger(__name__)

# Max messages from history to feed as context (sliding window)
MAX_CONTEXT_MESSAGES = 12


class RoomService:
    """Orchestrates room creation, history persistence, and context-aware chat."""

    def __init__(
        self,
        db: AsyncSession,
        ollama_client: OllamaClient,
        model_registry: ModelRegistry,
        model_router: ModelRouter,
    ) -> None:
        self.db = db
        self.client = ollama_client
        self.registry = model_registry
        self.router = model_router

    async def create_room(self, user_id: int, req: CreateRoomRequest) -> RoomDetailResponse:
        """Create a new chat room with optional initial system prompt."""
        room_id = f"room_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)

        room = ChatRoom(
            id=room_id,
            user_id=user_id,
            title=req.title.strip() if req.title else "New Chat",
            default_model=req.default_model or "auto",
            system_prompt=req.system_prompt.strip() if req.system_prompt else None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(room)

        # If system prompt is provided, seed the room with a system message
        if req.system_prompt:
            sys_msg = ChatMessage(
                room_id=room_id,
                role="system",
                content=req.system_prompt.strip(),
                created_at=now,
            )
            self.db.add(sys_msg)

        await self.db.commit()
        return await self.get_room_detail(user_id, room_id)

    async def list_rooms(self, user_id: int) -> List[RoomSummaryResponse]:
        """List all rooms belonging to a user, with total message counts."""
        stmt = (
            select(
                ChatRoom,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatRoom.id == ChatMessage.room_id)
            .where(ChatRoom.user_id == user_id)
            .group_by(ChatRoom.id)
            .order_by(ChatRoom.updated_at.desc())
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        summaries = []
        for room, count in rows:
            summaries.append(
                RoomSummaryResponse(
                    id=room.id,
                    title=room.title,
                    default_model=room.default_model,
                    message_count=count,
                    created_at=room.created_at,
                    updated_at=room.updated_at,
                )
            )
        return summaries

    async def get_room_detail(self, user_id: int, room_id: str) -> RoomDetailResponse:
        """Fetch full room details and message history (isolated to room owner)."""
        stmt = (
            select(ChatRoom)
            .options(selectinload(ChatRoom.messages))
            .where(ChatRoom.id == room_id, ChatRoom.user_id == user_id)
        )
        res = await self.db.execute(stmt)
        room = res.scalar_one_or_none()

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Room '{room_id}' not found.", "type": "room_not_found"}},
            )

        msg_responses = [RoomMessageResponse.model_validate(m) for m in room.messages]
        return RoomDetailResponse(
            id=room.id,
            title=room.title,
            default_model=room.default_model,
            system_prompt=room.system_prompt,
            created_at=room.created_at,
            updated_at=room.updated_at,
            messages=msg_responses,
        )

    async def update_room(self, user_id: int, room_id: str, req: UpdateRoomRequest) -> RoomDetailResponse:
        """Update room metadata (title, default model, or system prompt)."""
        stmt = select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.user_id == user_id)
        res = await self.db.execute(stmt)
        room = res.scalar_one_or_none()

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Room '{room_id}' not found.", "type": "room_not_found"}},
            )

        if req.title is not None:
            room.title = req.title.strip()
        if req.default_model is not None:
            room.default_model = req.default_model
        if req.system_prompt is not None:
            room.system_prompt = req.system_prompt

        room.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return await self.get_room_detail(user_id, room_id)

    async def delete_room(self, user_id: int, room_id: str) -> dict:
        """Delete room and all associated messages."""
        stmt = select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.user_id == user_id)
        res = await self.db.execute(stmt)
        room = res.scalar_one_or_none()

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Room '{room_id}' not found.", "type": "room_not_found"}},
            )

        await self.db.delete(room)
        await self.db.commit()
        return {"message": f"Room '{room_id}' deleted successfully."}

    def _build_context(
        self, room: ChatRoom, new_user_message: str
    ) -> List[Dict[str, str]]:
        """Construct sliding-window message context for Ollama."""
        context: List[Dict[str, str]] = []

        # System prompt first
        if room.system_prompt:
            context.append({"role": "system", "content": room.system_prompt})

        # Recent conversation history
        non_system_messages = [m for m in room.messages if m.role != "system"]
        sliced_history = non_system_messages[-MAX_CONTEXT_MESSAGES:]
        for m in sliced_history:
            context.append({"role": m.role, "content": m.content})

        # Append new user prompt
        context.append({"role": "user", "content": new_user_message})
        return context

    async def _resolve_model(self, room: ChatRoom, context: List[Dict[str, str]], override_model: Optional[str]) -> str:
        """Resolve requested or default model with auto-routing fallback."""
        model_candidate = override_model or room.default_model
        if not model_candidate or model_candidate.lower() in ("auto", "default"):
            target_model, reason, confidence, _ = self.router.route(
                messages=context,
                requested_model=None,
            )
            logger.info(f"Room {room.id} auto-routed to '{target_model}' ({reason})")
        else:
            target_model, _, _, _ = self.router.route(requested_model=model_candidate)

        # Verify model exists
        if not await self.registry.is_model_available(target_model):
            alt = target_model + ":latest" if ":" not in target_model else target_model.split(":")[0]
            if await self.registry.is_model_available(alt):
                target_model = alt
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"message": f"Model '{target_model}' not found in Ollama.", "type": "model_not_found"}},
                )
        return target_model

    async def execute_room_chat(
        self, user_id: int, room_id: str, req: RoomChatRequest
    ) -> RoomMessageResponse:
        """Process chat message in room, persist turns to DB, and return assistant response."""
        stmt = (
            select(ChatRoom)
            .options(selectinload(ChatRoom.messages))
            .where(ChatRoom.id == room_id, ChatRoom.user_id == user_id)
        )
        res = await self.db.execute(stmt)
        room = res.scalar_one_or_none()

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Room '{room_id}' not found.", "type": "room_not_found"}},
            )

        now = datetime.now(timezone.utc)
        context = self._build_context(room, req.message)
        target_model = await self._resolve_model(room, context, req.model)

        # 1. Save user message to database
        user_msg = ChatMessage(
            room_id=room_id,
            role="user",
            content=req.message.strip(),
            created_at=now,
        )
        self.db.add(user_msg)

        # 2. Query Ollama
        payload = {
            "model": target_model,
            "messages": context,
            "stream": False,
            "options": {"temperature": req.temperature},
        }
        ollama_resp = await self.client.chat_completion(payload)

        assistant_content = ollama_resp.get("message", {}).get("content", "")
        prompt_tokens = ollama_resp.get("prompt_eval_count", 0)
        completion_tokens = ollama_resp.get("eval_count", 0)

        # 3. Save assistant response to database
        assistant_msg = ChatMessage(
            room_id=room_id,
            role="assistant",
            content=assistant_content,
            model_used=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(assistant_msg)

        # 4. Update room title if it was the first turn and still default "New Chat"
        if room.title == "New Chat" and len(room.messages) <= 1:
            words = req.message.strip().split()
            room.title = " ".join(words[:6])[:60]

        room.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(assistant_msg)

        return RoomMessageResponse.model_validate(assistant_msg)

    async def stream_room_chat(
        self, user_id: int, room_id: str, req: RoomChatRequest
    ) -> AsyncGenerator[str, None]:
        """Stream SSE chunks for room conversation and commit full messages to DB upon completion."""
        stmt = (
            select(ChatRoom)
            .options(selectinload(ChatRoom.messages))
            .where(ChatRoom.id == room_id, ChatRoom.user_id == user_id)
        )
        res = await self.db.execute(stmt)
        room = res.scalar_one_or_none()

        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"message": f"Room '{room_id}' not found.", "type": "room_not_found"}},
            )

        now = datetime.now(timezone.utc)
        context = self._build_context(room, req.message)
        target_model = await self._resolve_model(room, context, req.model)

        # Save user message immediately
        user_msg = ChatMessage(
            room_id=room_id,
            role="user",
            content=req.message.strip(),
            created_at=now,
        )
        self.db.add(user_msg)
        await self.db.commit()

        payload = {
            "model": target_model,
            "messages": context,
            "stream": True,
            "options": {"temperature": req.temperature},
        }

        full_content = []
        prompt_tokens = 0
        completion_tokens = 0

        try:
            async for chunk in self.client.stream_chat_completion(payload):
                content = chunk.get("message", {}).get("content", "")
                done = chunk.get("done", False)

                if done:
                    prompt_tokens = chunk.get("prompt_eval_count", 0)
                    completion_tokens = chunk.get("eval_count", 0)
                    yield f"data: {json.dumps({'model': target_model, 'done': True, 'tokens': {'prompt': prompt_tokens, 'completion': completion_tokens}})}\n\n"
                    break

                if content:
                    full_content.append(content)
                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

            yield "data: [DONE]\n\n"

        finally:
            # Commit assistant message to database
            assistant_text = "".join(full_content)
            if assistant_text:
                assistant_msg = ChatMessage(
                    room_id=room_id,
                    role="assistant",
                    content=assistant_text,
                    model_used=target_model,
                    prompt_tokens=prompt_tokens if prompt_tokens > 0 else None,
                    completion_tokens=completion_tokens if completion_tokens > 0 else None,
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(assistant_msg)

                if room.title == "New Chat":
                    words = req.message.strip().split()
                    room.title = " ".join(words[:6])[:60]

                room.updated_at = datetime.now(timezone.utc)
                await self.db.commit()


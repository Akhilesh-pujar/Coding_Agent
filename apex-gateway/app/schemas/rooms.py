"""Pydantic schemas for chat rooms and persistent conversation history."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    title: Optional[str] = Field(default="New Chat", max_length=128, description="Room title")
    default_model: Optional[str] = Field(default="auto", description="Model preference (auto, apex-fast, apex-pro)")
    system_prompt: Optional[str] = Field(default=None, description="Optional system instruction for this room")


class UpdateRoomRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=128)
    default_model: Optional[str] = None
    system_prompt: Optional[str] = None


class RoomMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    model_used: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomSummaryResponse(BaseModel):
    id: str
    title: str
    default_model: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoomDetailResponse(BaseModel):
    id: str
    title: str
    default_model: str
    system_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[RoomMessageResponse]

    model_config = {"from_attributes": True}


class RoomChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt to send to the room")
    model: Optional[str] = Field(default=None, description="Override room's default model")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    stream: Optional[bool] = Field(default=False, description="Whether to stream response via SSE")


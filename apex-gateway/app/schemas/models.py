"""Pydantic schemas for OpenAI-compatible model listing and APEX routing."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.chat import ChatMessage


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "apex-local"
    permission: List[Dict[str, Any]] = []
    root: Optional[str] = None
    parent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelCard]


class RouteRequest(BaseModel):
    prompt: Optional[str] = Field(default=None, description="Raw prompt text to evaluate")
    messages: Optional[List[ChatMessage]] = Field(default=None, description="Chat messages to evaluate")
    task_hint: Optional[str] = Field(
        default=None,
        description="Explicit hint like 'architecture', 'debugging', 'simple', 'documentation'"
    )
    model: Optional[str] = Field(default=None, description="Explicit model selection if desired")


class RouteResponse(BaseModel):
    selected_model: str
    routing_reason: str
    confidence: float
    classification: str
    available_models: List[str]


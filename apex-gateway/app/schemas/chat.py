"""Pydantic schemas for OpenAI-compatible chat completions."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = Field(
        default=None,
        description="ID of the model to use. If omitted or 'auto', automatically routes to fast or pro.",
    )
    messages: List[ChatMessage] = Field(
        ..., min_length=1, description="A list of messages comprising the conversation so far."
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = Field(default=False)
    stop: Optional[Union[str, List[str]]] = Field(default=None)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    user: Optional[str] = None

    model_config = {"extra": "ignore"}


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo
    system_fingerprint: Optional[str] = "apex-gw-1.0"


class ChatDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatStreamChoice(BaseModel):
    index: int = 0
    delta: ChatDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatStreamChoice]
    usage: Optional[UsageInfo] = None
    system_fingerprint: Optional[str] = "apex-gw-1.0"


class CompletionRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="ID of model or 'auto'")
    prompt: Union[str, List[str]] = Field(..., description="Prompt string or list of prompt strings")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = Field(default=False)
    stop: Optional[Union[str, List[str]]] = Field(default=None)

    model_config = {"extra": "ignore"}


class CompletionChoice(BaseModel):
    text: str
    index: int = 0
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = "stop"


class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: List[CompletionChoice]
    usage: UsageInfo


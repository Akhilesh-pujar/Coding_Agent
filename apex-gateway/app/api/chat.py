"""OpenAI-compatible chat completions endpoint supporting streaming and non-streaming."""

import uuid
import logging
from typing import Union
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.dependencies import (
    get_ollama_client,
    get_model_registry,
    get_model_router,
    verify_api_key,
)
from app.core.ollama_client import OllamaClient
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    CompletionChoice,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat"])


def get_chat_service(
    client: OllamaClient = Depends(get_ollama_client),
    registry: ModelRegistry = Depends(get_model_registry),
    router_inst: ModelRouter = Depends(get_model_router),
) -> ChatService:
    return ChatService(client, registry, router_inst)


@router.post(
    "/chat/completions",
    response_model=None,
    summary="Create chat completion (OpenAI compatible)",
)
async def create_chat_completion(
    req: ChatCompletionRequest,
    service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key),
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """Execute chat completion request with auto-routing, streaming, and audit logging."""
    request_id = f"chatcmpl-{uuid.uuid4().hex}"

    if req.stream:
        return StreamingResponse(
            service.stream_completion(req, request_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream; charset=utf-8",
                "X-Accel-Buffering": "no",
            },
        )

    return await service.process_completion(req, request_id)


@router.post(
    "/completions",
    response_model=CompletionResponse,
    summary="Create text completion (OpenAI compatible)",
)
async def create_text_completion(
    req: CompletionRequest,
    service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key),
) -> CompletionResponse:
    """Execute text completion by converting prompt into chat format."""
    prompt_str = req.prompt if isinstance(req.prompt, str) else "\n".join(req.prompt)
    chat_req = ChatCompletionRequest(
        model=req.model,
        messages=[ChatMessage(role="user", content=prompt_str)],
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
        stream=False,
        stop=req.stop,
    )
    request_id = f"cmpl-{uuid.uuid4().hex}"
    chat_resp = await service.process_completion(chat_req, request_id)
    text = chat_resp.choices[0].message.content if chat_resp.choices else ""
    return CompletionResponse(
        id=request_id,
        created=chat_resp.created,
        model=chat_resp.model,
        choices=[CompletionChoice(text=text, index=0, finish_reason="stop")],
        usage=chat_resp.usage,
    )


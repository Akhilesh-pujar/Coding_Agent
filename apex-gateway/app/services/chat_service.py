"""Chat service orchestrating routing, Ollama interaction, streaming SSE, and metrics."""

import json
import time
import uuid
import logging
from typing import Any, AsyncGenerator, Dict, List
from fastapi import HTTPException, status
from app.config import get_settings
from app.core.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaResponseError,
)
from app.core.model_registry import ModelRegistry
from app.core.model_router import ModelRouter
from app.database.connection import record_audit_log
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatCompletionMessage,
    UsageInfo,
    ChatCompletionChunk,
    ChatStreamChoice,
    ChatDelta,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Coordinates chat completions, model routing, streaming SSE, and audit logging."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        model_registry: ModelRegistry,
        model_router: ModelRouter,
    ) -> None:
        self.client = ollama_client
        self.registry = model_registry
        self.router = model_router
        self.settings = get_settings()

    def _build_ollama_payload(
        self, req: ChatCompletionRequest, target_model: str, stream: bool
    ) -> Dict[str, Any]:
        """Convert OpenAI request parameters to Ollama format."""
        options: Dict[str, Any] = {}
        if req.temperature is not None:
            options["temperature"] = req.temperature
        if req.top_p is not None:
            options["top_p"] = req.top_p
        if req.max_tokens is not None:
            options["num_predict"] = req.max_tokens
        if req.stop is not None:
            options["stop"] = [req.stop] if isinstance(req.stop, str) else req.stop
        if req.frequency_penalty is not None and req.frequency_penalty != 0.0:
            options["frequency_penalty"] = req.frequency_penalty
        if req.presence_penalty is not None and req.presence_penalty != 0.0:
            options["presence_penalty"] = req.presence_penalty

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [m.model_dump(exclude_none=True) for m in req.messages],
            "stream": stream,
        }
        if options:
            payload["options"] = options

        return payload

    async def _resolve_and_verify_model(self, req: ChatCompletionRequest) -> str:
        """Resolve requested model or auto-route, then verify existence in Ollama."""
        target_model: str

        if not req.model or req.model.lower() in ("auto", "default", "apex-gateway"):
            target_model, reason, confidence, _ = self.router.route(
                messages=[m.model_dump() for m in req.messages],
                requested_model=None,
            )
            logger.info(
                f"Auto-routed request to '{target_model}' (confidence: {confidence:.2f}, reason: {reason})"
            )
        else:
            target_model, _, _, _ = self.router.route(
                messages=None,
                requested_model=req.model,
            )

        # Verify model actually exists in Ollama
        is_available = await self.registry.is_model_available(target_model)
        if not is_available:
            # Check without ':latest' or with ':latest'
            alt_name = (
                target_model + ":latest"
                if ":" not in target_model
                else target_model.split(":")[0]
            )
            if not await self.registry.is_model_available(alt_name):
                logger.warning(f"Requested model '{target_model}' not found in Ollama.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "message": f"The model '{target_model}' does not exist in local Ollama.",
                            "type": "invalid_request_error",
                            "param": "model",
                            "code": "model_not_found",
                        }
                    },
                )
            target_model = alt_name

        return target_model

    async def process_completion(
        self, req: ChatCompletionRequest, request_id: str
    ) -> ChatCompletionResponse:
        """Handle non-streaming OpenAI chat completion."""
        start_time = time.perf_counter()
        target_model = await self._resolve_and_verify_model(req)
        payload = self._build_ollama_payload(req, target_model, stream=False)

        try:
            ollama_resp = await self.client.chat_completion(payload)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Parse message content
            message_data = ollama_resp.get("message", {})
            content = message_data.get("content", "")
            role = message_data.get("role", "assistant")

            # Token metrics from Ollama
            prompt_tokens = ollama_resp.get("prompt_eval_count", 0)
            completion_tokens = ollama_resp.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens

            # OpenAI format response
            response = ChatCompletionResponse(
                id=request_id,
                created=int(time.time()),
                model=target_model,
                choices=[
                    ChatChoice(
                        index=0,
                        message=ChatCompletionMessage(role=role, content=content),
                        finish_reason="stop",
                    )
                ],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                ),
            )

            # Record metrics
            await record_audit_log(
                request_id=request_id,
                endpoint="/v1/chat/completions",
                selected_model=target_model,
                is_stream=False,
                duration_ms=elapsed_ms,
                http_status=200,
                success=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

            return response

        except OllamaConnectionError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            await record_audit_log(
                request_id=request_id,
                endpoint="/v1/chat/completions",
                selected_model=target_model,
                is_stream=False,
                duration_ms=elapsed_ms,
                http_status=503,
                success=False,
                error_message=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": {"message": str(e), "type": "service_unavailable", "code": "ollama_unavailable"}},
            )
        except OllamaTimeoutError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            await record_audit_log(
                request_id=request_id,
                endpoint="/v1/chat/completions",
                selected_model=target_model,
                is_stream=False,
                duration_ms=elapsed_ms,
                http_status=504,
                success=False,
                error_message=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": {"message": str(e), "type": "gateway_timeout", "code": "ollama_timeout"}},
            )
        except OllamaResponseError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            await record_audit_log(
                request_id=request_id,
                endpoint="/v1/chat/completions",
                selected_model=target_model,
                is_stream=False,
                duration_ms=elapsed_ms,
                http_status=e.status_code,
                success=False,
                error_message=e.message,
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": {"message": e.message, "type": "upstream_error", "code": "ollama_error"}},
            )

    async def stream_completion(
        self, req: ChatCompletionRequest, request_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI chat completion chunks formatted as Server-Sent Events (SSE)."""
        start_time = time.perf_counter()
        target_model = await self._resolve_and_verify_model(req)
        payload = self._build_ollama_payload(req, target_model, stream=True)

        created_ts = int(time.time())
        prompt_tokens = 0
        completion_tokens = 0
        success = True
        error_msg = None

        try:
            # Initial chunk providing the assistant role
            initial_chunk = ChatCompletionChunk(
                id=request_id,
                created=created_ts,
                model=target_model,
                choices=[ChatStreamChoice(index=0, delta=ChatDelta(role="assistant", content=""))],
            )
            yield f"data: {initial_chunk.model_dump_json()}\n\n"

            async for chunk in self.client.stream_chat_completion(payload):
                message = chunk.get("message", {})
                content = message.get("content", "")
                done = chunk.get("done", False)

                if done:
                    prompt_tokens = chunk.get("prompt_eval_count", 0)
                    completion_tokens = chunk.get("eval_count", 0)
                    total_tokens = prompt_tokens + completion_tokens

                    final_chunk = ChatCompletionChunk(
                        id=request_id,
                        created=created_ts,
                        model=target_model,
                        choices=[
                            ChatStreamChoice(
                                index=0,
                                delta=ChatDelta(),
                                finish_reason="stop",
                            )
                        ],
                        usage=UsageInfo(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                        ),
                    )
                    yield f"data: {final_chunk.model_dump_json()}\n\n"
                    break

                if content:
                    stream_chunk = ChatCompletionChunk(
                        id=request_id,
                        created=created_ts,
                        model=target_model,
                        choices=[
                            ChatStreamChoice(
                                index=0,
                                delta=ChatDelta(content=content),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {stream_chunk.model_dump_json()}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            success = False
            error_msg = str(e)
            logger.error(f"Error during stream processing: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "streaming_error",
                }
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"

        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            await record_audit_log(
                request_id=request_id,
                endpoint="/v1/chat/completions",
                selected_model=target_model,
                is_stream=True,
                duration_ms=elapsed_ms,
                http_status=200 if success else 500,
                success=success,
                prompt_tokens=prompt_tokens if prompt_tokens > 0 else None,
                completion_tokens=completion_tokens if completion_tokens > 0 else None,
                total_tokens=(prompt_tokens + completion_tokens) if (prompt_tokens + completion_tokens) > 0 else None,
                error_message=error_msg,
            )


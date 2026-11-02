"""Async client interface to local Ollama instance with timeout and error handling."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when the Ollama server cannot be reached."""
    pass


class OllamaTimeoutError(OllamaClientError):
    """Raised when an Ollama request times out."""
    pass


class OllamaResponseError(OllamaClientError):
    """Raised when Ollama returns an HTTP error status."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Ollama returned HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class OllamaClient:
    """Production-grade asynchronous HTTP client for Ollama."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or initialize reusable httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.OLLAMA_BASE_URL.rstrip("/"),
                timeout=httpx.Timeout(self.settings.APEX_REQUEST_TIMEOUT, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._client

    async def close(self) -> None:
        """Close client sessions cleanly."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def check_health(self) -> Dict[str, Any]:
        """Check Ollama connectivity and return version or status."""
        client = await self.get_client()
        try:
            resp = await client.get("/api/version")
            if resp.status_code == 200:
                data = resp.json()
                return {"connected": True, "version": data.get("version", "unknown")}
            return {"connected": False, "status_code": resp.status_code}
        except httpx.ConnectError:
            logger.warning("Ollama connection failed (ConnectError).")
            return {"connected": False, "error": "Connection refused"}
        except httpx.TimeoutException:
            logger.warning("Ollama connection timed out.")
            return {"connected": False, "error": "Connection timed out"}
        except Exception as e:
            logger.warning(f"Ollama connection probe failed: {e}")
            return {"connected": False, "error": str(e)}

    async def list_models(self) -> List[Dict[str, Any]]:
        """Fetch list of available models from Ollama /api/tags."""
        client = await self.get_client()
        try:
            resp = await client.get("/api/tags")
            if resp.status_code != 200:
                raise OllamaResponseError(resp.status_code, resp.text)
            data = resp.json()
            return data.get("models", [])
        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama /api/tags", exc_info=False)
            raise OllamaConnectionError(f"Cannot reach Ollama at {self.settings.OLLAMA_BASE_URL}") from e
        except httpx.TimeoutException as e:
            logger.error("Timeout connecting to Ollama /api/tags")
            raise OllamaTimeoutError("Timed out waiting for Ollama /api/tags") from e
        except OllamaResponseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in list_models: {e}", exc_info=True)
            raise OllamaClientError(str(e)) from e

    async def chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send non-streaming chat completion request to Ollama /api/chat."""
        client = await self.get_client()
        # Non-streaming enforces stream: false
        payload = {**payload, "stream": False}

        try:
            resp = await client.post("/api/chat", json=payload)
            if resp.status_code != 200:
                raise OllamaResponseError(resp.status_code, resp.text)
            return resp.json()
        except httpx.ConnectError as e:
            logger.error("Ollama connection error during chat_completion")
            raise OllamaConnectionError(f"Ollama unreachable at {self.settings.OLLAMA_BASE_URL}") from e
        except httpx.TimeoutException as e:
            logger.error("Ollama timeout during chat_completion")
            raise OllamaTimeoutError(f"Ollama timed out after {self.settings.APEX_REQUEST_TIMEOUT}s") from e
        except OllamaResponseError:
            raise
        except Exception as e:
            logger.error(f"Error executing chat completion: {e}", exc_info=True)
            raise OllamaClientError(str(e)) from e

    async def stream_chat_completion(
        self, payload: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat completions from Ollama /api/chat yielding parsed JSON chunks."""
        client = await self.get_client()
        payload = {**payload, "stream": True}

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise OllamaResponseError(response.status_code, error_text.decode("utf-8", errors="replace"))

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except json.JSONDecodeError as jde:
                        logger.warning(f"Failed to parse Ollama stream chunk: {line} - {jde}")
                        continue
        except httpx.ConnectError as e:
            logger.error("Ollama connection error during streaming")
            raise OllamaConnectionError(f"Ollama unreachable at {self.settings.OLLAMA_BASE_URL}") from e
        except httpx.TimeoutException as e:
            logger.error("Ollama timeout during streaming")
            raise OllamaTimeoutError("Streaming response from Ollama timed out") from e
        except OllamaResponseError:
            raise
        except Exception as e:
            logger.error(f"Error during streaming chat: {e}", exc_info=True)
            raise OllamaClientError(str(e)) from e


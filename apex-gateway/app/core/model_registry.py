"""Model registry for tracking and verifying models against Ollama instance."""

import time
import logging
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Manages model catalog and verifies existence against Ollama."""

    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama_client = ollama_client
        self.settings = get_settings()
        self._cache_time: float = 0.0
        self._cached_models: List[Dict[str, Any]] = []
        self._cache_ttl_seconds: float = 30.0  # 30-second cache

    def _normalize_name(self, name: str) -> str:
        """Normalize model name (e.g., 'apex-fast' -> 'apex-fast:latest')."""
        name = name.strip()
        if ":" not in name:
            return f"{name}:latest"
        return name

    async def refresh_models(self, force: bool = False) -> List[Dict[str, Any]]:
        """Fetch models from Ollama with TTL caching."""
        now = time.time()
        if not force and self._cached_models and (now - self._cache_time < self._cache_ttl_seconds):
            return self._cached_models

        try:
            models_data = await self.ollama_client.list_models()
            self._cached_models = models_data
            self._cache_time = now
            logger.debug(f"Refreshed model cache: {len(self._cached_models)} models found.")
        except Exception as e:
            logger.warning(f"Failed to refresh model registry from Ollama: {e}")
            if force or not self._cached_models:
                raise
        return self._cached_models

    async def get_installed_model_names(self) -> List[str]:
        """Return list of normalized model names currently installed in Ollama."""
        models = await self.refresh_models()
        names: List[str] = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                names.append(self._normalize_name(name))
        return names

    async def is_model_available(self, model_name: str) -> bool:
        """Check if a model exists in Ollama."""
        normalized = self._normalize_name(model_name)
        available = await self.get_installed_model_names()
        return normalized in available

    async def get_all_models_openai_format(self) -> List[Dict[str, Any]]:
        """Return models formatted for OpenAI /v1/models endpoint."""
        raw_models = await self.refresh_models()
        openai_models: List[Dict[str, Any]] = []

        seen = set()
        for m in raw_models:
            name = m.get("name") or m.get("model")
            if not name:
                continue
            normalized = self._normalize_name(name)
            if normalized in seen:
                continue
            seen.add(normalized)

            created_timestamp = int(self._cache_time or time.time())
            # Parse details
            details = m.get("details", {})
            openai_models.append(
                {
                    "id": normalized,
                    "object": "model",
                    "created": created_timestamp,
                    "owned_by": "apex-local",
                    "permission": [],
                    "root": normalized,
                    "parent": None,
                    "details": details,
                }
            )

        return openai_models


"""Intelligent Model Router for APEX.

Decides between apex-fast and apex-pro based on task complexity, heuristics,
context length, or explicit user selection.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from app.config import get_settings

logger = logging.getLogger(__name__)

# Heuristic patterns for complex software engineering tasks
COMPLEX_PATTERNS = [
    r"\barchitecture\b",
    r"\bsystem\s+design\b",
    r"\brefactor(ing)?\b",
    r"\bconcurrency\b|\brace\s+condition\b|\bdeadlock\b",
    r"\bmemory\s+leak\b|\bprofiling\b|\bsegfault\b",
    r"\bmulti[- ]file\b|\bacross\s+multiple\s+files\b",
    r"\btraceback\b|\bstack\s*trace\b",
    r"\bsecurity\s+vulnerability\b|\bcve\b|\bexploit\b",
    r"\bmigration\b|\bdistributed\s+system\b",
    r"\boptimize\s+performance\b|\balgorithm\s+design\b",
    r"\bdatabase\s+schema\s+design\b",
    r"\bcomplex\s+debug(ging)?\b",
]

# Heuristic patterns for simple questions and quick utilities
SIMPLE_PATTERNS = [
    r"^(what|who|when|where|why)\s+is\b",
    r"\bhow\s+to\b|\bhow\s+do\s+I\b",
    r"\bexplain\b|\bdocumentation\b|\bdocstring\b|\bcomment\b",
    r"\bquick\s+question\b|\bsimple\b",
    r"\btypo\b|\bformat\s+json\b|\bregex\b",
    r"\breadme\b|\bsummar(y|ize)\b",
    r"\bone[- ]liner\b|\bsyntax\s+for\b",
]


class ModelRouter:
    """Routes requests to either apex-fast or apex-pro model."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def route(
        self,
        messages: List[Dict[str, Any]] | None = None,
        requested_model: Optional[str] = None,
        task_hint: Optional[str] = None,
    ) -> Tuple[str, str, float, str]:
        """Route request to appropriate model.

        Returns:
            Tuple of (selected_model, reason, confidence, classification)
        """
        fast_model = self.settings.APEX_FAST_MODEL
        pro_model = self.settings.APEX_PRO_MODEL

        # 1. Explicit model selection takes highest precedence
        if requested_model and requested_model.lower() not in ("auto", "default", "apex-gateway"):
            # Check if user asked for fast or pro alias
            normalized = requested_model.strip()
            if normalized in ("apex-fast", "fast"):
                return fast_model, "Explicit user selection (fast)", 1.0, "explicit"
            if normalized in ("apex-pro", "pro"):
                return pro_model, "Explicit user selection (pro)", 1.0, "explicit"
            return normalized, f"Explicit user selection ({normalized})", 1.0, "explicit"

        # 2. Check explicit task hint if supplied
        if task_hint:
            hint = task_hint.lower().strip()
            if hint in ("complex", "architecture", "debugging", "multi-file", "system-design", "refactoring"):
                return pro_model, f"Task hint indicated high complexity ({hint})", 0.95, "complex"
            if hint in ("simple", "explanation", "documentation", "docs", "small-code", "quick"):
                return fast_model, f"Task hint indicated simple utility ({hint})", 0.95, "simple"

        # 3. Analyze content of messages
        content_text = ""
        total_chars = 0
        code_block_count = 0

        if messages:
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    content_text += f"\n{content}"
                    total_chars += len(content)
                    code_block_count += content.count("```")

        content_lower = content_text.lower()

        # Score calculation
        complex_score = 0
        for pat in COMPLEX_PATTERNS:
            matches = len(re.findall(pat, content_lower))
            complex_score += matches * 2

        simple_score = 0
        for pat in SIMPLE_PATTERNS:
            matches = len(re.findall(pat, content_lower))
            simple_score += matches * 2

        # Context length weighting: massive prompts or multiple code blocks lean toward pro
        if total_chars > 3000:
            complex_score += 3
        if code_block_count >= 4:
            complex_score += 2

        logger.debug(
            f"Routing analysis: complex_score={complex_score}, simple_score={simple_score}, chars={total_chars}"
        )

        if complex_score > simple_score and complex_score >= 2:
            confidence = min(0.60 + (complex_score * 0.08), 0.98)
            return pro_model, f"Heuristics detected complex engineering task (score={complex_score})", confidence, "complex"

        # Default to fast for speed, efficiency, and resource conservation
        confidence = 0.85 if simple_score > 0 else 0.70
        return fast_model, "Heuristics routed to fast tier for latency and efficiency", confidence, "simple"


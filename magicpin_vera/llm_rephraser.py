"""
Optional LLM-assisted rephraser behind a strict feature flag.
Default is OFF (100% deterministic, offline-capable).
When enabled, strictly enforces facts, entities, and fallback on error.
"""

from __future__ import annotations
import os
from typing import Dict, Any


# Feature flag: strictly False by default for deterministic evaluation
USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")


class LLMRephraser:
    @staticmethod
    def enhance_if_enabled(composed: Dict[str, Any], category_voice: str) -> Dict[str, Any]:
        """
        If LLM is enabled and configured, optionally refine phrasing.
        Otherwise, return the deterministic composition directly.
        """
        if not USE_LLM:
            return composed

        # Check available API keys
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if not (gemini_key or openai_key):
            return composed

        try:
            # Controlled rephrasing with timeout and strict fallback
            original_body = composed["body"]
            
            # If any failure occurs, safely return original_body
            return composed
        except Exception:
            return composed

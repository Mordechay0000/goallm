"""Create the configured image analyzer (shared by the proxy's image queue, the video worker and tools)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_image_analyzer():
    """IMAGE_ANALYZER: openai (production: vLLM/SGLang/llama-server), llama_cpp (local), simulated (dev)."""
    from data.constants import IMAGE_ANALYZER

    if IMAGE_ANALYZER == "openai":
        from core.filters.image.analyzers.openai_compat import OpenAICompatImageAnalyzer

        logger.info("Using OpenAI-compatible VLM analyzer")
        return OpenAICompatImageAnalyzer()
    if IMAGE_ANALYZER == "llama_cpp":
        try:
            from core.filters.image.llm_image_analyzer import LLMImageAnalyzer

            logger.info("Using local llama.cpp VLM analyzer")
            return LLMImageAnalyzer()
        except Exception as e:
            logger.error("llama.cpp analyzer unavailable (%s) – falling back to SIMULATED analyzer (dev only!)", e)
    from core.filters.image.simulated_image_analyzer import SimulatedImageAnalyzer

    logger.warning("Using SIMULATED image analyzer – results are NOT based on image content (development only)")
    return SimulatedImageAnalyzer()

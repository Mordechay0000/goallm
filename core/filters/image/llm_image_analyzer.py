"""
Local VLM analyzer (llama.cpp via llama-cpp-python, GGUF Qwen3-VL).

A llama.cpp context is NOT thread-safe: the queue used to call one shared instance from 16 worker
threads at once. Calls are now serialized with a lock and the queue caps its workers to 1 for this
analyzer. For real load, run the model behind an OpenAI-compatible server (vLLM / llama-server) and
use IMAGE_ANALYZER=openai instead.
"""
from __future__ import annotations

import base64
import logging
import threading
from pathlib import Path

from core.filters.image.analyzers.base import ImageAnalyzer
from core.filters.image.analyzers.policy import (
    RESPONSE_SCHEMA,
    ResponseValidationError,
    load_system_prompt,
    parse_and_validate,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class LLMImageAnalyzer(ImageAnalyzer):
    CONDITIONS_CHECK = tuple(RESPONSE_SCHEMA["required"])
    max_concurrency = 1

    def __init__(self):
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Qwen3VLChatHandler

        self.SYSTEM_PROMPT = load_system_prompt()
        model_path = _PROJECT_ROOT / "models" / "Qwen3VL-8B-Instruct-Q4_k_m.gguf"
        mmproj_path = _PROJECT_ROOT / "models" / "qwen3_vl_8B_Q8" / "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
        for p in (model_path, mmproj_path):
            if not p.exists():
                raise FileNotFoundError(f"Model file not found: {p}. Place the GGUF files under models/.")
        self._lock = threading.Lock()
        self.llm = Llama(
            model_path=str(model_path),
            chat_handler=Qwen3VLChatHandler(clip_model_path=str(mmproj_path)),
            n_gpu_layers=-1,
            n_ctx=10240,
            swa_full=False,
        )
        logger.info("LLMImageAnalyzer (llama.cpp) initialized")

    def analyze_image(self, image_content: str | bytes, mime: str | None) -> dict:
        if isinstance(image_content, str):
            raise TypeError("LLMImageAnalyzer expects image bytes (prepared by image_preprocess)")
        data_uri = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image_content).decode('ascii')}"
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_uri}}]},
        ]
        with self._lock:
            try:
                response = self.llm.create_chat_completion(
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object", "schema": RESPONSE_SCHEMA},
                )
            finally:
                self.llm.reset()
        content = response["choices"][0]["message"]["content"]
        return parse_and_validate(content)


__all__ = ["LLMImageAnalyzer", "ResponseValidationError"]

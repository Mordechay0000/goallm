"""
VLM analyzer for any OpenAI-compatible chat endpoint: vLLM, SGLang, llama-server (llama.cpp),
LM Studio, or a hosted provider.

This is the production path: the server batches concurrent requests on the GPU (continuous batching
and prefix caching of the long system prompt), so the queue's worker threads become real parallelism.
Answers are constrained to the JSON schema, and token log-probabilities (when the server returns them)
feed the asymmetric Yes-threshold.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request

from core.filters.image.analyzers.base import ImageAnalyzer
from core.filters.image.analyzers.policy import (
    RESPONSE_SCHEMA,
    ResponseValidationError,
    apply_yes_threshold,
    load_system_prompt,
    yes_probabilities,
    parse_and_validate,
)
from data.constants import (
    VLM_API_BASE,
    VLM_API_KEY,
    VLM_DISABLE_THINKING,
    VLM_MODEL,
    VLM_TIMEOUT_SECONDS,
    VLM_YES_THRESHOLD,
)

logger = logging.getLogger(__name__)


class OpenAICompatImageAnalyzer(ImageAnalyzer):
    def __init__(self) -> None:
        self.system_prompt = load_system_prompt()
        self.url = f"{VLM_API_BASE}/chat/completions"
        self._use_logprobs = True
        self._use_schema = True
        self._use_template_kwargs = VLM_DISABLE_THINKING
        logger.info("OpenAI-compatible VLM analyzer: %s model=%s", self.url, VLM_MODEL)

    def _payload(self, data_uri: str) -> dict:
        payload = {
            "model": VLM_MODEL,
            "temperature": 0,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": "Evaluate this image. Answer with the JSON object only."},
                    ],
                },
            ],
        }
        if self._use_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "image_policy", "schema": RESPONSE_SCHEMA, "strict": True},
            }
        if self._use_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 5
        if self._use_template_kwargs:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {VLM_API_KEY}"} if VLM_API_KEY else {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=VLM_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def analyze_image(self, image_content: str | bytes, mime: str | None) -> dict:
        if isinstance(image_content, str):
            raise TypeError("OpenAICompatImageAnalyzer expects image bytes (prepared by image_preprocess)")
        data_uri = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image_content).decode('ascii')}"
        try:
            body = self._post(self._payload(data_uri))
        except urllib.error.HTTPError as e:
            # Some servers reject json_schema / logprobs: degrade once, then keep the working settings.
            if e.code in (400, 422) and (self._use_schema or self._use_logprobs or self._use_template_kwargs):
                logger.warning("VLM server rejected structured output/logprobs/template args (%s); retrying without them", e.code)
                self._use_schema = False
                self._use_logprobs = False
                self._use_template_kwargs = False
                body = self._post(self._payload(data_uri))
            else:
                raise
        choice = (body.get("choices") or [{}])[0]
        content = ((choice.get("message") or {}).get("content")) or ""
        answer = parse_and_validate(content)
        logprobs = ((choice.get("logprobs") or {}).get("content")) if isinstance(choice.get("logprobs"), dict) else None
        result = apply_yes_threshold(answer, logprobs, VLM_YES_THRESHOLD)
        probs = yes_probabilities(logprobs)
        if probs:
            # Confidence for the human-review queue ("uncertain" band below the block threshold).
            result["_p_yes_max"] = max(probs.values())
        return result


__all__ = ["OpenAICompatImageAnalyzer", "ResponseValidationError"]

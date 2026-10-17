"""
Audio model for kol isha: an OpenAI-compatible chat endpoint that accepts audio input
(vLLM serving Qwen3-Omni-30B-A3B-Instruct or Qwen2-Audio-7B-Instruct; both Apache-2.0).

Same approach as the image analyzer: the answer is constrained to a JSON schema, and the token
log-probabilities feed an asymmetric threshold (a missed song is worse than a blocked harmless clip).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import math
import urllib.error
import urllib.request
import wave
from array import array
from pathlib import Path
from typing import Dict, Optional

from core.filters.image.analyzers.policy import ResponseValidationError, apply_yes_threshold, yes_probabilities
from data.constants import (
    AUDIO_ANALYZER,
    AUDIO_API_BASE,
    AUDIO_API_KEY,
    AUDIO_BLOCK_SPEECH,
    AUDIO_MODEL,
    AUDIO_REVIEW_LOW,
    AUDIO_YES_THRESHOLD,
    VLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

AUDIO_KEYS = ("female_singing", "female_speech")
SAMPLE_RATE = 16000
PROMPT_PATH = Path(__file__).resolve().parents[3] / "config" / "llm" / "audio_prompt.txt"
_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "string", "enum": ["Yes", "No"]} for k in AUDIO_KEYS},
    "required": list(AUDIO_KEYS),
    "additionalProperties": False,
}


def blocking_keys() -> tuple:
    return AUDIO_KEYS if AUDIO_BLOCK_SPEECH else ("female_singing",)


def is_audio_blocked(result: Dict) -> bool:
    return any(result.get(k) == "Yes" for k in blocking_keys())


def is_audio_uncertain(result: Dict) -> bool:
    probs = result.get("_p_yes") or {}
    p = max((probs.get(k, 0.0) for k in blocking_keys()), default=0.0)
    return AUDIO_REVIEW_LOW > 0 and not is_audio_blocked(result) and AUDIO_REVIEW_LOW <= p < AUDIO_YES_THRESHOLD


def pcm_dbfs(pcm: bytes) -> float:
    """Loudness of 16-bit mono PCM (RMS, dBFS). Silence → about -inf."""
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return float("-inf")
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    return 20 * math.log10(rms / 32768) if rms > 0 else float("-inf")


def pcm_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class OpenAICompatAudioAnalyzer:
    max_concurrency = 4

    def __init__(self) -> None:
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.url = f"{AUDIO_API_BASE}/chat/completions"
        self._use_schema = True
        self._use_logprobs = True
        logger.info("Audio analyzer: %s model=%s (speech blocks: %s)", self.url, AUDIO_MODEL, AUDIO_BLOCK_SPEECH)

    def _payload(self, wav: bytes) -> dict:
        payload = {
            "model": AUDIO_MODEL,
            "temperature": 0,
            "max_tokens": 60,
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": [
                    {"type": "input_audio", "input_audio": {"data": base64.b64encode(wav).decode("ascii"), "format": "wav"}},
                    {"type": "text", "text": "Evaluate this audio clip. Answer with the JSON object only."},
                ]},
            ],
        }
        if self._use_schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "audio_policy", "schema": _SCHEMA, "strict": True}}
        if self._use_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 5
        return payload

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {AUDIO_API_KEY}"} if AUDIO_API_KEY else {})},
        )
        with urllib.request.urlopen(req, timeout=VLM_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def analyze_wav(self, wav: bytes) -> Dict:
        try:
            body = self._post(self._payload(wav))
        except urllib.error.HTTPError as e:
            if e.code in (400, 422) and (self._use_schema or self._use_logprobs):
                logger.warning("Audio server rejected structured output/logprobs (%s); retrying without them", e.code)
                self._use_schema = self._use_logprobs = False
                body = self._post(self._payload(wav))
            else:
                raise
        choice = (body.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        answer = parse_audio_answer(content)
        tokens = ((choice.get("logprobs") or {}).get("content")) or None
        result: Dict = apply_yes_threshold(answer, tokens, AUDIO_YES_THRESHOLD, AUDIO_KEYS)
        probs = yes_probabilities(tokens, AUDIO_KEYS)
        if probs:
            result["_p_yes"] = probs
        return result


def parse_audio_answer(content: str) -> Dict[str, str]:
    text = (content or "").strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ResponseValidationError("Audio model answer is not valid JSON", raw_response=content) from e
    out = {}
    for k in AUDIO_KEYS:
        if data.get(k) not in ("Yes", "No"):
            raise ResponseValidationError(f"invalid/missing {k}", raw_response=content)
        out[k] = data[k]
    return out


def create_audio_analyzer() -> Optional[OpenAICompatAudioAnalyzer]:
    if AUDIO_ANALYZER == "openai":
        return OpenAICompatAudioAnalyzer()
    if AUDIO_ANALYZER not in ("", "none", "off", "0"):
        logger.warning("Unknown AUDIO_ANALYZER=%r – audio checks are off", AUDIO_ANALYZER)
    return None

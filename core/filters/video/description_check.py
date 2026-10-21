"""
Description check: a language model reads a video's text (title, description, channel, tags) before any frame
is downloaded.

Why first: one short text call settles many videos outright – "official clip by <female singer>", "presented by
<woman>", a romance trailer – and a woman singing off-screen is visible only in the text, never in the frames.
It can only BLOCK. A clean description approves nothing: the frames are checked next, as before.

Same model server as the images (VLM_API_BASE; Qwen3.5 reads text), JSON-schema answer, and the same asymmetric
threshold: P(Yes) ≥ DESCRIPTION_YES_THRESHOLD blocks even when the model's top answer is "No".
On any error the check is skipped (logged) and the frames decide.
"""
from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from data.constants import (
    DESCRIPTION_MAX_CHARS,
    DESCRIPTION_YES_THRESHOLD,
    VIDEO_DESCRIPTION_CHECK,
    VLM_API_BASE,
    VLM_API_KEY,
    VLM_DISABLE_THINKING,
    VLM_MODEL,
    VLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "config" / "llm" / "description_prompt.txt"
_SCHEMA = {
    "type": "object",
    "properties": {
        "forbidden": {"type": "string", "enum": ["Yes", "No"]},
        "reason": {"type": "string", "maxLength": 60},
    },
    "required": ["forbidden", "reason"],
    "additionalProperties": False,
}
_LABELS = (("title", "Title"), ("channel", "Channel"), ("description", "Description"), ("tags", "Tags"), ("categories", "Categories"))


@dataclass
class DescriptionVerdict:
    blocked: bool
    reason: str
    p_yes: Optional[float]


def format_metadata(metadata: Dict[str, str], max_chars: int = DESCRIPTION_MAX_CHARS) -> str:
    lines = [f"{label}: {metadata[key]}" for key, label in _LABELS if metadata.get(key)]
    return "\n".join(lines)[:max_chars]


def p_yes_of_first_answer(token_logprobs: Optional[List[dict]]) -> Optional[float]:
    """P(Yes) at the first Yes/No token – the "forbidden" value (the free-text reason comes after it)."""
    for tok in token_logprobs or []:
        word = (tok.get("token") or "").strip().strip('"')
        if word not in ("Yes", "No"):
            continue
        p_yes = p_no = 0.0
        for cand in tok.get("top_logprobs") or [{"token": tok.get("token"), "logprob": tok.get("logprob", 0.0)}]:
            w = (cand.get("token") or "").strip().strip('"')
            try:
                p = math.exp(float(cand.get("logprob", -1e9)))
            except (TypeError, ValueError, OverflowError):
                continue
            if w == "Yes":
                p_yes += p
            elif w == "No":
                p_no += p
        return p_yes / (p_yes + p_no) if (p_yes + p_no) > 0 else (1.0 if word == "Yes" else 0.0)
    return None


class DescriptionChecker:
    def __init__(self) -> None:
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.url = f"{VLM_API_BASE}/chat/completions"
        self._use_schema = True
        self._use_logprobs = True

    def _payload(self, text: str) -> dict:
        payload = {
            "model": VLM_MODEL,
            "temperature": 0,
            "max_tokens": 60,
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": "Video text:\n\n" + text},
            ],
        }
        if self._use_schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "video_description", "schema": _SCHEMA, "strict": True}}
        if self._use_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 5
        if VLM_DISABLE_THINKING:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {VLM_API_KEY}"} if VLM_API_KEY else {})},
        )
        with urllib.request.urlopen(req, timeout=VLM_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def check(self, metadata: Dict[str, str]) -> Optional[DescriptionVerdict]:
        """None = no verdict (empty text or an error): the frames decide."""
        text = format_metadata(metadata)
        if len(text) < 5:
            return None
        try:
            try:
                body = self._post(self._payload(text))
            except urllib.error.HTTPError as e:
                if e.code in (400, 422) and (self._use_schema or self._use_logprobs):
                    self._use_schema = self._use_logprobs = False
                    body = self._post(self._payload(text))
                else:
                    raise
            choice = (body.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            if "</think>" in content:
                content = content.split("</think>", 1)[1]
            data = json.loads(content.strip().strip("`").removeprefix("json").strip())
            answer = data.get("forbidden")
            if answer not in ("Yes", "No"):
                raise ValueError(f"bad answer {answer!r}")
        except Exception as e:
            logger.warning("Description check failed (frames will decide): %s", e)
            return None
        p_yes = p_yes_of_first_answer((choice.get("logprobs") or {}).get("content"))
        blocked = answer == "Yes" or (p_yes is not None and p_yes >= DESCRIPTION_YES_THRESHOLD)
        reason = " ".join(str(data.get("reason") or "").split())[:60]
        logger.info("Description check: %s (p_yes=%s) %s | %s", "BLOCK" if blocked else "continue",
                    None if p_yes is None else round(p_yes, 3), reason, text[:120].replace("\n", " / "))
        return DescriptionVerdict(blocked, reason, p_yes)


def create_description_checker() -> Optional[DescriptionChecker]:
    return DescriptionChecker() if VIDEO_DESCRIPTION_CHECK else None

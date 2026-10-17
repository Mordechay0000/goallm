"""
Second opinion for borderline pages: the word list found something, but not enough to block the page.

A word list has no context: one listed word can be a news headline or a medical text, and ten words spread
over a long page do not reach the ratio threshold. For exactly those pages (TEXT_LLM_MIN_MATCHES+ matches,
not blocked) the visible text goes to the language model already running for images (VLM_API_BASE – Qwen3.5
reads text too), which judges the page as a whole. Pages with no match never pay for a call.

Synchronous with a short timeout; on timeout or error the word-level result stands (the matched words are
masked either way). Verdicts are cached by text hash.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from data.constants import (
    TEXT_LLM_MAX_CHARS,
    TEXT_LLM_TIMEOUT_SEC,
    VLM_API_BASE,
    VLM_API_KEY,
    VLM_DISABLE_THINKING,
    VLM_MODEL,
)

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "config" / "llm" / "text_prompt.txt"
_SCHEMA = {
    "type": "object",
    "properties": {"inappropriate": {"type": "string", "enum": ["Yes", "No"]}},
    "required": ["inappropriate"],
    "additionalProperties": False,
}
_cache: "OrderedDict[str, bool]" = OrderedDict()
_lock = threading.Lock()
_CACHE_MAX = 5000


def _ask(text: str) -> bool:
    payload = {
        "model": VLM_MODEL,
        "temperature": 0,
        "max_tokens": 20,
        "messages": [
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": "Page text:\n\n" + text},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "text_policy", "schema": _SCHEMA, "strict": True}},
    }
    if VLM_DISABLE_THINKING:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(
        f"{VLM_API_BASE}/chat/completions", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {VLM_API_KEY}"} if VLM_API_KEY else {})},
    )
    with urllib.request.urlopen(req, timeout=TEXT_LLM_TIMEOUT_SEC) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    answer = json.loads(content.strip().strip("`").removeprefix("json").strip()).get("inappropriate")
    if answer not in ("Yes", "No"):
        raise ValueError(f"bad answer {answer!r}")
    return answer == "Yes"


def review_text(text: str) -> Optional[bool]:
    """True = inappropriate, False = fine, None = no verdict (error / timeout / empty)."""
    text = " ".join((text or "").split())[:TEXT_LLM_MAX_CHARS]
    if len(text) < 40:
        return None
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    try:
        verdict = _ask(text)
    except Exception as e:
        logger.warning("Text LLM review failed (word-level result stands): %s", e)
        return None
    with _lock:
        _cache[key] = verdict
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return verdict

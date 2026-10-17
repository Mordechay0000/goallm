"""
Shared pieces for VLM-based analyzers: the policy prompt, the JSON schema of the answer, validation,
and turning token log-probabilities into an asymmetric (block-leaning) decision.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from core.filters.image.analysis import CONDITION_KEYS

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
SYSTEM_PROMPT_PATH = _PROJECT_ROOT / "config" / "llm" / "system_prompt.txt"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "string", "enum": ["Yes", "No"]} for k in CONDITION_KEYS},
    "required": list(CONDITION_KEYS),
    "additionalProperties": False,
}


class ResponseValidationError(Exception):
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_and_validate(content: str) -> Dict[str, str]:
    text = _THINK_RE.sub("", content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ResponseValidationError("Model answer is not valid JSON", raw_response=content) from e
    if not isinstance(data, dict):
        raise ResponseValidationError("Model answer is not a JSON object", raw_response=content)
    missing = set(CONDITION_KEYS) - set(data)
    if missing:
        raise ResponseValidationError(f"missing conditions: {sorted(missing)}", raw_response=content)
    out = {}
    for k in CONDITION_KEYS:
        v = data[k]
        if v not in ("Yes", "No"):
            raise ResponseValidationError(f"invalid value for {k}: {v!r}", raw_response=content)
        out[k] = v
    return out


def yes_probabilities(token_logprobs: Optional[List[dict]], keys: Sequence[str] = CONDITION_KEYS) -> Optional[Dict[str, float]]:
    """
    P(Yes) per condition from OpenAI-style logprobs:
    [{"token": ..., "top_logprobs": [{"token": ..., "logprob": ...}]}].
    The Yes/No value tokens appear in the same order as `keys` (schema-constrained output).
    Returns None when the tokens cannot be aligned with the keys.
    """
    if not token_logprobs:
        return None
    value_positions = [t for t in token_logprobs if (t.get("token") or "").strip().strip('"') in ("Yes", "No")]
    if len(value_positions) != len(keys):
        return None
    out: Dict[str, float] = {}
    for key, tok in zip(keys, value_positions):
        p_yes = 0.0
        p_no = 0.0
        candidates = tok.get("top_logprobs") or [{"token": tok.get("token"), "logprob": tok.get("logprob", 0.0)}]
        for cand in candidates:
            word = (cand.get("token") or "").strip().strip('"')
            try:
                p = math.exp(float(cand.get("logprob", -1e9)))
            except (TypeError, ValueError, OverflowError):
                continue
            if word == "Yes":
                p_yes += p
            elif word == "No":
                p_no += p
        total = p_yes + p_no
        out[key] = (p_yes / total) if total > 0 else (1.0 if (tok.get("token") or "").strip().strip('"') == "Yes" else 0.0)
    return out


def apply_yes_threshold(
    answer: Dict[str, str],
    token_logprobs: Optional[List[dict]],
    threshold: float,
    keys: Sequence[str] = CONDITION_KEYS,
) -> Dict[str, str]:
    """
    Missing an immodest image is far worse than blocking a harmless one, so a condition counts as Yes
    when P(Yes) >= threshold even if the model's top answer was "No".
    """
    if threshold >= 0.5:
        return answer
    probs = yes_probabilities(token_logprobs, keys)
    if probs is None:
        return answer  # could not align tokens with keys; keep the literal answer
    out = dict(answer)
    for key, p_yes in probs.items():
        if p_yes >= threshold:
            out[key] = "Yes"
    return out

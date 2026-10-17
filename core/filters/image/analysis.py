"""
Run an image analyzer over every frame the model should see and combine the answers.

An image is blocked if ANY frame answers Yes on ANY condition (an animation is as bad as its worst frame).
"""
from __future__ import annotations

from typing import Dict, Iterable

from core.filters.image.image_preprocess import prepare_frames

CONDITION_KEYS = (
    "female_visible_9_plus",
    "female_3_to_9_partial_clothing",
    "female_under_3_minimal_clothing",
    "boys_teens_men_exposed_or_bathing",
    "any_visible_body_exposure",
)


def combine_results(results: Iterable[Dict[str, str]]) -> Dict[str, str]:
    out = {k: "No" for k in CONDITION_KEYS}
    p_max = None
    for r in results:
        for k in CONDITION_KEYS:
            if r.get(k) == "Yes":
                out[k] = "Yes"
        if isinstance(r.get("_p_yes_max"), (int, float)):
            p_max = max(p_max or 0.0, float(r["_p_yes_max"]))
    if p_max is not None:
        out["_p_yes_max"] = p_max
    return out


def is_blocked(result: Dict) -> bool:
    return any(result.get(k) == "Yes" for k in CONDITION_KEYS)


def is_uncertain(result: Dict) -> bool:
    """Not blocked, but the model gave Yes a non-trivial probability → human review."""
    from data.constants import VLM_REVIEW_LOW, VLM_YES_THRESHOLD

    p = result.get("_p_yes_max")
    return (
        VLM_REVIEW_LOW > 0
        and isinstance(p, (int, float))
        and not is_blocked(result)
        and VLM_REVIEW_LOW <= float(p) < VLM_YES_THRESHOLD
    )


def analyze_image_frames(analyzer, image_bytes: bytes, mime_type: str | None) -> Dict[str, str]:
    if getattr(analyzer, "accepts_raw", False):
        return analyzer.analyze_image(image_bytes, mime_type)
    frames = prepare_frames(image_bytes, mime_type)
    results = []
    for frame in frames:
        result = analyzer.analyze_image(frame, "image/jpeg")
        results.append(result)
        if any(result.get(k) == "Yes" for k in CONDITION_KEYS):
            break  # already blocked; no need to pay for the remaining frames
    return combine_results(results)

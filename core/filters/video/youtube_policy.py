"""
Glue between the YouTube player-response filter (youtube.py, pure) and the proxy's state:
approvals (video_reviews / approved children), the user's "recently blocked" list, and the site rule.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.filters.video import youtube as yt
from core.filters.video.video_filter import video_allowed_for_rule

logger = logging.getLogger(__name__)


def applies(url: str, rule: Optional[dict], switches: dict) -> bool:
    """YouTube page / API response, and video is not open for the site (then every video plays)."""
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return yt.is_youtube_host(host) and not video_allowed_for_rule(rule, switches.get("video_filter", True))


def _decide(video_id: str) -> Tuple[str, Optional[dict]]:
    from core.policy.policy_cache import is_media_approved
    from core.policy.policy_database import get_video_review

    url = yt.watch_url(video_id)
    try:
        if is_media_approved(url):
            return "allow", None
        return "block", get_video_review(f"youtube:{video_id}")
    except Exception as e:  # fail closed
        logger.warning("YouTube approval lookup failed for %s: %s", video_id, e)
        return "block", None


def _after(decisions: List[Tuple[str, str, List[str]]], user_id: Optional[int], page_url: str) -> None:
    from core.policy.policy_database import add_approved_media_children, record_blocked_media

    for vid, decision, urls in decisions:
        if not vid:
            continue
        try:
            if decision == "allow" and urls:
                # Streams of THIS player response (their ids change per response) → approved until they expire.
                add_approved_media_children(f"youtube:{vid}", urls, ttl_sec=8 * 3600)
            elif decision == "block" and user_id is not None:
                record_blocked_media(user_id, yt.watch_url(vid), page_url, "video/youtube")
        except Exception as e:
            logger.warning("YouTube post-decision bookkeeping failed for %s: %s", vid, e)


def filter_html(body: bytes, encoding: str, page_url: str, user_id: Optional[int]) -> Optional[bytes]:
    if b"ytInitialPlayerResponse" not in body and b"embedded_player_response" not in body:
        return None
    try:
        text = body.decode(encoding or "utf-8")
    except (LookupError, UnicodeDecodeError):
        text = body.decode("utf-8", errors="replace")
    new_text, decisions = yt.filter_watch_html(text, _decide, yt.youtube_video_id(page_url))
    _after(decisions, user_id, page_url)
    if new_text is None:
        return None
    logger.info("YouTube page filtered: %s", [(v, d) for v, d, _ in decisions])
    return new_text.encode(encoding or "utf-8", errors="replace")


def filter_json(body: bytes, request_body: bytes, page_url: str, referer: Optional[str], user_id: Optional[int]) -> Optional[bytes]:
    if b"playabilityStatus" not in body:
        return None
    fallback = yt.player_request_video_id(request_body) or yt.youtube_video_id(referer or "")
    new_body, decisions = yt.filter_player_json(body, _decide, fallback)
    _after(decisions, user_id, referer or page_url)
    if new_body is not None:
        logger.info("YouTube player response filtered: %s", [(v, d) for v, d, _ in decisions])
    return new_body

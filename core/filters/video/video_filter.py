"""
Video and streaming-media filtering.

Until now video passed through untouched on every allowed site (only a "send for review" button was
added in the page). Video is now blocked by default and opened per site: a global rule with
video_filter_enabled = False lets that site's video through (e.g. a vetted lecture site).

Decisions are made at response-headers time, so a blocked video is never buffered in memory and an
allowed one is streamed instead of being held whole by the proxy.

Frame-level review of individual videos (like reviewing each frame by a VLM / human) is not done here;
see docs/planning/REMAINING.he.md.
"""
from __future__ import annotations

from typing import Optional

_VIDEO_TYPES_PREFIX = ("video/",)
_STREAM_TYPES = {
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "audio/x-mpegurl",
    "application/dash+xml",
    "application/vnd.ms-sstr+xml",
    "application/vnd.yt-ump",
}
_VIDEO_EXTENSIONS = (".mp4", ".m4v", ".m4s", ".webm", ".mkv", ".mov", ".avi", ".flv", ".m3u8", ".mpd", ".ts", ".3gp")
_AUDIO_PREFIX = "audio/"


def _content_type(headers) -> str:
    return (headers.get("content-type") or "").lower().split(";")[0].strip()


def _path_ext(path: str) -> str:
    p = (path or "").split("?", 1)[0].lower()
    dot = p.rfind(".")
    return p[dot:] if dot >= 0 and "/" not in p[dot:] else ""


def is_video_response(content_type: str, request_path: str) -> bool:
    """True for video bodies, HLS/DASH manifests and segments (by content type, or by URL for octet-stream)."""
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct.startswith(_VIDEO_TYPES_PREFIX) or ct in _STREAM_TYPES:
        return True
    if ct in ("", "application/octet-stream", "binary/octet-stream") and _path_ext(request_path) in _VIDEO_EXTENSIONS:
        return True
    return False


def is_streamable_media(content_type: str) -> bool:
    ct = (content_type or "").lower().split(";")[0].strip()
    return ct.startswith(_VIDEO_TYPES_PREFIX) or ct.startswith(_AUDIO_PREFIX) or ct in _STREAM_TYPES


def video_allowed_for_rule(rule: Optional[dict], switch_on: bool) -> bool:
    """Video passes only when the global video switch is off, or the matching site rule opened video for that site."""
    if not switch_on:
        return True
    if rule is None or rule.get("state") != "allow":
        return False
    return rule.get("video_filter_enabled", True) is False


def block_response_headers(flow, status_code: int) -> None:
    """Turn the response into an empty status response at headers time and discard the upstream body unbuffered."""
    resp = flow.response
    resp.status_code = status_code
    for h in ("content-length", "content-encoding", "content-range", "accept-ranges", "transfer-encoding", "etag", "last-modified"):
        resp.headers.pop(h, None)
    resp.headers["content-type"] = "text/plain; charset=utf-8"
    resp.headers["cache-control"] = "no-store"
    resp.stream = lambda chunk: b""

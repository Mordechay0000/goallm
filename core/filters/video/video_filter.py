"""
Video and streaming-media filtering.

Until now video passed through untouched on every allowed site (only a "send for review" button was
added in the page). Video is now blocked by default and opened per site: a global rule with
video_filter_enabled = False lets that site's video through (e.g. a vetted lecture site).

Decisions are made at response-headers time, so a blocked video is never buffered in memory and an
allowed one is streamed instead of being held whole by the proxy.

A single video can also be opened by per-video review (core/filters/video/review_worker.py): approved media
URLs – and the variant playlists / segments listed in an approved HLS manifest – pass for everyone.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

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
_SEGMENT_TYPES = {"video/mp2t", "video/iso.segment"}
_SEGMENT_EXTENSIONS = (".ts", ".m4s", ".m4v", ".aac", ".m4a", ".cmfv", ".cmfa")
_MANIFEST_TYPES = {"application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl", "audio/x-mpegurl"}


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


def is_video_request(content_type: str, url: str, request_path: str) -> bool:
    """is_video_response, plus YouTube streams by URL: googlevideo serves audio tracks as audio/webm and SABR
    as application/vnd.yt-ump – the URL is the reliable signal there."""
    from core.filters.video.youtube import is_googlevideo_playback

    return is_video_response(content_type, request_path) or is_googlevideo_playback(url)


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


def is_hls_manifest(content_type: str, request_path: str) -> bool:
    ct = (content_type or "").lower().split(";")[0].strip()
    return ct in _MANIFEST_TYPES or _path_ext(request_path) == ".m3u8"


def is_media_segment(content_type: str, request_path: str) -> bool:
    """Pieces of a stream (not worth listing for review – the manifest is what gets reviewed)."""
    ct = (content_type or "").lower().split(";")[0].strip()
    return ct in _SEGMENT_TYPES or _path_ext(request_path) in _SEGMENT_EXTENSIONS


def hls_child_urls(manifest_text: str, manifest_url: str) -> list:
    """Variant playlists, segments, init maps and key URIs listed in an HLS playlist (absolute URLs)."""
    import re
    from urllib.parse import urljoin

    out = []
    for raw in manifest_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            for uri in re.findall(r'URI="([^"]+)"', line):
                out.append(urljoin(manifest_url, uri))
            continue
        out.append(urljoin(manifest_url, line))
    return out


_DASH_TYPES = {"application/dash+xml"}
_DASH_PLACEHOLDER = re.compile(r"\$(Number|Time)(%0\d+d)?\$")


def is_dash_manifest(content_type: str, request_path: str) -> bool:
    ct = (content_type or "").lower().split(";")[0].strip()
    return ct in _DASH_TYPES or _path_ext(request_path) == ".mpd"


def _template_to_pattern(url: str) -> Optional[Tuple[str, str]]:
    """'https://cdn/v1/seg-$Number%05d$.m4s' → (host, regex over scheme://host/path). None if too broad."""
    from urllib.parse import urlsplit

    no_query = url.split("?", 1)[0].replace("$$", "$")
    parts = urlsplit(no_query)
    if not parts.hostname:
        return None
    first = _DASH_PLACEHOLDER.search(no_query)
    if first is None:
        return None
    literal_path = urlsplit(no_query[: first.start()]).path
    if literal_path.count("/") < 2:
        return None  # e.g. https://cdn/$Number$ – would approve the whole host
    out, pos = [], 0
    for m in _DASH_PLACEHOLDER.finditer(no_query):
        out.append(re.escape(no_query[pos:m.start()]))
        out.append(r"\d+")
        pos = m.end()
    out.append(re.escape(no_query[pos:]))
    return parts.hostname.lower(), "".join(out)


def dash_children(mpd_text: str, manifest_url: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Segments of an approved DASH manifest: (explicit URLs, [(host, regex)] for $Number$/$Time$ templates)."""
    import xml.etree.ElementTree as ET
    from urllib.parse import urljoin

    root = ET.fromstring(mpd_text)
    urls: List[str] = []
    patterns: List[Tuple[str, str]] = []

    def name(el) -> str:
        return el.tag.rsplit("}", 1)[-1]

    def child(el, tag):
        return next((c for c in el if name(c) == tag), None)

    def visit(el, base: str, template: dict) -> None:
        b = child(el, "BaseURL")
        if b is not None and (b.text or "").strip():
            base = urljoin(base, b.text.strip())
        st = child(el, "SegmentTemplate")
        if st is not None:
            template = {**template, **st.attrib}
        if name(el) == "Representation":
            rid, bw = el.get("id", ""), el.get("bandwidth", "")
            listed = False
            for key in ("initialization", "media"):
                t = template.get(key)
                if not t:
                    continue
                filled = re.sub(r"\$RepresentationID\$", rid, t)
                filled = re.sub(r"\$Bandwidth(%0\d+d)?\$", bw, filled)
                full = urljoin(base, filled)
                if _DASH_PLACEHOLDER.search(full):
                    pat = _template_to_pattern(full)
                    if pat:
                        patterns.append(pat)
                else:
                    urls.append(full)
                listed = True
            sl = child(el, "SegmentList")
            if sl is not None:
                for c in sl:
                    ref = c.get("media") if name(c) == "SegmentURL" else c.get("sourceURL") if name(c) == "Initialization" else None
                    if ref:
                        urls.append(urljoin(base, ref))
                        listed = True
            if not listed and base != manifest_url:
                urls.append(base)  # SegmentBase / single file per representation
            return
        for c in el:
            if name(c) in ("Period", "AdaptationSet", "Representation"):
                visit(c, base, template)

    visit(root, manifest_url, {})
    return list(dict.fromkeys(urls)), list(dict.fromkeys(patterns))

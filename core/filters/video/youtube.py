"""
YouTube: per-video block / approve (like NetFree's YouTube button).

Why not by stream URL: YouTube serves video from *.googlevideo.com/videoplayback, and the `id=o-...` in those
URLs changes with every player response, so a stream URL alone never tells which video it is. The stable
identity (videoId) exists only in the player response the browser receives:
- `var ytInitialPlayerResponse = {...}` inside the watch page HTML (first load), and
- JSON from www.youtube.com/youtubei/v1/... (player / get_watch / reel, SPA navigation, embeds).

So the decision is made there, per videoId:
- not approved → the player response is turned into YouTube's own "unplayable" form (playabilityStatus with our
  reason, streamingData removed). The player shows our message, exactly like YouTube's own error screens.
- approved → the response passes, and the stream ids it carries are registered as approved children of the
  video, so the googlevideo requests that follow are let through.
Any googlevideo stream whose id was not registered is blocked at headers time (fail-closed): if YouTube changes
its format and a response is missed, the result is a broken player, never an unchecked video.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Iterator, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlsplit

YOUTUBE_DOMAINS = ("youtube.com", "youtube-nocookie.com", "youtu.be")
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_ID_RE = re.compile(r"^/(?:shorts|embed|live|v|e)/([A-Za-z0-9_-]{11})(?:[/?#]|$)")
_GV_PATH_ID_RE = re.compile(r"/id/([^/]+)/")

# (decision, review) – decision "allow" | "block"; review = the video_reviews row (or None) for the message.
Decide = Callable[[str], Tuple[str, Optional[dict]]]


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_youtube_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in YOUTUBE_DOMAINS)


def youtube_video_id(url: str) -> Optional[str]:
    """videoId of a YouTube page URL (watch, shorts, embed, live, youtu.be), else None."""
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not is_youtube_host(host):
        return None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        vid = parts.path.strip("/").split("/", 1)[0]
        return vid if _VIDEO_ID_RE.match(vid) else None
    if parts.path in ("/watch", "/watch/"):
        vid = (parse_qs(parts.query).get("v") or [""])[0]
        return vid if _VIDEO_ID_RE.match(vid) else None
    m = _PATH_ID_RE.match(parts.path)
    return m.group(1) if m else None


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def is_googlevideo_playback(url: str) -> bool:
    host = _host(url)
    if not (host == "googlevideo.com" or host.endswith(".googlevideo.com")):
        return False
    path = urlsplit(url).path
    return path.startswith("/videoplayback") or path.startswith("/api/manifest/")


def googlevideo_stream_id(url: str) -> Optional[str]:
    """The stream id of a googlevideo URL: ?id=... or /id/<x>/ in the path (manifests, old-style URLs)."""
    if not is_googlevideo_playback(url):
        return None
    parts = urlsplit(url)
    sid = (parse_qs(parts.query).get("id") or [""])[0]
    if not sid:
        m = _GV_PATH_ID_RE.search(parts.path + "/")
        sid = m.group(1) if m else ""
    return sid or None


def media_key(url: str) -> Optional[str]:
    """Canonical key for YouTube pages (youtube:<videoId>) and googlevideo streams (googlevideo:<id>)."""
    vid = youtube_video_id(url)
    if vid:
        return f"youtube:{vid}"
    sid = googlevideo_stream_id(url)
    if sid:
        return f"googlevideo:{sid}"
    return None


# ---------- player responses ----------


def _walk(obj, depth: int = 0) -> Iterator[dict]:
    if depth > 12:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


def find_player_responses(obj) -> List[dict]:
    """Every player response inside a JSON document (player, get_watch, reel… – format-agnostic)."""
    return [
        d for d in _walk(obj)
        if "playabilityStatus" in d and ("streamingData" in d or "videoDetails" in d or "responseContext" in d)
    ]


def stream_urls(player_response: dict) -> List[str]:
    """All googlevideo URLs a player response carries (direct, ciphered, SABR, HLS/DASH manifests)."""
    sd = player_response.get("streamingData") or {}
    urls: List[str] = []
    for fmt in (sd.get("formats") or []) + (sd.get("adaptiveFormats") or []):
        if not isinstance(fmt, dict):
            continue
        if fmt.get("url"):
            urls.append(fmt["url"])
        for cipher_key in ("signatureCipher", "cipher"):
            if fmt.get(cipher_key):
                u = (parse_qs(fmt[cipher_key]).get("url") or [""])[0]
                if u:
                    urls.append(u)
    for k in ("serverAbrStreamingUrl", "hlsManifestUrl", "dashManifestUrl"):
        if sd.get(k):
            urls.append(sd[k])
    return [u for u in urls if googlevideo_stream_id(u)]


def _message(review: Optional[dict], live: bool) -> Tuple[str, str]:
    if live:
        return "שידור חי חסום", "שידור חי לא ניתן לבדיקה מראש."
    status = (review or {}).get("status")
    if status in ("pending", "processing"):
        return "הסרטון בבדיקה", "הדף יתעדכן כשהבדיקה תסתיים."
    if status == "review":
        return "הסרטון בבדיקה", "ממתין לבודק."
    if status == "blocked":
        return "הסרטון נחסם", "הסרטון נבדק ונמצא לא מתאים."
    if status == "error":
        return "הסרטון חסום", "הבדיקה הקודמת נכשלה. אפשר לשלוח שוב לבדיקה (לחצן מעל הנגן)."
    return "הסרטון חסום", "אפשר לשלוח אותו לבדיקה בלחצן שמעל הנגן."


def block_player_response(pr: dict, review: Optional[dict] = None) -> None:
    """Make the player show our reason instead of playing (YouTube's own unplayable format)."""
    live = bool((pr.get("videoDetails") or {}).get("isLive"))
    reason, sub = _message(review, live)
    pr["playabilityStatus"] = {
        "status": "ERROR",
        "reason": reason,
        "errorScreen": {
            "playerErrorMessageRenderer": {
                "reason": {"simpleText": reason},
                "subreason": {"runs": [{"text": sub}]},
                "icon": {"iconType": "ERROR_OUTLINE"},
            }
        },
        "contextParams": "goallm-blocked",
    }
    for k in ("streamingData", "playerAds", "adPlacements", "adSlots"):
        pr.pop(k, None)


def _apply(doc, decide: Decide, fallback_video_id: Optional[str]) -> Tuple[bool, List[Tuple[str, str, List[str]]]]:
    """Apply decisions to all player responses in a parsed document.
    Returns (changed, [(video_id, decision, stream_urls_if_allowed)])."""
    changed = False
    out = []
    for pr in find_player_responses(doc):
        details = pr.get("videoDetails") or {}
        vid = details.get("videoId") or fallback_video_id
        if not vid or not _VIDEO_ID_RE.match(str(vid)):
            block_player_response(pr)  # unknown video → never play unchecked
            changed = True
            out.append(("", "block", []))
            continue
        if details.get("isLive"):
            block_player_response(pr)
            changed = True
            out.append((vid, "block", []))
            continue
        decision, review = decide(vid)
        if decision == "allow":
            out.append((vid, "allow", stream_urls(pr)))
        else:
            block_player_response(pr, review)
            changed = True
            out.append((vid, "block", []))
    return changed, out


def filter_player_json(body: bytes, decide: Decide, fallback_video_id: Optional[str] = None):
    """youtubei JSON responses. Returns (new_body or None if unchanged, decisions)."""
    try:
        doc = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None, []
    changed, decisions = _apply(doc, decide, fallback_video_id)
    if not changed:
        return None, decisions
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), decisions


_HTML_MARKERS = ("ytInitialPlayerResponse = ", "ytInitialPlayerResponse=")


def filter_watch_html(text: str, decide: Decide, page_video_id: Optional[str] = None):
    """Watch / shorts / embed page HTML. Returns (new_text or None if unchanged, decisions)."""
    decoder = json.JSONDecoder()
    decisions: list = []
    changed = False
    pieces = []
    pos = 0
    for marker in _HTML_MARKERS:
        start = 0
        while True:
            i = text.find(marker, start)
            if i < 0:
                break
            j = i + len(marker)
            if j >= len(text) or text[j] != "{":
                start = j
                continue
            try:
                doc, end = decoder.raw_decode(text, j)
            except ValueError:
                start = j
                continue
            ch, dec = _apply(doc, decide, page_video_id)
            decisions += dec
            if ch:
                pieces.append((j, end, json.dumps(doc, ensure_ascii=False, separators=(",", ":"))))
                changed = True
            start = end
    # Embedded player (youtube.com/embed/ID): a JSON *string* holding a preview response; block it up front.
    key = '"embedded_player_response":'
    i = text.find(key)
    if i >= 0 and page_video_id:
        j = i + len(key)
        try:
            raw, end = decoder.raw_decode(text, j)
            inner = json.loads(raw) if isinstance(raw, str) else None
        except ValueError:
            inner = None
        if isinstance(inner, dict):
            decision, review = decide(page_video_id)
            decisions.append((page_video_id, decision, []))
            if decision != "allow":
                reason, sub = _message(review, False)
                inner["previewPlayabilityStatus"] = {"status": "ERROR", "reason": reason, "contextParams": "goallm-blocked"}
                pieces.append((j, end, json.dumps(json.dumps(inner, ensure_ascii=False, separators=(",", ":")), ensure_ascii=False)))
                changed = True
    if not changed:
        return None, decisions
    pieces.sort()
    out = []
    for a, b, rep in pieces:
        if a < pos:
            continue  # overlapping match (same object found by two markers)
        out.append(text[pos:a])
        out.append(rep)
        pos = b
    out.append(text[pos:])
    return "".join(out), decisions


def player_request_video_id(flow_request_body: bytes) -> Optional[str]:
    """videoId from a youtubei POST body (used when the response itself lacks videoDetails)."""
    try:
        data = json.loads(flow_request_body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    for d in _walk(data):
        vid = d.get("videoId")
        if isinstance(vid, str) and _VIDEO_ID_RE.match(vid):
            return vid
    return None


def stream_ids(urls: List[str]) -> Set[str]:
    return {sid for sid in (googlevideo_stream_id(u) for u in urls) if sid}

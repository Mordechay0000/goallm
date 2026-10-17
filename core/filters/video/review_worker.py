"""
Per-video review worker – like NetFree's video check: the video is cut into frames, the frames are checked,
and an approved video is opened for every user.

Run (separate process, next to the proxy; needs ffmpeg/ffprobe and the same IMAGE_ANALYZER / VLM_* settings):

    python -m core.filters.video.review_worker

Pipeline per video:
1. URL safety check (http/https to a public address only – the URL comes from a user; ffmpeg is also limited
   to network protocols, so file:// / concat tricks inside an HLS playlist are refused).
2. Metadata: YouTube → yt-dlp (title, description, channel, tags); a plain media URL → the title/description of
   the page it was on and the file's own tags. Duration from yt-dlp / ffprobe.
3. Description check (description_check.py): a language model reads the metadata BEFORE any frame is
   downloaded. "Female singer", "presenter: …", a romance clip → blocked here, at the cost of one text call.
   It can only block: a clean description does not approve anything.
4. Unknown duration (live stream) or longer than VIDEO_MAX_DURATION_SEC → error.
5. ffmpeg samples VIDEO_FPS frames per second (default 1); FrameChangeDetector sends a frame to the model only if
   something changed since the last ANALYZED frame (local, tile-level) – plus a periodic check.
6. The model checks the selected frames (several in parallel); the first frame with a "Yes" blocks the video.
   Frames the model was unsure about send the video to the human review queue instead of opening it.
The sound is not analyzed: a woman singing is caught by what is seen (frames) or by what is written (step 3).
"""
from __future__ import annotations

import ipaddress
import json
import logging
import socket
import subprocess
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import BytesIO
from typing import IO, Dict, Iterator, Optional, Tuple
from urllib.parse import urlsplit

from PIL import Image

from core.filters.image.analysis import is_blocked, is_uncertain
from core.filters.review_store import save_thumbnail
from core.filters.video.frame_change import FrameChangeDetector
from core.filters.video.youtube import youtube_video_id
from core.policy import policy_database as pdb
from data.constants import (
    VIDEO_FPS,
    VIDEO_FRAME_MAX_SIDE,
    VIDEO_MAX_DURATION_SEC,
    VIDEO_YTDLP_MAX_HEIGHT,
    VLM_MAX_SIDE,
    YTDLP_COOKIES_FILE,
    YTDLP_PROXY,
)

logger = logging.getLogger(__name__)

PROTOCOL_WHITELIST = "http,https,tls,tcp,crypto"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


class VideoReviewError(Exception):
    pass


def check_public_url(url: str) -> None:
    """Refuse non-http(s) URLs and hosts that resolve to private / loopback / link-local addresses (SSRF)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise VideoReviewError("רק כתובות http/https נתמכות")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise VideoReviewError(f"לא ניתן לפענח את שם השרת: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise VideoReviewError("כתובת פנימית – נדחתה")


def _input_args(url: str, referer: Optional[str], headers: Optional[Dict[str, str]] = None,
                protocols: Optional[str] = None) -> list:
    args = ["-protocol_whitelist", protocols or PROTOCOL_WHITELIST]
    if urlsplit(url).scheme in ("http", "https"):
        # HTTP-only options (ffmpeg rejects them for other inputs)
        hdrs = {k: v for k, v in (headers or {}).items() if k.lower() not in ("user-agent",) and "\n" not in f"{k}{v}"}
        ua = next((v for k, v in (headers or {}).items() if k.lower() == "user-agent"), USER_AGENT)
        args += ["-user_agent", ua, "-rw_timeout", "20000000"]
        if referer and not any(k.lower() == "referer" for k in hdrs):
            hdrs["Referer"] = referer
        if hdrs:
            args += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())]
    return args + ["-i", url]


@dataclass
class MediaSource:
    """What ffmpeg reads: the URL the user sent, or the stream yt-dlp resolved for a YouTube page."""
    url: str
    referer: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    duration: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)  # title / description / channel / tags – for the description check


def resolve_youtube(page_url: str) -> MediaSource:
    """YouTube page → direct video stream URL (≤ VIDEO_YTDLP_MAX_HEIGHT) and the video's metadata, via yt-dlp."""
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as e:
        raise VideoReviewError("yt-dlp לא מותקן (pip install yt-dlp)") from e
    h = int(VIDEO_YTDLP_MAX_HEIGHT)
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "socket_timeout": 20,
        "format": f"bv*[height<={h}]/b[height<={h}]/bv*/b",
    }
    if YTDLP_COOKIES_FILE:
        opts["cookiefile"] = YTDLP_COOKIES_FILE
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
    except DownloadError as e:
        msg = str(e)
        if "not a bot" in msg or "Sign in" in msg:
            raise VideoReviewError("יוטיוב חסם את שרת הבדיקה (אימות 'לא בוט') – הגדירו YTDLP_COOKIES_FILE או YTDLP_PROXY") from e
        raise VideoReviewError("yt-dlp: " + msg[-300:]) from e
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise VideoReviewError("שידור חי או שידור עתידי – לא ניתן לבדוק מראש")
    formats = info.get("requested_formats") or [info]
    video = next((f for f in formats if f.get("vcodec") not in (None, "none")), formats[0])
    if not video.get("url"):
        raise VideoReviewError("yt-dlp לא החזיר כתובת וידאו")
    return MediaSource(
        url=video["url"],
        headers=dict(video.get("http_headers") or info.get("http_headers") or {}),
        duration=float(info["duration"]) if info.get("duration") else None,
        metadata=_clean_metadata({
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "description": info.get("description"),
            "tags": ", ".join(info.get("tags") or []),
            "categories": ", ".join(info.get("categories") or []),
        }),
    )


def _clean_metadata(raw: Dict[str, Optional[str]]) -> Dict[str, str]:
    return {k: " ".join(str(v).split())[:3000] for k, v in raw.items() if v and str(v).strip()}


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to public http(s) addresses (a redirect to 127.0.0.1 must not bypass the SSRF check)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _MetaParser(HTMLParser):
    _WANTED = {"description", "keywords", "og:title", "og:description", "twitter:title", "twitter:description"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: Dict[str, str] = {}
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in self._WANTED and a.get("content"):
                self.meta.setdefault(key, a["content"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 500:
            self.title += data


def fetch_page_metadata(page_url: Optional[str], max_bytes: int = 1_500_000) -> Dict[str, str]:
    """Title / description of the page the video was found on (the only text a plain media URL has)."""
    if not page_url or urlsplit(page_url).scheme not in ("http", "https"):
        return {}
    try:
        check_public_url(page_url)
        opener = urllib.request.build_opener(_PublicRedirects)
        req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with opener.open(req, timeout=10) as resp:
            if "html" not in (resp.headers.get("content-type") or "html"):
                return {}
            raw = resp.read(max_bytes)
            charset = resp.headers.get_content_charset() or "utf-8"
        parser = _MetaParser()
        parser.feed(raw.decode(charset, errors="replace"))
    except Exception as e:  # metadata is a bonus: the frames are checked either way
        logger.info("Page metadata unavailable for %s: %s", page_url[:120], e)
        return {}
    m = parser.meta
    return _clean_metadata({
        "title": m.get("og:title") or m.get("twitter:title") or parser.title,
        "description": m.get("og:description") or m.get("description") or m.get("twitter:description"),
        "tags": m.get("keywords"),
    })


def resolve_source(review: dict) -> MediaSource:
    url = review["source_url"]
    if youtube_video_id(url):
        src = resolve_youtube(url)
        check_public_url(src.url)
        return src
    check_public_url(url)
    return MediaSource(url=url, referer=review.get("page_url"), metadata=fetch_page_metadata(review.get("page_url")))


def probe_format(url: str, referer: Optional[str], timeout: int = 60, headers: Optional[Dict[str, str]] = None,
                 protocols: Optional[str] = None) -> Tuple[Optional[float], Dict[str, str]]:
    """(duration or None if unknown/live, the file's own text tags: title / artist / comment …)."""
    cmd = ["ffprobe", "-v", "error"] + _input_args(url, referer, headers, protocols) + [
        "-show_entries", "format=duration:format_tags", "-of", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise VideoReviewError("ffprobe timeout") from e
    if out.returncode != 0:
        raise VideoReviewError("ffprobe failed: " + out.stderr.decode("utf-8", "replace")[-300:])
    try:
        fmt = (json.loads(out.stdout.decode("utf-8", "replace") or "{}").get("format") or {})
    except ValueError:
        fmt = {}
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    tags = {str(k).lower(): str(v) for k, v in (fmt.get("tags") or {}).items()}
    meta = _clean_metadata({
        "title": tags.get("title"),
        "channel": tags.get("artist") or tags.get("album_artist"),
        "description": tags.get("description") or tags.get("comment") or tags.get("synopsis"),
    })
    return (duration if duration > 0 else None), meta


def probe_duration(url: str, referer: Optional[str], timeout: int = 60, headers: Optional[Dict[str, str]] = None,
                   protocols: Optional[str] = None) -> Optional[float]:
    return probe_format(url, referer, timeout, headers, protocols)[0]


def _read_exact(stream: IO[bytes], n: int) -> Optional[bytes]:
    chunks, got = [], 0
    while got < n:
        chunk = stream.read(n - got)
        if not chunk:
            return None
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def read_ppm_frame(stream: IO[bytes]) -> Optional[Image.Image]:
    """Read one binary PPM (P6) image from an ffmpeg image2pipe stream."""
    tokens: list = []
    buf = b""
    while len(tokens) < 4:
        c = stream.read(1)
        if not c:
            return None
        if c == b"#":
            while c and c not in (b"\n", b"\r"):
                c = stream.read(1)
            continue
        if c.isspace():
            if buf:
                tokens.append(buf)
                buf = b""
        else:
            buf += c
    if tokens[0] != b"P6":
        raise VideoReviewError("unexpected frame format from ffmpeg")
    width, height = int(tokens[1]), int(tokens[2])
    data = _read_exact(stream, width * height * 3)
    if data is None:
        return None
    return Image.frombytes("RGB", (width, height), data)


def iter_frames(url: str, referer: Optional[str], fps: float, max_side: int, max_duration: float,
                headers: Optional[Dict[str, str]] = None, protocols: Optional[str] = None) -> Iterator[Tuple[float, Image.Image]]:
    scale = (
        f"scale='if(gte(iw,ih),min({max_side},iw),-2)':'if(gte(iw,ih),-2,min({max_side},ih))'"
    )
    cmd = (
        ["ffmpeg", "-nostdin", "-loglevel", "error"]
        + _input_args(url, referer, headers, protocols)
        + ["-t", str(int(max_duration) + 1), "-an", "-sn", "-vf", f"fps={fps},{scale}", "-f", "image2pipe", "-vcodec", "ppm", "-"]
    )
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        index = 0
        while True:
            frame = read_ppm_frame(proc.stdout)
            if frame is None:
                break
            yield index / fps, frame
            index += 1
        proc.wait(timeout=30)
        if proc.returncode not in (0, None) and index == 0:
            err = proc.stderr.read().decode("utf-8", "replace")[-300:] if proc.stderr else ""
            raise VideoReviewError("ffmpeg failed: " + err)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


def frame_to_jpeg(frame: Image.Image) -> bytes:
    img = frame.convert("RGB")
    img.thumbnail((VLM_MAX_SIDE, VLM_MAX_SIDE))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def review_video(review: dict, analyzer, fps: float = VIDEO_FPS, max_parallel: Optional[int] = None,
                 description_checker=None) -> dict:
    """Review one video: first its description (title, description, channel, tags), then its frames.
    Returns the fields for finish_video_review."""
    src = resolve_source(review)
    duration = src.duration
    if duration is None:
        duration, file_meta = probe_format(src.url, src.referer, headers=src.headers)
        for k, v in file_meta.items():
            src.metadata.setdefault(k, v)

    # 1. The description – before a single frame is downloaded. It can only block (a woman singing, a female
    #    presenter…), never approve: a clean description still goes to the frame check.
    if description_checker is not None and src.metadata:
        verdict = description_checker.check(src.metadata)
        if verdict is not None and verdict.blocked:
            return {"status": "blocked", "duration_sec": duration, "frames_sampled": 0, "frames_analyzed": 0,
                    "reason": f"לפי התיאור: {verdict.reason}" if verdict.reason else "לפי התיאור"}

    if duration is None:
        raise VideoReviewError("שידור חי או אורך לא ידוע – לא ניתן לבדוק מראש")
    if duration > VIDEO_MAX_DURATION_SEC:
        raise VideoReviewError(f"הסרטון ארוך מדי לבדיקה אוטומטית ({int(duration)} שניות)")

    # 2. The frames.
    cap = getattr(analyzer, "max_concurrency", None)
    parallel = max(1, min(int(cap) if cap else 4, max_parallel or 4))
    try:
        sampled, analyzed, blocked_at, worst_uncertain = _frame_loop(src, fps, duration, FrameChangeDetector(), analyzer, parallel)
    except VideoReviewError as e:
        if youtube_video_id(review["source_url"]) and "403" in str(e):
            raise VideoReviewError(
                "יוטיוב סירב להוריד את הסרטון לשרת הבדיקה (403). בדרך כלל: כתובת IP של שרת ענן. "
                "פתרון: YTDLP_PROXY (פרוקסי ביתי), YTDLP_COOKIES_FILE, או תוסף PO-token ל-yt-dlp (bgutil-ytdlp-pot-provider)."
            ) from e
        raise
    if sampled == 0:
        raise VideoReviewError("לא חולצו פריימים מהסרטון (אין בו וידאו?)")
    stats = {"duration_sec": duration, "frames_sampled": sampled, "frames_analyzed": analyzed}
    return _verdict(review, stats, blocked_at, worst_uncertain)


def _frame_loop(src: "MediaSource", fps: float, duration: float, detector: FrameChangeDetector, analyzer, parallel: int):
    sampled = analyzed = 0
    worst_uncertain: Optional[Tuple[float, Image.Image]] = None
    blocked_at: Optional[Tuple[float, Image.Image]] = None

    def check(t: float, frame: Image.Image):
        return t, frame, analyzer.analyze_image(frame_to_jpeg(frame), "image/jpeg")

    pending: set[Future] = set()
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        frames = iter_frames(src.url, src.referer, fps, VIDEO_FRAME_MAX_SIDE, duration, src.headers)
        try:
            for t, frame in frames:
                sampled += 1
                if not detector.should_analyze(frame, t).analyze:
                    continue
                analyzed += 1
                pending.add(pool.submit(check, t, frame))
                if len(pending) >= parallel:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for fut in done:
                        ft, fframe, result = fut.result()
                        if is_blocked(result):
                            blocked_at = (ft, fframe)
                        elif is_uncertain(result) and worst_uncertain is None:
                            worst_uncertain = (ft, fframe)
                    if blocked_at:
                        break  # the first bad frame decides – stop paying for the rest
            for fut in pending:
                ft, fframe, result = fut.result()
                if is_blocked(result) and (blocked_at is None or ft < blocked_at[0]):
                    blocked_at = (ft, fframe)
                elif is_uncertain(result) and worst_uncertain is None:
                    worst_uncertain = (ft, fframe)
        finally:
            frames.close()
    return sampled, analyzed, blocked_at, worst_uncertain


def _verdict(review: dict, stats: dict, blocked_at, worst_uncertain) -> dict:
    if blocked_at:
        save_thumbnail("videos", review["video_key"], blocked_at[1])
        return {"status": "blocked", "blocked_at_sec": blocked_at[0], "reason": "נמצא פריים אסור", **stats}
    if worst_uncertain:
        save_thumbnail("videos", review["video_key"], worst_uncertain[1])
        return {"status": "review", "blocked_at_sec": worst_uncertain[0], "reason": "המודל לא בטוח – ממתין לבודק", **stats}
    return {"status": "allowed", **stats}


def process_one(analyzer, description_checker=None) -> bool:
    review = pdb.claim_next_video_review()
    if not review:
        return False
    key = review["video_key"]
    logger.info("Reviewing video %s", key)
    started = time.time()
    try:
        outcome = review_video(review, analyzer, description_checker=description_checker)
        status = outcome.pop("status")
        pdb.finish_video_review(key, status, **outcome)
        logger.info("Video %s → %s (%.0fs, %s/%s frames analyzed)", key, status, time.time() - started,
                    outcome.get("frames_analyzed"), outcome.get("frames_sampled"))
    except VideoReviewError as e:
        pdb.finish_video_review(key, "error", reason=str(e)[:500])
        logger.warning("Video %s → error: %s", key, e)
    except Exception as e:  # never leave a row in 'processing'
        pdb.finish_video_review(key, "error", reason=f"שגיאה פנימית: {e}"[:500])
        logger.exception("Video review crashed for %s", key)
    return True


def run_forever(poll_sec: float = 2.0) -> None:
    from core.filters.image.analyzer_factory import create_image_analyzer
    from core.logger.logging_config import setup_logging

    setup_logging()
    from core.filters.video.description_check import create_description_checker

    analyzer = create_image_analyzer()
    description_checker = create_description_checker()
    logger.info("Video review worker started (fps=%s, description check: %s)", VIDEO_FPS, "on" if description_checker else "off")
    last_requeue = 0.0
    while True:
        if time.time() - last_requeue > 300:
            pdb.requeue_stuck_video_reviews()
            last_requeue = time.time()
        if not process_one(analyzer, description_checker):
            time.sleep(poll_sec)


if __name__ == "__main__":
    run_forever()

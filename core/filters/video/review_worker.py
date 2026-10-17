"""
Per-video review worker – like NetFree's video check: the video is cut into frames, the frames are checked,
and an approved video is opened for every user.

Run (separate process, next to the proxy; needs ffmpeg/ffprobe and the same IMAGE_ANALYZER / VLM_* settings):

    python -m core.filters.video.review_worker

Pipeline per video:
1. URL safety check (http/https to a public address only – the URL comes from a user; ffmpeg is also limited
   to network protocols, so file:// / concat tricks inside an HLS playlist are refused).
2. ffprobe → duration. Unknown duration (live stream) or longer than VIDEO_MAX_DURATION_SEC → error
   (a live stream cannot be reviewed in advance).
3. ffmpeg samples VIDEO_FPS frames per second (default 1).
4. FrameChangeDetector sends a frame to the model only if something changed since the last ANALYZED frame
   (local, tile-level: a small figure entering the frame triggers; a static shot does not) – plus a periodic check.
5. The model checks the selected frames (several in parallel); the first frame with a "Yes" blocks the video.
   Frames the model was unsure about send the video to the human review queue instead of opening it.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from io import BytesIO
from typing import IO, Iterator, Optional, Tuple
from urllib.parse import urlsplit

from PIL import Image

from core.filters.image.analysis import is_blocked, is_uncertain
from core.filters.review_store import save_thumbnail
from core.filters.video.frame_change import FrameChangeDetector
from core.policy import policy_database as pdb
from data.constants import (
    VIDEO_FPS,
    VIDEO_FRAME_MAX_SIDE,
    VIDEO_MAX_DURATION_SEC,
    VLM_MAX_SIDE,
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


def _input_args(url: str, referer: Optional[str]) -> list:
    args = ["-protocol_whitelist", PROTOCOL_WHITELIST]
    if urlsplit(url).scheme in ("http", "https"):
        # HTTP-only options (ffmpeg rejects them for other inputs)
        args += ["-user_agent", USER_AGENT, "-rw_timeout", "20000000"]
        if referer:
            args += ["-headers", f"Referer: {referer}\r\n"]
    return args + ["-i", url]


def probe_duration(url: str, referer: Optional[str], timeout: int = 60) -> Optional[float]:
    cmd = ["ffprobe", "-v", "error"] + _input_args(url, referer) + ["-show_entries", "format=duration", "-of", "default=nw=1:nk=1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise VideoReviewError("ffprobe timeout") from e
    if out.returncode != 0:
        raise VideoReviewError("ffprobe failed: " + out.stderr.decode("utf-8", "replace")[-300:])
    text = out.stdout.decode().strip().splitlines()
    try:
        value = float(text[0]) if text else 0.0
    except ValueError:
        return None
    return value if value > 0 else None


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


def iter_frames(url: str, referer: Optional[str], fps: float, max_side: int, max_duration: float) -> Iterator[Tuple[float, Image.Image]]:
    scale = (
        f"scale='if(gte(iw,ih),min({max_side},iw),-2)':'if(gte(iw,ih),-2,min({max_side},ih))'"
    )
    cmd = (
        ["ffmpeg", "-nostdin", "-loglevel", "error"]
        + _input_args(url, referer)
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


def review_video(review: dict, analyzer, fps: float = VIDEO_FPS, max_parallel: Optional[int] = None) -> dict:
    """Review one video. Returns the fields for finish_video_review (status + stats)."""
    url = review["source_url"]
    referer = review.get("page_url")
    check_public_url(url)
    duration = probe_duration(url, referer)
    if duration is None:
        raise VideoReviewError("שידור חי או אורך לא ידוע – לא ניתן לבדוק מראש")
    if duration > VIDEO_MAX_DURATION_SEC:
        raise VideoReviewError(f"הסרטון ארוך מדי לבדיקה אוטומטית ({int(duration)} שניות)")

    cap = getattr(analyzer, "max_concurrency", None)
    parallel = max(1, min(int(cap) if cap else 4, max_parallel or 4))
    detector = FrameChangeDetector()
    sampled = analyzed = 0
    worst_uncertain: Optional[Tuple[float, Image.Image]] = None
    blocked_at: Optional[Tuple[float, Image.Image]] = None

    def check(t: float, frame: Image.Image):
        return t, frame, analyzer.analyze_image(frame_to_jpeg(frame), "image/jpeg")

    pending: set[Future] = set()
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        frames = iter_frames(url, referer, fps, VIDEO_FRAME_MAX_SIDE, duration)
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

    stats = {"duration_sec": duration, "frames_sampled": sampled, "frames_analyzed": analyzed}
    if blocked_at:
        save_thumbnail("videos", review["video_key"], blocked_at[1])
        return {"status": "blocked", "blocked_at_sec": blocked_at[0], "reason": "נמצא פריים אסור", **stats}
    if sampled == 0:
        raise VideoReviewError("לא חולצו פריימים מהסרטון")
    if worst_uncertain:
        save_thumbnail("videos", review["video_key"], worst_uncertain[1])
        return {"status": "review", "blocked_at_sec": worst_uncertain[0], "reason": "המודל לא בטוח – ממתין לבודק", **stats}
    return {"status": "allowed", **stats}


def process_one(analyzer) -> bool:
    review = pdb.claim_next_video_review()
    if not review:
        return False
    key = review["video_key"]
    logger.info("Reviewing video %s", key)
    started = time.time()
    try:
        outcome = review_video(review, analyzer)
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
    analyzer = create_image_analyzer()
    logger.info("Video review worker started (fps=%s)", VIDEO_FPS)
    last_requeue = 0.0
    while True:
        if time.time() - last_requeue > 300:
            pdb.requeue_stuck_video_reviews()
            last_requeue = time.time()
        if not process_one(analyzer):
            time.sleep(poll_sec)


if __name__ == "__main__":
    run_forever()

"""Description check: the model reads title/description/channel/tags before any frame is downloaded."""
import http.server
import shutil
import subprocess
import threading

import pytest

from core.filters.video import description_check as dc
from core.filters.video import review_worker

META = {"title": "Official Music Video", "channel": "Some Artist", "description": "Lyrics below", "tags": "pop, music"}


def _reply(content, logprobs=None):
    choice = {"message": {"content": content}}
    if logprobs is not None:
        choice["logprobs"] = {"content": logprobs}
    return {"choices": [choice]}


def test_model_says_yes_blocks_with_its_reason(monkeypatch):
    checker = dc.DescriptionChecker()
    sent = {}
    monkeypatch.setattr(checker, "_post", lambda payload: sent.update(payload) or _reply('{"forbidden": "Yes", "reason": "זמרת"}'))
    v = checker.check(META)
    assert v.blocked and v.reason == "זמרת"
    user_text = sent["messages"][1]["content"]
    assert "Title: Official Music Video" in user_text and "Channel: Some Artist" in user_text
    assert sent["response_format"]["json_schema"]["schema"]["required"] == ["forbidden", "reason"]


def test_asymmetric_threshold_on_the_forbidden_token_only(monkeypatch):
    checker = dc.DescriptionChecker()
    lp = [{"token": "No", "top_logprobs": [{"token": "No", "logprob": -0.36}, {"token": "Yes", "logprob": -1.2}]},
          {"token": "No", "top_logprobs": [{"token": "No", "logprob": -0.001}]}]  # a "No" inside the reason must not count
    monkeypatch.setattr(checker, "_post", lambda payload: _reply('{"forbidden": "No", "reason": ""}', lp))
    v = checker.check(META)
    assert v.blocked and 0.25 < v.p_yes < 0.35  # model's top answer "No", but P(Yes) ≈ 0.3 ≥ 0.2


def test_clean_description_does_not_block_and_errors_give_no_verdict(monkeypatch):
    checker = dc.DescriptionChecker()
    monkeypatch.setattr(checker, "_post", lambda payload: _reply('{"forbidden": "No", "reason": ""}'))
    assert checker.check({"title": "שיעור בגמרא – מסכת ברכות", "channel": "הרב כהן"}).blocked is False

    def down(payload):
        raise OSError("connection refused")

    monkeypatch.setattr(checker, "_post", down)
    assert checker.check(META) is None
    assert checker.check({}) is None  # nothing to read


# ---------- in the worker ----------


class _Checker:
    def __init__(self, blocked):
        self.blocked = blocked
        self.seen = []

    def check(self, metadata):
        self.seen.append(metadata)
        return dc.DescriptionVerdict(self.blocked, "זמרת" if self.blocked else "", None)


class _CountingFrames:
    max_concurrency = 1

    def __init__(self):
        self.calls = 0

    def analyze_image(self, data, mime):
        from core.filters.image.analysis import CONDITION_KEYS

        self.calls += 1
        return {k: "No" for k in CONDITION_KEYS}


def test_youtube_blocked_by_description_without_downloading_a_frame(monkeypatch):
    monkeypatch.setattr(review_worker, "resolve_youtube", lambda url: review_worker.MediaSource(
        url="https://rr1---sn-x.googlevideo.com/videoplayback?id=o-1", duration=200.0,
        metadata={"title": "Song – Official Video", "channel": "A Female Singer"}))
    monkeypatch.setattr(review_worker, "check_public_url", lambda u: None)

    def no_frames(*a, **k):
        raise AssertionError("frames must not be downloaded when the description already blocks")

    monkeypatch.setattr(review_worker, "iter_frames", no_frames)
    checker = _Checker(blocked=True)
    out = review_worker.review_video({"source_url": "https://youtu.be/jNQXAC9IVRw", "video_key": "youtube:jNQXAC9IVRw"},
                                     _CountingFrames(), description_checker=checker)
    assert out["status"] == "blocked" and out["reason"] == "לפי התיאור: זמרת" and out["frames_analyzed"] == 0
    assert checker.seen[0]["channel"] == "A Female Singer"


@pytest.fixture
def clip_and_page(tmp_path, monkeypatch):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg not installed")
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x406080:s=160x120:d=4:r=5",
                    "-metadata", "title=Clip title from the file", "-pix_fmt", "yuv420p", str(clip)], check=True)
    (tmp_path / "page.html").write_text(
        '<html><head><title>Ignored when og exists</title><meta property="og:title" content="Page OG title">'
        '<meta name="description" content="A page about the clip"></head><body></body></html>', encoding="utf-8")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(review_worker, "check_public_url", lambda u: None)
    monkeypatch.setattr(review_worker, "PROTOCOL_WHITELIST", "file,http,tcp")
    yield str(clip), f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


def test_plain_video_gets_page_and_file_metadata_and_a_clean_description_still_checks_frames(clip_and_page):
    clip, page = clip_and_page
    checker = _Checker(blocked=False)
    frames = _CountingFrames()
    out = review_worker.review_video({"source_url": clip, "page_url": page, "video_key": "t:" + clip}, frames,
                                     description_checker=checker)
    meta = checker.seen[0]
    assert meta["title"] == "Page OG title" and meta["description"] == "A page about the clip"
    assert out["status"] == "allowed" and frames.calls >= 1  # description approves nothing – frames decided


def test_file_tags_used_when_there_is_no_page(clip_and_page):
    clip, _ = clip_and_page
    checker = _Checker(blocked=True)
    out = review_worker.review_video({"source_url": clip, "video_key": "t2:" + clip}, _CountingFrames(), description_checker=checker)
    assert checker.seen[0]["title"] == "Clip title from the file"
    assert out["status"] == "blocked"


def test_page_metadata_refuses_redirect_to_an_internal_address(monkeypatch):
    calls = []

    def guard(url):
        calls.append(url)
        if "127.0.0.1" in url or "169.254" in url:
            raise review_worker.VideoReviewError("internal")

    monkeypatch.setattr(review_worker, "check_public_url", guard)
    assert review_worker.fetch_page_metadata("http://169.254.169.254/latest/meta-data") == {}
    assert calls == ["http://169.254.169.254/latest/meta-data"]

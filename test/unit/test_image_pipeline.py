import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import pytest
from PIL import Image

from core.filters.image import image_status_manager as ism
from core.filters.image.analysis import CONDITION_KEYS, analyze_image_frames
from core.filters.image.analyzers import openai_compat
from core.filters.image.analyzers.policy import apply_yes_threshold
from core.filters.image.image_preprocess import prepare_frames
from core.filters.image.image_processing_queue import ImageProcessingQueue
from core.filters.image.image_status_db import _db, get_image_status, mark_error, mark_pending


def _gif(colors):
    frames = [Image.new("RGB", (64, 48), c) for c in colors]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=50, loop=0)
    return buf.getvalue()


class TestPreprocess:
    def test_animation_samples_several_frames(self):
        frames = prepare_frames(_gif(["white", "white", "white", "red", "red", "white", "white", "white"]), "image/gif")
        assert 2 <= len(frames) <= 4
        assert all(f.startswith(b"\xff\xd8") for f in frames)

    def test_webp_and_small_images_become_upscaled_jpeg(self):
        buf = io.BytesIO()
        Image.new("RGBA", (40, 20), (255, 0, 0, 128)).save(buf, "WEBP")
        (frame,) = prepare_frames(buf.getvalue(), "image/webp")
        img = Image.open(io.BytesIO(frame))
        assert img.format == "JPEG" and min(img.size) >= 256 - 1

    def test_svg_is_rasterized(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
        (frame,) = prepare_frames(svg, "image/svg+xml")
        assert frame.startswith(b"\xff\xd8")


class TestFrameAnalysis:
    def test_any_bad_frame_blocks_the_animation(self):
        analyzer = MagicMock(spec=["analyze_image"])
        answers = iter([{k: "No" for k in CONDITION_KEYS}, {**{k: "No" for k in CONDITION_KEYS}, "female_visible_9_plus": "Yes"}])
        analyzer.analyze_image.side_effect = lambda *a: next(answers)
        result = analyze_image_frames(analyzer, _gif(["white", "white", "red", "red"]), "image/gif")
        assert result["female_visible_9_plus"] == "Yes"


class TestYesThreshold:
    def _logprobs(self, p_yes_for_first):
        import math
        toks = []
        for i, _ in enumerate(CONDITION_KEYS):
            p_yes = p_yes_for_first if i == 0 else 0.01
            toks.append({"token": "No", "logprob": math.log(1 - p_yes), "top_logprobs": [
                {"token": "No", "logprob": math.log(1 - p_yes)},
                {"token": "Yes", "logprob": math.log(p_yes)},
            ]})
        return toks

    def test_uncertain_no_becomes_yes(self):
        answer = {k: "No" for k in CONDITION_KEYS}
        out = apply_yes_threshold(answer, self._logprobs(0.3), threshold=0.2)
        assert out["female_visible_9_plus"] == "Yes"
        assert out["any_visible_body_exposure"] == "No"

    def test_confident_no_stays_no(self):
        answer = {k: "No" for k in CONDITION_KEYS}
        assert apply_yes_threshold(answer, self._logprobs(0.05), threshold=0.2) == answer


class _FakeVLM(BaseHTTPRequestHandler):
    last_body = None

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeVLM.last_body = body
        content = json.dumps({k: "No" for k in CONDITION_KEYS})
        resp = {"choices": [{"message": {"content": content}}]}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestOpenAICompatAnalyzer:
    def test_sends_schema_and_image(self, monkeypatch):
        server = HTTPServer(("127.0.0.1", 0), _FakeVLM)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            a = openai_compat.OpenAICompatImageAnalyzer()
            a.url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            result = a.analyze_image(b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")
            assert result == {k: "No" for k in CONDITION_KEYS}
            body = _FakeVLM.last_body
            assert body["response_format"]["type"] == "json_schema"
            assert body["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
            assert body["temperature"] == 0
        finally:
            server.shutdown()


class TestQueue:
    def test_dedupe_and_cleanup(self):
        release = threading.Event()
        analyzer = MagicMock()
        analyzer.analyze_image.side_effect = lambda *a: (release.wait(5), {k: "No" for k in CONDITION_KEYS})[1]
        done = []
        q = ImageProcessingQueue(analyzer, lambda *a: done.append(a), analysis_timeout_seconds=10, max_workers=1)
        try:
            assert q.enqueue(b"x" * 20, "image/png", {"image_hash": "dup"}) is not None
            assert q.enqueue(b"x" * 20, "image/png", {"image_hash": "dup"}) is None  # same image already in flight
            release.set()
            q.wait_until_done()
            assert len(done) == 1
            assert q.tasks == {} and not q.is_inflight("dup")  # finished tasks are forgotten (no leak)
        finally:
            q._shutdown.set()

    def test_full_queue_rejects(self):
        analyzer = MagicMock()
        analyzer.analyze_image.side_effect = lambda *a: time.sleep(1) or {k: "No" for k in CONDITION_KEYS}
        q = ImageProcessingQueue(analyzer, lambda *a: None, max_workers=1, max_queue=1)
        try:
            results = [q.enqueue(b"y" * 20, "image/png", {"image_hash": f"h{i}"}) for i in range(5)]
            assert results.count(None) >= 3
        finally:
            q._shutdown.set()


class TestRetry:
    def test_stale_pending_is_retried(self, monkeypatch):
        mark_pending("stale-hash", "https://x/1.png", "image/png", 10, 10)
        _db.execute("UPDATE image_status SET updated_at = 0 WHERE image_hash = 'stale-hash'")
        _db.commit()
        info = get_image_status("stale-hash")
        info["_hash"] = "stale-hash"
        assert ism._should_retry(info)

    def test_error_retried_until_max_attempts(self):
        mark_error("err-hash")
        _db.execute("UPDATE image_status SET updated_at = 0, attempts = 1 WHERE image_hash = 'err-hash'")
        _db.commit()
        info = {**get_image_status("err-hash"), "_hash": "err-hash"}
        assert ism._should_retry(info)
        _db.execute("UPDATE image_status SET attempts = 99 WHERE image_hash = 'err-hash'")
        _db.commit()
        info = {**get_image_status("err-hash"), "_hash": "err-hash"}
        assert not ism._should_retry(info)

    def test_animated_images_are_hashed_by_bytes(self):
        a = _gif(["white", "white", "red"])
        b = _gif(["white", "white", "blue"])
        assert ism._image_hash(a, "image/gif") != ism._image_hash(b, "image/gif")

"""Per-video review: frame change detection, the ffmpeg worker, the review queue and the proxy side."""
import io
import random
import shutil
import subprocess

import pytest
from mitmproxy.test import tflow, tutils
from PIL import Image, ImageDraw

from core.filters.image.analysis import CONDITION_KEYS
from core.filters.video import review_worker
from core.filters.video.frame_change import FrameChangeDetector
from core.filters.video.video_filter import hls_child_urls
from core.policy import policy_cache, policy_database as pdb
from core.proxy import mitmproxy_addon as addon_mod
from core.proxy import proxy_auth

# ---------- frame change detection ----------


def _scene(w=640, h=360, figure=None, shift=0, noise=0, seed=1):
    """A textured background (so a shift is visible), optionally with a small figure at `figure`=(x, y)."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), (90, 110, 130))
    d = ImageDraw.Draw(img)
    for i in range(0, w + 80, 40):
        d.rectangle([i + shift, 0, i + shift + 18, h], fill=(70, 90, 110))
    if figure:
        x, y = figure
        d.rectangle([x, y, x + 24, y + 48], fill=(230, 190, 160))
    if noise:
        px = img.load()
        for _ in range(w * h // 20):
            x, y = rnd.randrange(w), rnd.randrange(h)
            r, g, b = px[x, y]
            n = rnd.randint(-noise, noise)
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return img


class TestFrameChangeDetector:
    def test_first_frame_is_always_analyzed(self):
        assert FrameChangeDetector().should_analyze(_scene(), 0).analyze

    def test_static_shot_and_compression_noise_are_skipped(self):
        det = FrameChangeDetector(force_every_sec=1000)
        det.should_analyze(_scene(), 0)
        for t in range(1, 6):
            assert not det.should_analyze(_scene(noise=6, seed=t), t).analyze

    def test_small_figure_entering_a_corner_is_caught(self):
        det = FrameChangeDetector(force_every_sec=1000)
        det.should_analyze(_scene(), 0)
        d = det.should_analyze(_scene(figure=(600, 300)), 1)
        assert d.analyze and d.changed_tiles >= 1

    def test_slow_drift_accumulates_against_the_last_analyzed_frame(self):
        det = FrameChangeDetector(force_every_sec=1000)
        det.should_analyze(_scene(), 0)
        decisions = [det.should_analyze(_scene(shift=s), s).analyze for s in range(1, 12)]
        assert any(decisions), "a scene that keeps moving must be re-checked at some point"
        assert not decisions[0], "a 1-px move alone is not a new scene"

    def test_periodic_safety_check(self):
        det = FrameChangeDetector(force_every_sec=10)
        det.should_analyze(_scene(), 0)
        assert not det.should_analyze(_scene(), 5).analyze
        assert det.should_analyze(_scene(), 10).analyze


# ---------- worker pieces ----------


def test_read_ppm_frame_handles_header_comments():
    img = Image.new("RGB", (3, 2), (10, 20, 30))
    raw = b"P6\n# made by a test\n3 2\n255\n" + img.tobytes()
    stream = io.BytesIO(raw + raw)
    a = review_worker.read_ppm_frame(stream)
    b = review_worker.read_ppm_frame(stream)
    assert a.size == (3, 2) and a.getpixel((0, 0)) == (10, 20, 30)
    assert b is not None and review_worker.read_ppm_frame(stream) is None


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/v.mp4", "http://10.1.2.3/v.mp4", "http://[::1]/v.mp4", "http://169.254.169.254/latest",
    "file:///etc/passwd", "ftp://example.org/v.mp4", "concat:a|b",
])
def test_check_public_url_refuses_internal_and_non_http(url):
    with pytest.raises(review_worker.VideoReviewError):
        review_worker.check_public_url(url)


def test_ffmpeg_is_limited_to_network_protocols():
    args = review_worker._input_args("https://cdn.example/v.m3u8", "https://site.example/")
    whitelist = args[args.index("-protocol_whitelist") + 1].split(",")
    assert "file" not in whitelist and "concat" not in whitelist
    assert "Referer: https://site.example/\r\n" in args


# ---------- review queue ----------


def test_canonical_media_key_drops_signing_params_only():
    k1 = pdb.canonical_media_key("https://CDN.example/v.mp4?id=7&token=abc&Expires=1&X-Amz-Signature=z")
    k2 = pdb.canonical_media_key("https://cdn.example/v.mp4?token=other&id=7")
    assert k1 == k2 == "https://cdn.example/v.mp4?id=7"
    assert pdb.canonical_media_key("https://cdn.example/v.mp4?id=8") != k1


def _new_url(name):
    return f"https://videos.example/{name}-{random.randrange(10**9)}.mp4"


def test_request_claim_finish_and_approval():
    url = _new_url("flow")
    r = pdb.request_video_review(url, "https://site.example/p", 42)
    assert r["status"] == "pending"
    assert pdb.request_video_review(url + "?token=x", None, 43)["video_key"] == r["video_key"]  # deduplicated
    claimed = None
    while True:  # other tests may have left pending rows
        c = pdb.claim_next_video_review()
        assert c is not None
        if c["video_key"] == r["video_key"]:
            claimed = c
            break
        pdb.finish_video_review(c["video_key"], "error", reason="test cleanup")
    assert claimed["status"] == "processing"
    pdb.finish_video_review(r["video_key"], "allowed", duration_sec=12, frames_sampled=12, frames_analyzed=3)
    policy_cache.invalidate()
    assert policy_cache.is_media_approved(url + "?expires=99")


def test_hls_children_are_attached_to_the_root_and_revoked_with_it():
    master = _new_url("master").replace(".mp4", ".m3u8")
    r = pdb.request_video_review(master, None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    playlist = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nlow/index.m3u8\n#EXT-X-MEDIA:TYPE=AUDIO,URI=\"audio.m3u8\"\n"
    children = hls_child_urls(playlist, master)
    assert children == [master.rsplit("/", 1)[0] + "/low/index.m3u8", master.rsplit("/", 1)[0] + "/audio.m3u8"]
    pdb.add_approved_media_children(r["video_key"], children)
    variant_key = pdb.canonical_media_key(children[0])
    segment = children[0].rsplit("/", 1)[0] + "/seg1.ts"
    pdb.add_approved_media_children(variant_key, [segment])  # second level → still under the master
    policy_cache.invalidate()
    assert policy_cache.is_media_approved(segment)
    pdb.finish_video_review(r["video_key"], "blocked", reason="admin")
    policy_cache.invalidate()
    assert not policy_cache.is_media_approved(segment)
    assert not policy_cache.is_media_approved(master)


# ---------- the worker on a real clip ----------


class _RedFigureAnalyzer:
    """Stands in for the VLM: 'Yes' when the frame contains the red figure. Counts calls."""
    max_concurrency = 2

    def __init__(self, uncertain=False):
        self.calls = 0
        self.uncertain = uncertain

    def analyze_image(self, data, mime):
        self.calls += 1
        img = Image.open(io.BytesIO(data)).convert("RGB")
        px = img.tobytes()
        red = sum(1 for i in range(0, len(px), 3) if px[i] > 180 and px[i + 1] < 80 and px[i + 2] < 80)
        result = {k: "No" for k in CONDITION_KEYS}
        if red > 50:
            if self.uncertain:
                result["_p_yes_max"] = 0.1
            else:
                result[CONDITION_KEYS[0]] = "Yes"
        return result


@pytest.fixture
def clip(tmp_path):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg not installed")

    def make(figure_from=None, seconds=8):
        out = tmp_path / f"clip-{figure_from}.mp4"
        vf = "drawgrid=w=40:h=40:color=gray@0.5"
        if figure_from is not None:
            vf += f",drawbox=x=260:y=170:w=40:h=60:color=red:t=fill:enable='gte(t,{figure_from})'"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x406080:s=320x240:d={seconds}:r=10",
             "-vf", vf, "-pix_fmt", "yuv420p", str(out)],
            check=True,
        )
        return str(out)

    return make


@pytest.fixture
def local_files(monkeypatch):
    monkeypatch.setattr(review_worker, "check_public_url", lambda url: None)
    monkeypatch.setattr(review_worker, "PROTOCOL_WHITELIST", "file")


@pytest.mark.parametrize("fps", [1, 2])
def test_worker_blocks_at_the_frame_where_the_figure_enters(clip, local_files, fps):
    path = clip(figure_from=4)
    analyzer = _RedFigureAnalyzer()
    out = review_worker.review_video({"source_url": path, "video_key": "test:" + path}, analyzer, fps=fps)
    assert out["status"] == "blocked"
    assert 4.0 <= out["blocked_at_sec"] <= 4.5
    assert out["frames_analyzed"] < out["frames_sampled"], "unchanged frames must not reach the model"


def test_worker_allows_a_clean_clip_with_few_model_calls(clip, local_files):
    path = clip(figure_from=None)
    analyzer = _RedFigureAnalyzer()
    out = review_worker.review_video({"source_url": path, "video_key": "test:" + path}, analyzer, fps=2)
    assert out["status"] == "allowed"
    assert out["frames_sampled"] >= 15 and analyzer.calls <= 2


def test_worker_sends_unsure_video_to_human_review(clip, local_files):
    path = clip(figure_from=2)
    out = review_worker.review_video({"source_url": path, "video_key": "test:u:" + path}, _RedFigureAnalyzer(uncertain=True), fps=1)
    assert out["status"] == "review"


# ---------- proxy side ----------


def _video_flow(url, ct="video/mp4"):
    req = tutils.treq()
    req.url = url
    f = tflow.tflow(req=req)
    f.response = tutils.tresp(content=b"")
    f.response.headers["content-type"] = ct
    f.metadata["user_id"] = 42
    f.metadata["request_rule"] = {"state": "allow", "video_filter_enabled": True}
    return f


@pytest.fixture
def addon(monkeypatch):
    monkeypatch.setattr(proxy_auth, "PROXY_REQUIRE_AUTH", True)
    monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
    policy_cache.invalidate()
    return addon_mod.FilterAddon()


def test_blocked_video_is_recorded_for_the_review_page(addon):
    url = _new_url("blocked")
    f = _video_flow(url)
    addon.responseheaders(f)
    assert f.response.status_code == 418
    keys = [i["media_key"] for i in pdb.list_recent_blocked_media(42)]
    assert pdb.canonical_media_key(url) in keys


def test_approved_video_streams_and_approved_manifest_registers_its_segments(addon):
    import asyncio

    url = _new_url("ok")
    r = pdb.request_video_review(url, None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    policy_cache.invalidate()
    f = _video_flow(url + "?token=fresh")
    addon.responseheaders(f)
    assert f.response.status_code == 200 and f.response.stream is True

    master = url.replace(".mp4", ".m3u8")
    r = pdb.request_video_review(master, None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    policy_cache.invalidate()
    f = _video_flow(master, ct="application/vnd.apple.mpegurl")
    addon.responseheaders(f)
    assert f.metadata.get("approved_manifest")
    f.response.text = "#EXTM3U\n#EXTINF:4,\nseg-1.ts\n"
    asyncio.run(addon.response(f))
    seg = master.rsplit("/", 1)[0] + "/seg-1.ts"
    policy_cache.invalidate()
    g = _video_flow(seg, ct="video/mp2t")
    addon.responseheaders(g)
    assert g.response.status_code == 200

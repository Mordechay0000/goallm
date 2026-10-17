"""Audio (kol isha): proxy blocking of audio responses, the audio analyzer, and the worker's audio pass."""
import json
import shutil
import subprocess
from array import array

import pytest
from mitmproxy.test import tflow, tutils

from core.filters.audio import audio_analyzer as aa
from core.filters.video import review_worker
from core.filters.video.video_filter import is_audio_response
from core.policy import policy_cache, policy_database as pdb
from core.proxy import mitmproxy_addon as addon_mod
from core.proxy import proxy_auth


@pytest.mark.parametrize("ct,path,expected", [
    ("audio/mpeg", "/song", True), ("audio/ogg; codecs=opus", "/v", True), ("", "/a/b.mp3", True),
    ("application/octet-stream", "/voice.opus", True), ("audio/x-mpegurl", "/list.m3u8", False),
    ("text/html", "/x.mp3", False), ("image/png", "/a.png", False),
])
def test_is_audio_response(ct, path, expected):
    assert is_audio_response(ct, path) is expected


def _audio_flow(url="https://songs.example/track.mp3", ct="audio/mpeg"):
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
    yield addon_mod.FilterAddon()
    pdb.set_filter_switch("audio_filter", True)


def test_song_is_blocked_unbuffered_and_listed_for_review(addon):
    f = _audio_flow("https://songs.example/blocked-song.mp3")
    addon.responseheaders(f)
    assert f.response.status_code == 418 and f.response.stream(b"x") == b""
    assert f.metadata["traffic_status"] == "audio_blocked"
    assert "https://songs.example/blocked-song.mp3" in [m["media_url"] for m in pdb.list_recent_blocked_media(42)]


def test_audio_passes_when_switch_off_site_open_or_approved(addon):
    pdb.set_filter_switch("audio_filter", False)
    policy_cache.invalidate()
    f = _audio_flow()
    addon.responseheaders(f)
    assert f.response.status_code == 200 and f.response.stream is True
    pdb.set_filter_switch("audio_filter", True)
    policy_cache.invalidate()
    g = _audio_flow()
    g.metadata["request_rule"] = {"state": "allow", "video_filter_enabled": False}  # media open for the site
    addon.responseheaders(g)
    assert g.response.status_code == 200
    r = pdb.request_video_review("https://songs.example/approved.mp3", None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    policy_cache.invalidate()
    h = _audio_flow("https://songs.example/approved.mp3")
    addon.responseheaders(h)
    assert h.response.status_code == 200


# ---------- analyzer ----------


def test_pcm_loudness():
    assert aa.pcm_dbfs(b"\x00\x00" * 1000) == float("-inf")
    loud = array("h", [20000, -20000] * 1000).tobytes()
    assert -5 < aa.pcm_dbfs(loud) < 0


def test_analyzer_parses_and_applies_the_asymmetric_threshold(monkeypatch):
    an = aa.OpenAICompatAudioAnalyzer()
    sent = {}

    def fake_post(payload):
        sent.update(payload)
        # model says "No" to singing, but with P(Yes)=0.3 ≥ threshold 0.2 → Yes
        return {"choices": [{"message": {"content": '{"female_singing": "No", "female_speech": "No"}'},
                             "logprobs": {"content": [
                                 {"token": "No", "top_logprobs": [{"token": "No", "logprob": -0.36}, {"token": "Yes", "logprob": -1.2}]},
                                 {"token": "No", "top_logprobs": [{"token": "No", "logprob": -0.01}]},
                             ]}}]}

    monkeypatch.setattr(an, "_post", fake_post)
    result = an.analyze_wav(aa.pcm_to_wav(b"\x00\x00" * 16000))
    assert result["female_singing"] == "Yes" and aa.is_audio_blocked(result)
    part = sent["messages"][1]["content"][0]
    assert part["type"] == "input_audio" and part["input_audio"]["format"] == "wav"
    assert sent["response_format"]["json_schema"]["schema"]["required"] == ["female_singing", "female_speech"]


def test_speech_blocks_only_when_configured(monkeypatch):
    r = {"female_singing": "No", "female_speech": "Yes"}
    monkeypatch.setattr(aa, "AUDIO_BLOCK_SPEECH", False)
    assert not aa.is_audio_blocked(r)
    monkeypatch.setattr(aa, "AUDIO_BLOCK_SPEECH", True)
    assert aa.is_audio_blocked(r)


def test_bad_answer_raises():
    with pytest.raises(Exception):
        aa.parse_audio_answer('{"female_singing": "maybe"}')


# ---------- worker ----------


class _PitchAnalyzer:
    """Stands in for the audio model: 'female singing' = a high tone (> 700 Hz by zero crossings)."""
    max_concurrency = 2

    def __init__(self):
        self.calls = 0

    def analyze_wav(self, wav):
        import io
        import wave

        self.calls += 1
        with wave.open(io.BytesIO(wav)) as w:
            pcm = array("h", w.readframes(w.getnframes()))
        crossings = sum(1 for a, b in zip(pcm, pcm[1:]) if (a < 0) != (b < 0))
        freq = crossings / 2 / (len(pcm) / 16000)
        return {"female_singing": "Yes" if freq > 700 else "No", "female_speech": "No"}


@pytest.fixture
def media(tmp_path, monkeypatch):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg not installed")
    monkeypatch.setattr(review_worker, "check_public_url", lambda url: None)
    monkeypatch.setattr(review_worker, "PROTOCOL_WHITELIST", "file")

    def make(name, filters, video=False):
        out = tmp_path / name
        cmd = ["ffmpeg", "-loglevel", "error", "-y"]
        if video:
            cmd += ["-f", "lavfi", "-i", "color=c=0x406080:s=160x120:d=60:r=5"]
        cmd += ["-f", "lavfi", "-i", filters]
        if video:
            cmd += ["-shortest", "-pix_fmt", "yuv420p", "-c:v", "libvpx-vp9", "-b:v", "50k"]
        subprocess.run(cmd + ["-c:a", "libopus", str(out)], check=True)
        return str(out)

    return make


# 20 s silence, 20 s low tone (a man), 20 s high tone (stands for a woman singing)
_TRACK = ("anullsrc=r=16000:cl=mono:d=20[s];sine=f=220:d=20:r=16000[l];sine=f=1000:d=20:r=16000[h];"
          "[s][l][h]concat=n=3:v=0:a=1")


def test_audio_file_is_checked_skipping_silence_and_blocked_at_the_right_second(media):
    path = media("song.webm", _TRACK)
    an = _PitchAnalyzer()
    out = review_worker.review_video({"source_url": path, "video_key": "t:" + path}, object(), audio_analyzer=an)
    assert out["status"] == "blocked" and "שירה של אישה" in out["reason"]
    assert 39 <= out["blocked_at_sec"] <= 41
    assert an.calls == 2  # the silent first chunk never reached the model


def test_clean_audio_allowed(media):
    path = media("speech.webm", "sine=f=220:d=30:r=16000")
    out = review_worker.review_video({"source_url": path, "video_key": "t:" + path}, object(), audio_analyzer=_PitchAnalyzer())
    assert out["status"] == "allowed"


def test_video_with_sound_waits_for_a_human_when_no_audio_model(media, monkeypatch):
    import data.constants as c

    monkeypatch.setattr(c, "VIDEO_REQUIRE_AUDIO_CHECK", True)
    path = media("clip.webm", "sine=f=1000:d=60:r=16000", video=True)

    class CleanFrames:
        max_concurrency = 2

        def analyze_image(self, data, mime):
            from core.filters.image.analysis import CONDITION_KEYS
            return {k: "No" for k in CONDITION_KEYS}

    out = review_worker.review_video({"source_url": path, "video_key": "t:" + path}, CleanFrames())
    assert out["status"] == "review" and "הקול לא נבדק" in out["reason"]
    out2 = review_worker.review_video({"source_url": path, "video_key": "t2:" + path}, CleanFrames(), audio_analyzer=_PitchAnalyzer())
    assert out2["status"] == "blocked"  # clean frames, but a woman "sings" in the background

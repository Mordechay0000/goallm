"""YouTube per-video filtering (player responses + stream ids) and the blocked-video overlay endpoints."""
import asyncio
import json
import random

import pytest
from mitmproxy.test import tflow, tutils

from core.filters.video import review_worker
from core.filters.video import youtube as yt
from core.flow.http_flow_processor import process_http_response
from core.policy import policy_cache, policy_database as pdb
from core.proxy import mitmproxy_addon as addon_mod
from core.proxy import proxy_auth
from core.proxy.video_overlay import OVERLAY_SCRIPT, ReviewRateLimiter, request_review, video_status

GV = "https://rr2---sn-tt1e7nl6.googlevideo.com/videoplayback?expire=1792285015&ei=x&ip=1.2.3.4&id={sid}&itag={itag}&source=youtube&mime=video%2Fmp4&sig=s"


def _vid():
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") for _ in range(11))


def _player(vid, sid="o-AD5LmFC0K7jDNj_ww", live=False):
    return {
        "responseContext": {},
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"videoId": vid, "isLive": live, "lengthSeconds": "19"},
        "streamingData": {
            "formats": [{"itag": 18, "url": GV.format(sid=sid, itag=18)}],
            "adaptiveFormats": [{"itag": 140, "signatureCipher": "s=AB&sp=sig&url=" + GV.format(sid=sid, itag=140).replace("&", "%26").replace("=", "%3D").replace("?", "%3F")}],
            "serverAbrStreamingUrl": GV.format(sid=sid, itag=0) + "&sabr=1",
        },
    }


def _watch_html(pr):
    # Same shape as the real page: inline script with a nonce, the object, then more code on the same line.
    return ('<html><body><script nonce="abc">var ytInitialPlayerResponse = ' + json.dumps(pr)
            + ";var meta = document.createElement('meta');</script></body></html>")


@pytest.fixture(scope="module", autouse=True)
def _sites():
    # Whitelist: the sites are allowed, video stays filtered (the default) – except video-open.example.
    for domain in ("youtube.com", "googlevideo.com", "news.example"):
        pdb.add_policy(domain, None, state="allow", source="global")
    pdb.add_policy("video-open.example", None, state="allow", source="global", video_filter_enabled=False)
    pdb.set_profile_mode("blacklist", 42)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
    monkeypatch.setattr(proxy_auth, "PROXY_REQUIRE_AUTH", True)
    policy_cache.invalidate()
    yield


def _approve(vid):
    r = pdb.request_video_review(yt.watch_url(vid), None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    policy_cache.invalidate()


# ---------- URL identity ----------


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=jNQXAC9IVRw&t=3", "https://youtu.be/jNQXAC9IVRw", "https://m.youtube.com/shorts/jNQXAC9IVRw",
    "https://www.youtube-nocookie.com/embed/jNQXAC9IVRw?rel=0", "https://www.youtube.com/live/jNQXAC9IVRw",
])
def test_every_youtube_url_form_maps_to_one_key(url):
    assert pdb.canonical_media_key(url) == "youtube:jNQXAC9IVRw"


def test_lookalike_hosts_and_bad_ids_are_not_youtube():
    assert yt.youtube_video_id("https://youtube.com.evil.example/watch?v=jNQXAC9IVRw") is None
    assert yt.youtube_video_id("https://www.youtube.com/watch?v=short") is None


def test_googlevideo_key_uses_the_stream_id():
    assert pdb.canonical_media_key(GV.format(sid="o-ABC", itag=18)) == "googlevideo:o-ABC"
    manifest = "https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1/ei/x/id/8cd417002f48551c/itag/233/source/youtube"
    assert pdb.canonical_media_key(manifest) == "googlevideo:8cd417002f48551c"


# ---------- player responses ----------


def test_watch_page_of_unapproved_video_shows_our_message_and_loses_its_streams():
    vid = _vid()
    new, decisions = yt.filter_watch_html(_watch_html(_player(vid)), lambda v: ("block", {"status": "pending"}), vid)
    assert decisions == [(vid, "block", [])]
    obj, end = json.JSONDecoder().raw_decode(new, new.index("ytInitialPlayerResponse = ") + 26)
    assert obj["playabilityStatus"]["status"] == "ERROR" and obj["playabilityStatus"]["reason"] == "הסרטון בבדיקה"
    assert "streamingData" not in obj
    assert new[end:].startswith(";var meta")  # the rest of the script is intact


def test_approved_video_passes_untouched_and_reports_all_its_streams():
    vid = _vid()
    html = _watch_html(_player(vid, sid="o-XYZ"))
    new, decisions = yt.filter_watch_html(html, lambda v: ("allow", None), vid)
    assert new is None
    (_, decision, urls), = decisions
    assert decision == "allow" and yt.stream_ids(urls) == {"o-XYZ"} and len(urls) == 3  # direct, ciphered, SABR


def test_live_stream_is_blocked_even_if_asked_to_allow():
    vid = _vid()
    _, decisions = yt.filter_player_json(json.dumps(_player(vid, live=True)).encode(), lambda v: ("allow", None))
    assert decisions[0][1] == "block"


def test_nested_api_responses_are_found_whatever_the_wrapper():
    vid = _vid()
    doc = [{"playerResponse": _player(vid)}, {"watchNextResponse": {"contents": {}}}]  # get_watch-like
    new, decisions = yt.filter_player_json(json.dumps(doc).encode(), lambda v: ("block", None))
    assert decisions[0][:2] == (vid, "block")
    assert json.loads(new)[0]["playerResponse"]["playabilityStatus"]["status"] == "ERROR"


def test_embed_preview_is_blocked_up_front():
    vid = _vid()
    inner = json.dumps({"responseContext": {}, "previewPlayabilityStatus": {"status": "OK"}})
    html = '<script>ytcfg.set({"PLAYER_VARS":{"embedded_player_response":' + json.dumps(inner) + '}});</script>'
    new, _ = yt.filter_watch_html(html, lambda v: ("block", None), vid)
    k = '"embedded_player_response":'
    raw, _ = json.JSONDecoder().raw_decode(new, new.index(k) + len(k))
    assert json.loads(raw)["previewPlayabilityStatus"]["status"] == "ERROR"


# ---------- through the proxy ----------


def _api_flow(vid, pr, user_id=42):
    req = tutils.treq(method=b"POST", content=json.dumps({"context": {}, "videoId": vid}).encode())
    req.url = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
    req.headers["referer"] = yt.watch_url(vid)
    f = tflow.tflow(req=req)
    f.response = tutils.tresp(content=json.dumps(pr).encode())
    f.response.headers["content-type"] = "application/json; charset=UTF-8"
    f.metadata["user_id"] = user_id
    return f


def _stream_flow(url, ct="audio/webm"):
    req = tutils.treq()
    req.url = url
    f = tflow.tflow(req=req)
    f.response = tutils.tresp(content=b"")
    f.response.headers["content-type"] = ct
    f.metadata["user_id"] = 42
    f.metadata["request_rule"] = {"state": "allow", "video_filter_enabled": True}
    return f


def test_player_api_blocks_unapproved_and_records_it_for_the_user():
    vid = _vid()
    f = _api_flow(vid, _player(vid))
    process_http_response(f)
    body = json.loads(f.response.content)
    assert body["playabilityStatus"]["status"] == "ERROR" and "streamingData" not in body
    assert yt.watch_url(vid) in [m["media_url"] for m in pdb.list_recent_blocked_media(42)]


def test_approved_video_opens_exactly_its_own_streams_audio_included():
    vid = _vid()
    _approve(vid)
    f = _api_flow(vid, _player(vid, sid="o-OWN"))
    process_http_response(f)
    assert json.loads(f.response.content)["playabilityStatus"]["status"] == "OK"
    policy_cache.invalidate()
    a = addon_mod.FilterAddon()
    own = _stream_flow(GV.format(sid="o-OWN", itag=140), ct="audio/webm")
    a.responseheaders(own)
    assert own.response.status_code == 200 and own.response.stream is True
    other = _stream_flow(GV.format(sid="o-SOMEONE-ELSE", itag=140), ct="audio/webm")
    a.responseheaders(other)
    assert other.response.status_code == 418  # audio track of an unknown video: blocked, not "not a video"
    sabr = _stream_flow(GV.format(sid="o-OTHER", itag=0), ct="application/vnd.yt-ump")
    a.responseheaders(sabr)
    assert sabr.response.status_code == 418


def test_site_with_video_open_is_not_touched():
    vid = _vid()
    f = _api_flow(vid, _player(vid))
    f.metadata["user_id"] = 42
    from core.filters.video import youtube_policy
    assert not youtube_policy.applies(f.request.url, {"state": "allow", "video_filter_enabled": False}, {"video_filter": True})


# ---------- worker: YouTube source ----------


def test_worker_resolves_youtube_through_yt_dlp_and_explains_403(monkeypatch):
    calls = []

    def fake_resolve(url):
        calls.append(url)
        return review_worker.MediaSource(url="https://rr1---sn-x.googlevideo.com/videoplayback?id=o-1", duration=19.0,
                                         headers={"User-Agent": "UA-from-yt-dlp"})

    monkeypatch.setattr(review_worker, "resolve_youtube", fake_resolve)
    monkeypatch.setattr(review_worker, "check_public_url", lambda u: None)

    def failing_frames(*a, **k):
        raise review_worker.VideoReviewError("ffmpeg failed: Server returned 403 Forbidden (access denied)")
        yield  # pragma: no cover

    monkeypatch.setattr(review_worker, "iter_frames", failing_frames)
    with pytest.raises(review_worker.VideoReviewError, match="YTDLP_PROXY"):
        review_worker.review_video({"source_url": "https://youtu.be/jNQXAC9IVRw", "video_key": "youtube:jNQXAC9IVRw"}, object())
    assert calls == ["https://youtu.be/jNQXAC9IVRw"]


def test_ffmpeg_gets_yt_dlp_headers_without_header_injection():
    args = review_worker._input_args("https://x.googlevideo.com/videoplayback", None,
                                     {"User-Agent": "UA1", "Accept": "*/*", "X-Bad": "a\r\nInjected: 1"})
    assert args[args.index("-user_agent") + 1] == "UA1"
    hdrs = args[args.index("-headers") + 1]
    assert "Accept: */*" in hdrs and "Injected" not in hdrs


# ---------- overlay endpoints ----------


def test_video_status_reports_blocked_approved_and_page_blocked():
    vid = _vid()
    blocked_url = f"https://cdn.example/{vid}.mp4"
    approved = _vid()
    _approve(approved)
    pdb.record_blocked_media(42, f"https://cdn.example/{vid}.m3u8", f"https://site.example/watch/{vid}", "application/x-mpegurl")
    out = video_status({"urls": [blocked_url, yt.watch_url(approved), "javascript:alert(1)"],
                        "page_url": "https://site.example/other"}, 42)
    assert out["items"][blocked_url]["blocked"] is True
    assert out["items"][yt.watch_url(approved)]["blocked"] is False
    assert "javascript:alert(1)" not in out["items"]
    assert f"https://cdn.example/{vid}.m3u8" in [p["url"] for p in out["page_blocked"]]  # same origin as the page


def test_review_request_validates_and_is_rate_limited():
    limiter = ReviewRateLimiter(per_hour=2)
    assert request_review({"url": "file:///etc/passwd"}, 42, limiter)[0] == 400
    vid = _vid()
    code, data = request_review({"url": yt.watch_url(vid), "page_url": yt.watch_url(vid)}, 42, limiter)
    assert code == 200 and data["status"] == "pending"
    assert pdb.get_video_review(f"youtube:{vid}")["requested_by"] == 42
    assert request_review({"url": yt.watch_url(_vid())}, 42, limiter)[0] == 200
    assert request_review({"url": yt.watch_url(_vid())}, 42, limiter)[0] == 429
    assert request_review({"url": yt.watch_url(_vid())}, 43, limiter)[0] == 200  # per user


def test_overlay_paths_are_answered_by_the_proxy_with_the_users_identity():
    import base64

    pdb.set_proxy_users([{"user_id": 77, "is_admin": False, "proxy_username": "u77",
                          "proxy_secret_hash": proxy_auth.hash_proxy_secret("pw77")}])
    a = addon_mod.FilterAddon()
    vid = _vid()
    req = tutils.treq(method=b"POST", content=json.dumps({"url": yt.watch_url(vid), "page_url": yt.watch_url(vid)}).encode())
    req.url = "https://www.youtube.com/__goallm__/video-review"
    req.headers["Proxy-Authorization"] = "Basic " + base64.b64encode(b"u77:pw77").decode()
    f = tflow.tflow(req=req)
    f.client_conn.peername = ("203.0.113.50", 5000)
    a.requestheaders(f)
    asyncio.run(a.request(f))
    assert f.response is not None and f.response.status_code == 200  # answered locally, never forwarded
    assert json.loads(f.response.content)["status"] == "pending"
    assert pdb.get_video_review(f"youtube:{vid}")["requested_by"] == 77


def test_overlay_script_is_ascii_and_injected_only_where_video_is_filtered():
    assert OVERLAY_SCRIPT.isascii() and "innerHTML" not in OVERLAY_SCRIPT

    def page(host):
        req = tutils.treq()
        req.url = f"https://{host}/{_vid()}"
        f = tflow.tflow(req=req)
        f.response = tutils.tresp(content=b"<html><body><video src='/v.mp4'></video></body></html>")
        f.response.headers["content-type"] = "text/html; charset=utf-8"
        f.metadata["user_id"] = 42
        process_http_response(f)
        return f.response.content

    assert b"/__goallm__/video-status" in page("news.example")
    assert b"/__goallm__/video-status" not in page("video-open.example")

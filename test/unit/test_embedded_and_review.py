"""CSP nonce, base64 data-URI images (HTML/JSON/JS/WebSocket), uncertain → human review, review endpoints."""
import asyncio
import base64
import io
import random

import pytest
from mitmproxy import websocket
from mitmproxy.test import tflow, tutils
from PIL import Image

from core.filters.image import image_status_manager as ism
from core.filters.image.analysis import CONDITION_KEYS
from core.filters.image.data_uri_filter import filter_data_uri_images
from core.filters.image.image_status_db import get_image_status, save_analysis_result
from core.filters.review_store import thumbnail_path
from core.proxy import mitmproxy_addon as addon_mod
from core.proxy import proxy_auth
from core.proxy.csp import _rewrite_policy, add_nonce, prepare_csp_nonce


def _png(seed=None, size=(48, 40)):
    """A noisy picture: well above the 200-byte "too small to show a person" cut-off once compressed."""
    rnd = random.Random(seed)
    img = Image.frombytes("RGB", size, bytes(rnd.randrange(256) for _ in range(size[0] * size[1] * 3)))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _allow(data, mime="image/png"):
    save_analysis_result(ism._image_hash(data, mime), {k: "No" for k in CONDITION_KEYS}, mime_type=mime)


# ---------- CSP ----------


class TestCsp:
    def test_nonce_added_to_script_src(self):
        out, used = _rewrite_policy("default-src 'self'; script-src 'self' cdn.example", "N")
        assert used and "script-src 'self' cdn.example 'nonce-N'" in out
        assert "default-src 'self'" in out  # untouched when script-src exists

    def test_unsafe_inline_policy_is_left_alone(self):
        out, used = _rewrite_policy("script-src 'self' 'unsafe-inline'", "N")
        assert not used and "nonce" not in out

    def test_none_is_replaced(self):
        out, used = _rewrite_policy("script-src 'none'", "N")
        assert used and "'none'" not in out.split("script-src", 1)[1].split(";")[0]

    def test_default_src_fallback_and_connect_src_from_the_original(self):
        out, used = _rewrite_policy("default-src 'none'", "N")
        assert used and "default-src 'nonce-N'" in out
        connect = [p for p in out.split("; ") if p.startswith("connect-src")][0]
        assert connect == "connect-src 'self'"  # no nonce copied into connect-src

    def test_prepare_on_flow_and_add_nonce_to_our_snippet_only(self):
        f = tflow.tflow(resp=True)
        f.response.headers["content-security-policy"] = "script-src 'strict-dynamic' 'nonce-site'"
        nonce = prepare_csp_nonce(f)
        assert nonce and f"'nonce-{nonce}'" in f.response.headers["content-security-policy"]
        snippet = add_nonce('<script>a()</script><script nonce="x">b()</script>', nonce)
        assert snippet.count(f'nonce="{nonce}"') == 1 and 'nonce="x"' in snippet

    def test_no_csp_no_nonce(self):
        assert prepare_csp_nonce(tflow.tflow(resp=True)) is None


# ---------- data URIs ----------


class TestDataUriFilter:
    def test_inline_script_in_html(self):
        b64 = base64.b64encode(_png(1)).decode()
        body = f'<html><script>var t = "data:image/png;base64,{b64}";</script></html>'.encode()
        new, n = filter_data_uri_images(body, "https://s.example/")
        assert n == 1 and b64.encode() not in new and b"data:image/" in new

    def test_json_with_escaped_slashes_and_padding(self):
        b64 = base64.b64encode(_png(2)).decode()
        escaped = b64.replace("/", "\\/").replace("=", "\\u003d")
        body = ('{"thumb":"data:image\\/png;base64,' + escaped + '"}').encode()
        # the "data:image\/" form: mime separator escaped too
        body = body.replace(b"data:image\\/png", b"data:image/png")
        new, n = filter_data_uri_images(body, "https://api.example/x.json")
        assert n == 1 and escaped.encode() not in new

    def test_allowed_image_is_untouched_byte_for_byte(self):
        data = _png(3)
        _allow(data)
        body = b"x = 'data:image/png;base64," + base64.b64encode(data) + b"';"
        new, n = filter_data_uri_images(body, "https://s.example/app.js")
        assert n == 0 and new == body

    def test_tiny_images_and_garbage_are_ignored(self):
        tiny = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 40)
        body = b"data:image/png;base64," + tiny + b" data:image/gif;base64,!!!notbase64!!!"
        new, n = filter_data_uri_images(body, "https://s.example/")
        assert n == 0 and new == body

    def test_cap_replaces_the_rest_fail_closed(self):
        body = b" ".join(b"data:image/png;base64," + base64.b64encode(_png(100 + i)) for i in range(3))
        new, n = filter_data_uri_images(body, "https://s.example/", max_images=1)
        assert n == 3  # first: unknown → checking placeholder; the other two: over the cap
        assert new.count(b"data:image/gif;base64,R0lGODlhAQABAIAAAMzMzAAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==") == 2

    def test_json_response_goes_through_the_flow_processor(self):
        from core.flow.http_flow_processor import process_http_response

        b64 = base64.b64encode(_png(4))
        req = tutils.treq()
        req.url = "https://api.example/feed"
        f = tflow.tflow(req=req)
        f.response = tutils.tresp(content=b'{"img":"data:image/png;base64,' + b64 + b'"}')
        f.response.headers["content-type"] = "application/json"
        f.metadata["user_id"] = 42
        process_http_response(f)
        assert b64 not in f.response.content


# ---------- WebSocket ----------


@pytest.fixture
def addon(monkeypatch):
    monkeypatch.setattr(proxy_auth, "PROXY_REQUIRE_AUTH", True)
    return addon_mod.FilterAddon()


def _ws_flow(content, from_client=False, is_text=False, user_id=42):
    f = tflow.twebsocketflow(messages=False)
    f.websocket.messages.append(websocket.WebSocketMessage(1 if is_text else 2, from_client, content))
    f.metadata["user_id"] = user_id
    return f


class TestWebSocket:
    def test_binary_image_from_server_is_replaced(self, addon):
        data = _png(10)
        f = _ws_flow(data)
        asyncio.run(addon.websocket_message(f))
        assert f.websocket.messages[-1].content != data

    def test_allowed_image_passes(self, addon):
        data = _png(11)
        _allow(data)
        f = _ws_flow(data)
        asyncio.run(addon.websocket_message(f))
        assert f.websocket.messages[-1].content == data

    def test_client_messages_and_non_images_untouched(self, addon):
        data = _png(12)
        f = _ws_flow(data, from_client=True)
        asyncio.run(addon.websocket_message(f))
        assert f.websocket.messages[-1].content == data
        g = _ws_flow(b"\x00\x01binary-protocol-frame" * 4)
        asyncio.run(addon.websocket_message(g))
        assert g.websocket.messages[-1].content == b"\x00\x01binary-protocol-frame" * 4

    def test_text_message_with_data_uri(self, addon):
        b64 = base64.b64encode(_png(13))
        f = _ws_flow(b'{"avatar":"data:image/png;base64,' + b64 + b'"}', is_text=True)
        asyncio.run(addon.websocket_message(f))
        assert b64 not in f.websocket.messages[-1].content

    def test_unidentified_connection_untouched(self, addon):
        data = _png(14)
        f = _ws_flow(data, user_id=None)
        asyncio.run(addon.websocket_message(f))
        assert f.websocket.messages[-1].content == data


# ---------- uncertain → human review ----------


def test_uncertain_result_goes_to_review_with_thumbnail_and_stays_closed():
    data = _png(20)
    h = ism._image_hash(data, "image/png")
    result = {k: "No" for k in CONDITION_KEYS}
    result["_p_yes_max"] = 0.1  # between VLM_REVIEW_LOW (0.05) and VLM_YES_THRESHOLD (0.2)
    ism._on_analysis_done("t1", "done", result, {"image_hash": h, "image_url": "https://i.example/a.png",
                                                 "mime_type": "image/png", "image_bytes": data}, None)
    assert get_image_status(h)["status"] == "review"
    assert thumbnail_path("images", h) is not None
    _, _, status = ism.get_image_with_status(data, "https://i.example/a.png", None, "image/png")
    assert status != "allowed"


# ---------- review endpoints ----------


def test_review_endpoints_are_admin_only_and_decisions_apply():
    from test.unit.test_crm_security import _client, _register_and_login
    from crm.database import db_connection

    user_headers, plain = _register_and_login(_client())
    admin_headers, admin = _register_and_login(_client())
    db_connection.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (plain["id"],))  # first user is admin by default
    db_connection.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))
    db_connection.commit()
    c = _client()

    for path in ("/api/admin/review/summary", "/api/admin/review/images", "/api/admin/review/videos"):
        assert c.get(path, headers=user_headers).status_code == 403

    data = _png(30)
    h = ism._image_hash(data, "image/png")
    result = {k: "No" for k in CONDITION_KEYS}
    result["_p_yes_max"] = 0.12
    ism._on_analysis_done("t2", "done", result, {"image_hash": h, "mime_type": "image/png", "image_bytes": data}, None)
    items = c.get("/api/admin/review/images?status=review", headers=admin_headers).json()["items"]
    assert any(i["image_hash"] == h and i["has_thumb"] for i in items)
    assert c.get(f"/api/admin/review/images/{h}/thumb", headers=admin_headers).status_code == 200
    assert c.get("/api/admin/review/images/..%2F..%2Fetc/thumb", headers=admin_headers).status_code in (404, 422)
    assert c.post(f"/api/admin/review/images/{h}", json={"decision": "allow"}, headers=user_headers).status_code == 403
    assert c.post(f"/api/admin/review/images/{h}", json={"decision": "allow"}, headers=admin_headers).status_code == 200
    assert get_image_status(h)["status"] == "allowed"

    url = f"https://videos.example/req-{random.randrange(10**9)}.mp4"
    assert c.post("/api/video-reviews", json={"url": "file:///etc/passwd"}, headers=user_headers).status_code == 400
    r = c.post("/api/video-reviews", json={"url": url, "page_url": "https://s.example/"}, headers=user_headers)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    key = r.json()["video_key"]
    assert c.post("/api/admin/review/videos/decide", json={"key": key, "decision": "allow"}, headers=user_headers).status_code == 403
    r = c.post("/api/admin/review/videos/decide", json={"key": key, "decision": "allow"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "allowed"
    assert c.get(f"/api/video-reviews/status?url={url}", headers=user_headers).json()["status"] == "allowed"

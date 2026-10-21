import asyncio
import base64
import gzip
import io

import pytest
from mitmproxy import http
from mitmproxy.test import tflow, tutils
from PIL import Image

from core.policy import policy_cache, policy_database as pdb
from core.proxy import mitmproxy_addon as addon_mod
from core.proxy import proxy_auth
from core.proxy.proxy_auth import Identity, ProxyAuthenticator, hash_proxy_secret

PEER = "203.0.113.10"


def _flow(url="https://site.example/page", peer=PEER, headers=None, method="GET"):
    req = tutils.treq()
    req.method = method
    req.url = url
    for k, v in (headers or {}).items():
        req.headers[k] = v
    f = tflow.tflow(req=req)
    f.client_conn.peername = (peer, 50000)
    return f


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
    policy_cache.invalidate()
    yield


@pytest.fixture
def user_creds():
    pdb.set_proxy_users([{"user_id": 42, "is_admin": False, "proxy_username": "u42", "proxy_secret_hash": hash_proxy_secret("s3cret")}])
    return "u42", "s3cret"


class TestProxyAuth:
    def test_missing_credentials_get_407(self):
        a = ProxyAuthenticator()
        f = _flow()
        a.requestheaders(f)
        assert f.response is not None and f.response.status_code == 407
        assert "Proxy-Authenticate" in f.response.headers

    def test_personal_credentials_identify_user_and_are_not_forwarded(self, user_creds):
        a = ProxyAuthenticator()
        f = _flow(headers={"Proxy-Authorization": _basic(*user_creds)})
        a.requestheaders(f)
        assert f.response is None
        assert f.metadata["goallm_identity"] == Identity("user", 42)
        assert "Proxy-Authorization" not in f.request.headers

    def test_connect_authenticates_the_whole_tunnel(self, user_creds):
        a = ProxyAuthenticator()
        connect = _flow(headers={"Proxy-Authorization": _basic(*user_creds)}, method="CONNECT")
        a.http_connect(connect)
        inner = tflow.tflow(client_conn=connect.client_conn)
        a.requestheaders(inner)
        assert inner.metadata["goallm_identity"].user_id == 42

    def test_wrong_password_rejected(self, user_creds):
        a = ProxyAuthenticator()
        f = _flow(headers={"Proxy-Authorization": _basic("u42", "nope")})
        a.requestheaders(f)
        assert f.response.status_code == 407

    def test_shared_legacy_credential(self, monkeypatch):
        monkeypatch.setattr(proxy_auth, "PROXY_AUTH", "family:pw")
        a = ProxyAuthenticator()
        f = _flow(headers={"Proxy-Authorization": _basic("family", "pw")})
        a.requestheaders(f)
        assert f.metadata["goallm_identity"] == Identity("shared")


def _addon(monkeypatch, require_auth=True):
    monkeypatch.setattr(proxy_auth, "PROXY_REQUIRE_AUTH", require_auth)
    return addon_mod.FilterAddon()


def _run(coro):
    return asyncio.run(coro)


class TestAddonRequest:
    def test_forged_forwarded_for_does_not_borrow_another_binding(self, monkeypatch):
        pdb.set_ip_bindings([("198.51.100.7", 5)])
        a = _addon(monkeypatch, require_auth=False)
        f = _flow(headers={"X-Forwarded-For": "198.51.100.7"})
        a.requestheaders(f)
        _run(a.request(f))
        # the spoofed IP is ignored: the real peer is unbound → redirect to the bind page
        assert f.response.status_code == 302
        assert "/bind?" in f.response.headers["Location"]

    def test_bind_host_gets_overwritten_forwarded_for(self, monkeypatch):
        a = _addon(monkeypatch, require_auth=False)
        f = _flow(url="https://filter.example.org/bind", headers={"X-Forwarded-For": "198.51.100.7"})
        a.requestheaders(f)
        _run(a.request(f))
        assert f.request.headers["x-forwarded-for"] == PEER
        assert f.response is None

    def test_personal_credentials_skip_ip_binding(self, monkeypatch, user_creds):
        pdb.add_policy("allowed-site.example", None, state="allow", source="global")
        pdb.set_profile_mode("blacklist", 42)
        a = _addon(monkeypatch)
        f = _flow(url="https://allowed-site.example/x", headers={"Proxy-Authorization": _basic(*user_creds)})
        a.requestheaders(f)
        _run(a.request(f))
        assert f.response is None
        assert f.metadata["user_id"] == 42

    def test_unknown_site_gets_review_page(self, monkeypatch, user_creds):
        a = _addon(monkeypatch)
        f = _flow(url="https://not-in-list.example/", headers={"Proxy-Authorization": _basic(*user_creds)})
        a.requestheaders(f)
        _run(a.request(f))
        assert f.response.status_code == 418

    def test_policy_error_fails_closed(self, monkeypatch, user_creds):
        class Boom:
            def resolve(self, *a, **k):
                raise RuntimeError("db down")

        monkeypatch.setattr(addon_mod, "get_policy_resolver", lambda uid: Boom())
        a = _addon(monkeypatch)
        f = _flow(url="https://allowed-site.example/x", headers={"Proxy-Authorization": _basic(*user_creds)})
        a.requestheaders(f)
        _run(a.request(f))
        assert f.response.status_code == 418

    def test_reload_param_is_stripped_before_upstream(self, monkeypatch, user_creds):
        a = _addon(monkeypatch)
        f = _flow(url="https://allowed-site.example/img.jpg?sig=abc%2F1&goallm_r=1712345", headers={"Proxy-Authorization": _basic(*user_creds)})
        a.requestheaders(f)
        _run(a.request(f))
        assert f.request.path == "/img.jpg?sig=abc%2F1"


class TestVideo:
    def _video_flow(self, rule):
        f = _flow(url="https://allowed-site.example/v.mp4")
        f.response = tutils.tresp(content=b"")
        f.response.headers["content-type"] = "video/mp4"
        f.response.headers["content-length"] = "123456789"
        f.metadata["user_id"] = 42
        f.metadata["request_rule"] = rule
        return f

    def test_video_blocked_without_buffering(self, monkeypatch):
        a = _addon(monkeypatch)
        f = self._video_flow({"state": "allow", "video_filter_enabled": True})
        a.responseheaders(f)
        assert f.response.status_code == 418
        assert callable(f.response.stream) and f.response.stream(b"data") == b""
        assert "content-length" not in f.response.headers

    def test_video_open_for_site_is_streamed(self, monkeypatch):
        a = _addon(monkeypatch)
        f = self._video_flow({"state": "allow", "video_filter_enabled": False})
        a.responseheaders(f)
        assert f.response.status_code == 200
        assert f.response.stream is True


def _png_bytes(color="red", size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


class TestImagesByContent:
    def _process(self, content, content_type, encoding=None):
        from core.flow.http_flow_processor import process_http_response

        f = _flow(url=f"https://img.example/{abs(hash(content))}.bin")
        f.response = tutils.tresp(content=b"")
        f.response.headers["content-type"] = content_type
        if encoding:
            f.response.headers["content-encoding"] = encoding
        f.response.raw_content = content
        f.metadata["user_id"] = 42
        process_http_response(f)
        return f

    def test_image_labelled_html_is_still_filtered(self):
        f = self._process(_png_bytes("blue"), "text/html")
        assert f.response.headers.get("X-Goallm-Image-Status") in ("checking", "pending")

    def test_gzip_hidden_image_is_filtered(self):
        f = self._process(gzip.compress(_png_bytes("green")), "application/octet-stream", encoding="gzip")
        assert f.response.headers.get("X-Goallm-Image-Status") in ("checking", "pending")
        assert "content-encoding" not in f.response.headers

    def test_avif_is_filtered(self):
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), "yellow").save(buf, "AVIF")
        f = self._process(buf.getvalue(), "image/avif")
        assert f.response.headers.get("X-Goallm-Image-Status") in ("checking", "pending")

    def test_svg_placeholder_is_png(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="5"/></svg>'
        f = self._process(svg, "image/svg+xml")
        assert f.response.headers["Content-Type"] == "image/png"
        assert f.response.raw_content.startswith(b"\x89PNG")


class TestResponseSkipsUnidentified:
    def test_407_reaches_the_client_untouched(self, monkeypatch):
        a = _addon(monkeypatch)
        f = _flow(url="https://allowed-site.example/")
        a.requestheaders(f)
        _run(a.request(f))
        _run(a.response(f))
        assert f.response.status_code == 407


class TestProxyIdentityHeader:
    def test_crm_gets_signed_user_and_client_copy_is_dropped(self, monkeypatch, user_creds):
        from core.proxy_identity import HEADER, verify_user

        a = _addon(monkeypatch)
        f = _flow(url="https://filter.example.org/diagnostic", headers={"Proxy-Authorization": _basic(*user_creds), HEADER: "1.1.forged"})
        a.requestheaders(f)
        _run(a.request(f))
        assert verify_user(f.request.headers[HEADER]) == 42

    def test_forged_or_stale_header_rejected(self):
        from core.proxy_identity import sign_user, verify_user

        assert verify_user("42.0.deadbeef") is None
        assert verify_user(sign_user(42, now=1000), now=1000 + 3600) is None
        assert verify_user(sign_user(7)) == 7

"""Text-filter evasion + model second opinion, meta-tag CSP, DASH approval, learned TLS passthrough, calibration."""
import re
import shutil
import subprocess

import pytest

from core.filters.text import llm_review, text_filter
from core.filters.text.text_filter import _filter_plain_text, filter_text_content
from core.filters.video.video_filter import dash_children
from core.policy import policy_cache, policy_database as pdb
from core.proxy.csp import rewrite_meta_csp

# ---------- text filter: evasive spellings ----------


@pytest.mark.parametrize("text", ["s3x", "s e x", "s.e.x", "se​x", "sеx", "seeexxx", "$ex", "ס.ק.ס", "ס ק ס"])
def test_evasive_spellings_are_caught_and_masked(text):
    out, _block, _reason, debug = _filter_plain_text(f"before {text} after")
    assert debug["counts"]["matched"] == 1
    assert out.startswith("before ") and out.endswith(" after") and set(out[7:-6]) == {"X"}


@pytest.mark.parametrize("text", ["Essex county", "the sextant", "U S A", "$100", "a b c d", "שלום ס ב א", "ר' משה"])
def test_innocent_text_is_left_alone(text):
    out, _block, _reason, debug = _filter_plain_text(text)
    assert debug["counts"]["matched"] == 0 and out == text


# ---------- text filter: second opinion ----------


def _page(words):
    body = " ".join(["תוכן רגיל של אתר חדשות"] * 60 + words)
    return f"<html><body><div>{body}</div></body></html>".encode("utf-8")


def test_borderline_page_goes_to_the_model_and_its_verdict_counts(monkeypatch):
    asked = []
    monkeypatch.setattr(text_filter, "TEXT_LLM_REVIEW", True)
    monkeypatch.setattr(llm_review, "_ask", lambda text: asked.append(text) or True)
    llm_review._cache.clear()
    _out, block, reason, _dbg = filter_text_content(_page(["sex"]), url="https://news.example/a", content_type="text/html")
    assert block and reason.startswith("llm_review") and "תוכן רגיל" in asked[0]


def test_clean_pages_never_call_the_model_and_failures_keep_the_word_result(monkeypatch):
    monkeypatch.setattr(text_filter, "TEXT_LLM_REVIEW", True)
    calls = []
    monkeypatch.setattr(llm_review, "_ask", lambda text: calls.append(1) or True)
    llm_review._cache.clear()
    _out, block, _r, _d = filter_text_content(_page([]), url="https://news.example/b", content_type="text/html")
    assert not block and calls == []

    def boom(text):
        raise TimeoutError("slow model")

    monkeypatch.setattr(llm_review, "_ask", boom)
    out, block, _r, _d = filter_text_content(_page(["sex", "word2"]), url="https://news.example/c", content_type="text/html")
    assert not block and b"XXX" in out  # word masked, page not blocked on a model error


def test_off_by_default():
    assert text_filter.TEXT_LLM_REVIEW is False


# ---------- CSP in a meta tag ----------


def test_meta_csp_gets_the_nonce_and_the_header_nonce_is_reused():
    body = b'<head><meta http-equiv="Content-Security-Policy" content="script-src \'self\'"></head>'
    out, nonce = rewrite_meta_csp(body, "HDR")
    assert nonce == "HDR" and b"'nonce-HDR'" in out
    out2, nonce2 = rewrite_meta_csp(body, None)
    assert nonce2 and f"'nonce-{nonce2}'".encode() in out2


def test_meta_csp_allowing_inline_is_not_given_a_nonce():
    body = b"<head><meta http-equiv='content-security-policy' content='script-src &apos;unsafe-inline&apos;'></head>"
    out, nonce = rewrite_meta_csp(body, None)
    assert nonce is None and b"nonce" not in out


# ---------- DASH ----------

_MPD = '''<?xml version="1.0"?><MPD xmlns="urn:mpeg:dash:schema:mpd:2011"><Period>
<AdaptationSet><SegmentTemplate initialization="$RepresentationID$/init.mp4" media="$RepresentationID$/seg-$Number%05d$.m4s?t=1"/>
<Representation id="v720" bandwidth="2000000"/></AdaptationSet>
<AdaptationSet><Representation id="a1"><BaseURL>audio/a1.mp4</BaseURL><SegmentBase indexRange="0-9"/></Representation></AdaptationSet>
</Period></MPD>'''


def test_dash_manifest_children_and_patterns():
    urls, pats = dash_children(_MPD, "https://cdn.example/videos/abc/manifest.mpd")
    assert "https://cdn.example/videos/abc/v720/init.mp4" in urls and "https://cdn.example/videos/abc/audio/a1.mp4" in urls
    (host, pattern), = pats
    assert host == "cdn.example"
    assert re.fullmatch(pattern, "https://cdn.example/videos/abc/v720/seg-00042.m4s")
    assert not re.fullmatch(pattern, "https://cdn.example/videos/OTHER/v720/seg-00042.m4s")


def test_too_broad_template_is_refused():
    mpd = _MPD.replace("$RepresentationID$/seg-$Number%05d$.m4s?t=1", "/$Number$")
    _urls, pats = dash_children(mpd, "https://cdn.example/m.mpd")
    assert pats == []


def test_approved_dash_segments_pass_and_are_revoked_with_the_video(monkeypatch):
    monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
    manifest = "https://cdn.example/videos/dash1/manifest.mpd"
    r = pdb.request_video_review(manifest, None, 42)
    pdb.finish_video_review(r["video_key"], "allowed")
    _urls, pats = dash_children(_MPD, manifest)
    pdb.add_approved_media_patterns(r["video_key"], pats)
    policy_cache.invalidate()
    seg = "https://cdn.example/videos/dash1/v720/seg-00007.m4s?token=zzz"
    assert policy_cache.is_media_approved(seg)
    pdb.finish_video_review(r["video_key"], "blocked")
    policy_cache.invalidate()
    assert not policy_cache.is_media_approved(seg)


# ---------- learned TLS passthrough (apps with certificate pinning) ----------


class _Conn:
    def __init__(self, sni=None, error=None):
        self.sni = sni
        self.error = error
        self.peername = ("203.0.113.70", 4000)


class _Ctx:
    def __init__(self, client):
        self.client = client


class _Hello:
    def __init__(self, sni):
        self.sni = sni


class _HelloData:
    def __init__(self, sni, client):
        self.client_hello = _Hello(sni)
        self.context = _Ctx(client)
        self.ignore_connection = False


class _TlsData:
    def __init__(self, client, error):
        self.context = _Ctx(client)
        self.conn = _Conn(error=error)


def test_pinned_app_host_is_learned_and_passed_through_only_where_allowed(monkeypatch):
    from core.proxy import mitmproxy_addon as addon_mod

    monkeypatch.setattr(addon_mod, "AUTO_PASSTHROUGH_PINNED_APPS", True)
    monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
    pdb.add_policy("api.pinned-app.example", None, state="allow", source="global")
    pdb.set_profile_mode("blacklist", 42)
    pdb.set_ip_bindings([("203.0.113.70", 42)])
    a = addon_mod.FilterAddon()
    client = _Conn(sni="api.pinned-app.example")
    err = "The client does not trust the proxy's certificate for api.pinned-app.example (tlsv1 alert unknown ca)"
    a.tls_failed_client(_TlsData(client, err))
    policy_cache.invalidate()
    d = _HelloData("api.pinned-app.example", client)
    a.tls_clienthello(d)
    assert d.ignore_connection is False  # one failure is not enough
    a.tls_failed_client(_TlsData(client, err))
    policy_cache.invalidate()
    d = _HelloData("api.pinned-app.example", client)
    a.tls_clienthello(d)
    assert d.ignore_connection is True
    # a host the list does not allow is never passed through, learned or not
    other = _Conn(sni="tracker.unlisted.example")
    for _ in range(3):
        a.tls_failed_client(_TlsData(other, "The client does not trust the proxy's certificate"))
    policy_cache.invalidate()
    d = _HelloData("tracker.unlisted.example", other)
    a.tls_clienthello(d)
    assert d.ignore_connection is False


def test_unrelated_handshake_errors_do_not_count(monkeypatch):
    from core.proxy import mitmproxy_addon as addon_mod

    monkeypatch.setattr(addon_mod, "AUTO_PASSTHROUGH_PINNED_APPS", True)
    a = addon_mod.FilterAddon()
    client = _Conn(sni="flaky.example")
    for _ in range(5):
        a.tls_failed_client(_TlsData(client, "Client and mitmproxy cannot agree on a TLS version to use."))
    assert "flaky.example" not in pdb.get_learned_passthrough_hosts()


# ---------- calibration tool ----------


def test_calibration_finds_settings_that_miss_nothing(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    from tools import calibrate_video_change as cal

    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=0x406080:s=320x240:d=12:r=10", "-vf",
                    "drawgrid=w=40:h=40:color=gray@0.5,drawbox=x=260:y=170:w=24:h=40:color=red:t=fill:enable='gte(t,6)'",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    labels = tmp_path / "labels.csv"
    labels.write_text(f"video,events\n{clip},6\n", encoding="utf-8")
    videos = cal.parse_labels(str(labels))
    cal.load_frames(videos[0], 2, 320)
    grid = {"pixel_delta": (28, 250), "tile_fraction": (0.03,), "tile_mean": (10.0, 250.0), "tile_px": (16,), "force_every_sec": (1000.0,)}
    rows = cal.evaluate(videos, [1, 2], 2, 1.0, 320, grid)
    assert rows[0]["missed"] == 0
    insensitive = [r for r in rows if r["pixel_delta"] == 250 and r["tile_mean"] == 250.0]
    assert all(r["missed"] == 1 for r in insensitive)  # thresholds too high → the event is missed and reported


def test_learned_passthrough_admin_endpoints():
    from crm.database import db_connection
    from test.unit.test_crm_security import _client, _register_and_login

    pdb.record_tls_client_failure("app.learned.example", 1)
    user_h, plain = _register_and_login(_client())
    admin_h, admin = _register_and_login(_client())
    db_connection.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (plain["id"],))
    db_connection.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))
    db_connection.commit()
    c = _client()
    assert c.get("/api/admin/learned-passthrough", headers=user_h).status_code == 403
    assert "app.learned.example" in c.get("/api/admin/learned-passthrough", headers=admin_h).json()["hosts"]
    assert c.delete("/api/admin/learned-passthrough/app.learned.example", headers=admin_h).status_code == 200
    assert "app.learned.example" not in pdb.get_learned_passthrough_hosts()

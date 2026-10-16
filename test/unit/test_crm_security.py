import io
import itertools

import pytest
from fastapi.testclient import TestClient

import crm.main as crm_main
from crm.database import db_connection
from core.policy import policy_database as pdb
from core.proxy.proxy_auth import ProxyAuthenticator

crm_main.limiter.enabled = False
_phones = (f"05{n:08d}" for n in itertools.count(10000000))


def _client(peer="203.0.113.9"):
    return TestClient(crm_main.app, client=(peer, 50000))


def _register_and_login(client):
    phone = next(_phones)
    r = client.post(
        "/api/auth/register",
        data={"email": f"{phone}@example.org", "password": "Passw0rd!", "first_name": "a", "last_name": "b", "phone": phone},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"phone": phone, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]


@pytest.fixture(scope="module")
def admin():
    c = _client()
    headers, user = _register_and_login(c)
    if not user["is_admin"]:
        db_connection.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
        db_connection.commit()
    return headers, user


@pytest.fixture
def user():
    return _register_and_login(_client())


def test_security_headers():
    r = _client().get("/api/auth/setup-status")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_regular_user_cannot_change_global_tag_rules(admin, user):
    c = _client()
    assert c.post("/api/tag-rules", json={"tag": "games", "state": "allow"}, headers=user[0]).status_code == 403
    r = c.post("/api/tag-rules", json={"tag": "games-x", "state": "block"}, headers=admin[0])
    assert r.status_code == 201
    rid = r.json()["id"]
    assert c.delete(f"/api/tag-rules/{rid}", headers=user[0]).status_code == 403
    assert c.delete(f"/api/tag-rules/{rid}", headers=admin[0]).status_code == 204


def test_resolver_rules_all_requires_admin(admin, user):
    c = _client()
    assert c.get("/api/resolver/rules/all").status_code in (401, 403)
    assert c.get("/api/resolver/rules/all", headers=user[0]).status_code == 403
    assert c.get("/api/resolver/rules/all", headers=admin[0]).status_code == 200


def test_locked_settings_are_enforced_by_the_server(admin, user):
    c = _client()
    uh, u = user
    profiles = c.get("/api/profiles", headers=uh).json()
    pid = profiles[0]["id"]
    for key in ("rules", "profile_mode"):
        assert c.post(f"/api/admin/users/{u['id']}/locked-settings", json={"setting_key": key}, headers=admin[0]).status_code == 200
    assert set(c.get("/api/user/me/locked-settings", headers=uh).json()["locked_settings"]) == {"profile_mode", "rules"}
    assert c.post(f"/api/profiles/{pid}/rules", json={"url": "example.com", "action": "allow"}, headers=uh).status_code == 403
    assert c.put(f"/api/profiles/{pid}", json={"mode": "blacklist" if profiles[0]["mode"] != "blacklist" else "whitelist"}, headers=uh).status_code == 403
    assert c.post("/api/profiles", json={"name": "lax", "mode": "blacklist"}, headers=uh).status_code == 403
    assert c.post(f"/api/profiles/{pid}/schedules", json={"days": [0], "from_time": "00:00", "to_time": "23:59"}, headers=uh).status_code == 403
    # the admin managing that user is not blocked
    r = c.post(f"/api/profiles/{pid}/rules?managed_user_id={u['id']}", json={"url": "example.com", "action": "block"}, headers=admin[0])
    assert r.status_code == 201, r.text


def test_unknown_lock_key_rejected(admin, user):
    r = _client().post(f"/api/admin/users/{user[1]['id']}/locked-settings", json={"setting_key": "whatever"}, headers=admin[0])
    assert r.status_code == 400


def test_support_upload_rejects_html_and_serves_safely(user):
    c = _client()
    r = c.post("/api/support/upload", files={"file": ("x.html", b"<script>alert(1)</script>", "text/html")}, headers=user[0])
    assert r.status_code == 400
    r = c.post("/api/support/upload", files={"file": ("doc.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=user[0])
    assert r.status_code == 200
    url = r.json()["url"]
    served = c.get(url)
    assert served.status_code == 200
    assert served.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in served.headers["content-security-policy"]
    # path traversal: the encoded form reaches the route; it must not serve anything outside uploads/
    assert c.get("/uploads/support/..%2F..%2Fcrm.db").status_code == 404
    assert c.get("/uploads/other/x.png").status_code == 404


def test_attachment_and_avatar_urls_are_validated(user):
    c = _client()
    r = c.post(
        "/api/support/tickets",
        json={"subject": "s", "content": "c", "attachments": [{"name": "x", "url": "javascript:alert(1)"}]},
        headers=user[0],
    )
    assert r.status_code == 422
    assert c.put("/api/user/me", json={"avatar_url": "https://tracker.example/p.gif"}, headers=user[0]).status_code == 422


def test_bind_ignores_forged_forwarded_for_from_untrusted_peer(user):
    c = _client(peer="203.0.113.9")
    r = c.post("/api/me/bindings", headers={**user[0], "X-Forwarded-For": "198.51.100.1"})
    assert r.status_code == 201
    assert r.json()["ip"] == "203.0.113.9"


def test_bind_honors_forwarded_for_from_trusted_proxy(user):
    c = _client(peer="127.0.0.1")
    r = c.post("/api/me/bindings", headers={**user[0], "X-Forwarded-For": "198.51.100.2"})
    assert r.status_code == 201
    assert r.json()["ip"] == "198.51.100.2"


def test_cannot_bind_the_proxy_itself(user):
    r = _client(peer="127.0.0.1").post("/api/me/bindings", headers=user[0])
    assert r.status_code == 400


def test_old_token_surf_endpoints_are_gone(admin, user):
    c = _client()
    assert c.post("/api/surf-widget/quick-rule", json={"token": "x", "url": "https://a.b", "action": "allow", "scope": "domain_only"}).status_code in (404, 405)
    assert c.post("/api/admin/surf-quick-rule", json={"url": "https://a.b", "action": "allow", "scope": "domain_only"}, headers=user[0]).status_code == 403
    r = c.post("/api/admin/surf-quick-rule", json={"url": "https://quick.example/", "action": "allow", "scope": "domain_only"}, headers=admin[0])
    assert r.status_code == 200, r.text


def test_personal_proxy_credentials_work_in_the_proxy(user):
    c = _client()
    r = c.post("/api/me/proxy-credentials/rotate", headers=user[0])
    assert r.status_code == 200
    creds = r.json()
    assert creds["username"] == f"u{user[1]['id']}" and len(creds["password"]) >= 20
    assert c.get("/api/me/proxy-credentials", headers=user[0]).json()["has_password"] is True
    identity = ProxyAuthenticator()._check(creds["username"], creds["password"])
    assert identity is not None and identity.user_id == user[1]["id"]
    assert ProxyAuthenticator()._check(creds["username"], "wrong") is None


def test_otp_code_dies_after_too_many_wrong_guesses(user):
    c = _client()
    phone = user[1]["phone"]
    assert c.post("/api/auth/request-phone-code", json={"phone": phone}).status_code == 200
    code = db_connection.execute("SELECT code FROM verification_codes WHERE target = ? ORDER BY id DESC", (phone,)).fetchone()["code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert c.post("/api/auth/verify-phone-code", json={"phone": phone, "code": wrong}).status_code == 400
    assert c.post("/api/auth/verify-phone-code", json={"phone": phone, "code": code}).status_code == 400


def test_sync_is_idempotent_and_writes_nothing_when_unchanged(admin):
    from crm.services import sync_crm_rules_to_core

    sync_crm_rules_to_core(None)
    v = pdb.get_policy_version()
    sync_crm_rules_to_core(None)
    assert pdb.get_policy_version() == v


def test_sync_survives_a_conflicting_row(admin):
    """www.x and x normalize to the same core key; the sync must still apply every other rule."""
    from crm.services import sync_crm_rules_to_core

    c = _client()
    for url in ("www.dup-sync.example", "dup-sync.example", "other-sync.example"):
        c.post("/api/admin/global-rules", json={"url": url, "action": "allow"}, headers=admin[0])
    sync_crm_rules_to_core(None)
    domains = {p["domain"] for p in pdb.get_all_policies(source_filter="global")}
    assert "other-sync.example" in domains and "dup-sync.example" in domains

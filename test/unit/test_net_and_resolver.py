import time

from core.net_utils import normalize_ip, resolve_client_ip
from core.policy import policy_cache, policy_database as pdb
from core.policy.url_policy_resolver import URLPolicyResolver


class TestResolveClientIp:
    def test_untrusted_peer_ignores_forwarded_headers(self):
        # A surfer cannot claim another family's IP by sending X-Forwarded-For.
        assert resolve_client_ip("203.0.113.5", "198.51.100.7", "198.51.100.7") == "203.0.113.5"

    def test_trusted_peer_walks_chain_from_the_right(self):
        trusted = "127.0.0.1,10.0.0.0/8"
        # client injected 1.1.1.1 at the left; the real client (5.5.5.5) was appended by our proxy
        assert resolve_client_ip("127.0.0.1", "1.1.1.1, 5.5.5.5, 10.0.0.2", trusted=trusted) == "5.5.5.5"

    def test_trusted_peer_without_header_is_peer(self):
        assert resolve_client_ip("127.0.0.1", None, trusted="127.0.0.1") == "127.0.0.1"

    def test_malformed_hop_returns_none(self):
        assert resolve_client_ip("127.0.0.1", "not-an-ip", trusted="127.0.0.1") is None

    def test_ipv4_mapped_ipv6_is_normalized(self):
        assert normalize_ip("::ffff:192.0.2.1") == "192.0.2.1"


def _resolver(global_rules, user_rules=None, mode="blacklist", tag_rules=None):
    return URLPolicyResolver(
        global_policies=global_rules, user_policies=user_rules or [], default_mode=mode, tag_rules=tag_rules or []
    )


class TestResolver:
    def test_not_in_global_list_is_review(self):
        r = _resolver([{"domain": "kosher.org", "path": None, "type": "*", "state": "allow"}])
        assert r.resolve("https://other.org/", "*")["state"] == "review"

    def test_wildcard_and_www(self):
        r = _resolver([{"domain": "*.kosher.org", "path": None, "type": "*", "state": "allow"}])
        assert r.resolve("https://www.kosher.org/x", "*")["state"] == "allow"
        assert r.resolve("https://a.b.kosher.org/x", "*")["state"] == "allow"
        assert r.resolve("https://evilkosher.org/x", "*")["state"] == "review"

    def test_path_prefix_respects_segment_boundary(self):
        r = _resolver([{"domain": "site.org", "path": "/forum", "type": "*", "state": "allow"}])
        assert r.resolve("https://site.org/forum", "*")["state"] == "allow"
        assert r.resolve("https://site.org/forum/thread/1", "*")["state"] == "allow"
        assert r.resolve("https://site.org/forum?page=2", "*")["state"] == "allow"
        assert r.resolve("https://site.org/forums-uncensored", "*")["state"] == "review"

    def test_user_block_in_blacklist_mode(self):
        r = _resolver(
            [{"domain": "site.org", "path": None, "type": "*", "state": "allow"}],
            [{"domain": "site.org", "path": "/news", "type": "*", "state": "block"}],
        )
        assert r.resolve("https://site.org/news/1", "*")["state"] == "block"
        assert r.resolve("https://site.org/torah", "*")["state"] == "allow"

    def test_tag_block_overrides_global_allow(self):
        r = _resolver(
            [{"domain": "site.org", "path": None, "type": "*", "state": "allow", "tags": ["games"]}],
            tag_rules=[{"tag": "games", "state": "block"}],
        )
        assert r.resolve("https://site.org/", "*")["state"] == "block"

    def test_whitelist_mode_requires_user_allow(self):
        g = [{"domain": "site.org", "path": None, "type": "*", "state": "allow"}]
        assert _resolver(g, mode="whitelist").resolve("https://site.org/", "*")["state"] == "block"
        u = [{"domain": "site.org", "path": None, "type": "*", "state": "allow"}]
        assert _resolver(g, u, mode="whitelist").resolve("https://site.org/", "*")["state"] == "allow"


class TestPolicyCache:
    def test_cache_refreshes_after_policy_write(self, monkeypatch):
        monkeypatch.setattr(policy_cache, "CHECK_INTERVAL_SEC", 0.0)
        policy_cache.invalidate()
        url = "https://cache-test.example/"
        assert policy_cache.get_policy_resolver(None).resolve(url, "*")["state"] == "review"
        pdb.add_policy("cache-test.example", None, state="allow", source="global")
        pdb.set_profile_mode("blacklist")
        state = policy_cache.get_policy_resolver(None).resolve(url, "*")["state"]
        assert state in ("allow", "block")  # depends on default user mode, but no longer "review"

    def test_version_bumps_on_write(self):
        v1 = pdb.get_policy_version()
        pdb.set_filter_switch("google_search_filter", True)
        assert pdb.get_policy_version() == v1 + 1

"""
In-memory caches for the proxy hot path.

Every request used to hit SQLite 5-6 times and rebuild a URLPolicyResolver from scratch.
Now the proxy keeps resolvers / switches / bindings in memory and checks a single
change counter (meta.policy_version, bumped by every policy write in policy_database)
at most once per CHECK_INTERVAL_SEC. Staleness after a CRM change is therefore ≤ 1 second.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

from core.policy import policy_database as pdb

CHECK_INTERVAL_SEC = 1.0

_lock = threading.Lock()
_version: Optional[int] = None
_checked_at = float("-inf")  # monotonic() can be small right after boot
_caches: Dict[str, dict] = {}


def _bucket(name: str) -> dict:
    """Return the named cache dict, clearing all caches first if the DB changed."""
    global _version, _checked_at
    now = time.monotonic()
    if now - _checked_at >= CHECK_INTERVAL_SEC:
        with _lock:
            if now - _checked_at >= CHECK_INTERVAL_SEC:
                v = pdb.get_policy_version()
                _checked_at = now
                if v != _version:
                    _version = v
                    _caches.clear()
    return _caches.setdefault(name, {})


def invalidate() -> None:
    global _checked_at
    with _lock:
        _caches.clear()
        _checked_at = float("-inf")


def _cached(name: str, key, compute):
    bucket = _bucket(name)
    if key in bucket:
        return bucket[key]
    value = compute()
    bucket[key] = value
    return value


def get_filter_switches() -> Dict[str, bool]:
    return dict(_cached("switches", None, pdb.get_filter_switches))


def get_user_id_for_ip(ip: Optional[str]) -> Optional[int]:
    if not ip:
        return None
    return _cached("ip_users", ip, lambda: pdb.get_user_id_for_ip(ip))


def get_active_traffic_session_id(user_id: int) -> Optional[int]:
    return _cached("traffic_sessions", user_id, lambda: pdb.get_active_traffic_session_id(user_id))


def get_profile_mode(user_id: Optional[int]) -> str:
    return _cached("profile_mode", user_id, lambda: pdb.get_profile_mode(user_id))


def get_user_is_admin(user_id: Optional[int]) -> bool:
    return _cached("is_admin", user_id, lambda: pdb.get_user_is_admin(user_id))


def get_site_injection_for_url(url: str):
    # Injection rules are few; cache per URL would grow unbounded, so cache the "any rules?" flag only.
    has_rules = _cached(
        "injections_exist",
        None,
        lambda: pdb.db_connection.execute("SELECT 1 FROM site_injections WHERE enabled = 1 LIMIT 1").fetchone() is not None,
    )
    if not has_rules:
        return None
    return pdb.get_site_injection_for_url(url)


def get_policy_resolver(user_id: Optional[int]):
    from core.policy.policy_loader import build_policy_resolver

    return _cached("resolvers", user_id, lambda: build_policy_resolver(user_id))


def is_media_approved(url: str) -> bool:
    """A video approved by per-video review, a child URL of an approved HLS manifest, or a DASH segment of one."""
    key = pdb.canonical_media_key(url)
    if key in _cached("approved_media", None, pdb.get_approved_media_keys):
        return True
    return pdb.is_approved_media_child(key) or pdb.is_approved_media_pattern(url)


def get_learned_passthrough() -> set:
    return _cached("learned_passthrough", None, pdb.get_learned_passthrough_hosts)

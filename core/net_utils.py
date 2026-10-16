"""
Client-IP resolution that cannot be spoofed with X-Forwarded-For.

X-Forwarded-For / X-Real-IP are plain request headers: any client can send them.
They are honored only when the direct peer is a trusted proxy (TRUSTED_PROXY_IPS),
and the chain is walked right-to-left so a value the client injected at the left
end is never picked while a trusted hop appended a real address after it.
"""
from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Optional

from data.constants import TRUSTED_PROXY_IPS

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def normalize_ip(value: Optional[str]) -> Optional[str]:
    """Return a canonical IP string (IPv4-mapped IPv6 → IPv4), or None if not a valid IP."""
    if not value:
        return None
    raw = str(value).strip()
    if raw.startswith("[") and "]" in raw:
        raw = raw[1 : raw.index("]")]
    if "%" in raw:
        raw = raw.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return str(ip)


@lru_cache(maxsize=8)
def _parse_networks(spec: str) -> tuple[IPNetwork, ...]:
    nets = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return tuple(nets)


def is_trusted_proxy(ip: Optional[str], trusted: Optional[str] = None) -> bool:
    norm = normalize_ip(ip)
    if norm is None:
        return False
    addr = ipaddress.ip_address(norm)
    return any(addr in net for net in _parse_networks(TRUSTED_PROXY_IPS if trusted is None else trusted))


def resolve_client_ip(
    peer_ip: Optional[str],
    forwarded_for: Optional[str] = None,
    real_ip: Optional[str] = None,
    trusted: Optional[str] = None,
) -> Optional[str]:
    """
    Return the real client IP.
    - Untrusted peer: the peer itself (headers ignored).
    - Trusted peer: walk X-Forwarded-For from the right, skipping trusted hops; the first
      untrusted hop is the client. Falls back to X-Real-IP, then to the peer.
    A malformed hop stops the walk (we cannot know who wrote it), returning None.
    """
    peer = normalize_ip(peer_ip)
    if peer is None:
        return None
    if not is_trusted_proxy(peer, trusted):
        return peer
    hops = [h.strip() for h in (forwarded_for or "").split(",") if h.strip()]
    for hop in reversed(hops):
        norm = normalize_ip(hop)
        if norm is None:
            return None
        if not is_trusted_proxy(norm, trusted):
            return norm
    if hops:
        return normalize_ip(hops[0])
    real = normalize_ip(real_ip)
    return real or peer


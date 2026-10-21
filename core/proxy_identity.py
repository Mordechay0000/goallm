"""
Signed "this request came through our proxy as user X" header, added by the proxy to requests for the CRM.

With personal proxy credentials the CRM can no longer infer "the connection is filtered" from an IP binding.
The proxy adds X-Goallm-Proxy-User = "<user_id>.<unix_ts>.<hmac>" (HMAC with CRM_PROXY_SECRET) and strips any
copy the client sent; the CRM accepts it only with a valid signature and a fresh timestamp.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

from data.constants import CRM_PROXY_SECRET

HEADER = "X-Goallm-Proxy-User"
MAX_AGE_SEC = 300


def _mac(payload: str) -> str:
    return hmac.new(CRM_PROXY_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_user(user_id: int, now: Optional[int] = None) -> str:
    payload = f"{int(user_id)}.{int(now if now is not None else time.time())}"
    return f"{payload}.{_mac(payload)}"


def verify_user(value: Optional[str], now: Optional[int] = None) -> Optional[int]:
    if not value or value.count(".") != 2:
        return None
    uid, ts, mac = value.split(".")
    payload = f"{uid}.{ts}"
    if not hmac.compare_digest(mac, _mac(payload)):
        return None
    try:
        age = int(now if now is not None else time.time()) - int(ts)
        user_id = int(uid)
    except ValueError:
        return None
    if age < -60 or age > MAX_AGE_SEC:
        return None
    return user_id

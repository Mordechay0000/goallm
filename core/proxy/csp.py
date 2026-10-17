"""
Let our injected inline scripts (surf widget, image refresh, site injections) run on pages with a strict
Content-Security-Policy, without weakening that policy for anything else.

For each CSP header that restricts scripts (script-src / script-src-elem, or default-src as fallback):
- If the directive already allows inline scripts ('unsafe-inline' without nonces/hashes), nothing is added –
  adding a nonce would make browsers IGNORE 'unsafe-inline' and break the site's own inline scripts.
- Otherwise a per-response nonce is appended ('none' is replaced, since it must stand alone), and the same
  nonce is put on our <script> tags.
- connect-src gets 'self' if missing, so the refresh script can ask the proxy (same origin) about images.
"""
from __future__ import annotations

import re
import secrets
from typing import List, Optional, Tuple

_HEADER = "content-security-policy"


def _parse(value: str) -> List[Tuple[str, List[str]]]:
    out = []
    for part in value.split(";"):
        tokens = part.strip().split()
        if tokens:
            out.append((tokens[0].lower(), tokens[1:]))
    return out


def _serialize(directives: List[Tuple[str, List[str]]]) -> str:
    return "; ".join(" ".join([name] + values) for name, values in directives)


def _allows_inline(values: List[str]) -> bool:
    lowered = [v.lower() for v in values]
    has_nonce_or_hash = any(v.startswith(("'nonce-", "'sha256-", "'sha384-", "'sha512-")) for v in lowered)
    return "'unsafe-inline'" in lowered and not has_nonce_or_hash and "'strict-dynamic'" not in lowered


def _with_nonce(values: List[str], nonce: str) -> List[str]:
    kept = [v for v in values if v.lower() != "'none'"]
    return kept + [f"'nonce-{nonce}'"]


def _rewrite_policy(value: str, nonce: str) -> Tuple[str, bool]:
    directives = _parse(value)
    names = [n for n, _ in directives]
    original_default = next((list(v) for n, v in directives if n == "default-src"), None)
    script_names = [n for n in ("script-src", "script-src-elem") if n in names]
    targets = script_names or (["default-src"] if "default-src" in names else [])
    used = False
    for i, (name, values) in enumerate(directives):
        if name in targets and not _allows_inline(values):
            directives[i] = (name, _with_nonce(values, nonce))
            used = True
    # same-origin fetch for the image-status call
    connect = next((i for i, (n, _) in enumerate(directives) if n == "connect-src"), None)
    if connect is not None:
        name, values = directives[connect]
        if not any(v in ("'self'", "*") for v in values):
            directives[connect] = (name, [v for v in values if v.lower() != "'none'"] + ["'self'"])
    elif original_default is not None:
        if not any(v in ("'self'", "*") for v in original_default):
            directives.append(("connect-src", [v for v in original_default if v.lower() != "'none'"] + ["'self'"]))
    return _serialize(directives), used


def prepare_csp_nonce(flow) -> Optional[str]:
    """Rewrite the response's CSP header(s) if needed. Returns the nonce to put on injected scripts, or None."""
    values = flow.response.headers.get_all(_HEADER)
    if not values:
        return None
    nonce = secrets.token_urlsafe(16)
    new_values = []
    used_any = False
    for v in values:
        rewritten, used = _rewrite_policy(v, nonce)
        new_values.append(rewritten)
        used_any = used_any or used
    flow.response.headers.set_all(_HEADER, new_values)
    return nonce if used_any else None


_SCRIPT_TAG = re.compile(r"<script(?![^>]*\snonce=)", re.IGNORECASE)


def add_nonce(snippet: str, nonce: Optional[str]) -> str:
    """Put nonce="..." on every <script> tag of OUR snippet (never applied to the site's own HTML)."""
    if not nonce or not snippet:
        return snippet
    return _SCRIPT_TAG.sub(f'<script nonce="{nonce}"', snippet)

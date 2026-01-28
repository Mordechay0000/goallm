"""
Test server for URL Policy Resolver. Uses only stdlib (no Flask).

Run:
  python3 -u -m test.url_policy.server [PORT]
  ./test/url_policy/run_server.sh [PORT]

(-u = פלט מיידי; אם אין פלט נסה את run_server.sh)
"""
from __future__ import annotations

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

# Add project root for imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.policy_processor.url_policy_resolver import (
    URLPolicyResolver,
    URLPolicyResolverError,
)

DIR = Path(__file__).parent


def validate_rule_domain(s: str) -> str | None:
    """Returns error message if invalid, else None. Domain: no protocol, no path."""
    t = (s or "").strip()
    if not t:
        return "נא להזין דומיין."
    if "://" in t:
        return "דומיין לא יכול לכלול פרוטוקול (למשל https://)."
    if "/" in t:
        return "דומיין לא יכול לכלול נתיב (ללא /)."
    return None


def validate_rule_path(s: str) -> str | None:
    """Returns error message if invalid, else None. Empty path is valid (optional)."""
    t = (s or "").strip()
    if not t:
        return None
    if not t.startswith("/"):
        return "נתיב חייב להתחיל ב-/."
    if "//" in t:
        return "נתיב לא יכול להכיל //."
    return None


def _domain_matches(rule_domain: str, domain: str) -> bool:
    domain = domain.lower().rstrip(".")
    if rule_domain.startswith("*."):
        base = rule_domain[2:].lower()
        return domain == base or domain.endswith("." + base)
    return domain == rule_domain.lower()


def _path_matches(rule_path: str | None, path: str) -> bool:
    if not rule_path:
        return True
    rp = rule_path.rstrip("/") if rule_path != "/" else rule_path
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if not path:
        path = "/"
    if "*" in rp:
        r_seg = [s for s in rp.split("/") if s]
        p_seg = [s for s in path.split("/") if s] if path != "/" else []
        return _segments_match(r_seg, p_seg)
    return path.startswith(rp) or (rp == "/" and path.startswith("/"))


def _segments_match(rule: list[str], path: list[str]) -> bool:
    """* in rule = exactly one segment. Must match resolver."""
    i, j = 0, 0
    while i < len(rule) and j < len(path):
        if rule[i] == "*":
            i += 1
            j += 1
            continue
        if rule[i] == path[j]:
            i += 1
            j += 1
            continue
        return False
    return i == len(rule) and j == len(path)


def _normalize_domain_path(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower().rstrip(".")
    path = unquote(parsed.path or "")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if not path:
        path = "/"
    return domain, path


def _path_rule_segments(path_prefix: str) -> list[str]:
    """Parse rule path into segments. /api/*/bar -> ['api','*','bar']."""
    p = (path_prefix or "").strip().rstrip("/") or ""
    return [s for s in p.split("/") if s]


def _examples_for_wildcard_path(segments: list[str]) -> tuple[list[str], list[str]]:
    """
    Generate path strings (e.g. /api/x/bar) that match / don't match the segment rule.
    * = exactly one segment. Returns (match_paths, no_match_paths).
    """
    match_paths: list[str] = []
    no_match_paths: list[str] = []
    placeholders = ["x", "v1", "id", "abc", "item", "user"]

    def path_from_segs(segs: list[str]) -> str:
        return "/" + "/".join(segs) if segs else "/"

    # Build one concrete match by replacing each * with a placeholder
    fill: list[str] = []
    pi = 0
    for s in segments:
        if s == "*":
            fill.append(placeholders[min(pi % len(placeholders), len(placeholders) - 1)])
            pi += 1
        else:
            fill.append(s)
    match_paths.append(path_from_segs(fill))
    # More match variants
    for sub in ["a", "v2", "123", "key", "long-segment"]:
        f2: list[str] = []
        px = 0
        for s in segments:
            if s == "*":
                f2.append(sub if px == 0 else placeholders[px % len(placeholders)])
                px += 1
            else:
                f2.append(s)
        cand = path_from_segs(f2)
        if cand not in match_paths:
            match_paths.append(cand)

    # No-match: too few segments (collapse over *)
    if "*" in segments:
        no_fill: list[str] = []
        for s in segments:
            if s == "*":
                continue
            no_fill.append(s)
        if no_fill and no_fill != segments:
            no_match_paths.append(path_from_segs(no_fill))
        # Too many segments: add two concrete segments where rule has one *
        idx = next(i for i, x in enumerate(segments) if x == "*")
        before = segments[:idx]
        after = segments[idx + 1 :]
        extra_segs = before + ["a", "b"] + [s for s in after if s != "*"]
        if len(extra_segs) > len(segments):
            no_match_paths.append(path_from_segs(extra_segs))
        # Wrong last segment (e.g. /api/x/baz instead of .../bar)
        last_lit = next((s for s in reversed(after) if s != "*"), None)
        if last_lit:
            wrong_last = before + [placeholders[0]] + [last_lit + "x"]
            no_match_paths.append(path_from_segs(wrong_last))
            no_match_paths.append(path_from_segs(before + [placeholders[0]] + ["other"]))
        # Prefix only (missing last segments)
        if len(before) >= 1:
            no_match_paths.append(path_from_segs(before))
            no_match_paths.append(path_from_segs(before) + "/")
        # Same start, one extra segment after (e.g. /api/x/bar/extra)
        same_plus = fill + ["extra"]
        no_match_paths.append(path_from_segs(same_plus))

    return (match_paths, no_match_paths)


def _example_complexity(url: str, rule_domain: str, path_prefix: str | None, want_match: bool) -> int:
    """Higher = more complex/misleading (show first). Same domain + tricky path = high."""
    d, p = _normalize_domain_path(url)
    same_domain = _domain_matches(rule_domain, d)
    path_len = len(p)
    score = 0
    if same_domain:
        score += 80
    if path_len > 20:
        score += 25
    elif path_len > 10:
        score += 15
    if path_prefix and same_domain and not want_match:
        if path_prefix in p or (path_prefix.rstrip("/") and path_prefix.rstrip("/") in p):
            score += 40
        if p.startswith(path_prefix[: min(5, len(path_prefix))]):
            score += 20
    if not same_domain:
        score -= 50
    return max(0, score)


def generate_rule_examples(domain: str, path: str | None) -> dict:
    """Generate example URLs that match / don't match. Sorted: most complex first."""
    err = validate_rule_domain(domain)
    if err:
        return {"match": [], "noMatch": [], "error": err}
    path = (path or "").strip() or None
    err = validate_rule_path(path or "")
    if err:
        return {"match": [], "noMatch": [], "error": err}

    is_wildcard = domain.strip().startswith("*.")
    base = domain.strip()[2:] if is_wildcard else domain.strip()
    base = base.lower().rstrip(".")
    path_prefix = (path or "").strip() or None
    if path_prefix and path_prefix != "/" and path_prefix.endswith("/"):
        path_prefix = path_prefix[:-1]
    host_match = f"sub.{base}" if is_wildcard else base
    host_no = base if is_wildcard else f"sub.{base}"
    scheme = "https://"

    match: list[str] = []
    no_match: list[str] = []

    def ok(u: str, want: bool) -> bool:
        d, p = _normalize_domain_path(u)
        return (_domain_matches(domain.strip(), d) and _path_matches(path_prefix, p)) == want

    if path_prefix and path_prefix != "/":
        has_wild = "*" in (path_prefix or "")
        if has_wild:
            segs = _path_rule_segments(path_prefix)
            pm, pn = _examples_for_wildcard_path(segs)
            for p in pm:
                match.append(f"{scheme}{host_match}{p}")
            for p in pn:
                no_match.append(f"{scheme}{host_match}{p}")
            no_match.append(f"{scheme}{host_match}/")
        else:
            match.extend([
                f"{scheme}{host_match}{path_prefix}",
                f"{scheme}{host_match}{path_prefix}/",
                f"{scheme}{host_match}{path_prefix}/x",
                f"{scheme}{host_match}{path_prefix}/long/sub/path",
                f"{scheme}{host_match}{path_prefix}/a/b/c/d/e",
            ])
            no_match.extend([
                f"{scheme}{host_match}/",
                f"{scheme}{host_match}/x{path_prefix}",
                f"{scheme}{host_match}{path_prefix[:-1]}" if len(path_prefix) > 1 else f"{scheme}{host_match}/",
            ])
    else:
        match.extend([
            f"{scheme}{host_match}/",
            f"{scheme}{host_match}/foo",
            f"{scheme}{host_match}/api/img/1",
            f"{scheme}{host_match}/long/path/a/b/c",
        ])
        no_match.extend([
            f"{scheme}{host_no}/",
            f"{scheme}other.com/",
            f"{scheme}{base}.evil.com/",
        ])

    match = [m for m in match if ok(m, True)]
    no_match = [m for m in no_match if ok(m, False)]

    if not match:
        m = f"{scheme}{host_match}/" if not (path_prefix and path_prefix != "/") else f"{scheme}{host_match}{path_prefix}"
        if ok(m, True):
            match = [m]
    if not no_match:
        no_match = [f"{scheme}other.com/", f"{scheme}{base}.other.com/"]

    rule_d = domain.strip()
    key = lambda u, w: -_example_complexity(u, rule_d, path_prefix, w)
    match.sort(key=lambda u: key(u, True))
    no_match.sort(key=lambda u: key(u, False))

    return {"match": match[:14], "noMatch": no_match[:14]}


def api_resolve(body: dict) -> tuple[int, dict]:
    """Returns (status_code, json_body). Server handles errors."""
    url = body.get("url", "")
    req_type = body.get("type", "image")
    policies = body.get("policies", [])

    rules = [
        {"domain": r["domain"], "path": r.get("path") or None, "type": r.get("type", "*")}
        for r in policies
    ]
    resolver = URLPolicyResolver(rules)
    try:
        rule = resolver.resolve(url, req_type)
    except URLPolicyResolverError as e:
        return 400, {"error": str(e), "rule": None, "debug": []}

    debug = resolver.get_debug_log()
    matched_full = None
    if rule:
        for r in policies:
            if (
                r.get("domain") == rule["domain"]
                and (r.get("path") or None) == rule.get("path")
                and r.get("type") == rule.get("type")
            ):
                matched_full = r
                break
        if not matched_full:
            matched_full = {**rule, "state": "allow"}

    return 200, {"rule": matched_full, "debug": debug}


def api_examples(body: dict) -> dict:
    domain = body.get("domain", "")
    path = body.get("path") or ""
    return generate_rule_examples(domain, path or None)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((DIR / "index.html").read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/resolve":
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}
            status, out = api_resolve(body)
            self._json(status, out)
        elif self.path == "/api/examples":
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}
            out = api_examples(body)
            self._json(200, out)
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    try:
        server = HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"שגיאה: פורט {port} תפוס. נסה: python -m test.url_policy.server 8766", file=sys.stderr, flush=True)
            sys.exit(1)
        raise
    msg = f"URL Policy test server: http://127.0.0.1:{port}/\n"
    sys.stderr.write(msg)
    sys.stderr.flush()
    server.serve_forever()

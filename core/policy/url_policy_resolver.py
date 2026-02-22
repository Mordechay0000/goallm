import re
from urllib.parse import urlparse, unquote
from typing import List, Dict, Optional


class URLPolicyResolverError(ValueError):
    """Raised when URL or inputs are invalid. Caller (server/page) should handle."""

    pass


class URLPolicyResolver:
    """Resolves URL to policy (allow/block) from DB-backed policies and tag rules.
    Two-phase mode: when global_policies and user_policies are provided,
    first check global whitelist (no match → review), then user rules (block match → block with block_reason user_settings).
    """

    def __init__(
        self,
        policies: Optional[List[Dict]] = None,
        tag_rules: Optional[List[Dict]] = None,
        default_mode: Optional[str] = None,
        global_policies: Optional[List[Dict]] = None,
        user_policies: Optional[List[Dict]] = None,
    ):
        # Two-phase: global (base whitelist) + user (overrides)
        self._two_phase = global_policies is not None and user_policies is not None
        if self._two_phase:
            self.global_policies = list(global_policies or [])
            self.user_policies = list(user_policies or [])
            self.policies = []
        else:
            self.global_policies = []
            self.user_policies = []
            self.policies = list(policies or [])
        self.tag_rules = list(tag_rules or [])
        self.default_mode = (default_mode or "").strip().lower()
        if self.default_mode not in ("whitelist", "blacklist"):
            self.default_mode = "whitelist"
        self._tag_block: Dict[str, bool] = {
            r["tag"].strip(): (r.get("state") == "block")
            for r in self.tag_rules
            if r.get("tag") and r.get("state") in ("allow", "block")
        }
        self._debug_log = []

    # ---------- Debug helpers ----------

    def _log(self, message: str) -> None:
        self._debug_log.append(message)

    def get_debug_log(self) -> List[str]:
        return self._debug_log.copy()

    def clear_debug(self) -> None:
        self._debug_log.clear()

    # ---------- Normalization ----------

    def _normalize_path(self, path: str) -> str:
        """Normalize path: collapse //, resolve . and .., unquote, strip trailing /."""
        if not path or path == "/":
            return "/"
        path = unquote(path)
        path = re.sub(r"/+", "/", path.strip("/"))
        parts = path.split("/")
        out = []
        for p in parts:
            if p == "." or p == "":
                continue
            if p == "..":
                if out:
                    out.pop()
                continue
            out.append(p)
        result = "/" + "/".join(out) if out else "/"
        return result.rstrip("/") if result != "/" else "/"

    def _normalize_url(self, url: str) -> tuple[str, str]:
        """Normalize URL before matching: scheme, domain (lowercase, collapse .., strip www.), path+query (//, ., ..)."""
        u = (url or "").strip()
        if "://" not in u:
            u = "https://" + u
        parsed = urlparse(u)
        domain = (parsed.hostname or "").lower().rstrip(".")
        while ".." in domain:
            domain = domain.replace("..", ".")
        domain = ".".join(p for p in domain.split(".") if p)
        if domain.startswith("www."):
            domain = domain[4:]
        path = parsed.path or ""
        if parsed.query:
            path = path + "?" + parsed.query
        path = self._normalize_path(path)
        # Lowercase path (and query) so matching is case-insensitive; CRM stores rules with lowercased URL
        path = path.lower()

        self._log(f"Normalized URL -> domain={domain}, path={path}")
        return domain, path

    # ---------- Matching logic ----------

    def _domain_matches(self, rule_domain: str, domain: str) -> bool:
        # Normalize rule_domain: treat www. like non-www for matching
        r = (rule_domain or "").strip()
        if r.startswith("www."):
            r = r[4:]
        if r.startswith("*."):
            base = r[2:]
            if base.startswith("www."):
                base = base[4:]
            match = domain == base or domain.endswith("." + base)
        else:
            match = domain == r

        self._log(
            f"Domain match check: rule={rule_domain}, target={domain}, result={match}"
        )
        return match

    def _path_matches(self, rule_path: Optional[str], path: str) -> bool:
        if rule_path is None:
            self._log("Path match: rule has no path -> match=True")
            return True

        rp = (rule_path.rstrip("/") if rule_path != "/" else rule_path).lower()
        path = path.lower()
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        if not path:
            path = "/"

        if "*" in rp:
            r_seg = [s for s in rp.split("/") if s]
            p_seg = [s for s in path.split("/") if s] if path != "/" else []
            match = self._segments_match(r_seg, p_seg)
            self._log(
                f"Path wildcard match: rule={rule_path}, target={path}, result={match}"
            )
            return match
        match = path.startswith(rp) or (rp == "/" and path.startswith("/"))
        self._log(
            f"Path prefix match: rule={rule_path}, target={path}, result={match}"
        )
        return match

    def _segments_match(self, rule: list[str], path: list[str]) -> bool:
        """Match path segments; * in rule = exactly one segment."""
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
        return i == len(rule)


    def _domain_specificity(self, rule_domain: str) -> int:
        if rule_domain.startswith("*."):
            return rule_domain.count(".")
        return 100 + rule_domain.count(".")

    def _path_specificity(self, rule_path: Optional[str]) -> int:
        if rule_path is None:
            return 0
        return len(rule_path)

    # ---------- Public API ----------

    def _validate_normalized(self, domain: str, path: str) -> None:
        if not domain or not domain.strip():
            raise URLPolicyResolverError("ה-URL חייב לכלול דומיין חוקי (כתובת עם hostname)")
        if not path.startswith("/"):
            raise URLPolicyResolverError("נתיב ה-URL חייב להתחיל ב-/")

    def _match_candidates(self, policies: List[Dict], domain: str, path: str, req_type: str) -> Optional[Dict]:
        """Find best matching rule in policies for domain, path, req_type. Returns rule or None."""
        candidates = []
        for rule in policies:
            if not self._domain_matches(rule["domain"], domain):
                continue
            if not self._path_matches(rule.get("path"), path):
                continue
            rule_type = rule.get("type") or "*"
            if rule_type != req_type and rule_type != "*":
                continue
            candidates.append(rule)
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: (
                self._domain_specificity(r["domain"]),
                self._path_specificity(r.get("path")),
            ),
            reverse=True,
        )
        rule = candidates[0]
        # Tag rules: if policy has tags and any tag has block rule, override to block
        tags = rule.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tags:
            if self._tag_block.get(tag):
                return {**rule, "state": "block"}
        return rule

    def resolve(self, url: str, req_type: str) -> Optional[Dict]:
        self.clear_debug()
        self._log(f"Resolving policy for url={url}, type={req_type}")

        domain, path = self._normalize_url(url)
        self._validate_normalized(domain, path)

        if self._two_phase:
            # Phase 1: global list. Only URLs in the global list are considered; rest → review.
            global_rule = self._match_candidates(self.global_policies, domain, path, req_type)
            if global_rule is None:
                self._log("Not in global list -> review")
                return {"state": "review"}
            if global_rule.get("state") == "block":
                self._log("Global rule says block (e.g. tag)")
                return global_rule
            # Phase 2: user profile mode. Subject to global, apply user rules.
            user_rule = self._match_candidates(self.user_policies, domain, path, req_type)
            if self.default_mode == "blacklist":
                # Blacklist: all open except what the user added as block.
                if user_rule is not None and user_rule.get("state") == "block":
                    self._log("User rule blocks -> block_reason user_settings")
                    return {**user_rule, "state": "block", "block_reason": "user_settings"}
                self._log("In global, no user block -> allow")
                return {**global_rule, "state": "allow"}
            # Whitelist: all blocked except what the user added as allow.
            if user_rule is not None and user_rule.get("state") == "allow":
                self._log("User rule allows -> allow")
                return {**global_rule, "state": "allow"}
            self._log("In global, no user allow -> block (whitelist mode)")
            return {"state": "block", "block_reason": "user_settings"}

        # Legacy single-phase: one policies list
        candidates = []
        for rule in self.policies:
            self._log(f"Evaluating rule: {rule}")
            if not self._domain_matches(rule["domain"], domain):
                self._log("Rule rejected: domain mismatch")
                continue
            if not self._path_matches(rule.get("path"), path):
                self._log("Rule rejected: path mismatch")
                continue
            candidates.append(rule)
            self._log("Rule accepted as candidate")
        candidates.sort(
            key=lambda r: (
                self._domain_specificity(r["domain"]),
                self._path_specificity(r.get("path")),
            ),
            reverse=True,
        )
        self._log(f"Candidates after sorting: {len(candidates)}")
        for rule in candidates:
            rule_type = rule.get("type") or "*"
            if rule_type != req_type and rule_type != "*":
                continue
            self._log(f"Rule selected: {rule}")
            tags = rule.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tags:
                if self._tag_block.get(tag):
                    self._log(f"Tag rule override: tag={tag} -> block")
                    return {**rule, "state": "block"}
            return rule
        self._log("No matching rule found")
        if self.default_mode == "whitelist":
            self._log("Default mode whitelist -> review (no rule = send for review)")
            return {"state": "review"}
        if self.default_mode == "blacklist":
            self._log("Default mode blacklist -> allow (no rule = open)")
            return {"state": "allow"}
        return None

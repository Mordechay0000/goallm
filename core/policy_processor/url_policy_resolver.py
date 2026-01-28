from urllib.parse import urlparse, unquote
from typing import List, Dict, Optional


class URLPolicyResolverError(ValueError):
    """Raised when URL or inputs are invalid. Caller (server/page) should handle."""

    pass


class URLPolicyResolver:
    def __init__(self, policies: List[Dict]):
        self.policies = policies
        self._debug_log: List[str] = []

    # ---------- Debug helpers ----------

    def _log(self, message: str) -> None:
        self._debug_log.append(message)

    def get_debug_log(self) -> List[str]:
        return self._debug_log.copy()

    def clear_debug(self) -> None:
        self._debug_log.clear()

    # ---------- Normalization ----------

    def _normalize_url(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower().rstrip(".")
        path = unquote(parsed.path or "")

        if path != "/" and path.endswith("/"):
            path = path[:-1]

        if not path:
            path = "/"

        self._log(f"Normalized URL -> domain={domain}, path={path}")
        return domain, path

    # ---------- Matching logic ----------

    def _domain_matches(self, rule_domain: str, domain: str) -> bool:
        if rule_domain.startswith("*."):
            base = rule_domain[2:]
            match = domain == base or domain.endswith("." + base)
        else:
            match = domain == rule_domain

        self._log(
            f"Domain match check: rule={rule_domain}, target={domain}, result={match}"
        )
        return match

    def _path_matches(self, rule_path: Optional[str], path: str) -> bool:
        if rule_path is None:
            self._log("Path match: rule has no path -> match=True")
            return True

        rp = rule_path.rstrip("/") if rule_path != "/" else rule_path
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

    def resolve(self, url: str, req_type: str) -> Optional[Dict]:
        self.clear_debug()
        self._log(f"Resolving policy for url={url}, type={req_type}")

        domain, path = self._normalize_url(url)
        self._validate_normalized(domain, path)
        candidates = []

        # Collect matching candidates
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

        # Sort by specificity
        candidates.sort(
            key=lambda r: (
                self._domain_specificity(r["domain"]),
                self._path_specificity(r.get("path")),
            ),
            reverse=True,
        )

        self._log(f"Candidates after sorting: {len(candidates)}")

        # Resolve by type
        for rule in candidates:
            rule_type = rule["type"]
            if rule_type == req_type:
                self._log(f"Rule selected (exact type match): {rule}")
                return rule
            if rule_type == "*":
                self._log(f"Rule selected (wildcard type): {rule}")
                return rule

            self._log(
                f"Rule skipped due to type mismatch: rule_type={rule_type}, req_type={req_type}"
            )

        self._log("No matching rule found")
        return None

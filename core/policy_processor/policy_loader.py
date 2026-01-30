"""
Load policies, tag rules, and profile mode from DB and build URLPolicyResolver instances.
"""
from typing import List, Dict, Any

from core.policy_processor.policy_database import (
    get_policies_for_resolver,
    get_tag_rules,
    get_profile_mode,
)
from core.policy_processor.url_policy_resolver import URLPolicyResolver


def get_policy_resolver() -> URLPolicyResolver:
    """Return a URLPolicyResolver with enabled policies, tag rules, and profile mode from the DB."""
    policies = get_policies_for_resolver()
    tag_rules = get_tag_rules(enabled_only=True)
    default_mode = get_profile_mode()
    resolver_policies = [
        {
            "domain": p["domain"],
            "path": p.get("path"),
            "type": p["type"],
            "state": p.get("state", "block"),
            "tags": p.get("tags", []),
        }
        for p in policies
    ]
    return URLPolicyResolver(
        resolver_policies,
        tag_rules=tag_rules,
        default_mode=default_mode,
    )


def get_all_policies_dict() -> List[Dict[str, Any]]:
    """Return all enabled policies as list of dicts (domain, path, type, state)."""
    return get_policies_for_resolver()

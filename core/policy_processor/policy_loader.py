"""
Load policies from DB and build URLPolicyResolver instances.
"""
from typing import List, Dict, Any

from core.policy_processor.policy_database import get_policies_for_resolver
from core.policy_processor.url_policy_resolver import URLPolicyResolver


def get_policy_resolver() -> URLPolicyResolver:
    """Return a URLPolicyResolver populated with enabled policies from the DB."""
    policies = get_policies_for_resolver()
    resolver_policies = [
        {"domain": p["domain"], "path": p.get("path"), "type": p["type"]}
        for p in policies
    ]
    return URLPolicyResolver(resolver_policies)


def get_all_policies_dict() -> List[Dict[str, Any]]:
    """Return all enabled policies as list of dicts (domain, path, type, state)."""
    return get_policies_for_resolver()

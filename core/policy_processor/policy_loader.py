"""
Helper module to load policies from database for use with URLPolicyResolver.
"""
from typing import List, Dict
from core.policy_processor.policy_database import get_policies_for_resolver
from core.policy_processor.url_policy_resolver import URLPolicyResolver


def get_policy_resolver() -> URLPolicyResolver:
    """
    Get a URLPolicyResolver instance loaded with policies from the database.
    """
    policies = get_policies_for_resolver()
    # Convert to format expected by URLPolicyResolver
    resolver_policies = [
        {
            "domain": p["domain"],
            "path": p.get("path"),
            "type": p["type"],
        }
        for p in policies
    ]
    return URLPolicyResolver(resolver_policies)


def get_all_policies_dict() -> List[Dict]:
    """
    Get all policies as dictionaries for use in other parts of the system.
    """
    return get_policies_for_resolver()

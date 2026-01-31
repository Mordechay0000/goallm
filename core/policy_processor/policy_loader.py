"""
Load policies, tag rules, and profile mode from DB and build URLPolicyResolver instances.
Two-phase: global (base whitelist) + user policies when both exist in DB.
"""
from typing import List, Dict, Any

from core.policy_processor.policy_database import (
    get_policies_for_resolver,
    get_global_policies_for_resolver,
    get_user_policies_for_resolver,
    get_tag_rules,
    get_profile_mode,
)
from core.policy_processor.url_policy_resolver import URLPolicyResolver


def get_policy_resolver() -> URLPolicyResolver:
    """Return a URLPolicyResolver. Two-phase: global whitelist + user overrides (not in global → review)."""
    tag_rules = get_tag_rules(enabled_only=True)
    default_mode = get_profile_mode()
    global_policies = get_global_policies_for_resolver()
    user_policies = get_user_policies_for_resolver()
    return URLPolicyResolver(
        tag_rules=tag_rules,
        default_mode=default_mode,
        global_policies=global_policies,
        user_policies=user_policies,
    )


def get_all_policies_dict() -> List[Dict[str, Any]]:
    """Return all enabled policies as list of dicts (domain, path, type, state)."""
    return get_policies_for_resolver()

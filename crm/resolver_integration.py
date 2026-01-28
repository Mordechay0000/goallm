"""
Integration with existing url_policy_resolver.
Converts CRM rules to format expected by URLPolicyResolver.
"""
from typing import List, Dict
from .services import get_profile_rules
from .database import db_connection


def get_active_profile_id(user_id: int) -> int | None:
    """Get the currently active profile ID for a user (default or scheduled)."""
    # TODO: Implement schedule logic to determine active profile
    # For now, return default profile
    cursor = db_connection.execute("""
        SELECT id FROM profiles 
        WHERE user_id = ? AND is_default = 1
        LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    return row["id"] if row else None


def get_rules_for_resolver(user_id: int) -> List[Dict]:
    """
    Get rules in format expected by URLPolicyResolver.
    Returns list of dicts with: domain, path, type, state
    """
    profile_id = get_active_profile_id(user_id)
    if not profile_id:
        return []
    
    rules = get_profile_rules(profile_id)
    
    # Convert to resolver format
    resolver_rules = []
    for rule in rules:
        resolver_rules.append({
            "domain": rule["domain_pattern"],
            "path": rule["path_pattern"],
            "type": rule["type"],
            "state": rule["action"],  # action -> state mapping
        })
    
    return resolver_rules


def get_all_enabled_rules_for_resolver() -> List[Dict]:
    """
    Get all enabled rules from all users (for system-wide resolver).
    This is useful for the proxy addon.
    """
    cursor = db_connection.execute("""
        SELECT r.domain_pattern, r.path_pattern, r.type, r.action, p.mode
        FROM rules r
        JOIN profiles p ON r.profile_id = p.id
        WHERE p.is_default = 1
        ORDER BY r.created_at DESC
    """)
    
    resolver_rules = []
    for row in cursor.fetchall():
        # Map action based on profile mode
        # In whitelist mode: block action means block, allow action means allow
        # In blacklist mode: block action means block, allow action means allow
        # The resolver expects 'state' field
        resolver_rules.append({
            "domain": row["domain_pattern"],
            "path": row["path_pattern"],
            "type": row["type"],
            "state": row["action"],
        })
    
    return resolver_rules

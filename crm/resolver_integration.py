"""
Integration with url_policy_resolver.
Converts CRM rules to format expected by URLPolicyResolver.
Supports active profile by schedule (תזמונים) and whitelist/blacklist mode.
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from .services import get_profile_rules, get_profile, get_tag_rules
from .database import db_connection


def _current_weekday_bitmask() -> int:
    """Current day as bit for schedule: 0=Sunday (א), 1=Monday (ב), ..., 6=Saturday (ש)."""
    # Python weekday(): 0=Monday, ..., 6=Sunday → we want 0=Sunday
    py_weekday = datetime.now().weekday()  # 0=Mon .. 6=Sun
    return 1 << ((py_weekday + 1) % 7)


def _current_time_str() -> str:
    """Current time as HH:MM."""
    return datetime.now().strftime("%H:%M")


def _time_in_range(now_hhmm: str, from_time: Optional[str], to_time: Optional[str]) -> bool:
    """True if now_hhmm is in [from_time, to_time]. None means no bound. HH:MM string comparison.
    Overnight ranges (e.g. 22:00–06:00, from > to) wrap around midnight."""
    if from_time is None and to_time is None:
        return True
    if from_time is None:
        from_time = "00:00"
    if to_time is None:
        to_time = "23:59"
    if from_time <= to_time:
        return from_time <= now_hhmm <= to_time
    return now_hhmm >= from_time or now_hhmm <= to_time


def get_active_profile_id(user_id: int) -> Optional[int]:
    """
    Get the currently active profile ID for a user.
    Uses schedule: if a schedule matches current day and time, that profile is active.
    Otherwise returns the default profile.
    """
    now_day_bit = _current_weekday_bitmask()
    now_time = _current_time_str()

    cursor = db_connection.execute("""
        SELECT p.id AS profile_id, p.is_default, s.id AS schedule_id,
               s.days_bitmask, s.from_time, s.to_time
        FROM profiles p
        LEFT JOIN schedules s ON s.profile_id = p.id
        WHERE p.user_id = ?
        ORDER BY p.is_default DESC, p.id ASC, s.id ASC
    """, (user_id,))
    rows = list(cursor.fetchall())

    # First: find a schedule that matches current day and time
    for row in rows:
        schedule_id = row["schedule_id"]
        if schedule_id is None:
            continue
        days_bitmask = row["days_bitmask"] or 0
        if not (days_bitmask & now_day_bit):
            continue
        if _time_in_range(now_time, row["from_time"], row["to_time"]):
            return row["profile_id"]

    # No matching schedule: return default profile
    for row in rows:
        if row["is_default"]:
            return row["profile_id"]
    if rows:
        return rows[0]["profile_id"]
    return None


def get_rules_for_resolver(user_id: int) -> List[Dict]:
    """
    Get rules in format expected by URLPolicyResolver for the given user's active profile.
    Returns list of dicts with: domain, path, type, state, tags.
    """
    profile_id = get_active_profile_id(user_id)
    if not profile_id:
        return []

    rules = get_profile_rules(profile_id)
    return [
        {
            "domain": r["domain_pattern"],
            "path": r["path_pattern"],
            "type": r["type"],
            "state": r["action"],
            "tags": r.get("tags", []),
        }
        for r in rules
    ]


def get_system_active_profile_and_rules(
    user_id: Optional[int] = None,
) -> Tuple[Optional[str], List[Dict], List[Dict]]:
    """
    Get (mode, rules, tag_rules) for the active profile.
    When user_id is given (e.g. current user from API), use that user's active profile.
    When user_id is None (e.g. proxy/cron), use the first user's active profile.
    Returns: (mode, resolver_rules, tag_rules). mode is 'whitelist' or 'blacklist'.
    """
    if user_id is None:
        cursor = db_connection.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return "whitelist", [], []
        user_id = row["id"]
    profile_id = get_active_profile_id(user_id)
    if not profile_id:
        return "whitelist", [], []

    profile = get_profile(profile_id)
    mode = (profile.get("mode") or "whitelist").strip().lower()
    if mode not in ("whitelist", "blacklist"):
        mode = "whitelist"

    rules = get_profile_rules(profile_id)
    resolver_rules = [
        {
            "domain": r["domain_pattern"],
            "path": r["path_pattern"],
            "type": r["type"],
            "state": r["action"],
            "tags": r.get("tags", []),
        }
        for r in rules
    ]
    tag_rules = get_tag_rules(enabled_only=False)
    return mode, resolver_rules, tag_rules


def get_all_enabled_rules_for_resolver() -> List[Dict]:
    """
    Get all enabled rules from the system active profile (for backward compatibility).
    Uses get_system_active_profile_and_rules and returns only the rules part.
    """
    _, rules, _ = get_system_active_profile_and_rules()
    return rules

"""
Traffic status helpers for flow processing.
Used by mitmproxy_addon and http_flow_processor for consistent traffic_status values.
"""


def blocked_traffic_status(rule: dict, is_file: bool) -> str:
    """Return traffic_status for a block: blocked_user / blocked_global or file_blocked_user / file_blocked_global."""
    prefix = "file_blocked_" if is_file else "blocked_"
    if rule.get("source") == "global":
        return prefix + "global"
    if rule.get("source") == "user" or rule.get("block_reason") == "user_settings":
        return prefix + "user"
    return prefix + "global"

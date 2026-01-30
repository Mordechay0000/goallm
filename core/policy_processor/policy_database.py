"""
Database management for URL policies.
Stores policies in SQLite database similar to image_status_manager.
DB path is fixed relative to project root so CRM and proxy (mitmdump) use the same file
regardless of CWD (e.g. running uvicorn from crm/ vs mitmdump from project root).
"""
import sqlite3
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Project root = parent of core/; .storage at project root so all processes share one DB
_project_root = Path(__file__).resolve().parent.parent.parent
_storage_dir = _project_root / ".storage"
_storage_dir.mkdir(parents=True, exist_ok=True)
_db_path = _storage_dir / "policies.db"

db_connection = sqlite3.connect(str(_db_path), check_same_thread=False)
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.execute("PRAGMA synchronous=NORMAL;")

POLICIES_TABLE_NAME = "url_policies"
TAG_RULES_TABLE_NAME = "tag_rules"


def init_db_schema():
    """Initialize or update database schema for policies and tag rules."""
    logger.info("Initializing policies database schema...")

    db_connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {POLICIES_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            path TEXT,
            type TEXT NOT NULL DEFAULT '*',
            state TEXT NOT NULL DEFAULT 'block',
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(domain, path, type)
        )
    """)

    # Add tags column if missing (migration)
    cursor = db_connection.execute(f"PRAGMA table_info({POLICIES_TABLE_NAME})")
    columns = [row[1] for row in cursor.fetchall()]
    if "tags" not in columns:
        db_connection.execute(f"ALTER TABLE {POLICIES_TABLE_NAME} ADD COLUMN tags TEXT")
        logger.info("Added tags column to url_policies")

    db_connection.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_domain_path 
        ON {POLICIES_TABLE_NAME}(domain, path)
    """)

    # Tag rules: rule per tag (e.g. tag=ממכר -> state=block)
    db_connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {TAG_RULES_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL DEFAULT 'block',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    db_connection.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_tag_rules_tag ON {TAG_RULES_TABLE_NAME}(tag)
    """)

    # Profile mode for resolver: whitelist = default allow, blacklist = default block
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS resolver_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    db_connection.execute(
        "INSERT OR IGNORE INTO resolver_settings (key, value) VALUES ('profile_mode', 'whitelist')"
    )

    db_connection.commit()
    logger.info("Policies database schema initialized successfully")


def set_profile_mode(mode: str) -> None:
    """Set profile mode for resolver: whitelist (no rule = review) or blacklist (no rule = allow)."""
    if mode not in ("whitelist", "blacklist"):
        mode = "whitelist"
    db_connection.execute(
        "INSERT OR REPLACE INTO resolver_settings (key, value) VALUES ('profile_mode', ?)",
        (mode,),
    )
    db_connection.commit()
    logger.info("Profile mode set to %s (core DB: %s)", mode, _db_path)


def get_profile_mode() -> str:
    """Get profile mode: whitelist or blacklist. Default whitelist.
    Whitelist = site not in list → send for review. Blacklist = site not in list → allow (open)."""
    cursor = db_connection.execute(
        "SELECT value FROM resolver_settings WHERE key = 'profile_mode'"
    )
    row = cursor.fetchone()
    if row:
        v = (row[0] or "").strip().lower()
        if v in ("whitelist", "blacklist"):
            return v
    return "whitelist"


def get_core_resolver_db_path() -> str:
    """Return the DB path core uses (for debugging)."""
    return str(_db_path)


def _tags_to_str(tags: Optional[List[str]]) -> Optional[str]:
    """Convert list of tags to comma-separated string for DB."""
    if not tags:
        return None
    return ",".join(t.strip() for t in tags if t and t.strip())


def _parse_tags(tags_val: Optional[str]) -> List[str]:
    """Parse tags from DB (comma-separated) to list."""
    if not tags_val or not tags_val.strip():
        return []
    return [t.strip() for t in tags_val.split(",") if t.strip()]


def validate_policy(domain: str, path: Optional[str] = None,
                    policy_type: str = "*", state: str = "block",
                    tags: Optional[List[str]] = None) -> Optional[str]:
    """Validate policy fields. Returns error message if invalid, None if valid."""
    domain = (domain or "").strip()
    if not domain:
        return "נא להזין דומיין."
    if "://" in domain:
        return "דומיין לא יכול לכלול פרוטוקול (למשל https://)."
    if "/" in domain:
        return "דומיין לא יכול לכלול נתיב (ללא /)."

    if path:
        path = path.strip()
        if path and not path.startswith("/"):
            return "נתיב חייב להתחיל ב-/."
        if "//" in path:
            return "נתיב לא יכול להכיל //."

    if policy_type not in ["*", "image", "html", "script", "css"]:
        return f"סוג לא חוקי: {policy_type}. אפשרויות: *, image, html, script, css"

    if state not in ["allow", "block"]:
        return f"סטטוס לא חוקי: {state}. אפשרויות: allow, block"

    return None


def add_policy(domain: str, path: Optional[str] = None,
               policy_type: str = "*", state: str = "block",
               description: Optional[str] = None, enabled: bool = True,
               tags: Optional[List[str]] = None) -> Dict:
    """Add a new policy. Returns the created policy dict."""
    error = validate_policy(domain, path, policy_type, state, tags)
    if error:
        raise ValueError(error)

    now = int(datetime.now().timestamp())
    path = path.strip() if path else None
    tags_str = _tags_to_str(tags) if tags else None

    try:
        db_connection.execute(f"""
            INSERT INTO {POLICIES_TABLE_NAME} 
            (domain, path, type, state, description, enabled, created_at, updated_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (domain, path, policy_type, state, description, 1 if enabled else 0, now, now, tags_str))
        db_connection.commit()
        
        # Get the inserted row
        cursor = db_connection.execute(f"""
            SELECT * FROM {POLICIES_TABLE_NAME} 
            WHERE domain = ? AND (path = ? OR (path IS NULL AND ? IS NULL)) AND type = ?
        """, (domain, path, path, policy_type))
        
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)
        raise Exception("Failed to retrieve created policy")
        
    except sqlite3.IntegrityError:
        raise ValueError("כלל עם דומיין, נתיב וסוג זה כבר קיים")


def update_policy(policy_id: int, domain: Optional[str] = None,
                  path: Optional[str] = None, policy_type: Optional[str] = None,
                  state: Optional[str] = None, description: Optional[str] = None,
                  enabled: Optional[bool] = None, tags: Optional[List[str]] = None) -> Dict:
    """Update an existing policy. Returns the updated policy dict."""
    cursor = db_connection.execute(f"""
        SELECT * FROM {POLICIES_TABLE_NAME} WHERE id = ?
    """, (policy_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"כלל עם ID {policy_id} לא נמצא")

    current = row_to_dict(row)
    new_tags = tags if tags is not None else current.get("tags")
    # Update fields
    new_domain = domain if domain is not None else current["domain"]
    new_path = path if path is not None else current["path"]
    new_type = policy_type if policy_type is not None else current["type"]
    new_state = state if state is not None else current["state"]
    new_description = description if description is not None else current["description"]
    new_enabled = enabled if enabled is not None else current["enabled"]

    # Validate
    error = validate_policy(new_domain, new_path, new_type, new_state, new_tags if isinstance(new_tags, list) else None)
    if error:
        raise ValueError(error)

    now = int(datetime.now().timestamp())
    new_path = new_path.strip() if new_path else None
    new_tags_str = _tags_to_str(new_tags) if isinstance(new_tags, list) else (new_tags if isinstance(new_tags, str) else _tags_to_str(current.get("tags")))

    try:
        db_connection.execute(f"""
            UPDATE {POLICIES_TABLE_NAME}
            SET domain = ?, path = ?, type = ?, state = ?,
                description = ?, enabled = ?, updated_at = ?, tags = ?
            WHERE id = ?
        """, (new_domain, new_path, new_type, new_state,
              new_description, 1 if new_enabled else 0, now, new_tags_str, policy_id))
        db_connection.commit()
        
        # Return updated policy
        cursor = db_connection.execute(f"""
            SELECT * FROM {POLICIES_TABLE_NAME} WHERE id = ?
        """, (policy_id,))
        row = cursor.fetchone()
        return row_to_dict(row)
        
    except sqlite3.IntegrityError:
        raise ValueError("כלל עם דומיין, נתיב וסוג זה כבר קיים")


def delete_policy(policy_id: int) -> bool:
    """Delete a policy by ID. Returns True if deleted, False if not found."""
    cursor = db_connection.execute(f"""
        DELETE FROM {POLICIES_TABLE_NAME} WHERE id = ?
    """, (policy_id,))
    db_connection.commit()
    return cursor.rowcount > 0


def get_policy(policy_id: int) -> Optional[Dict]:
    """Get a single policy by ID."""
    cursor = db_connection.execute(f"""
        SELECT * FROM {POLICIES_TABLE_NAME} WHERE id = ?
    """, (policy_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None


def get_all_policies(enabled_only: bool = False) -> List[Dict]:
    """Get all policies, optionally filtered by enabled status."""
    query = f"SELECT * FROM {POLICIES_TABLE_NAME}"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY created_at DESC"
    
    cursor = db_connection.execute(query)
    return [row_to_dict(row) for row in cursor.fetchall()]


def get_policies_for_resolver() -> List[Dict]:
    """Get all enabled policies in the format expected by URLPolicyResolver (with tags)."""
    policies = get_all_policies(enabled_only=True)
    return [
        {
            "domain": p["domain"],
            "path": p["path"],
            "type": p["type"],
            "state": p["state"],
            "tags": p.get("tags", []),
        }
        for p in policies
    ]


def get_tag_rules(enabled_only: bool = True) -> List[Dict]:
    """Get tag rules (e.g. tag=ממכר -> state=block)."""
    query = f"SELECT * FROM {TAG_RULES_TABLE_NAME}"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY tag"
    cursor = db_connection.execute(query)
    return [tag_rule_row_to_dict(row) for row in cursor.fetchall()]


def validate_tag_rule(tag: str, state: str = "block") -> Optional[str]:
    if not (tag or "").strip():
        return "נא להזין תגית."
    if state not in ["allow", "block"]:
        return f"סטטוס לא חוקי: {state}. אפשרויות: allow, block"
    return None


def add_tag_rule(tag: str, state: str = "block", enabled: bool = True) -> Dict:
    """Add a tag rule. Returns the created rule dict."""
    tag = (tag or "").strip()
    error = validate_tag_rule(tag, state)
    if error:
        raise ValueError(error)
    now = int(datetime.now().timestamp())
    try:
        db_connection.execute(f"""
            INSERT INTO {TAG_RULES_TABLE_NAME} (tag, state, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (tag, state, 1 if enabled else 0, now, now))
        db_connection.commit()
        cursor = db_connection.execute(
            f"SELECT * FROM {TAG_RULES_TABLE_NAME} WHERE tag = ?", (tag,)
        )
        row = cursor.fetchone()
        if row:
            return tag_rule_row_to_dict(row)
        raise Exception("Failed to retrieve created tag rule")
    except sqlite3.IntegrityError:
        raise ValueError(f"כלל לתגית '{tag}' כבר קיים")


def update_tag_rule(rule_id: int, tag: Optional[str] = None, state: Optional[str] = None,
                    enabled: Optional[bool] = None) -> Dict:
    """Update a tag rule. Returns the updated rule dict."""
    cursor = db_connection.execute(f"SELECT * FROM {TAG_RULES_TABLE_NAME} WHERE id = ?", (rule_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"כלל תגית עם ID {rule_id} לא נמצא")
    current = tag_rule_row_to_dict(row)
    new_tag = (tag or current["tag"]).strip() if tag is not None else current["tag"]
    new_state = state if state is not None else current["state"]
    new_enabled = enabled if enabled is not None else current["enabled"]
    error = validate_tag_rule(new_tag, new_state)
    if error:
        raise ValueError(error)
    now = int(datetime.now().timestamp())
    db_connection.execute(f"""
        UPDATE {TAG_RULES_TABLE_NAME} SET tag = ?, state = ?, enabled = ?, updated_at = ?
        WHERE id = ?
    """, (new_tag, new_state, 1 if new_enabled else 0, now, rule_id))
    db_connection.commit()
    cursor = db_connection.execute(f"SELECT * FROM {TAG_RULES_TABLE_NAME} WHERE id = ?", (rule_id,))
    row = cursor.fetchone()
    return tag_rule_row_to_dict(row) if row else current


def delete_tag_rule(rule_id: int) -> bool:
    """Delete a tag rule by ID."""
    cursor = db_connection.execute(f"DELETE FROM {TAG_RULES_TABLE_NAME} WHERE id = ?", (rule_id,))
    db_connection.commit()
    return cursor.rowcount > 0


def tag_rule_row_to_dict(row: tuple) -> Dict:
    return {
        "id": row[0],
        "tag": row[1],
        "state": row[2],
        "enabled": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
    }


def row_to_dict(row: tuple) -> Dict:
    """Convert database row to dictionary (policies table; includes tags)."""
    d = {
        "id": row[0],
        "domain": row[1],
        "path": row[2],
        "type": row[3],
        "state": row[4],
        "description": row[5],
        "enabled": bool(row[6]),
        "created_at": row[7],
        "updated_at": row[8],
    }
    if len(row) > 9:
        d["tags"] = _parse_tags(row[9]) if row[9] else []
    else:
        d["tags"] = []
    return d


# Initialize schema on import
init_db_schema()

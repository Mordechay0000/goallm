"""
Database management for URL policies.
Stores policies in SQLite database (pattern similar to image_status_db).
DB path is fixed relative to project root so CRM and proxy (mitmdump) use the same file
regardless of CWD (e.g. running uvicorn from crm/ vs mitmdump from project root).
"""
import contextlib
import sqlite3
import logging
import os
import secrets
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from data.constants import POLICIES_TABLE_NAME, TAG_RULES_TABLE_NAME, GOALLM_STORAGE_DIR

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parent.parent.parent


def _get_storage_dir():
    if GOALLM_STORAGE_DIR:
        return Path(GOALLM_STORAGE_DIR)
    return _project_root / ".storage"


_storage_dir = _get_storage_dir()
os.makedirs(str(_storage_dir), mode=0o755, exist_ok=True)
_db_path = _storage_dir / "policies.db"

try:
    db_connection = sqlite3.connect(str(_db_path), check_same_thread=False, timeout=10)
except sqlite3.OperationalError:
    _fallback = Path.home() / ".goallm" / "storage"
    if _fallback.resolve() != _storage_dir.resolve():
        os.makedirs(str(_fallback), mode=0o755, exist_ok=True)
        _db_path = _fallback / "policies.db"
        db_connection = sqlite3.connect(str(_db_path), check_same_thread=False, timeout=10)
        logger.warning("Using fallback policies DB at %s", _db_path)
    else:
        raise
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.execute("PRAGMA synchronous=NORMAL;")


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

    # Add source column: 'global' (base whitelist) or 'user' (per-user rules). Allow same URL in both.
    cursor = db_connection.execute(f"PRAGMA table_info({POLICIES_TABLE_NAME})")
    columns = [row[1] for row in cursor.fetchall()]
    if "source" not in columns:
        # Recreate table with (domain, path, type, source) unique so global and user can have same URL
        db_connection.execute(f"""
            CREATE TABLE url_policies_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                path TEXT,
                type TEXT NOT NULL DEFAULT '*',
                state TEXT NOT NULL DEFAULT 'block',
                description TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                tags TEXT,
                source TEXT NOT NULL DEFAULT 'user',
                UNIQUE(domain, path, type, source)
            )
        """)
        db_connection.execute(f"""
            INSERT INTO url_policies_new
            (id, domain, path, type, state, description, enabled, created_at, updated_at, tags, source)
            SELECT id, domain, path, type, state, description, enabled, created_at, updated_at, tags, 'user'
            FROM {POLICIES_TABLE_NAME}
        """)
        db_connection.execute(f"DROP TABLE {POLICIES_TABLE_NAME}")
        db_connection.execute("ALTER TABLE url_policies_new RENAME TO " + POLICIES_TABLE_NAME)
        db_connection.commit()
        logger.info("Added source column to url_policies (global/user)")

    # Migration: text_filter_enabled (per global rule; default 1)
    cursor = db_connection.execute(f"PRAGMA table_info({POLICIES_TABLE_NAME})")
    columns = [row[1] for row in cursor.fetchall()]
    if "text_filter_enabled" not in columns:
        db_connection.execute(f"ALTER TABLE {POLICIES_TABLE_NAME} ADD COLUMN text_filter_enabled INTEGER NOT NULL DEFAULT 1")
        logger.info("Added text_filter_enabled to url_policies")
        columns = [row[1] for row in db_connection.execute(f"PRAGMA table_info({POLICIES_TABLE_NAME})").fetchall()]
    if "image_filter_enabled" not in columns:
        db_connection.execute(f"ALTER TABLE {POLICIES_TABLE_NAME} ADD COLUMN image_filter_enabled INTEGER NOT NULL DEFAULT 1")
        logger.info("Added image_filter_enabled to url_policies")

    # Migration: user_id for per-user policies (NULL = global, integer = user)
    cursor = db_connection.execute(f"PRAGMA table_info({POLICIES_TABLE_NAME})")
    columns = [row[1] for row in cursor.fetchall()]
    if "user_id" not in columns:
        db_connection.execute(f"""
            CREATE TABLE url_policies_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                path TEXT,
                type TEXT NOT NULL DEFAULT '*',
                state TEXT NOT NULL DEFAULT 'block',
                description TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                tags TEXT,
                source TEXT NOT NULL DEFAULT 'user',
                text_filter_enabled INTEGER NOT NULL DEFAULT 1,
                image_filter_enabled INTEGER NOT NULL DEFAULT 1,
                user_id INTEGER,
                UNIQUE(domain, path, type, source, user_id)
            )
        """)
        db_connection.execute(f"""
            INSERT INTO url_policies_new
            (id, domain, path, type, state, description, enabled, created_at, updated_at, tags, source, text_filter_enabled, image_filter_enabled, user_id)
            SELECT id, domain, path, type, state, description, enabled, created_at, updated_at, tags, source,
                   COALESCE(text_filter_enabled, 1), COALESCE(image_filter_enabled, 1),
                   CASE WHEN source = 'global' THEN NULL ELSE 0 END
            FROM {POLICIES_TABLE_NAME}
        """)
        db_connection.execute(f"DROP TABLE {POLICIES_TABLE_NAME}")
        db_connection.execute("ALTER TABLE url_policies_new RENAME TO " + POLICIES_TABLE_NAME)
        db_connection.commit()
        logger.info("Added user_id to url_policies")

    db_connection.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_domain_path 
        ON {POLICIES_TABLE_NAME}(domain, path)
    """)

    # Per-user profile mode (for IP-bound users)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS resolver_settings_user (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
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
    db_connection.execute(
        "INSERT OR IGNORE INTO resolver_settings (key, value) VALUES ('default_user_id', '0')"
    )

    # Global filter switches: each filter type can be enabled/disabled independently (1 = on, 0 = off)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS filter_switches (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 1
        )
    """)
    for key in ("url_policy", "text_filter", "image_filter", "embedded_image_filter"):
        db_connection.execute(
            "INSERT OR IGNORE INTO filter_switches (key, value) VALUES (?, 1)",
            (key,),
        )

    # Migration: audit fields for filter_switches (who changed, when – not displayed in API)
    fs_cursor = db_connection.execute("PRAGMA table_info(filter_switches)")
    fs_cols = [row[1] for row in fs_cursor.fetchall()]
    if "updated_by_user_id" not in fs_cols:
        db_connection.execute("ALTER TABLE filter_switches ADD COLUMN updated_by_user_id INTEGER")
        logger.info("Added updated_by_user_id to filter_switches")
    if "updated_at" not in fs_cols:
        db_connection.execute("ALTER TABLE filter_switches ADD COLUMN updated_at INTEGER")
        logger.info("Added updated_at to filter_switches")

    # IP bindings: synced from CRM; proxy resolves client IP → user_id
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS ip_bindings (
            ip TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL
        )
    """)

    # Allowed file downloads: URLs approved by admin (from "request file" flow); proxy skips file-download block for these
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS allowed_file_downloads (
            url TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL
        )
    """)

    # Traffic recording: user starts recording in CRM → proxy logs each request until user stops
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS traffic_recording_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at INTEGER NOT NULL,
            ended_at INTEGER
        )
    """)
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_traffic_sessions_user_ended
        ON traffic_recording_sessions(user_id, ended_at)
    """)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS traffic_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            protocol TEXT,
            status TEXT NOT NULL,
            time_sec REAL,
            content_type TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES traffic_recording_sessions(id)
        )
    """)
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_traffic_log_session ON traffic_log(session_id)
    """)

    # share_token: צפייה בהקלטה לכל מי שיש לו את הקישור
    cursor = db_connection.execute("PRAGMA table_info(traffic_recording_sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "share_token" not in columns:
        db_connection.execute("ALTER TABLE traffic_recording_sessions ADD COLUMN share_token TEXT")
        db_connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_traffic_sessions_share_token ON traffic_recording_sessions(share_token)")
        db_connection.commit()
        logger.info("Added share_token to traffic_recording_sessions")

    db_connection.commit()
    logger.info("Policies database schema initialized successfully")


def set_profile_mode(mode: str, user_id: Optional[int] = None) -> None:
    """Set profile mode. When user_id is set, store per-user; else global default."""
    if mode not in ("whitelist", "blacklist"):
        mode = "whitelist"
    if user_id is not None:
        db_connection.execute(
            "INSERT OR REPLACE INTO resolver_settings_user (user_id, key, value) VALUES (?, 'profile_mode', ?)",
            (user_id, mode),
        )
    else:
        db_connection.execute(
            "INSERT OR REPLACE INTO resolver_settings (key, value) VALUES ('profile_mode', ?)",
            (mode,),
        )
    db_connection.commit()
    logger.info("Profile mode set to %s (core DB: %s)%s", mode, _db_path, f" user_id={user_id}" if user_id is not None else "")


def get_default_user_id() -> Optional[int]:
    """User ID to use when flow has no bound user (e.g. IP binding disabled). Set by CRM sync."""
    cursor = db_connection.execute(
        "SELECT value FROM resolver_settings WHERE key = 'default_user_id'"
    )
    row = cursor.fetchone()
    if not row or row[0] is None:
        return None
    try:
        return int(row[0])
    except (ValueError, TypeError):
        return None


def set_default_user_id(user_id: Optional[int]) -> None:
    """Set the default user_id for unbound flows (when IP binding is off)."""
    val = str(user_id) if user_id is not None else ""
    db_connection.execute(
        "INSERT OR REPLACE INTO resolver_settings (key, value) VALUES ('default_user_id', ?)",
        (val,),
    )
    db_connection.commit()


def get_profile_mode(user_id: Optional[int] = None) -> str:
    """Get profile mode. When user_id is set, use per-user setting; else use default_user_id then global."""
    _uid = user_id if user_id is not None else get_default_user_id()
    if _uid is not None:
        cursor = db_connection.execute(
            "SELECT value FROM resolver_settings_user WHERE user_id = ? AND key = 'profile_mode'",
            (_uid,),
        )
        row = cursor.fetchone()
        if row:
            v = (row[0] or "").strip().lower()
            if v in ("whitelist", "blacklist"):
                return v
    cursor = db_connection.execute(
        "SELECT value FROM resolver_settings WHERE key = 'profile_mode'"
    )
    row = cursor.fetchone()
    if row:
        v = (row[0] or "").strip().lower()
        if v in ("whitelist", "blacklist"):
            return v
    return "whitelist"


def get_user_id_for_ip(ip: str):
    """Resolve client IP to user_id. Returns int or None if not bound."""
    if not ip or not str(ip).strip():
        return None
    ip = str(ip).strip()
    cursor = db_connection.execute("SELECT user_id FROM ip_bindings WHERE ip = ?", (ip,))
    row = cursor.fetchone()
    return int(row[0]) if row else None


def set_ip_bindings(bindings: list) -> None:
    """Replace all ip_bindings with list of (ip, user_id). Called when syncing from CRM."""
    db_connection.execute("DELETE FROM ip_bindings")
    for ip, user_id in bindings:
        ip = str(ip).strip()
        if ip:
            db_connection.execute(
                "INSERT OR REPLACE INTO ip_bindings (ip, user_id) VALUES (?, ?)",
                (ip, int(user_id)),
            )
    db_connection.commit()
    logger.info("ip_bindings updated: %s entries", len(bindings))


def get_core_resolver_db_path() -> str:
    """Return the DB path core uses (for debugging)."""
    return str(_db_path)


FILTER_SWITCH_KEYS = ("url_policy", "text_filter", "image_filter", "embedded_image_filter", "file_download_filter")


def get_filter_switches() -> Dict[str, bool]:
    """Get global filter switches. Each filter works independently when enabled. Default all True."""
    placeholders = ", ".join("?" * len(FILTER_SWITCH_KEYS))
    cursor = db_connection.execute(
        f"SELECT key, value FROM filter_switches WHERE key IN ({placeholders})",
        FILTER_SWITCH_KEYS,
    )
    out = {k: True for k in FILTER_SWITCH_KEYS}
    for row in cursor.fetchall():
        out[row[0]] = bool(row[1])
    return out


def set_filter_switch(key: str, enabled: bool, updated_by_user_id: Optional[int] = None) -> None:
    """Set one filter switch. key: url_policy, text_filter, image_filter, embedded_image_filter, file_download_filter.
    updated_by_user_id is stored for audit only (not displayed in API)."""
    if key not in FILTER_SWITCH_KEYS:
        raise ValueError(f"Invalid filter key: {key}")
    now = int(datetime.now().timestamp())
    db_connection.execute(
        "INSERT OR REPLACE INTO filter_switches (key, value, updated_by_user_id, updated_at) VALUES (?, ?, ?, ?)",
        (key, 1 if enabled else 0, updated_by_user_id, now),
    )
    db_connection.commit()
    logger.info("Filter switch %s set to %s", key, enabled)


def set_filter_switches(switches: Dict[str, bool], updated_by_user_id: Optional[int] = None) -> None:
    """Set multiple filter switches. Only provided keys are updated.
    updated_by_user_id is stored for audit only (not displayed in API)."""
    now = int(datetime.now().timestamp())
    for key, enabled in switches.items():
        if key in FILTER_SWITCH_KEYS:
            db_connection.execute(
                "INSERT OR REPLACE INTO filter_switches (key, value, updated_by_user_id, updated_at) VALUES (?, ?, ?, ?)",
                (key, 1 if enabled else 0, updated_by_user_id, now),
            )
    db_connection.commit()
    logger.info("Filter switches updated: %s", switches)


def set_allowed_file_urls(urls: List[str]) -> None:
    """Replace the allowed file-download list (synced from CRM). Core does not own this list; CRM does."""
    db_connection.execute("DELETE FROM allowed_file_downloads")
    now = int(datetime.now().timestamp())
    for url in (urls or []):
        u = (url or "").strip()
        if u:
            db_connection.execute(
                "INSERT INTO allowed_file_downloads (url, created_at) VALUES (?, ?)",
                (u, now),
            )
    db_connection.commit()
    logger.info("Allowed file URLs synced from CRM: %s entries", len([u for u in (urls or []) if (u or "").strip()]))


def is_file_url_allowed(url: str) -> bool:
    """Return True if this URL is in the global allowed file-download list (approved by admin)."""
    url = (url or "").strip()
    if not url:
        return False
    cursor = db_connection.execute(
        "SELECT 1 FROM allowed_file_downloads WHERE url = ? LIMIT 1",
        (url,),
    )
    return cursor.fetchone() is not None


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
               tags: Optional[List[str]] = None, source: str = "user",
               text_filter_enabled: bool = True, image_filter_enabled: bool = True,
               user_id: Optional[int] = None) -> Dict:
    """Add a new policy. source: 'global' (user_id must be None) or 'user' (user_id optional, for per-user rules)."""
    if source not in ("global", "user"):
        source = "user"
    if source == "global":
        user_id = None
    elif user_id is None:
        user_id = 0  # legacy
    error = validate_policy(domain, path, policy_type, state, tags)
    if error:
        raise ValueError(error)

    now = int(datetime.now().timestamp())
    path = path.strip() if path else None
    tags_str = _tags_to_str(tags) if tags else None
    tf = 1 if text_filter_enabled else 0
    imgf = 1 if image_filter_enabled else 0

    try:
        db_connection.execute(f"""
            INSERT INTO {POLICIES_TABLE_NAME} 
            (domain, path, type, state, description, enabled, created_at, updated_at, tags, source, text_filter_enabled, image_filter_enabled, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (domain, path, policy_type, state, description, 1 if enabled else 0, now, now, tags_str, source, tf, imgf, user_id))
        db_connection.commit()
        
        cursor = db_connection.execute(f"""
            SELECT * FROM {POLICIES_TABLE_NAME} 
            WHERE domain = ? AND (path = ? OR (path IS NULL AND ? IS NULL)) AND type = ? AND source = ? AND (user_id = ? OR (user_id IS NULL AND ? IS NULL))
        """, (domain, path, path, policy_type, source, user_id, user_id))
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)
        raise Exception("Failed to retrieve created policy")
        
    except sqlite3.IntegrityError:
        raise ValueError("כלל עם דומיין, נתיב וסוג זה כבר קיים (למקור זה)")


def update_policy(policy_id: int, domain: Optional[str] = None,
                  path: Optional[str] = None, policy_type: Optional[str] = None,
                  state: Optional[str] = None, description: Optional[str] = None,
                  enabled: Optional[bool] = None, tags: Optional[List[str]] = None,
                  source: Optional[str] = None, text_filter_enabled: Optional[bool] = None,
                  image_filter_enabled: Optional[bool] = None) -> Dict:
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
    new_source = source if source is not None else current.get("source", "user")
    if new_source not in ("global", "user"):
        new_source = "user"
    new_text_filter = text_filter_enabled if text_filter_enabled is not None else current.get("text_filter_enabled", True)
    new_image_filter = image_filter_enabled if image_filter_enabled is not None else current.get("image_filter_enabled", True)

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
                description = ?, enabled = ?, updated_at = ?, tags = ?, source = ?, text_filter_enabled = ?, image_filter_enabled = ?
            WHERE id = ?
        """, (new_domain, new_path, new_type, new_state,
              new_description, 1 if new_enabled else 0, now, new_tags_str, new_source, 1 if new_text_filter else 0, 1 if new_image_filter else 0, policy_id))
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


def delete_user_policies(user_id: int) -> None:
    """Delete all user policies for a given user_id (used when syncing that user from CRM)."""
    db_connection.execute(f"DELETE FROM {POLICIES_TABLE_NAME} WHERE source = 'user' AND user_id = ?", (user_id,))
    db_connection.commit()


def get_policy(policy_id: int) -> Optional[Dict]:
    """Get a single policy by ID."""
    cursor = db_connection.execute(f"""
        SELECT * FROM {POLICIES_TABLE_NAME} WHERE id = ?
    """, (policy_id,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None


def get_all_policies(enabled_only: bool = False, source_filter: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict]:
    """Get all policies. When source_filter='user' and user_id is set, return only that user's policies."""
    query = f"SELECT * FROM {POLICIES_TABLE_NAME}"
    params = []
    where = []
    if enabled_only:
        where.append("enabled = 1")
    if source_filter in ("global", "user"):
        where.append("source = ?")
        params.append(source_filter)
    if source_filter == "user" and user_id is not None:
        where.append("user_id = ?")
        params.append(user_id)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"
    cursor = db_connection.execute(query, params) if params else db_connection.execute(query)
    return [row_to_dict(row) for row in cursor.fetchall()]


def get_policies_for_resolver() -> List[Dict]:
    """Get all enabled policies in the format expected by URLPolicyResolver (with tags). Backward compat: returns both global and user."""
    policies = get_all_policies(enabled_only=True)
    return [
        {
            "domain": p["domain"],
            "path": p["path"],
            "type": p["type"],
            "state": p["state"],
            "tags": p.get("tags", []),
            "source": p.get("source", "user"),
        }
        for p in policies
    ]


def get_global_policies_for_resolver() -> List[Dict]:
    """Get enabled global (base whitelist) policies for resolver."""
    policies = get_all_policies(enabled_only=True, source_filter="global")
    return [
        {"domain": p["domain"], "path": p["path"], "type": p["type"], "state": p["state"], "tags": p.get("tags", []), "text_filter_enabled": p.get("text_filter_enabled", True), "image_filter_enabled": p.get("image_filter_enabled", True)}
        for p in policies
    ]


def get_user_policies_for_resolver(user_id: Optional[int] = None) -> List[Dict]:
    """Get enabled user policies for resolver. When user_id is None, use default_user_id (first user)."""
    _uid = user_id if user_id is not None else get_default_user_id()
    policies = get_all_policies(enabled_only=True, source_filter="user", user_id=_uid)
    return [
        {"domain": p["domain"], "path": p["path"], "type": p["type"], "state": p["state"], "tags": p.get("tags", [])}
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
    """Convert database row to dictionary (policies table; includes tags and source)."""
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
    if len(row) > 10:
        d["source"] = (row[10] or "user")
    else:
        d["source"] = "user"
    if len(row) > 11:
        d["text_filter_enabled"] = bool(row[11])
    else:
        d["text_filter_enabled"] = True
    if len(row) > 12:
        d["image_filter_enabled"] = bool(row[12])
    else:
        d["image_filter_enabled"] = True
    if len(row) > 13:
        d["user_id"] = row[13] if row[13] is not None else None
    else:
        d["user_id"] = None
    return d


# --- Traffic recording (start/stop from CRM, proxy appends log entries) ---


def start_traffic_session(user_id: int) -> int:
    """Start a traffic recording session for user. Returns session id."""
    now = int(datetime.now().timestamp())
    cursor = db_connection.execute(
        "INSERT INTO traffic_recording_sessions (user_id, started_at, ended_at) VALUES (?, ?, NULL)",
        (user_id, now),
    )
    db_connection.commit()
    return cursor.lastrowid


def get_traffic_log_entry_count(session_id: int, user_id: int) -> int:
    """Return number of log entries for the session. Session must belong to user_id."""
    cursor = db_connection.execute(
        "SELECT id FROM traffic_recording_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not cursor.fetchone():
        return 0
    cursor = db_connection.execute(
        "SELECT COUNT(*) FROM traffic_log WHERE session_id = ?",
        (session_id,),
    )
    return cursor.fetchone()[0] or 0


def stop_traffic_session(user_id: int) -> Optional[Tuple[int, Optional[str]]]:
    """End the active traffic session for user. Always closes the session (sets ended_at).
    Returns (session_id, share_token). share_token is None if no traffic was captured —
    then caller should return error and not expose a link."""
    now = int(datetime.now().timestamp())
    cursor = db_connection.execute(
        "SELECT id FROM traffic_recording_sessions WHERE user_id = ? AND ended_at IS NULL LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    session_id = row[0]
    entry_count = get_traffic_log_entry_count(session_id, user_id)
    if entry_count == 0:
        db_connection.execute(
            "UPDATE traffic_recording_sessions SET ended_at = ? WHERE id = ?",
            (now, session_id),
        )
        db_connection.commit()
        return (session_id, None)
    share_token = secrets.token_urlsafe(32)
    db_connection.execute(
        "UPDATE traffic_recording_sessions SET ended_at = ?, share_token = ? WHERE id = ?",
        (now, share_token, session_id),
    )
    db_connection.commit()
    return (session_id, share_token)


def get_active_traffic_session_id(user_id: int) -> Optional[int]:
    """Return active session id for user (for proxy to know if it should log)."""
    cursor = db_connection.execute(
        "SELECT id FROM traffic_recording_sessions WHERE user_id = ? AND ended_at IS NULL LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def add_traffic_log_entry(
    session_id: int,
    user_id: int,
    url: str,
    protocol: str,
    status: str,
    time_sec: float,
    content_type: Optional[str],
) -> None:
    """Append one request to traffic log. Proxy calls this; session must belong to user_id."""
    cursor = db_connection.execute(
        "SELECT id FROM traffic_recording_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not cursor.fetchone():
        logger.warning("add_traffic_log_entry: session %s not found for user %s", session_id, user_id)
        return
    now = int(datetime.now().timestamp())
    db_connection.execute(
        """INSERT INTO traffic_log (session_id, url, protocol, status, time_sec, content_type, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, url or "", protocol or "", status or "open", time_sec, content_type or "", now),
    )
    db_connection.commit()


def get_traffic_sessions(user_id: int) -> List[Dict]:
    """List recording sessions for user (for CRM)."""
    cursor = db_connection.execute(
        """SELECT id, user_id, started_at, ended_at FROM traffic_recording_sessions
           WHERE user_id = ? ORDER BY started_at DESC""",
        (user_id,),
    )
    return [
        {"id": row[0], "user_id": row[1], "started_at": row[2], "ended_at": row[3]}
        for row in cursor.fetchall()
    ]


def get_traffic_log(session_id: int, user_id: int) -> List[Dict]:
    """Get log entries for a session. Session must belong to user_id.
    Uses a dedicated connection so it is safe when called from a thread (e.g. asyncio.to_thread).
    """
    with contextlib.closing(sqlite3.connect(str(_db_path), timeout=10)) as conn:
        cursor = conn.execute(
            "SELECT id FROM traffic_recording_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if not cursor.fetchone():
            return []
        return _get_traffic_log_rows(session_id, conn)


def get_traffic_session_by_token(token: str) -> Optional[Dict]:
    """Get session by share_token. For public view (anyone with link)."""
    if not token or not token.strip():
        return None
    cursor = db_connection.execute(
        "SELECT id, user_id, started_at, ended_at, share_token FROM traffic_recording_sessions WHERE share_token = ?",
        (token.strip(),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "started_at": row[2],
        "ended_at": row[3],
        "share_token": row[4],
    }


def get_traffic_log_by_session_id(session_id: int) -> List[Dict]:
    """Get log entries for a session (public – no user check). Use with get_traffic_session_by_token."""
    return _get_traffic_log_rows(session_id, None)


def _get_traffic_log_rows(session_id: int, conn: Optional[sqlite3.Connection] = None) -> List[Dict]:
    """conn: if provided (e.g. from get_traffic_log thread), use it; else use global db_connection."""
    connection = conn if conn is not None else db_connection
    cursor = connection.execute(
        """SELECT id, session_id, url, protocol, status, time_sec, content_type, created_at
           FROM traffic_log WHERE session_id = ? ORDER BY id ASC""",
        (session_id,),
    )
    return [
        {
            "id": row[0],
            "session_id": row[1],
            "url": row[2],
            "protocol": row[3],
            "status": row[4],
            "time_sec": row[5],
            "content_type": row[6] or "",
            "created_at": row[7],
        }
        for row in cursor.fetchall()
    ]


# Initialize schema on import
init_db_schema()

"""
Database management for URL policies.
Stores policies in SQLite database similar to image_status_manager.
"""
import sqlite3
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Ensure .storage directory exists
os.makedirs(".storage", exist_ok=True)

db_connection = sqlite3.connect(".storage/policies.db", check_same_thread=False)
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.execute("PRAGMA synchronous=NORMAL;")

POLICIES_TABLE_NAME = "url_policies"


def init_db_schema():
    """Initialize or update database schema for policies."""
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
    
    # Create index for faster lookups
    db_connection.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_domain_path 
        ON {POLICIES_TABLE_NAME}(domain, path)
    """)
    
    db_connection.commit()
    logger.info("Policies database schema initialized successfully")


def validate_policy(domain: str, path: Optional[str] = None, 
                    policy_type: str = "*", state: str = "block") -> Optional[str]:
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
               description: Optional[str] = None, enabled: bool = True) -> Dict:
    """Add a new policy. Returns the created policy dict."""
    error = validate_policy(domain, path, policy_type, state)
    if error:
        raise ValueError(error)
    
    now = int(datetime.now().timestamp())
    path = path.strip() if path else None
    
    try:
        db_connection.execute(f"""
            INSERT INTO {POLICIES_TABLE_NAME} 
            (domain, path, type, state, description, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (domain, path, policy_type, state, description, 1 if enabled else 0, now, now))
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
                 enabled: Optional[bool] = None) -> Dict:
    """Update an existing policy. Returns the updated policy dict."""
    # Get current policy
    cursor = db_connection.execute(f"""
        SELECT * FROM {POLICIES_TABLE_NAME} WHERE id = ?
    """, (policy_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"כלל עם ID {policy_id} לא נמצא")
    
    current = row_to_dict(row)
    
    # Update fields
    new_domain = domain if domain is not None else current["domain"]
    new_path = path if path is not None else current["path"]
    new_type = policy_type if policy_type is not None else current["type"]
    new_state = state if state is not None else current["state"]
    new_description = description if description is not None else current["description"]
    new_enabled = enabled if enabled is not None else current["enabled"]
    
    # Validate
    error = validate_policy(new_domain, new_path, new_type, new_state)
    if error:
        raise ValueError(error)
    
    now = int(datetime.now().timestamp())
    new_path = new_path.strip() if new_path else None
    
    try:
        db_connection.execute(f"""
            UPDATE {POLICIES_TABLE_NAME}
            SET domain = ?, path = ?, type = ?, state = ?, 
                description = ?, enabled = ?, updated_at = ?
            WHERE id = ?
        """, (new_domain, new_path, new_type, new_state, 
              new_description, 1 if new_enabled else 0, now, policy_id))
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
    """Get all enabled policies in the format expected by URLPolicyResolver."""
    policies = get_all_policies(enabled_only=True)
    return [
        {
            "domain": p["domain"],
            "path": p["path"],
            "type": p["type"],
            "state": p["state"],
        }
        for p in policies
    ]


def row_to_dict(row: tuple) -> Dict:
    """Convert database row to dictionary."""
    return {
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


# Initialize schema on import
init_db_schema()

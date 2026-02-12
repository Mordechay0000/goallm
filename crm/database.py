"""
Database schema and management for CRM system.
Supports Users, Profiles, Rules, and Schedules.
"""
import logging
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from data.constants import GOALLM_STORAGE_DIR

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parent.parent


def _get_storage_dir():
    if GOALLM_STORAGE_DIR:
        return Path(GOALLM_STORAGE_DIR)
    return _project_root / ".storage"


def _init_db_connection():
    storage_dir = _get_storage_dir()
    db_path = storage_dir / "crm.db"
    os.makedirs(str(storage_dir), mode=0o755, exist_ok=True)
    try:
        return sqlite3.connect(str(db_path), check_same_thread=False, timeout=10)
    except sqlite3.OperationalError:
        fallback = Path.home() / ".goallm" / "storage"
        if fallback.resolve() == storage_dir.resolve():
            raise
        os.makedirs(str(fallback), mode=0o755, exist_ok=True)
        fallback_db = fallback / "crm.db"
        try:
            conn = sqlite3.connect(str(fallback_db), check_same_thread=False, timeout=10)
            logger.warning(
                "Using fallback DB at %s (project .storage not writable)", fallback_db
            )
            return conn
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"Cannot open database. Tried: {db_path} and {fallback_db}. "
                "Set GOALLM_STORAGE_DIR to a writable path. Error: " + str(e)
            ) from e


db_connection = _init_db_connection()
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.execute("PRAGMA synchronous=NORMAL;")
db_connection.row_factory = sqlite3.Row


def init_db_schema():
    """Initialize or update database schema for CRM."""
    logger.info("Initializing CRM database schema...")
    
    # Check if users table exists
    cursor = db_connection.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='users'
    """)
    table_exists = cursor.fetchone() is not None
    
    if table_exists:
        # Check if migration is needed
        try:
            # Check current schema
            cursor = db_connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            schema_row = cursor.fetchone()
            needs_migration = False
            
            if schema_row:
                schema_sql = schema_row[0].lower()
                # Check if email has UNIQUE or phone doesn't have UNIQUE
                if "email" in schema_sql and "unique" in schema_sql:
                    email_pos = schema_sql.find("email")
                    unique_pos = schema_sql.find("unique")
                    if unique_pos < email_pos or (unique_pos > email_pos and "email" in schema_sql[unique_pos:unique_pos+50]):
                        needs_migration = True
                        logger.info("Old schema detected: email has UNIQUE constraint")
                
                # Check if phone doesn't have UNIQUE
                if "phone" in schema_sql and "unique" not in schema_sql.split("phone")[1][:100]:
                    needs_migration = True
                    logger.info("Old schema detected: phone missing UNIQUE constraint")
            
            # Check if unique index on phone exists
            cursor = db_connection.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_users_phone_unique'
            """)
            phone_index_exists = cursor.fetchone() is not None
            
            if not phone_index_exists:
                # Check if there are duplicate phones
                cursor = db_connection.execute("""
                    SELECT phone, COUNT(*) as count
                    FROM users
                    WHERE phone IS NOT NULL AND phone != ''
                    GROUP BY phone
                    HAVING count > 1
                    LIMIT 1
                """)
                has_duplicates = cursor.fetchone() is not None
                
                if has_duplicates:
                    needs_migration = True
                    logger.info("Duplicate phones detected, migration needed")
                elif not needs_migration:
                    # No duplicates and schema looks OK, just create the index
                    try:
                        db_connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON users(phone)")
                        db_connection.commit()
                        logger.info("Created phone UNIQUE index")
                    except sqlite3.OperationalError as e:
                        if "UNIQUE constraint failed" in str(e):
                            needs_migration = True
                            logger.info("Cannot create index due to duplicates, migration needed")
            
            if needs_migration:
                logger.info("Migrating users table: phone becomes UNIQUE, email loses UNIQUE...")
                
                # First, check for duplicate phones and handle them
                cursor = db_connection.execute("""
                    SELECT phone, COUNT(*) as count, GROUP_CONCAT(id) as ids
                    FROM users
                    WHERE phone IS NOT NULL AND phone != ''
                    GROUP BY phone
                    HAVING count > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    logger.warning(f"Found {len(duplicates)} duplicate phone numbers. Keeping first occurrence, updating others...")
                    for dup in duplicates:
                        phone = dup[0]
                        ids = [int(x) for x in dup[2].split(',')]
                        # Keep the first ID, update others with a suffix
                        keep_id = ids[0]
                        for user_id in ids[1:]:
                            new_phone = f"{phone}_dup_{user_id}"
                            db_connection.execute("UPDATE users SET phone = ? WHERE id = ?", (new_phone, user_id))
                            logger.info(f"Updated duplicate phone for user {user_id}: {phone} -> {new_phone}")
                    db_connection.commit()
                
                # Check for NULL or empty phones
                cursor = db_connection.execute("SELECT COUNT(*) FROM users WHERE phone IS NULL OR phone = ''")
                null_count = cursor.fetchone()[0]
                if null_count > 0:
                    logger.warning(f"Found {null_count} users with NULL/empty phone. Setting placeholder values...")
                    cursor = db_connection.execute("SELECT id FROM users WHERE phone IS NULL OR phone = ''")
                    null_users = cursor.fetchall()
                    for (user_id,) in null_users:
                        placeholder = f"__placeholder_{user_id}__"
                        db_connection.execute("UPDATE users SET phone = ? WHERE id = ?", (placeholder, user_id))
                    db_connection.commit()
                
                # Drop users_new if it exists (from previous failed migration)
                db_connection.execute("DROP TABLE IF EXISTS users_new")
                
                # Now create new table with correct schema
                db_connection.execute("""
                    CREATE TABLE users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT NOT NULL UNIQUE,
                        avatar_url TEXT,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                """)
                
                # Copy data
                db_connection.execute("""
                    INSERT INTO users_new (id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at)
                    SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at
                    FROM users
                """)
                
                # Drop old table and rename new one
                db_connection.execute("DROP TABLE users")
                db_connection.execute("ALTER TABLE users_new RENAME TO users")
                db_connection.commit()
                logger.info("Migration completed successfully")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db_connection.rollback()
            raise
    
    # Users table (phone is UNIQUE, email is NOT UNIQUE)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT NOT NULL UNIQUE,
            avatar_url TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    
    # Ensure phone unique index exists
    try:
        db_connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON users(phone)")
    except:
        pass  # May already exist
    
    # Profiles table (mode: blacklist = default allow / add blocks; whitelist = default block / add allows)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'blacklist',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, name)
        )
    """)
    
    # Rules table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            domain_pattern TEXT NOT NULL,
            path_pattern TEXT,
            action TEXT NOT NULL DEFAULT 'block',
            type TEXT NOT NULL DEFAULT '*',
            include_subdomains INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
    """)
    
    # Schedules table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            days_bitmask INTEGER NOT NULL DEFAULT 0,
            from_time TEXT,
            to_time TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
    """)
    
    # Migrate schedules table if needed (allow NULL for from_time and to_time)
    try:
        cursor = db_connection.execute("PRAGMA table_info(schedules)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        # Check if from_time or to_time have NOT NULL constraint
        if 'from_time' in columns and columns['from_time'][3] == 1:  # 3 is notnull flag
            logger.info("Migrating schedules table: making from_time and to_time nullable...")
            # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
            db_connection.execute("""
                CREATE TABLE schedules_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    days_bitmask INTEGER NOT NULL DEFAULT 0,
                    from_time TEXT,
                    to_time TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                )
            """)
            db_connection.execute("""
                INSERT INTO schedules_new 
                (id, profile_id, days_bitmask, from_time, to_time, created_at, updated_at)
                SELECT id, profile_id, days_bitmask, from_time, to_time, created_at, updated_at
                FROM schedules
            """)
            db_connection.execute("DROP TABLE schedules")
            db_connection.execute("ALTER TABLE schedules_new RENAME TO schedules")
            db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedules_profile_id 
                ON schedules(profile_id)
            """)
            db_connection.commit()
            logger.info("Schedules table migration completed successfully")
    except Exception as e:
        logger.warning(f"Schedule migration check failed (may be OK if already migrated): {e}")
        db_connection.rollback()
    
    # Create indexes
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_profiles_user_id 
        ON profiles(user_id)
    """)
    
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_rules_profile_id 
        ON rules(profile_id)
    """)

    # Add tags column to rules if missing (migration)
    cursor = db_connection.execute("PRAGMA table_info(rules)")
    rule_columns = [row[1] for row in cursor.fetchall()]
    if "tags" not in rule_columns:
        db_connection.execute("ALTER TABLE rules ADD COLUMN tags TEXT")
        logger.info("Added tags column to rules")

    # Tag rules: rule per tag (e.g. tag=ממכר -> state=block)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS tag_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL DEFAULT 'block',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_rules_tag ON tag_rules(tag)
    """)
    # Migration: audit fields for tag_rules (who created/updated – stored for logging/security, not displayed in API)
    tr_cursor = db_connection.execute("PRAGMA table_info(tag_rules)")
    tr_cols = [row[1] for row in tr_cursor.fetchall()]
    if "created_by_user_id" not in tr_cols:
        db_connection.execute("ALTER TABLE tag_rules ADD COLUMN created_by_user_id INTEGER")
        logger.info("Added created_by_user_id to tag_rules")
    if "updated_by_user_id" not in tr_cols:
        db_connection.execute("ALTER TABLE tag_rules ADD COLUMN updated_by_user_id INTEGER")
        logger.info("Added updated_by_user_id to tag_rules")
    
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_profile_id 
        ON schedules(profile_id)
    """)

    # Verification codes (phone / email)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            code TEXT NOT NULL,
            type TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    db_connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_verification_target_type 
        ON verification_codes(target, type)
    """)

    # is_admin on users (migration)
    cursor = db_connection.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if "is_admin" not in user_cols:
        db_connection.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        logger.info("Added is_admin column to users")

    # user_locked_settings: which settings are locked by admin for a user
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS user_locked_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            setting_key TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(user_id, setting_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_locked_settings_user ON user_locked_settings(user_id)")

    # rule_requests: user requests (open site / change rule) for admin to approve
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS rule_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request_type TEXT NOT NULL,
            url TEXT,
            domain_pattern TEXT,
            path_pattern TEXT,
            action TEXT,
            type TEXT,
            include_subdomains INTEGER DEFAULT 0,
            tags TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_rule_requests_user ON rule_requests(user_id)")
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_rule_requests_status ON rule_requests(status)")
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_rule_requests_created ON rule_requests(created_at)")

    # Add approved_rule_id and approved_profile_id if missing (migration)
    cursor = db_connection.execute("PRAGMA table_info(rule_requests)")
    rr_cols = [row[1] for row in cursor.fetchall()]
    if "approved_rule_id" not in rr_cols:
        db_connection.execute("ALTER TABLE rule_requests ADD COLUMN approved_rule_id INTEGER")
        logger.info("Added approved_rule_id to rule_requests")
    if "approved_profile_id" not in rr_cols:
        db_connection.execute("ALTER TABLE rule_requests ADD COLUMN approved_profile_id INTEGER")
        logger.info("Added approved_profile_id to rule_requests")
    if "request_url" not in rr_cols:
        db_connection.execute("ALTER TABLE rule_requests ADD COLUMN request_url TEXT")
        logger.info("Added request_url to rule_requests")
    if "notes" not in rr_cols:
        db_connection.execute("ALTER TABLE rule_requests ADD COLUMN notes TEXT")
        logger.info("Added notes to rule_requests")
    if "resolved_by_user_id" not in rr_cols:
        db_connection.execute("ALTER TABLE rule_requests ADD COLUMN resolved_by_user_id INTEGER")
        logger.info("Added resolved_by_user_id to rule_requests")

    # global_rules: base whitelist managed only by admins (same shape as rules, no profile_id)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS global_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_pattern TEXT NOT NULL,
            path_pattern TEXT,
            action TEXT NOT NULL DEFAULT 'allow',
            include_subdomains INTEGER NOT NULL DEFAULT 0,
            tags TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_global_rules_domain ON global_rules(domain_pattern)")

    # Migration: text_filter_enabled per site (default 1 = yes)
    gr_cursor = db_connection.execute("PRAGMA table_info(global_rules)")
    gr_cols = [row[1] for row in gr_cursor.fetchall()]
    if "text_filter_enabled" not in gr_cols:
        db_connection.execute("ALTER TABLE global_rules ADD COLUMN text_filter_enabled INTEGER NOT NULL DEFAULT 1")
        logger.info("Added text_filter_enabled to global_rules")
        gr_cols = [row[1] for row in db_connection.execute("PRAGMA table_info(global_rules)").fetchall()]
    if "image_filter_enabled" not in gr_cols:
        db_connection.execute("ALTER TABLE global_rules ADD COLUMN image_filter_enabled INTEGER NOT NULL DEFAULT 1")
        logger.info("Added image_filter_enabled to global_rules")
        gr_cols = [row[1] for row in db_connection.execute("PRAGMA table_info(global_rules)").fetchall()]
    if "file_filter_enabled" not in gr_cols:
        db_connection.execute("ALTER TABLE global_rules ADD COLUMN file_filter_enabled INTEGER NOT NULL DEFAULT 1")
        logger.info("Added file_filter_enabled to global_rules")
    # Migration: audit fields (who created/updated – stored for logging/security, not displayed in API)
    gr_cols = [row[1] for row in db_connection.execute("PRAGMA table_info(global_rules)").fetchall()]
    if "created_by_user_id" not in gr_cols:
        db_connection.execute("ALTER TABLE global_rules ADD COLUMN created_by_user_id INTEGER")
        logger.info("Added created_by_user_id to global_rules")
    if "updated_by_user_id" not in gr_cols:
        db_connection.execute("ALTER TABLE global_rules ADD COLUMN updated_by_user_id INTEGER")
        logger.info("Added updated_by_user_id to global_rules")
    # Migration: remove type column from global_rules (no longer used)
    gr_cols = [row[1] for row in db_connection.execute("PRAGMA table_info(global_rules)").fetchall()]
    if "type" in gr_cols:
        try:
            db_connection.execute("ALTER TABLE global_rules DROP COLUMN type")
            db_connection.commit()
            logger.info("Dropped type column from global_rules")
        except Exception as e:
            logger.warning("Could not drop global_rules.type (e.g. SQLite < 3.35): %s", e)

    # IP bindings: which client IP is associated with which user (for filter per-user)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS ip_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ip TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(ip)
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_ip_bindings_user ON ip_bindings(user_id)")
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_ip_bindings_ip ON ip_bindings(ip)")
    gr_cursor = db_connection.execute("PRAGMA table_info(ip_bindings)")
    ib_cols = [row[1] for row in gr_cursor.fetchall()]
    if "last_used_at" not in ib_cols:
        db_connection.execute("ALTER TABLE ip_bindings ADD COLUMN last_used_at INTEGER")
        logger.info("Added last_used_at to ip_bindings")

    # support_tickets: user support requests (subject + content, markdown)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id)")
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_created ON support_tickets(created_at)")

    # support_replies: admin/user replies to tickets (author_id = user who wrote the reply)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS support_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_support_replies_ticket ON support_replies(ticket_id)")

    # attachments on tickets and replies (JSON array of {name, url})
    for table in ("support_tickets", "support_replies"):
        cursor = db_connection.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        if "attachments" not in cols:
            db_connection.execute(f"ALTER TABLE {table} ADD COLUMN attachments TEXT")
            logger.info("Added attachments column to %s", table)

    # support_tickets: optional attached rule request (בקשה לפתיחה) – client sees snapshot + status
    st_cursor = db_connection.execute("PRAGMA table_info(support_tickets)")
    st_cols = [row[1] for row in st_cursor.fetchall()]
    if "attached_rule_request_id" not in st_cols:
        db_connection.execute("ALTER TABLE support_tickets ADD COLUMN attached_rule_request_id INTEGER REFERENCES rule_requests(id)")
        logger.info("Added attached_rule_request_id to support_tickets")
    if "request_snapshot_for_client" not in st_cols:
        db_connection.execute("ALTER TABLE support_tickets ADD COLUMN request_snapshot_for_client TEXT")
        logger.info("Added request_snapshot_for_client to support_tickets")

    # support_replies: optional attached request snapshot (user sends edited copy as reply)
    sr_cursor = db_connection.execute("PRAGMA table_info(support_replies)")
    sr_cols = [row[1] for row in sr_cursor.fetchall()]
    if "attached_request_snapshot" not in sr_cols:
        db_connection.execute("ALTER TABLE support_replies ADD COLUMN attached_request_snapshot TEXT")
        logger.info("Added attached_request_snapshot to support_replies")
    if "is_support_reply" not in sr_cols:
        db_connection.execute("ALTER TABLE support_replies ADD COLUMN is_support_reply INTEGER NOT NULL DEFAULT 0")
        logger.info("Added is_support_reply to support_replies (0=תגובת משתמש, 1=תגובת תמיכה)")

    # support_ticket_views: when user last viewed ticket (for unread replies)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS support_ticket_views (
            ticket_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_read_at INTEGER NOT NULL,
            PRIMARY KEY (ticket_id, user_id),
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_support_ticket_views_user ON support_ticket_views(user_id)")

    # לוג אבטחה: צפיות בהקלטות תעבורה (משתמש + זמן צפייה)
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS traffic_recording_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            traffic_session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            viewed_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_traffic_recording_views_session ON traffic_recording_views(traffic_session_id)")
    db_connection.execute("CREATE INDEX IF NOT EXISTS idx_traffic_recording_views_user ON traffic_recording_views(user_id)")

    db_connection.commit()
    logger.info("CRM database schema initialized successfully")


def get_db():
    """Get database connection (for FastAPI dependency)."""
    return db_connection


def log_traffic_recording_view(traffic_session_id: int, user_id: int) -> None:
    """רישום לוג אבטחה: משתמש צפה בהקלטת תעבורה."""
    import time
    viewed_at = int(time.time())
    db_connection.execute(
        "INSERT INTO traffic_recording_views (traffic_session_id, user_id, viewed_at) VALUES (?, ?, ?)",
        (traffic_session_id, user_id, viewed_at),
    )
    db_connection.commit()


def get_traffic_recording_views(session_id: Optional[int] = None) -> List[Dict]:
    """החזרת רשימת צפיות בהקלטות תעבורה (ללוג אבטחה). אם session_id נתון – רק צפיות להקלטה זו."""
    sql = """
        SELECT v.id, v.traffic_session_id, v.user_id, v.viewed_at,
               u.email, u.first_name, u.last_name
        FROM traffic_recording_views v
        JOIN users u ON u.id = v.user_id
    """
    params: tuple = ()
    if session_id is not None:
        sql += " WHERE v.traffic_session_id = ?"
        params = (session_id,)
    sql += " ORDER BY v.viewed_at DESC"
    cursor = db_connection.execute(sql, params)
    rows = cursor.fetchall()
    return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]


# Initialize schema on import
init_db_schema()

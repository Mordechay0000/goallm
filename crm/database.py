"""
Database schema and management for CRM system.
Supports Users, Profiles, Rules, and Schedules.
"""
import sqlite3
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure .storage directory exists
os.makedirs(".storage", exist_ok=True)

db_path = Path(__file__).resolve().parent.parent / ".storage" / "crm.db"
db_connection = sqlite3.connect(str(db_path), check_same_thread=False)
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
    
    # Profiles table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'whitelist',
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
    
    db_connection.commit()
    logger.info("CRM database schema initialized successfully")


def get_db():
    """Get database connection (for FastAPI dependency)."""
    return db_connection


# Initialize schema on import
init_db_schema()

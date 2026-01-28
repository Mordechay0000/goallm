"""
Migration script to add new columns to users table.
"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / ".storage" / "crm.db"

if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # Add new columns if they don't exist
    if 'first_name' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
        print("Added first_name column")
    
    if 'last_name' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
        print("Added last_name column")
    
    if 'phone' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        print("Added phone column")
    
    if 'avatar_url' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        print("Added avatar_url column")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully!")
else:
    print("Database not found - will be created on first run")

"""
Business logic services for CRM.
"""
from typing import Optional, List, Dict
from datetime import datetime
import logging
import sqlite3

from .database import db_connection
from .security import get_password_hash, verify_password, validate_password_strength

logger = logging.getLogger(__name__)


# User services
def create_user(email: str, password: str, first_name: str, last_name: str,
                phone: str, avatar_url: Optional[str] = None) -> Dict:
    """Create a new user and default profile. Phone required (login is always by phone)."""
    # Validate password strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Validate email format (already done by Pydantic, but double-check)
    if not email or '@' not in email:
        raise ValueError("כתובת אימייל לא תקינה")
    
    normalized = _normalize_phone(phone)
    if len(normalized) < 9:
        raise ValueError("מספר טלפון לא תקין")
    existing_phone = get_user_by_phone(phone)
    if existing_phone:
        raise ValueError("מספר טלפון זה כבר רשום במערכת")
    
    # Hash password using bcrypt
    password_hash = get_password_hash(password)
    now = int(datetime.now().timestamp())
    
    try:
        cursor = db_connection.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, password_hash, first_name, last_name, phone, avatar_url, now, now))
        user_id = cursor.lastrowid
        
        # Create default profile
        db_connection.execute("""
            INSERT INTO profiles (user_id, name, mode, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, "ברירת מחדל", "whitelist", 1, now, now))
        
        db_connection.commit()
        
        return {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "avatar_url": avatar_url,
            "created_at": now,
            "updated_at": now
        }
    except sqlite3.IntegrityError as e:
        db_connection.rollback()
        if "UNIQUE constraint failed: users.phone" in str(e):
            raise ValueError("מספר טלפון זה כבר רשום במערכת")
        raise ValueError(f"שגיאה ביצירת משתמש: {str(e)}")
    except Exception as e:
        db_connection.rollback()
        raise ValueError(f"שגיאה ביצירת משתמש: {str(e)}")


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    cursor = db_connection.execute("""
        SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at
        FROM users WHERE email = ?
    """, (email,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "phone": row["phone"],
        "avatar_url": row["avatar_url"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit()).strip()


def get_user_by_phone(phone: str) -> Optional[Dict]:
    """Get user by phone (normalized digits)."""
    normalized = _normalize_phone(phone)
    if not normalized:
        return None
    cursor = db_connection.execute("""
        SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at
        FROM users
    """)
    for row in cursor.fetchall():
        u = dict(row)
        if _normalize_phone(u.get("phone") or "") == normalized:
            return u
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID."""
    cursor = db_connection.execute("""
        SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at
        FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "phone": row["phone"],
        "avatar_url": row["avatar_url"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def update_user(user_id: int, email: Optional[str] = None, first_name: Optional[str] = None,
                last_name: Optional[str] = None, phone: Optional[str] = None,
                avatar_url: Optional[str] = None) -> Dict:
    """Update user profile. Phone must be unique."""
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("משתמש לא נמצא")
    
    # Check if phone already exists (if changing phone)
    if phone and phone != user["phone"]:
        normalized = _normalize_phone(phone)
        if len(normalized) < 9:
            raise ValueError("מספר טלפון לא תקין")
        existing = get_user_by_phone(phone)
        if existing and existing["id"] != user_id:
            raise ValueError("מספר טלפון זה כבר רשום במערכת")
    
    now = int(datetime.now().timestamp())
    updates = []
    values = []
    
    if email is not None:
        updates.append("email = ?")
        values.append(email)
    if first_name is not None:
        updates.append("first_name = ?")
        values.append(first_name)
    if last_name is not None:
        updates.append("last_name = ?")
        values.append(last_name)
    if phone is not None:
        updates.append("phone = ?")
        values.append(phone)
    if avatar_url is not None:
        updates.append("avatar_url = ?")
        # Convert empty string to None for database
        values.append(avatar_url if avatar_url else None)
    
    if not updates:
        return user
    
    updates.append("updated_at = ?")
    values.append(now)
    values.append(user_id)
    
    try:
        db_connection.execute(f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ?
        """, values)
        db_connection.commit()
    except sqlite3.IntegrityError as e:
        db_connection.rollback()
        if "UNIQUE constraint failed: users.phone" in str(e):
            raise ValueError("מספר טלפון זה כבר רשום במערכת")
        raise ValueError(f"שגיאה בעדכון משתמש: {str(e)}")
    
    return get_user_by_id(user_id)


def change_password(user_id: int, current_password: str, new_password: str) -> bool:
    """Change user password."""
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("משתמש לא נמצא")
    
    # Verify current password
    if not verify_password(current_password, user["password_hash"]):
        raise ValueError("סיסמה נוכחית שגויה")
    
    # Validate new password strength
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Hash new password
    new_password_hash = get_password_hash(new_password)
    now = int(datetime.now().timestamp())
    
    db_connection.execute("""
        UPDATE users
        SET password_hash = ?, updated_at = ?
        WHERE id = ?
    """, (new_password_hash, now, user_id))
    db_connection.commit()
    
    return True


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Authenticate user by email and return user dict if successful."""
    user = get_user_by_email(email)
    if not user:
        return None
    if verify_password(password, user["password_hash"]):
        return {
            "id": user["id"],
            "email": user["email"],
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "phone": user.get("phone"),
            "avatar_url": user.get("avatar_url"),
            "created_at": user["created_at"],
            "updated_at": user.get("updated_at", user["created_at"])
        }
    return None


def authenticate_user_by_phone(phone: str, password: str) -> Optional[Dict]:
    """Authenticate user by phone and password. Login is always via phone."""
    user = get_user_by_phone(phone)
    if not user:
        return None
    if verify_password(password, user["password_hash"]):
        return {
            "id": user["id"],
            "email": user["email"],
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "phone": user.get("phone"),
            "avatar_url": user.get("avatar_url"),
            "created_at": user["created_at"],
            "updated_at": user.get("updated_at", user["created_at"])
        }
    return None


# Profile services
def create_profile(user_id: int, name: str, mode: str = "whitelist") -> Dict:
    """Create a new profile for user."""
    now = int(datetime.now().timestamp())
    
    try:
        cursor = db_connection.execute("""
            INSERT INTO profiles (user_id, name, mode, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, mode, 0, now, now))
        profile_id = cursor.lastrowid
        db_connection.commit()
        
        return get_profile(profile_id)
    except Exception as e:
        db_connection.rollback()
        raise ValueError(f"שגיאה ביצירת פרופיל: {str(e)}")


def get_profile(profile_id: int) -> Optional[Dict]:
    """Get profile by ID."""
    cursor = db_connection.execute("""
        SELECT id, user_id, name, mode, is_default, created_at, updated_at
        FROM profiles WHERE id = ?
    """, (profile_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return dict(row)


def get_user_profiles(user_id: int) -> List[Dict]:
    """Get all profiles for a user."""
    cursor = db_connection.execute("""
        SELECT id, user_id, name, mode, is_default, created_at, updated_at
        FROM profiles WHERE user_id = ?
        ORDER BY is_default DESC, created_at ASC
    """, (user_id,))
    return [dict(row) for row in cursor.fetchall()]


def update_profile(profile_id: int, name: Optional[str] = None, 
                   mode: Optional[str] = None) -> Dict:
    """Update profile."""
    profile = get_profile(profile_id)
    if not profile:
        raise ValueError("פרופיל לא נמצא")
    
    new_name = name if name is not None else profile["name"]
    new_mode = mode if mode is not None else profile["mode"]
    
    if new_mode not in ["whitelist", "blacklist"]:
        raise ValueError("מצב לא חוקי")
    
    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE profiles
        SET name = ?, mode = ?, updated_at = ?
        WHERE id = ?
    """, (new_name, new_mode, now, profile_id))
    db_connection.commit()
    
    return get_profile(profile_id)


def delete_profile(profile_id: int) -> bool:
    """Delete profile (cascade deletes rules and schedules)."""
    cursor = db_connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    db_connection.commit()
    return cursor.rowcount > 0


# Rule services
def parse_url(url: str) -> tuple[str, Optional[str], bool]:
    """
    Parse URL into domain, path, and subdomain flag.
    Returns: (domain, path, include_subdomains)
    """
    # Remove protocol if present
    url = url.strip()
    if url.startswith('http://'):
        url = url[7:]
    elif url.startswith('https://'):
        url = url[8:]
    
    # Check for subdomain wildcard
    include_subdomains = False
    if url.startswith('*.'):
        include_subdomains = True
        url = url[2:]
    elif url.startswith('*'):
        include_subdomains = True
        url = url[1:]
    
    # Split domain and path
    if '/' in url:
        parts = url.split('/', 1)
        domain = parts[0].lower().rstrip('.')
        path = '/' + parts[1] if parts[1] else '/'
    else:
        domain = url.lower().rstrip('.')
        path = None
    
    return domain, path, include_subdomains


def create_rule(profile_id: int, url: str, action: str = "block", 
                rule_type: str = "*", include_subdomains: bool = False) -> Dict:
    """Create a new rule."""
    domain, path, inferred_subdomains = parse_url(url)
    
    # Use inferred subdomains if URL had *., otherwise use provided flag
    if inferred_subdomains:
        include_subdomains = True
    
    # Format domain pattern
    domain_pattern = domain
    if include_subdomains:
        domain_pattern = f"*.{domain}" if not domain.startswith("*.") else domain
    
    now = int(datetime.now().timestamp())
    
    try:
        cursor = db_connection.execute("""
            INSERT INTO rules 
            (profile_id, domain_pattern, path_pattern, action, type, include_subdomains, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (profile_id, domain_pattern, path, action, rule_type, 
              1 if include_subdomains else 0, now, now))
        rule_id = cursor.lastrowid
        db_connection.commit()
        
        return get_rule(rule_id)
    except Exception as e:
        db_connection.rollback()
        raise ValueError(f"שגיאה ביצירת כלל: {str(e)}")


def get_rule(rule_id: int) -> Optional[Dict]:
    """Get rule by ID."""
    cursor = db_connection.execute("""
        SELECT id, profile_id, domain_pattern, path_pattern, action, type, 
               include_subdomains, created_at, updated_at
        FROM rules WHERE id = ?
    """, (rule_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return dict(row)


def get_profile_rules(profile_id: int) -> List[Dict]:
    """Get all rules for a profile."""
    cursor = db_connection.execute("""
        SELECT id, profile_id, domain_pattern, path_pattern, action, type,
               include_subdomains, created_at, updated_at
        FROM rules WHERE profile_id = ?
        ORDER BY created_at DESC
    """, (profile_id,))
    return [dict(row) for row in cursor.fetchall()]


def update_rule(rule_id: int, url: Optional[str] = None, action: Optional[str] = None,
                rule_type: Optional[str] = None, include_subdomains: Optional[bool] = None) -> Dict:
    """Update rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise ValueError("כלל לא נמצא")
    
    if url is not None:
        domain, path, inferred_subdomains = parse_url(url)
        domain_pattern = domain
        if inferred_subdomains or (include_subdomains is True):
            domain_pattern = f"*.{domain}" if not domain.startswith("*.") else domain
            include_subdomains = True
        else:
            include_subdomains = include_subdomains if include_subdomains is not None else rule["include_subdomains"]
    else:
        domain_pattern = rule["domain_pattern"]
        path = rule["path_pattern"]
        include_subdomains = include_subdomains if include_subdomains is not None else rule["include_subdomains"]
    
    new_action = action if action is not None else rule["action"]
    new_type = rule_type if rule_type is not None else rule["type"]
    
    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE rules
        SET domain_pattern = ?, path_pattern = ?, action = ?, type = ?, 
            include_subdomains = ?, updated_at = ?
        WHERE id = ?
    """, (domain_pattern, path, new_action, new_type, 
          1 if include_subdomains else 0, now, rule_id))
    db_connection.commit()
    
    return get_rule(rule_id)


def delete_rule(rule_id: int) -> bool:
    """Delete rule."""
    cursor = db_connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    db_connection.commit()
    return cursor.rowcount > 0


# Schedule services
def create_schedule(profile_id: int, days: List[int], from_time: Optional[str] = None, to_time: Optional[str] = None) -> Dict:
    """Create a new schedule."""
    bitmask = 0
    for day in days:
        if 0 <= day <= 6:
            bitmask |= (1 << day)
    
    now = int(datetime.now().timestamp())
    
    try:
        cursor = db_connection.execute("""
            INSERT INTO schedules 
            (profile_id, days_bitmask, from_time, to_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (profile_id, bitmask, from_time, to_time, now, now))
        schedule_id = cursor.lastrowid
        db_connection.commit()
        
        return get_schedule(schedule_id)
    except Exception as e:
        db_connection.rollback()
        raise ValueError(f"שגיאה ביצירת תזמון: {str(e)}")


def get_schedule(schedule_id: int) -> Optional[Dict]:
    """Get schedule by ID."""
    cursor = db_connection.execute("""
        SELECT id, profile_id, days_bitmask, from_time, to_time, created_at, updated_at
        FROM schedules WHERE id = ?
    """, (schedule_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return dict(row)


def get_profile_schedules(profile_id: int) -> List[Dict]:
    """Get all schedules for a profile."""
    cursor = db_connection.execute("""
        SELECT id, profile_id, days_bitmask, from_time, to_time, created_at, updated_at
        FROM schedules WHERE profile_id = ?
        ORDER BY from_time ASC
    """, (profile_id,))
    return [dict(row) for row in cursor.fetchall()]


def update_schedule(schedule_id: int, days: Optional[List[int]] = None,
                    from_time: Optional[str] = None, to_time: Optional[str] = None) -> Dict:
    """Update schedule."""
    schedule = get_schedule(schedule_id)
    if not schedule:
        raise ValueError("תזמון לא נמצא")
    
    if days is not None:
        bitmask = 0
        for day in days:
            if 0 <= day <= 6:
                bitmask |= (1 << day)
    else:
        bitmask = schedule["days_bitmask"]
    
    # Handle None values explicitly - if from_time/to_time is explicitly None, set to NULL
    # If not provided (None in update), keep existing value
    # We use a sentinel value to distinguish between "not provided" and "set to NULL"
    # For now, we'll use the fact that if from_time/to_time is provided as None in the update,
    # it means "set to NULL", otherwise keep existing
    new_from_time = from_time if from_time is not None else schedule.get("from_time")
    new_to_time = to_time if to_time is not None else schedule.get("to_time")
    
    # If explicitly set to empty string, convert to None
    if new_from_time == "":
        new_from_time = None
    if new_to_time == "":
        new_to_time = None
    
    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE schedules
        SET days_bitmask = ?, from_time = ?, to_time = ?, updated_at = ?
        WHERE id = ?
    """, (bitmask, new_from_time, new_to_time, now, schedule_id))
    db_connection.commit()
    
    return get_schedule(schedule_id)


def delete_schedule(schedule_id: int) -> bool:
    """Delete schedule."""
    cursor = db_connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    db_connection.commit()
    return cursor.rowcount > 0

"""
Business logic services for CRM.
"""
from typing import Optional, List, Dict
from datetime import datetime
import logging
import re
import sqlite3
from urllib.parse import unquote, urlparse

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
    
    _validate_phone_format(phone)
    normalized = _normalize_phone(phone)
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


def _validate_phone_format(phone: str) -> None:
    """Validate phone: min 10 digits, must start with 05 (Israeli) or + (international)."""
    raw = (phone or "").strip()
    digits = _normalize_phone(raw)
    if len(digits) < 10:
        raise ValueError("מספר טלפון חייב להכיל לפחות 10 ספרות")
    # Israeli: 05 + 8 digits = 10 total
    if digits.startswith("05") and len(digits) == 10:
        return
    # International: must start with +
    if raw.startswith("+") and len(digits) >= 10:
        return
    raise ValueError("מספר טלפון חייב להתחיל ב־05 (ישראל) או ב־+ (קידומת בינלאומית)")


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
        SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, created_at, updated_at,
               COALESCE(is_admin, 0) AS is_admin
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
        "is_admin": bool(row["is_admin"]),
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
        _validate_phone_format(phone)
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


def list_all_profiles_for_admin() -> List[Dict]:
    """Get all profiles with user phone (admin only)."""
    cursor = db_connection.execute("""
        SELECT p.id, p.user_id, p.name, p.mode, p.is_default, p.created_at, p.updated_at, u.phone AS user_phone
        FROM profiles p
        JOIN users u ON u.id = p.user_id
        ORDER BY u.phone ASC, p.is_default DESC, p.created_at ASC
    """)
    return [dict(row) for row in cursor.fetchall()]


def update_profile(profile_id: int, name: Optional[str] = None, 
                   mode: Optional[str] = None) -> Dict:
    """Update profile. Default profile (is_default=1) name cannot be changed."""
    profile = get_profile(profile_id)
    if not profile:
        raise ValueError("פרופיל לא נמצא")
    
    new_name = name if name is not None else profile["name"]
    new_mode = mode if mode is not None else profile["mode"]
    if profile.get("is_default") and name is not None and name.strip() != profile.get("name", "").strip():
        raise ValueError("לא ניתן לשנות את שם פרופיל ברירת המחדל")
    
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
def _normalize_path_component(path: str) -> str:
    """Normalize path: unquote, collapse //, resolve . and .., strip trailing slash."""
    if not path or path == "/":
        return "/"
    path = unquote(path)
    path = re.sub(r"/+", "/", path.strip("/"))
    parts = path.split("/")
    out = []
    for p in parts:
        if p == "." or p == "":
            continue
        if p == "..":
            if out:
                out.pop()
            continue
        out.append(p)
    result = "/" + "/".join(out) if out else "/"
    return result.rstrip("/") if result != "/" else "/"


def _normalize_url(url: str) -> str:
    """Full URL normalization: protocol, *, lowercase, dots, slashes, path."""
    url = (url or "").strip()
    if url.startswith("https://"):
        url = url[8:]
    elif url.startswith("http://"):
        url = url[7:]
    url = url.lower()
    if "/" in url:
        idx = url.index("/")
        domain = url[:idx].rstrip(".")
        path = url[idx:]
        while ".." in domain:
            domain = domain.replace("..", ".")
        domain = ".".join(p for p in domain.split(".") if p)
        path = _normalize_path_component(path)
        url = domain + path
    else:
        domain = url.rstrip(".")
        while ".." in domain:
            domain = domain.replace("..", ".")
        domain = ".".join(p for p in domain.split(".") if p)
        url = domain
    while len(url) > 1 and url.endswith("/"):
        url = url[:-1]
    return url


def parse_url(url: str) -> tuple[str, Optional[str], bool]:
    """
    Parse URL into domain, path, and subdomain flag.
    Returns: (domain, path, include_subdomains)
    """
    url = _normalize_url(url)
    include_subdomains = False
    if url.startswith("*."):
        include_subdomains = True
        url = url[2:]
    elif url.startswith("*"):
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


def _tags_to_str(tags: Optional[List[str]]) -> Optional[str]:
    """Convert list of tags to comma-separated string for DB."""
    if not tags:
        return None
    return ",".join((t or "").strip() for t in tags if t and str(t).strip())


def _parse_tags(tags_val: Optional[str]) -> List[str]:
    """Parse tags from DB (comma-separated) to list."""
    if not tags_val or not str(tags_val).strip():
        return []
    return [t.strip() for t in str(tags_val).split(",") if t.strip()]


def _canonical_path(path: Optional[str]) -> Optional[str]:
    """Normalize path for duplicate comparison: None, '', '/' all become None."""
    if not path or not path.strip():
        return None
    p = path.strip().rstrip("/")
    return None if not p or p == "/" else p


def _path_for_match(path: Optional[str]) -> str:
    """Normalize path for DB match: root (None/'/'/'') -> '__ROOT__', else path."""
    p = _canonical_path(path)
    return "__ROOT__" if p is None else (p if p.startswith("/") else "/" + p)


def _rule_exists_for_profile(profile_id: int, domain_pattern: str, path: Optional[str], include_subdomains: bool) -> Optional[int]:
    """Check if rule with same (domain, path, subdomains) exists. Returns rule_id or None."""
    pm = _path_for_match(path)
    if pm == "__ROOT__":
        cursor = db_connection.execute("""
            SELECT id FROM rules
            WHERE profile_id = ? AND domain_pattern = ? AND include_subdomains = ?
            AND (path_pattern IS NULL OR path_pattern = '' OR path_pattern = '/')
        """, (profile_id, domain_pattern, 1 if include_subdomains else 0))
    else:
        cursor = db_connection.execute("""
            SELECT id FROM rules
            WHERE profile_id = ? AND domain_pattern = ? AND include_subdomains = ?
            AND path_pattern = ?
        """, (profile_id, domain_pattern, 1 if include_subdomains else 0, pm))
    row = cursor.fetchone()
    return row[0] if row else None


def _global_rule_exists(domain_pattern: str, path: Optional[str], include_subdomains: bool) -> Optional[int]:
    """Check if global rule with same (domain, path, subdomains) exists. Returns rule_id or None."""
    pm = _path_for_match(path)
    if pm == "__ROOT__":
        cursor = db_connection.execute("""
            SELECT id FROM global_rules
            WHERE domain_pattern = ? AND include_subdomains = ?
            AND (path_pattern IS NULL OR path_pattern = '' OR path_pattern = '/')
        """, (domain_pattern, 1 if include_subdomains else 0))
    else:
        cursor = db_connection.execute("""
            SELECT id FROM global_rules
            WHERE domain_pattern = ? AND include_subdomains = ?
            AND path_pattern = ?
        """, (domain_pattern, 1 if include_subdomains else 0, pm))
    row = cursor.fetchone()
    return row[0] if row else None


def create_rule(profile_id: int, url: str, action: str = "block",
               rule_type: str = "*", include_subdomains: bool = False,
               tags: Optional[List[str]] = None) -> Dict:
    """Create a new rule."""
    url = _normalize_url(url)
    domain, path, inferred_subdomains = parse_url(url)

    if inferred_subdomains:
        include_subdomains = True

    domain_pattern = domain
    if include_subdomains:
        domain_pattern = f"*.{domain}" if not domain.startswith("*.") else domain

    existing = _rule_exists_for_profile(profile_id, domain_pattern, path, include_subdomains)
    if existing:
        raise ValueError("כלל זהה כבר קיים (כפילות)")

    now = int(datetime.now().timestamp())
    tags_str = _tags_to_str(tags)
    path_val = path if path else "/"

    try:
        cursor = db_connection.execute("""
            INSERT INTO rules 
            (profile_id, domain_pattern, path_pattern, action, type, include_subdomains, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (profile_id, domain_pattern, path_val, action, rule_type,
              1 if include_subdomains else 0, tags_str, now, now))
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
               include_subdomains, tags, created_at, updated_at
        FROM rules WHERE id = ?
    """, (rule_id,))
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = _parse_tags(d.get("tags"))
    return d


def get_profile_rules(profile_id: int) -> List[Dict]:
    """Get all rules for a profile."""
    cursor = db_connection.execute("""
        SELECT id, profile_id, domain_pattern, path_pattern, action, type,
               include_subdomains, tags, created_at, updated_at
        FROM rules WHERE profile_id = ?
        ORDER BY created_at DESC
    """, (profile_id,))
    rows = cursor.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["tags"] = _parse_tags(d.get("tags"))
        out.append(d)
    return out


def update_rule(rule_id: int, url: Optional[str] = None, action: Optional[str] = None,
                rule_type: Optional[str] = None, include_subdomains: Optional[bool] = None,
                tags: Optional[List[str]] = None) -> Dict:
    """Update rule. Raises if change would create duplicate."""
    rule = get_rule(rule_id)
    if not rule:
        raise ValueError("כלל לא נמצא")
    profile_id = rule["profile_id"]

    if url is not None:
        url = _normalize_url(url)
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

    existing = _rule_exists_for_profile(profile_id, domain_pattern, path, include_subdomains)
    if existing and existing != rule_id:
        raise ValueError("כלל זהה כבר קיים (כפילות)")

    new_action = action if action is not None else rule["action"]
    new_type = rule_type if rule_type is not None else rule["type"]
    new_tags_str = _tags_to_str(tags) if tags is not None else _tags_to_str(rule.get("tags"))
    path_val = path if path else "/"

    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE rules
        SET domain_pattern = ?, path_pattern = ?, action = ?, type = ?,
            include_subdomains = ?, tags = ?, updated_at = ?
        WHERE id = ?
    """, (domain_pattern, path_val, new_action, new_type,
          1 if include_subdomains else 0, new_tags_str, now, rule_id))
    db_connection.commit()

    return get_rule(rule_id)


def delete_rule(rule_id: int) -> bool:
    """Delete rule."""
    cursor = db_connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    db_connection.commit()
    return cursor.rowcount > 0


# Global rules (רשימה גלובלית – רק אדמין, רשימה לבנה בסיסית)
def get_global_rules() -> List[Dict]:
    """Get all global rules (base whitelist)."""
    cursor = db_connection.execute("""
        SELECT id, domain_pattern, path_pattern, action,
               include_subdomains, tags, created_at, updated_at,
               COALESCE(text_filter_enabled, 1) AS text_filter_enabled,
               COALESCE(image_filter_enabled, 1) AS image_filter_enabled,
               COALESCE(file_filter_enabled, 1) AS file_filter_enabled
        FROM global_rules
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["tags"] = _parse_tags(d.get("tags"))
        d["text_filter_enabled"] = bool(d.get("text_filter_enabled", 1))
        d["image_filter_enabled"] = bool(d.get("image_filter_enabled", 1))
        d["file_filter_enabled"] = bool(d.get("file_filter_enabled", 1))
        out.append(d)
    return out


def _parse_url_for_resolve(url: str) -> tuple[str, str]:
    """Parse URL into (domain, path) for rule matching. Normalized like policy resolver."""
    u = (url or "").strip()
    if not u:
        return "", "/"
    if "://" not in u:
        u = "https://" + u
    parsed = urlparse(u)
    domain = (parsed.hostname or "").lower().rstrip(".")
    path = (parsed.path or "").strip() or "/"
    path = "/" + path.lstrip("/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return domain, path


def _domain_matches_rule(rule_domain: str, domain: str) -> bool:
    """True if domain matches the rule's domain_pattern (*.x or exact)."""
    if not rule_domain or not domain:
        return False
    if rule_domain.startswith("*."):
        base = rule_domain[2:]
        return domain == base or domain.endswith("." + base)
    return domain == rule_domain


def _path_matches_rule(rule_path: Optional[str], path: str) -> bool:
    """True if path matches the rule's path_pattern (prefix or /)."""
    if not rule_path or rule_path == "/" or (rule_path or "").strip() == "":
        return True
    rp = (rule_path or "").rstrip("/")
    if not path:
        path = "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path.startswith(rp) or (rp == "/" and path.startswith("/"))


def resolve_global_rule_for_url(url: str) -> Optional[Dict]:
    """Return the global rule that applies to this URL (best match), or None. Type treated as *."""
    domain, path = _parse_url_for_resolve(url)
    if not domain:
        return None
    rules = get_global_rules()
    best = None
    best_score = -1
    for r in rules:
        if not _domain_matches_rule(r.get("domain_pattern") or "", domain):
            continue
        rpath = r.get("path_pattern") or "/"
        if not _path_matches_rule(rpath, path):
            continue
        # Prefer more specific: longer path, then exact domain (not *. )
        p_score = len((r.get("path_pattern") or "").rstrip("/"))
        d_score = 100 if (r.get("domain_pattern") or "").startswith("*.") else 200
        score = d_score + p_score
        if score > best_score:
            best_score = score
            best = r
    return best


def get_global_rule(rule_id: int) -> Optional[Dict]:
    """Get a single global rule by ID."""
    cursor = db_connection.execute("""
        SELECT id, domain_pattern, path_pattern, action,
               include_subdomains, tags, created_at, updated_at,
               COALESCE(text_filter_enabled, 1) AS text_filter_enabled,
               COALESCE(image_filter_enabled, 1) AS image_filter_enabled,
               COALESCE(file_filter_enabled, 1) AS file_filter_enabled
        FROM global_rules WHERE id = ?
    """, (rule_id,))
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = _parse_tags(d.get("tags"))
    d["text_filter_enabled"] = bool(d.get("text_filter_enabled", 1))
    d["image_filter_enabled"] = bool(d.get("image_filter_enabled", 1))
    d["file_filter_enabled"] = bool(d.get("file_filter_enabled", 1))
    return d


def create_global_rule(
    url: str,
    action: str = "allow",
    include_subdomains: bool = False,
    tags: Optional[List[str]] = None,
    text_filter_enabled: bool = True,
    image_filter_enabled: bool = True,
    file_filter_enabled: bool = True,
    created_by_user_id: Optional[int] = None,
) -> Dict:
    """Create a global rule (admin only). Raises if exact duplicate exists."""
    url = _normalize_url(url)
    domain, path, inferred_subdomains = parse_url(url)
    if inferred_subdomains:
        include_subdomains = True
    domain_pattern = domain
    if include_subdomains:
        domain_pattern = f"*.{domain}" if not domain.startswith("*.") else domain
    existing = _global_rule_exists(domain_pattern, path, include_subdomains)
    if existing:
        raise ValueError("כלל גלובלי זהה כבר קיים (כפילות)")
    now = int(datetime.now().timestamp())
    tags_str = _tags_to_str(tags)
    path_val = path if path else "/"
    try:
        cursor = db_connection.execute("""
            INSERT INTO global_rules
            (domain_pattern, path_pattern, action, include_subdomains, tags, text_filter_enabled, image_filter_enabled, file_filter_enabled, created_at, updated_at, created_by_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (domain_pattern, path_val, action, 1 if include_subdomains else 0, tags_str, 1 if text_filter_enabled else 0, 1 if image_filter_enabled else 0, 1 if file_filter_enabled else 0, now, now, created_by_user_id, created_by_user_id))
        rule_id = cursor.lastrowid
        db_connection.commit()
        return get_global_rule(rule_id)
    except Exception as e:
        db_connection.rollback()
        raise ValueError(f"שגיאה ביצירת כלל גלובלי: {str(e)}")


def update_global_rule(
    rule_id: int,
    url: Optional[str] = None,
    action: Optional[str] = None,
    include_subdomains: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    text_filter_enabled: Optional[bool] = None,
    image_filter_enabled: Optional[bool] = None,
    file_filter_enabled: Optional[bool] = None,
    updated_by_user_id: Optional[int] = None,
) -> Dict:
    """Update a global rule. Raises if change would create duplicate."""
    rule = get_global_rule(rule_id)
    if not rule:
        raise ValueError("כלל גלובלי לא נמצא")
    if url is not None:
        url = _normalize_url(url)
        domain, path, inferred_subdomains = parse_url(url)
        domain_pattern = domain
        if inferred_subdomains or (include_subdomains is True):
            domain_pattern = f"*.{domain}" if not domain.startswith("*.") else domain
            include_subdomains = True
        else:
            include_subdomains = include_subdomains if include_subdomains is not None else rule["include_subdomains"]
        path = (path if path is not None else "/")
    else:
        domain_pattern = rule["domain_pattern"]
        path = rule["path_pattern"]
        include_subdomains = include_subdomains if include_subdomains is not None else rule["include_subdomains"]

    existing = _global_rule_exists(domain_pattern, path, include_subdomains)
    if existing and existing != rule_id:
        raise ValueError("כלל גלובלי זהה כבר קיים (כפילות)")
    new_action = action if action is not None else rule["action"]
    new_tags_str = _tags_to_str(tags) if tags is not None else _tags_to_str(rule.get("tags"))
    new_text_filter = text_filter_enabled if text_filter_enabled is not None else rule.get("text_filter_enabled", True)
    new_image_filter = image_filter_enabled if image_filter_enabled is not None else rule.get("image_filter_enabled", True)
    new_file_filter = file_filter_enabled if file_filter_enabled is not None else rule.get("file_filter_enabled", True)
    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE global_rules
        SET domain_pattern = ?, path_pattern = ?, action = ?,
            include_subdomains = ?, tags = ?, text_filter_enabled = ?, image_filter_enabled = ?, file_filter_enabled = ?, updated_at = ?, updated_by_user_id = ?
        WHERE id = ?
    """, (domain_pattern, path, new_action, 1 if include_subdomains else 0, new_tags_str, 1 if new_text_filter else 0, 1 if new_image_filter else 0, 1 if new_file_filter else 0, now, updated_by_user_id, rule_id))
    db_connection.commit()
    return get_global_rule(rule_id)


def ensure_global_block_rule_for_url(
    url: str,
    updated_by_user_id: Optional[int] = None,
) -> Dict:
    """
    Ensure the exact URL (domain + path, no subdomains) is blocked.
    If a global rule already exists for this exact (domain, path, include_subdomains=False),
    update it to block. Otherwise create a new rule with action=block, include_subdomains=False.
    """
    url = _normalize_url(url)
    if not url.startswith("http"):
        url = "https://" + url
    domain, path, _ = parse_url(url)
    if not domain:
        raise ValueError("לא ניתן לפרש את הכתובת")
    path = path or "/"
    # Exact match only (no *. prefix)
    rule_id = _global_rule_exists(domain, path, include_subdomains=False)
    if rule_id:
        return update_global_rule(
            rule_id,
            action="block",
            updated_by_user_id=updated_by_user_id,
        )
    return create_global_rule(
        url=url,
        action="block",
        include_subdomains=False,
        created_by_user_id=updated_by_user_id,
    )


def find_and_update_global_rule_to_block(
    domain_pattern: str,
    path_pattern: Optional[str],
    updated_by_user_id: Optional[int] = None,
) -> Dict:
    """
    Find a global rule by domain_pattern and path_pattern (exact match), update to block.
    Tries with include_subdomains True and False. Raises ValueError if not found.
    """
    domain_pattern = (domain_pattern or "").strip()
    path_pattern = (path_pattern or "/").strip() or "/"
    for inc in (True, False):
        rule_id = _global_rule_exists(domain_pattern, path_pattern, inc)
        if rule_id:
            return update_global_rule(
                rule_id,
                action="block",
                updated_by_user_id=updated_by_user_id,
            )
    raise ValueError(
        "הכלל לא נמצא ברשימה הגלובלית – אי אפשר לעדכן. השתמש ב׳חסום את האתר׳ ליצירת כלל חדש."
    )


def delete_global_rule(rule_id: int) -> bool:
    """Delete a global rule."""
    cursor = db_connection.execute("DELETE FROM global_rules WHERE id = ?", (rule_id,))
    db_connection.commit()
    return cursor.rowcount > 0


# IP bindings (שיוך IP לחשבון – סינון לפי משתמש)
def get_all_ip_bindings() -> List[Dict]:
    """Get all ip→user bindings (for syncing to core)."""
    cursor = db_connection.execute("""
        SELECT id, user_id, ip, created_at, last_used_at FROM ip_bindings ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    return [_binding_row_to_dict(row) for row in rows]


def _binding_row_to_dict(row) -> Dict:
    d = dict(row)
    if "last_used_at" in d and d["last_used_at"] is not None:
        d["last_used_at"] = int(d["last_used_at"])
    return d


def get_user_id_for_ip(ip: str) -> Optional[int]:
    """Return user_id bound to this IP, or None."""
    ip = (ip or "").strip()
    if not ip:
        return None
    row = db_connection.execute("SELECT user_id FROM ip_bindings WHERE ip = ?", (ip,)).fetchone()
    return int(row["user_id"]) if row else None


def list_bindings_for_user(user_id: int) -> List[Dict]:
    """List all IP bindings for a user (includes last_used_at)."""
    cursor = db_connection.execute("""
        SELECT id, user_id, ip, created_at, last_used_at FROM ip_bindings WHERE user_id = ? ORDER BY created_at DESC
    """, (user_id,))
    return [_binding_row_to_dict(row) for row in cursor.fetchall()]


def touch_ip_binding(ip: str) -> bool:
    """Update last_used_at for the binding with this IP. Returns True if updated."""
    ip = (ip or "").strip()
    if not ip:
        return False
    now = int(datetime.now().timestamp())
    cursor = db_connection.execute(
        "UPDATE ip_bindings SET last_used_at = ? WHERE ip = ?",
        (now, ip),
    )
    db_connection.commit()
    return cursor.rowcount > 0


def add_ip_binding(user_id: int, ip: str) -> Dict:
    """Bind an IP to a user. Replaces any existing binding for this IP. Returns the binding dict."""
    ip = (ip or "").strip()
    if not ip:
        raise ValueError("נא להזין כתובת IP.")
    now = int(datetime.now().timestamp())
    try:
        cursor = db_connection.execute("SELECT id FROM ip_bindings WHERE ip = ?", (ip,))
        existing = cursor.fetchone()
        if existing:
            db_connection.execute(
                "UPDATE ip_bindings SET user_id = ?, created_at = ? WHERE ip = ?",
                (user_id, now, ip),
            )
        else:
            db_connection.execute(
                "INSERT INTO ip_bindings (user_id, ip, created_at) VALUES (?, ?, ?)",
                (user_id, ip, now),
            )
        db_connection.commit()
        row = db_connection.execute("SELECT id, user_id, ip, created_at, last_used_at FROM ip_bindings WHERE ip = ?", (ip,)).fetchone()
        return _binding_row_to_dict(row) if row else {}
    except sqlite3.IntegrityError:
        db_connection.rollback()
        raise ValueError("שיוך IP נכשל")


def remove_ip_binding(binding_id: int, user_id: int) -> bool:
    """Remove a binding. Only the owning user can remove. Returns True if deleted."""
    row = db_connection.execute("SELECT id, user_id FROM ip_bindings WHERE id = ?", (binding_id,)).fetchone()
    if not row or int(row["user_id"]) != user_id:
        return False
    cursor = db_connection.execute("DELETE FROM ip_bindings WHERE id = ? AND user_id = ?", (binding_id, user_id))
    db_connection.commit()
    return cursor.rowcount > 0


def sync_ip_bindings_to_core() -> None:
    """Push all CRM ip_bindings to core so the proxy can resolve IP→user_id."""
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core.policy.policy_database import set_ip_bindings
        bindings = get_all_ip_bindings()
        set_ip_bindings([(b["ip"], b["user_id"]) for b in bindings])
    except Exception as e:
        logger.warning("sync_ip_bindings_to_core failed: %s", e)


# Tag rules (כללי תגיות)
def get_tag_rules(enabled_only: bool = False) -> List[Dict]:
    """Get all tag rules."""
    query = "SELECT id, tag, state, enabled, created_at, updated_at FROM tag_rules"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY tag"
    cursor = db_connection.execute(query)
    return [dict(row) for row in cursor.fetchall()]


def add_tag_rule(tag: str, state: str = "block", enabled: bool = True, created_by_user_id: Optional[int] = None) -> Dict:
    """Add a tag rule. created_by_user_id stored for audit only (not displayed in API)."""
    tag = (tag or "").strip()
    if not tag:
        raise ValueError("נא להזין תגית.")
    if state not in ("allow", "block"):
        raise ValueError("סטטוס לא חוקי. אפשרויות: allow, block")
    now = int(datetime.now().timestamp())
    try:
        cursor = db_connection.execute("""
            INSERT INTO tag_rules (tag, state, enabled, created_at, updated_at, created_by_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tag, state, 1 if enabled else 0, now, now, created_by_user_id, created_by_user_id))
        db_connection.commit()
        rid = cursor.lastrowid
        row = db_connection.execute("SELECT id, tag, state, enabled, created_at, updated_at FROM tag_rules WHERE id = ?", (rid,)).fetchone()
        return dict(row) if row else {"id": rid, "tag": tag, "state": state, "enabled": enabled, "created_at": now, "updated_at": now}
    except sqlite3.IntegrityError:
        raise ValueError(f"כלל לתגית '{tag}' כבר קיים")


def update_tag_rule(rule_id: int, tag: Optional[str] = None, state: Optional[str] = None, enabled: Optional[bool] = None, updated_by_user_id: Optional[int] = None) -> Dict:
    """Update a tag rule. updated_by_user_id stored for audit only (not displayed in API)."""
    cursor = db_connection.execute("SELECT * FROM tag_rules WHERE id = ?", (rule_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError("כלל תגית לא נמצא")
    cur = dict(row)
    new_tag = (tag or cur["tag"]).strip() if tag is not None else cur["tag"]
    new_state = state if state is not None else cur["state"]
    new_enabled = enabled if enabled is not None else cur["enabled"]
    if new_state not in ("allow", "block"):
        raise ValueError("סטטוס לא חוקי")
    now = int(datetime.now().timestamp())
    db_connection.execute("""
        UPDATE tag_rules SET tag = ?, state = ?, enabled = ?, updated_at = ?, updated_by_user_id = ? WHERE id = ?
    """, (new_tag, new_state, 1 if new_enabled else 0, now, updated_by_user_id, rule_id))
    db_connection.commit()
    row = db_connection.execute("SELECT id, tag, state, enabled, created_at, updated_at FROM tag_rules WHERE id = ?", (rule_id,)).fetchone()
    return dict(row)


def delete_tag_rule(rule_id: int) -> bool:
    """Delete a tag rule."""
    cursor = db_connection.execute("DELETE FROM tag_rules WHERE id = ?", (rule_id,))
    db_connection.commit()
    return cursor.rowcount > 0


def get_user_ids_with_profiles() -> List[int]:
    """Return all user IDs that have at least one profile (for periodic schedule sync)."""
    cursor = db_connection.execute("SELECT DISTINCT user_id FROM profiles ORDER BY user_id ASC")
    return [row["user_id"] for row in cursor.fetchall()]


def sync_crm_rules_to_core(user_id: Optional[int] = None, set_default: bool = True) -> None:
    """
    Sync CRM global rules (base whitelist) + active user profile rules and tag_rules to core policy_database.
    Global rules go to core with source='global'; user's active profile rules with source='user'.
    When user_id is None, sync first user's active profile for user layer.
    When set_default is False, do not update core default_user_id (for periodic schedule sync of all users).
    """
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from .resolver_integration import get_system_active_profile_and_rules
        from core.policy.policy_database import (
            get_all_policies,
            add_policy as core_add_policy,
            update_policy as core_update_policy,
            delete_policy as core_delete_policy,
            delete_user_policies as core_delete_user_policies,
            get_tag_rules as core_get_tag_rules,
            add_tag_rule as core_add_tag_rule,
            update_tag_rule as core_update_tag_rule,
            delete_tag_rule as core_delete_tag_rule,
            set_profile_mode as core_set_profile_mode,
            set_default_user_id as core_set_default_user_id,
        )
        # Which user to sync for user layer (None → first user for backward compat)
        sync_user_id = user_id
        if sync_user_id is None:
            row = db_connection.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
            if row:
                sync_user_id = row["id"]

        # Global rules (base whitelist) – from CRM global_rules
        crm_global = get_global_rules()
        crm_global_keys = {(r["domain_pattern"], r.get("path_pattern") or None, r.get("type") or "*") for r in crm_global}
        # User's active profile rules
        mode, crm_rules, crm_tag_rules = get_system_active_profile_and_rules(user_id=user_id)
        if sync_user_id is not None:
            core_set_profile_mode(mode, sync_user_id)
            if set_default:
                core_set_default_user_id(sync_user_id)  # so unbound flows use this user when binding is disabled
        else:
            core_set_profile_mode(mode)
        crm_user_keys = {(r["domain"], r.get("path") or None, r.get("type") or "*") for r in crm_rules}

        core_global = get_all_policies(enabled_only=False, source_filter="global")
        core_user = get_all_policies(enabled_only=False, source_filter="user", user_id=sync_user_id) if sync_user_id is not None else []
        for p in core_global:
            key = (p["domain"], p.get("path") or None, p.get("type") or "*")
            if key not in crm_global_keys:
                core_delete_policy(p["id"])
        for p in core_user:
            key = (p["domain"], p.get("path") or None, p.get("type") or "*")
            if key not in crm_user_keys:
                core_delete_policy(p["id"])

        core_global = get_all_policies(enabled_only=False, source_filter="global")
        core_user = get_all_policies(enabled_only=False, source_filter="user", user_id=sync_user_id) if sync_user_id is not None else []
        for r in crm_global:
            domain = r["domain_pattern"]
            path = r.get("path_pattern")
            typ = r.get("type") or "*"
            state = r.get("action") or "allow"
            tags = r.get("tags") or []
            text_filter_enabled = r.get("text_filter_enabled", True)
            image_filter_enabled = r.get("image_filter_enabled", True)
            existing = next((p for p in core_global if p["domain"] == domain and (p.get("path") or None) == (path or None) and (p.get("type") or "*") == typ), None)
            if existing:
                core_update_policy(existing["id"], state=state, tags=tags, source="global", text_filter_enabled=text_filter_enabled, image_filter_enabled=image_filter_enabled)
            else:
                core_add_policy(domain, path, policy_type=typ, state=state, tags=tags, source="global", text_filter_enabled=text_filter_enabled, image_filter_enabled=image_filter_enabled)
        if sync_user_id is not None:
            core_delete_user_policies(sync_user_id)
        for r in crm_rules:
            domain = r["domain"]
            path = r.get("path")
            typ = r.get("type") or "*"
            state = r.get("state") or "block"
            tags = r.get("tags") or []
            core_add_policy(domain, path, policy_type=typ, state=state, tags=tags, source="user", user_id=sync_user_id or 0)

        core_tag_rules = core_get_tag_rules(enabled_only=False)
        crm_tag_set = {tr["tag"] for tr in crm_tag_rules}
        for tr in core_tag_rules:
            if tr["tag"] not in crm_tag_set:
                core_delete_tag_rule(tr["id"])
        core_tag_by_tag = {tr["tag"]: tr for tr in core_get_tag_rules(enabled_only=False)}
        for tr in crm_tag_rules:
            if tr["tag"] in core_tag_by_tag:
                core_update_tag_rule(core_tag_by_tag[tr["tag"]]["id"], state=tr["state"], enabled=bool(tr["enabled"]))
            else:
                core_add_tag_rule(tr["tag"], tr["state"], bool(tr["enabled"]))
    except Exception as e:
        logger.warning("sync_crm_rules_to_core failed: %s", e)


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


# ---------- Admin: list users (no password) ----------
def list_users(
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
) -> tuple[List[Dict], int]:
    """List users with sort, pagination and optional search (admin). Returns (list of users, total count)."""
    if sort_by not in ("id", "phone", "first_name", "last_name", "email", "is_admin", "created_at"):
        sort_by = "id"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size
    order_col = sort_by
    direction = "ASC" if sort_order == "asc" else "DESC"
    where = ""
    params: List = []
    if search and (q := search.strip()):
        q = f"%{q}%"
        where = " WHERE (phone LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
        params = [q, q, q, q]
    cursor = db_connection.execute(f"SELECT COUNT(*) FROM users{where}", params)
    total = cursor.fetchone()[0]
    cursor = db_connection.execute(
        f"""
        SELECT id, phone, first_name, last_name, email, COALESCE(is_admin, 0) AS is_admin, created_at
        FROM users{where}
        ORDER BY {order_col} {direction}
        LIMIT ? OFFSET ?
    """,
        params + [page_size, offset],
    )
    rows = cursor.fetchall()
    out = [
        {
            "id": row["id"],
            "phone": row["phone"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return out, total


def delete_user(user_id: int) -> None:
    """Delete a user and all their data (profiles, rules, schedules, rule_requests, locked_settings). Admin only. Cannot delete self."""
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("משתמש לא נמצא")
    # Delete in order: support_replies (via tickets), support_tickets, rule_requests, user_locked_settings, then profiles
    cursor = db_connection.execute("SELECT id FROM support_tickets WHERE user_id = ?", (user_id,))
    ticket_ids = [row[0] for row in cursor.fetchall()]
    for tid in ticket_ids:
        db_connection.execute("DELETE FROM support_replies WHERE ticket_id = ?", (tid,))
    db_connection.execute("DELETE FROM support_tickets WHERE user_id = ?", (user_id,))
    db_connection.execute("DELETE FROM rule_requests WHERE user_id = ?", (user_id,))
    db_connection.execute("DELETE FROM user_locked_settings WHERE user_id = ?", (user_id,))
    cursor = db_connection.execute("SELECT id FROM profiles WHERE user_id = ?", (user_id,))
    profile_ids = [row[0] for row in cursor.fetchall()]
    for pid in profile_ids:
        db_connection.execute("DELETE FROM schedules WHERE profile_id = ?", (pid,))
        db_connection.execute("DELETE FROM rules WHERE profile_id = ?", (pid,))
    db_connection.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
    db_connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db_connection.commit()


def set_user_admin(user_id: int, is_admin: bool) -> Dict:
    """Set user admin flag (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("משתמש לא נמצא")
    now = int(datetime.now().timestamp())
    db_connection.execute(
        "UPDATE users SET is_admin = ?, updated_at = ? WHERE id = ?",
        (1 if is_admin else 0, now, user_id),
    )
    db_connection.commit()
    return get_user_by_id(user_id)


# ---------- Locked settings (admin locks a setting for a user) ----------
LOCKABLE_KEYS = {"profile_name", "profile_mode", "rules", "schedules", "tag_rules"}


def get_locked_settings(user_id: int) -> List[str]:
    """Return list of setting_key that are locked for this user."""
    cursor = db_connection.execute(
        "SELECT setting_key FROM user_locked_settings WHERE user_id = ?",
        (user_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def set_locked_setting(user_id: int, setting_key: str) -> None:
    """Lock a setting for a user. setting_key must be in LOCKABLE_KEYS."""
    if setting_key not in LOCKABLE_KEYS:
        raise ValueError(f"הגדרה לא נתמכת: {setting_key}")
    now = int(datetime.now().timestamp())
    db_connection.execute(
        "INSERT OR IGNORE INTO user_locked_settings (user_id, setting_key, created_at) VALUES (?, ?, ?)",
        (user_id, setting_key, now),
    )
    db_connection.commit()


def remove_locked_setting(user_id: int, setting_key: str) -> None:
    """Unlock a setting for a user."""
    db_connection.execute(
        "DELETE FROM user_locked_settings WHERE user_id = ? AND setting_key = ?",
        (user_id, setting_key),
    )
    db_connection.commit()


# ---------- Rule requests (user requests open/change for admin to approve) ----------


def add_rule_request(
    user_id: int,
    request_type: str,
    url: Optional[str] = None,
    domain_pattern: Optional[str] = None,
    path_pattern: Optional[str] = None,
    action: Optional[str] = None,
    include_subdomains: bool = False,
    tags: Optional[List[str]] = None,
    request_url: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict:
    """Create a rule request (open, change, or file). status=pending. If url given, parse to domain/path if missing (for open/change). request_url = full URL (e.g. file URL). notes = for file requests: user description."""
    if request_type not in ("open", "change", "file"):
        raise ValueError("סוג בקשה לא חוקי")
    if url and request_type != "file":
        url = _normalize_url(url)
    if url and request_type != "file" and (not domain_pattern and not path_pattern):
        parsed_domain, parsed_path, _ = parse_url(url)
        domain_pattern = parsed_domain or ""
        path_pattern = parsed_path or "/"
    now = int(datetime.now().timestamp())
    tags_str = _tags_to_str(tags)
    req_url = (request_url or "").strip() or None
    notes_val = (notes or "").strip() or None
    if request_type == "file" and req_url is None and (url or "").strip():
        req_url = (url or "").strip()
    cursor = db_connection.execute("""
        INSERT INTO rule_requests
        (user_id, request_type, url, domain_pattern, path_pattern, action, type, include_subdomains, tags, status, created_at, updated_at, request_url, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
    """, (user_id, request_type, url or "", domain_pattern or "", path_pattern or "", action or "allow", "*", 1 if include_subdomains else 0, tags_str, now, now, req_url, notes_val))
    rid = cursor.lastrowid
    db_connection.commit()
    return get_rule_request(rid)


def get_rule_request(request_id: int) -> Optional[Dict]:
    """Get a single rule request. Includes resolved_by_user_id and resolved_by_name (from users)."""
    cursor = db_connection.execute("""
        SELECT r.id, r.user_id, r.request_type, r.url, r.domain_pattern, r.path_pattern, r.action, r.type, r.include_subdomains, r.tags, r.status, r.created_at, r.updated_at,
               r.approved_rule_id, r.approved_profile_id, r.request_url, r.notes, r.resolved_by_user_id
        FROM rule_requests r WHERE r.id = ?
    """, (request_id,))
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = _parse_tags(d.get("tags"))
    d["resolved_by_name"] = None
    if d.get("resolved_by_user_id"):
        u = get_user_by_id(d["resolved_by_user_id"])
        if u:
            name = ((u.get("first_name") or "") + " " + (u.get("last_name") or "")).strip()
            d["resolved_by_name"] = name or u.get("phone") or "—"
    return d


def list_rule_requests(
    status_filter: Optional[str] = None,
    request_type_filter: Optional[str] = None,
    user_id_filter: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[List[Dict], int]:
    """List rule requests with filters, search, sort and pagination. Returns (list, total count)."""
    if sort_by not in ("created_at", "request_type", "status", "user_id"):
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size
    order_col = sort_by
    direction = "ASC" if sort_order == "asc" else "DESC"
    where = "WHERE 1=1"
    params: List = []
    if status_filter:
        where += " AND status = ?"
        params.append(status_filter)
    if request_type_filter:
        where += " AND request_type = ?"
        params.append(request_type_filter)
    if user_id_filter is not None:
        where += " AND user_id = ?"
        params.append(user_id_filter)
    if search and (q := search.strip()):
        q = f"%{q}%"
        where += " AND (url LIKE ? OR domain_pattern LIKE ? OR COALESCE(path_pattern, '') LIKE ?)"
        params.extend([q, q, q])
    cursor = db_connection.execute(f"SELECT COUNT(*) FROM rule_requests {where}", params)
    total = cursor.fetchone()[0]
    cursor = db_connection.execute(
        f"""
        SELECT id, user_id, request_type, url, domain_pattern, path_pattern, action, type, include_subdomains, tags, status, created_at, updated_at,
               approved_rule_id, approved_profile_id, request_url, notes, resolved_by_user_id
        FROM rule_requests {where}
        ORDER BY {order_col} {direction}
        LIMIT ? OFFSET ?
    """,
        params + [page_size, offset],
    )
    rows = cursor.fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["tags"] = _parse_tags(d.get("tags"))
        d["resolved_by_name"] = None
        if d.get("resolved_by_user_id"):
            u = get_user_by_id(d["resolved_by_user_id"])
            if u:
                name = ((u.get("first_name") or "") + " " + (u.get("last_name") or "")).strip()
                d["resolved_by_name"] = name or u.get("phone") or "—"
        out.append(d)
    return out, total


def approve_rule_request(request_id: int, profile_id: Optional[int] = None, resolved_by_user_id: Optional[int] = None) -> Dict:
    """Admin approves a request: add or update rule in global list. For file requests, only mark as approved (no rule)."""
    req = get_rule_request(request_id)
    if not req:
        raise ValueError("בקשה לא נמצאה")
    if req["status"] == "approved":
        raise ValueError("הבקשה כבר אושרה")
    now = int(datetime.now().timestamp())
    if req.get("request_type") == "file":
        db_connection.execute(
            "UPDATE rule_requests SET status = 'approved', updated_at = ?, approved_rule_id = ?, approved_profile_id = ?, resolved_by_user_id = ? WHERE id = ?",
            (now, None, None, resolved_by_user_id, request_id),
        )
        db_connection.commit()
        return get_rule_request(request_id)
    url_raw = (req.get("url") or "").strip()
    if url_raw:
        url_for_rule = _normalize_url(url_raw)
    else:
        dom = (req.get("domain_pattern") or "").strip()
        path = (req.get("path_pattern") or "").strip()
        if not path or not path.startswith("/"):
            path = "/"
        url_for_rule = _normalize_url(dom + path) if dom else ""
    if not url_for_rule:
        raise ValueError("חסר כתובת בבקשה")
    domain, path, inc = parse_url(url_for_rule)
    inc = inc or bool(req.get("include_subdomains"))
    domain_pattern = f"*.{domain}" if inc else domain
    action = req.get("action") or "allow"
    tags = req.get("tags")
    existing_id = _global_rule_exists(domain_pattern, path, inc)
    if existing_id:
        updated = update_global_rule(
            existing_id,
            action=action,
            include_subdomains=inc,
            tags=tags,
        )
        rule_id = updated["id"]
    else:
        tf = imgf = filef = (action == "allow")
        created = create_global_rule(
            url=url_for_rule,
            action=action,
            include_subdomains=inc,
            tags=tags,
            text_filter_enabled=tf,
            image_filter_enabled=imgf,
            file_filter_enabled=filef,
        )
        rule_id = created["id"]
    db_connection.execute(
        "UPDATE rule_requests SET status = 'approved', updated_at = ?, approved_rule_id = ?, approved_profile_id = ?, resolved_by_user_id = ? WHERE id = ?",
        (now, rule_id, None, resolved_by_user_id, request_id),
    )
    db_connection.commit()
    sync_crm_rules_to_core(None)
    return get_rule_request(request_id)


def update_rule_request(
    request_id: int,
    url: Optional[str] = None,
    action: Optional[str] = None,
    include_subdomains: Optional[bool] = None,
    tags: Optional[List[str]] = None,
) -> Dict:
    """Update a pending or rejected rule request (admin or owner)."""
    req = get_rule_request(request_id)
    if not req:
        raise ValueError("בקשה לא נמצאה")
    if req["status"] == "approved":
        raise ValueError("לא ניתן לערוך בקשה שאושרה")
    if url is not None:
        url = _normalize_url(url.strip())
        domain_pattern, path_pattern, inc = parse_url(url)
        db_connection.execute(
            "UPDATE rule_requests SET url = ?, domain_pattern = ?, path_pattern = ?, updated_at = ? WHERE id = ?",
            (url, domain_pattern or "", path_pattern or "/", int(datetime.now().timestamp()), request_id),
        )
    if action is not None and action in ("allow", "block"):
        db_connection.execute("UPDATE rule_requests SET action = ?, updated_at = ? WHERE id = ?", (action, int(datetime.now().timestamp()), request_id))
    if include_subdomains is not None:
        db_connection.execute("UPDATE rule_requests SET include_subdomains = ?, updated_at = ? WHERE id = ?", (1 if include_subdomains else 0, int(datetime.now().timestamp()), request_id))
    if tags is not None:
        db_connection.execute("UPDATE rule_requests SET tags = ?, updated_at = ? WHERE id = ?", (_tags_to_str(tags), int(datetime.now().timestamp()), request_id))
    db_connection.commit()
    return get_rule_request(request_id)


def reject_rule_request(request_id: int, resolved_by_user_id: Optional[int] = None) -> Dict:
    """Admin rejects a request."""
    req = get_rule_request(request_id)
    if not req:
        raise ValueError("בקשה לא נמצאה")
    if req["status"] != "pending":
        raise ValueError("הבקשה כבר טופלה")
    now = int(datetime.now().timestamp())
    db_connection.execute(
        "UPDATE rule_requests SET status = 'rejected', updated_at = ?, resolved_by_user_id = ? WHERE id = ?",
        (now, resolved_by_user_id, request_id),
    )
    db_connection.commit()
    return get_rule_request(request_id)


def delete_rule_request(request_id: int) -> bool:
    """Admin or user deletes a request (only pending)."""
    req = get_rule_request(request_id)
    if not req:
        return False
    db_connection.execute("DELETE FROM rule_requests WHERE id = ?", (request_id,))
    db_connection.commit()
    return True


# ---------- Support tickets (פניות משתמשים) ----------

def _support_attachments_json(attachments: Optional[List[Dict]] = None) -> Optional[str]:
    if not attachments:
        return None
    import json
    return json.dumps([{"name": str(a.get("name", "")), "url": str(a.get("url", ""))} for a in attachments], ensure_ascii=False)


def _support_attachments_parse(raw: Optional[str] = None) -> List[Dict]:
    if not raw or not str(raw).strip():
        return []
    import json
    try:
        out = json.loads(raw)
        if not isinstance(out, list):
            return []
        return [{"name": str(x.get("name", "")), "url": str(x.get("url", ""))} for x in out if isinstance(x, dict)]
    except Exception:
        return []


def _content_preview(content: str, max_len: int = 200) -> str:
    if not content:
        return ""
    text = (content or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def create_support_ticket(
    user_id: int,
    subject: str,
    content: str,
    attachments: Optional[List[Dict]] = None,
    attached_rule_request_id: Optional[int] = None,
    request_snapshot_for_client: Optional[str] = None,
) -> Dict:
    """Create a new support ticket. attachments = list of {name, url}. Optional: attached_rule_request_id + request_snapshot_for_client (JSON) for בקשה לפתיחה."""
    subject = (subject or "").strip()
    content = (content or "").strip()
    if not subject:
        raise ValueError("נא להזין נושא")
    if not content and not attached_rule_request_id:
        raise ValueError("נא להזין תוכן או לצרף בקשה")
    now = int(datetime.now().timestamp())
    att_json = _support_attachments_json(attachments)
    snapshot = (request_snapshot_for_client or "").strip() or None
    rid = attached_rule_request_id
    cursor = db_connection.execute(
        "INSERT INTO support_tickets (user_id, subject, content, created_at, updated_at, attachments, attached_rule_request_id, request_snapshot_for_client) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, subject, content or "", now, now, att_json, rid, snapshot),
    )
    tid = cursor.lastrowid
    db_connection.commit()
    return get_support_ticket(tid)


def get_support_ticket(ticket_id: int) -> Optional[Dict]:
    """Get a single support ticket. If attached_rule_request_id set, includes request_snapshot_for_client and attached_request_status (from rule_requests)."""
    cursor = db_connection.execute(
        "SELECT id, user_id, subject, content, created_at, updated_at, attachments, attached_rule_request_id, request_snapshot_for_client FROM support_tickets WHERE id = ?",
        (ticket_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["attachments"] = _support_attachments_parse(d.get("attachments"))
    rid = d.get("attached_rule_request_id")
    if rid:
        req = get_rule_request(rid)
        d["attached_request_status"] = req["status"] if req else None
    return d


def _get_ticket_last_read_at(ticket_id: int, user_id: int) -> int:
    """Return last_read_at for user on this ticket, or 0 if never read."""
    cursor = db_connection.execute(
        "SELECT last_read_at FROM support_ticket_views WHERE ticket_id = ? AND user_id = ?",
        (ticket_id, user_id),
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def mark_support_ticket_read(ticket_id: int, user_id: int) -> None:
    """Mark ticket as read by user (updates last_read_at so replies become read)."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        return
    now = int(datetime.now().timestamp())
    cursor = db_connection.execute(
        "SELECT 1 FROM support_ticket_views WHERE ticket_id = ? AND user_id = ?",
        (ticket_id, user_id),
    )
    if cursor.fetchone():
        db_connection.execute(
            "UPDATE support_ticket_views SET last_read_at = ? WHERE ticket_id = ? AND user_id = ?",
            (now, ticket_id, user_id),
        )
    else:
        db_connection.execute(
            "INSERT INTO support_ticket_views (ticket_id, user_id, last_read_at) VALUES (?, ?, ?)",
            (ticket_id, user_id, now),
        )
    db_connection.commit()


def list_my_support_tickets(
    user_id: int,
    page: int = 1,
    page_size: int = 25,
    sort_order: str = "desc",
) -> tuple[List[Dict], int]:
    """List support tickets for a user (own only). Includes replies_count and unread_replies_count."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size
    direction = "DESC" if sort_order == "desc" else "ASC"
    cursor = db_connection.execute(
        "SELECT COUNT(*) FROM support_tickets WHERE user_id = ?", (user_id,)
    )
    total = cursor.fetchone()[0]
    cursor = db_connection.execute(
        f"""
        SELECT t.id, t.user_id, t.subject, t.content, t.created_at, t.updated_at,
               t.attached_rule_request_id, t.request_snapshot_for_client,
               (SELECT COUNT(*) FROM support_replies r WHERE r.ticket_id = t.id) AS replies_count
        FROM support_tickets t
        WHERE t.user_id = ?
        ORDER BY t.updated_at {direction}
        LIMIT ? OFFSET ?
        """,
        (user_id, page_size, offset),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    for r in rows:
        r["content_preview"] = _content_preview(r.get("content") or "")
        r["replies_count"] = r.get("replies_count") or 0
        last_read = _get_ticket_last_read_at(r["id"], user_id)
        cursor2 = db_connection.execute(
            "SELECT COUNT(*) FROM support_replies WHERE ticket_id = ? AND author_id != ? AND created_at > ?",
            (r["id"], user_id, last_read),
        )
        r["unread_replies_count"] = cursor2.fetchone()[0] or 0
        if r.get("attached_rule_request_id"):
            req = get_rule_request(r["attached_rule_request_id"])
            r["attached_request_status"] = req["status"] if req else None
        else:
            r["attached_request_status"] = None
    return rows, total


def list_all_support_tickets(
    page: int = 1,
    page_size: int = 25,
    sort_order: str = "desc",
    search: Optional[str] = None,
    viewer_id: Optional[int] = None,
) -> tuple[List[Dict], int]:
    """List all support tickets (admin). Returns (list, total). When viewer_id is set, unread_replies_count is from that viewer's perspective (so admin sees 0 after reading)."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size
    direction = "DESC" if sort_order == "desc" else "ASC"
    where = ""
    params: list = []
    if search and (q := search.strip()):
        q_like = f"%{q}%"
        where = """
        WHERE (
            t.subject LIKE ? OR t.content LIKE ?
            OR u.first_name LIKE ? OR u.last_name LIKE ? OR u.phone LIKE ?
        )
        """
        params = [q_like, q_like, q_like, q_like, q_like]
    cursor = db_connection.execute(
        f"SELECT COUNT(*) FROM support_tickets t LEFT JOIN users u ON u.id = t.user_id {where}",
        params,
    )
    total = cursor.fetchone()[0]
    cursor = db_connection.execute(
        f"""
        SELECT t.id, t.user_id, t.subject, t.content, t.created_at, t.updated_at,
               t.attached_rule_request_id, t.request_snapshot_for_client,
               (SELECT COUNT(*) FROM support_replies r WHERE r.ticket_id = t.id) AS replies_count
        FROM support_tickets t
        LEFT JOIN users u ON u.id = t.user_id
        {where}
        ORDER BY t.updated_at {direction}
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    rows = [dict(row) for row in cursor.fetchall()]
    for r in rows:
        r["content_preview"] = _content_preview(r.get("content") or "")
        r["replies_count"] = r.get("replies_count") or 0
        # unread_replies_count: when viewer_id (admin) is set, count replies after viewer's last read; else owner's unread
        if viewer_id is not None:
            last_read = _get_ticket_last_read_at(r["id"], viewer_id)
            cursor2 = db_connection.execute(
                "SELECT COUNT(*) FROM support_replies WHERE ticket_id = ? AND created_at > ?",
                (r["id"], last_read),
            )
            r["unread_replies_count"] = cursor2.fetchone()[0] or 0
        else:
            owner_id = r["user_id"]
            last_read = _get_ticket_last_read_at(r["id"], owner_id)
            cursor2 = db_connection.execute(
                "SELECT COUNT(*) FROM support_replies WHERE ticket_id = ? AND author_id != ? AND created_at > ?",
                (r["id"], owner_id, last_read),
            )
            r["unread_replies_count"] = cursor2.fetchone()[0] or 0
        user = get_user_by_id(r["user_id"])
        r["user_first_name"] = (user or {}).get("first_name")
        r["user_phone"] = (user or {}).get("phone")
        if r.get("attached_rule_request_id"):
            req = get_rule_request(r["attached_rule_request_id"])
            r["attached_request_status"] = req["status"] if req else None
        else:
            r["attached_request_status"] = None
    return rows, total


def count_my_tickets_with_replies(user_id: int) -> int:
    """Count tickets belonging to user that have at least one reply."""
    cursor = db_connection.execute(
        """
        SELECT COUNT(*) FROM support_tickets t
        WHERE t.user_id = ? AND EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id)
        """,
        (user_id,),
    )
    return cursor.fetchone()[0] or 0


def count_my_tickets_with_unread_replies(user_id: int) -> int:
    """Count tickets where the owner has at least one unread reply (from someone else)."""
    cursor = db_connection.execute(
        """
        SELECT COUNT(DISTINCT t.id) FROM support_tickets t
        JOIN support_replies r ON r.ticket_id = t.id AND r.author_id != t.user_id
        LEFT JOIN support_ticket_views v ON v.ticket_id = t.id AND v.user_id = t.user_id
        WHERE t.user_id = ?
          AND r.created_at > COALESCE(v.last_read_at, 0)
        """,
        (user_id,),
    )
    return cursor.fetchone()[0] or 0


def count_all_tickets_with_replies() -> int:
    """Count all tickets that have at least one reply (admin)."""
    cursor = db_connection.execute(
        """
        SELECT COUNT(*) FROM support_tickets t
        WHERE EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id)
        """
    )
    return cursor.fetchone()[0] or 0


def count_all_tickets_with_unread_replies(admin_viewer_id: Optional[int] = None) -> int:
    """Count tickets with unread replies. When admin_viewer_id is set, count from admin's perspective (replies after admin's last read). Else owner's unread."""
    if admin_viewer_id is not None:
        cursor = db_connection.execute(
            """
            SELECT COUNT(DISTINCT t.id) FROM support_tickets t
            JOIN support_replies r ON r.ticket_id = t.id
            LEFT JOIN support_ticket_views v ON v.ticket_id = t.id AND v.user_id = ?
            WHERE r.created_at > COALESCE(v.last_read_at, 0)
            """,
            (admin_viewer_id,),
        )
        return cursor.fetchone()[0] or 0
    cursor = db_connection.execute(
        """
        SELECT COUNT(DISTINCT t.id) FROM support_tickets t
        JOIN support_replies r ON r.ticket_id = t.id AND r.author_id != t.user_id
        LEFT JOIN support_ticket_views v ON v.ticket_id = t.id AND v.user_id = t.user_id
        WHERE r.created_at > COALESCE(v.last_read_at, 0)
        """
    )
    return cursor.fetchone()[0] or 0


def add_support_reply(
    ticket_id: int,
    author_id: int,
    content: str,
    attachments: Optional[List[Dict]] = None,
    attached_request_snapshot: Optional[str] = None,
) -> Dict:
    """Add a reply to a ticket (admin or ticket owner). attachments = list of {name, url}. attached_request_snapshot = JSON when user sends edited copy of request."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError("פנייה לא נמצאה")
    content = (content or "").strip()
    snapshot = (attached_request_snapshot or "").strip() or None
    if not content and not attachments and not snapshot:
        raise ValueError("נא להזין תוכן תגובה, לצרף קובץ או לצרף עותק ערוך של הבקשה")
    now = int(datetime.now().timestamp())
    att_json = _support_attachments_json(attachments)
    cursor = db_connection.execute(
        "INSERT INTO support_replies (ticket_id, author_id, content, created_at, attachments, attached_request_snapshot) VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_id, author_id, content or "", now, att_json, snapshot),
    )
    rid = cursor.lastrowid
    db_connection.execute(
        "UPDATE support_tickets SET updated_at = ? WHERE id = ?", (now, ticket_id)
    )
    db_connection.commit()
    return get_support_reply(rid)


def get_support_reply(reply_id: int) -> Optional[Dict]:
    """Get a single support reply with author profile (first_name, last_name, avatar_url), attachments, and optional attached_request_snapshot."""
    cursor = db_connection.execute(
        "SELECT id, ticket_id, author_id, content, created_at, attachments, attached_request_snapshot FROM support_replies WHERE id = ?",
        (reply_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["attachments"] = _support_attachments_parse(d.get("attachments"))
    author = get_user_by_id(d["author_id"])
    if author:
        d["author_first_name"] = author.get("first_name") or "—"
        d["author_last_name"] = author.get("last_name") or ""
        d["author_avatar_url"] = author.get("avatar_url")
    else:
        d["author_first_name"] = "—"
        d["author_last_name"] = ""
        d["author_avatar_url"] = None
    return d


def list_support_replies(ticket_id: int, viewer_id: Optional[int] = None) -> List[Dict]:
    """List all replies for a ticket, with author profile. If viewer_id is the ticket owner, set is_unread for replies from others not yet read."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        return []
    last_read = _get_ticket_last_read_at(ticket_id, viewer_id) if viewer_id else 0
    ticket_owner_id = ticket["user_id"]
    cursor = db_connection.execute(
        """
        SELECT id, ticket_id, author_id, content, created_at, attachments, attached_request_snapshot
        FROM support_replies WHERE ticket_id = ?
        ORDER BY created_at ASC
        """,
        (ticket_id,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    for r in rows:
        r["attachments"] = _support_attachments_parse(r.get("attachments"))
        author = get_user_by_id(r["author_id"])
        if author:
            r["author_first_name"] = author.get("first_name") or "—"
            r["author_last_name"] = author.get("last_name") or ""
            r["author_avatar_url"] = author.get("avatar_url")
        else:
            r["author_first_name"] = "—"
            r["author_last_name"] = ""
            r["author_avatar_url"] = None
        # Unread only for ticket owner: reply from someone else, after their last read
        if viewer_id == ticket_owner_id and r["author_id"] != ticket_owner_id:
            r["is_unread"] = r["created_at"] > last_read
        else:
            r["is_unread"] = False
    return rows


def delete_support_ticket(ticket_id: int) -> bool:
    """Delete a support ticket and all its replies. Returns True if deleted."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        return False
    db_connection.execute("DELETE FROM support_replies WHERE ticket_id = ?", (ticket_id,))
    db_connection.execute("DELETE FROM support_ticket_views WHERE ticket_id = ?", (ticket_id,))
    db_connection.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
    db_connection.commit()
    return True

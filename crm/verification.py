"""
Phone and email verification (OTP).
Backend validation; delivery through crm/notify.py (SMTP / Twilio / webhook).
"""
import logging
import secrets
import string
from typing import Optional
from datetime import datetime, timedelta

from data.constants import CODE_LENGTH, CODE_EXPIRE_MINUTES, RATE_LIMIT_MINUTES, CODE_MAX_ATTEMPTS

from . import notify
from .database import db_connection
from .services import get_user_by_phone, get_user_by_email

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit()).strip()


def _generate_code() -> str:
    # secrets, not random: random's Mersenne Twister output is predictable from earlier outputs.
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def _store_code(target: str, code: str, kind: str) -> None:
    now = int(datetime.now().timestamp())
    expires = int((datetime.now() + timedelta(minutes=CODE_EXPIRE_MINUTES)).timestamp())
    db_connection.execute("""
        INSERT INTO verification_codes (target, code, type, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (target, code, kind, expires, now))
    db_connection.commit()


def _check_rate_limit(target: str, kind: str) -> Optional[str]:
    since = int((datetime.now() - timedelta(minutes=RATE_LIMIT_MINUTES)).timestamp())
    cursor = db_connection.execute("""
        SELECT id FROM verification_codes
        WHERE target = ? AND type = ? AND created_at > ?
        ORDER BY created_at DESC LIMIT 1
    """, (target, kind, since))
    if cursor.fetchone():
        return f"נא להמתין {RATE_LIMIT_MINUTES} דקות לפני שליחת קוד מחדש."
    return None


def _consume_code(target: str, code: str, kind: str) -> bool:
    """Check the latest live code for target. Every wrong guess counts; after CODE_MAX_ATTEMPTS the code is
    deleted (per-IP rate limits alone still allowed ~100 guesses per code from each IP)."""
    now = int(datetime.now().timestamp())
    row = db_connection.execute("""
        SELECT id, code, COALESCE(attempts, 0) AS attempts FROM verification_codes
        WHERE target = ? AND type = ? AND expires_at > ?
        ORDER BY created_at DESC LIMIT 1
    """, (target, kind, now)).fetchone()
    if not row:
        return False
    if secrets.compare_digest(str(row["code"]), str(code)):
        db_connection.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
        db_connection.commit()
        return True
    if row["attempts"] + 1 >= CODE_MAX_ATTEMPTS:
        db_connection.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
    else:
        db_connection.execute("UPDATE verification_codes SET attempts = COALESCE(attempts, 0) + 1 WHERE id = ?", (row["id"],))
    db_connection.commit()
    return False




def _deliver(send, *args) -> None:
    try:
        send(*args)
    except notify.DeliveryNotConfigured as e:
        raise ValueError("שליחת קוד לא הוגדרה בשרת – היכנסו עם סיסמה.") from e
    except notify.DeliveryFailed as e:
        raise ValueError("שליחת הקוד נכשלה. נסו שוב מאוחר יותר.") from e


def request_phone_code(phone_raw: str) -> dict:
    """Request OTP for phone. Returns { sent: True } or raises ValueError."""
    from .services import _validate_phone_format
    _validate_phone_format(phone_raw)
    phone = _normalize_phone(phone_raw)
    user = get_user_by_phone(phone)
    if not user:
        raise ValueError("לא נמצא משתמש עם מספר טלפון זה.")
    if not notify.sms_configured():
        raise ValueError("שליחת קוד ב-SMS לא הוגדרה בשרת – היכנסו עם סיסמה.")
    err = _check_rate_limit(phone, "phone")
    if err:
        raise ValueError(err)
    code = _generate_code()
    _store_code(phone, code, "phone")
    _deliver(notify.send_sms, phone, f"קוד הכניסה שלך: {code}\nתקף ל-{CODE_EXPIRE_MINUTES} דקות. אל תמסרו אותו לאיש.")
    return {"sent": True, "message": "נשלח קוד לנייד."}


def verify_phone_code(phone: str, code: str) -> dict:
    """Verify OTP and return user dict. Raises ValueError on failure."""
    phone = _normalize_phone(phone)
    if not phone or not code or len(code) != CODE_LENGTH or not code.isdigit():
        raise ValueError("קוד לא תקין.")
    if not _consume_code(phone, code, "phone"):
        raise ValueError("קוד שגוי או שפג תוקפו.")
    user = get_user_by_phone(phone)
    if not user:
        raise ValueError("משתמש לא נמצא.")
    return {k: v for k, v in user.items() if k != "password_hash"}


def request_email_code(email: str) -> dict:
    """Request OTP for email. Returns { sent: True } or raises ValueError."""
    email = (email or "").strip().lower()
    if "@" not in email:
        raise ValueError("כתובת אימייל לא תקינה.")
    user = get_user_by_email(email)
    if not user:
        raise ValueError("לא נמצא משתמש עם כתובת אימייל זו.")
    if not notify.email_configured():
        raise ValueError("שליחת קוד באימייל לא הוגדרה בשרת – היכנסו עם סיסמה.")
    err = _check_rate_limit(email, "email")
    if err:
        raise ValueError(err)
    code = _generate_code()
    _store_code(email, code, "email")
    _deliver(notify.send_email, email, "קוד כניסה", f"קוד הכניסה שלך: {code}\nתקף ל-{CODE_EXPIRE_MINUTES} דקות. אל תמסרו אותו לאיש.")
    return {"sent": True, "message": "נשלח קוד לאימייל."}


def verify_email_code(email: str, code: str) -> dict:
    """Verify OTP and return user dict. Raises ValueError on failure."""
    email = (email or "").strip().lower()
    if not email or not code or len(code) != CODE_LENGTH or not code.isdigit():
        raise ValueError("קוד לא תקין.")
    if not _consume_code(email, code, "email"):
        raise ValueError("קוד שגוי או שפג תוקפו.")
    user = get_user_by_email(email)
    if not user:
        raise ValueError("משתמש לא נמצא.")
    return {k: v for k, v in user.items() if k != "password_hash"}

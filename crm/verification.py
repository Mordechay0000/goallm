"""
Phone and email verification (OTP).
Backend validation; SMS/email sending pluggable (mock in dev).
"""
import random
import string
import logging
from typing import Optional
from datetime import datetime, timedelta

from data.constants import CODE_LENGTH, CODE_EXPIRE_MINUTES, RATE_LIMIT_MINUTES

from .database import db_connection
from .services import get_user_by_phone, get_user_by_email

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit()).strip()


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=CODE_LENGTH))


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
    now = int(datetime.now().timestamp())
    cursor = db_connection.execute("""
        SELECT id FROM verification_codes
        WHERE target = ? AND type = ? AND code = ? AND expires_at > ?
        ORDER BY created_at DESC LIMIT 1
    """, (target, kind, code, now))
    row = cursor.fetchone()
    if not row:
        return False
    db_connection.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
    db_connection.commit()
    return True




def _send_sms_mock(phone: str, code: str) -> None:
    logger.info("SMS (mock) to %s: code=%s", phone, code)


def _send_email_mock(email: str, code: str) -> None:
    logger.info("Email (mock) to %s: code=%s", email, code)


def request_phone_code(phone_raw: str) -> dict:
    """Request OTP for phone. Returns { sent: True } or raises ValueError."""
    from .services import _validate_phone_format
    _validate_phone_format(phone_raw)
    phone = _normalize_phone(phone_raw)
    user = get_user_by_phone(phone)
    if not user:
        raise ValueError("לא נמצא משתמש עם מספר טלפון זה.")
    err = _check_rate_limit(phone, "phone")
    if err:
        raise ValueError(err)
    code = _generate_code()
    _store_code(phone, code, "phone")
    _send_sms_mock(phone, code)
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
    err = _check_rate_limit(email, "email")
    if err:
        raise ValueError(err)
    code = _generate_code()
    _store_code(email, code, "email")
    _send_email_mock(email, code)
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

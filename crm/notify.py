"""
Delivery of one-time codes: e-mail over SMTP, SMS through Twilio or a generic webhook.

The webhook covers Israeli SMS providers (019, InforU, Cellact…) without a dependency per provider: point
SMS_WEBHOOK_URL at a small adapter that receives {"to": "+9725…", "text": "…"} and calls the provider.

No provider configured → DeliveryNotConfigured: the code login is refused instead of silently "sent"
(the old mock wrote codes to the log, where anyone with log access could log in as any user).
"""
from __future__ import annotations

import base64
import json
import logging
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage

import data.constants as C

logger = logging.getLogger(__name__)


class DeliveryNotConfigured(Exception):
    pass


class DeliveryFailed(Exception):
    pass


def to_e164(phone: str) -> str:
    """Israeli local numbers (05X…) → +9725X…; anything already international is kept."""
    digits = "".join(c for c in phone if c.isdigit())
    if phone.strip().startswith("+"):
        return "+" + digits
    if digits.startswith("972"):
        return "+" + digits
    if digits.startswith("0"):
        return "+972" + digits[1:]
    return "+" + digits


def email_configured() -> bool:
    return bool(C.SMTP_HOST and C.SMTP_FROM) or C.OTP_DEV_LOG_CODES


def sms_configured() -> bool:
    if C.SMS_PROVIDER == "twilio":
        return bool(C.TWILIO_ACCOUNT_SID and C.TWILIO_AUTH_TOKEN and C.TWILIO_FROM)
    if C.SMS_PROVIDER == "webhook":
        return bool(C.SMS_WEBHOOK_URL)
    return C.OTP_DEV_LOG_CODES


def send_email(to: str, subject: str, body: str) -> None:
    if not (C.SMTP_HOST and C.SMTP_FROM):
        if C.OTP_DEV_LOG_CODES:
            logger.warning("DEV ONLY – e-mail to %s not sent (no SMTP): %s", to, body)
            return
        raise DeliveryNotConfigured("SMTP is not configured")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = C.SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        if C.SMTP_SECURITY == "ssl":
            server = smtplib.SMTP_SSL(C.SMTP_HOST, C.SMTP_PORT, timeout=15, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(C.SMTP_HOST, C.SMTP_PORT, timeout=15)
        with server:
            if C.SMTP_SECURITY == "starttls":
                server.starttls(context=ssl.create_default_context())
            if C.SMTP_USER:
                server.login(C.SMTP_USER, C.SMTP_PASSWORD)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        logger.error("SMTP delivery to %s failed: %s", to, e)
        raise DeliveryFailed(str(e)) from e


def _post(url: str, data: bytes, headers: dict) -> None:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status >= 300:
                raise DeliveryFailed(f"HTTP {resp.status}")
    except OSError as e:
        raise DeliveryFailed(str(e)) from e


def send_sms(phone: str, text: str) -> None:
    to = to_e164(phone)
    if C.SMS_PROVIDER == "twilio" and sms_configured():
        url = f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(C.TWILIO_ACCOUNT_SID)}/Messages.json"
        auth = base64.b64encode(f"{C.TWILIO_ACCOUNT_SID}:{C.TWILIO_AUTH_TOKEN}".encode()).decode()
        _post(url, urllib.parse.urlencode({"To": to, "From": C.TWILIO_FROM, "Body": text}).encode(),
              {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"})
        return
    if C.SMS_PROVIDER == "webhook" and sms_configured():
        headers = {"Content-Type": "application/json"}
        if C.SMS_WEBHOOK_TOKEN:
            headers["Authorization"] = f"Bearer {C.SMS_WEBHOOK_TOKEN}"
        _post(C.SMS_WEBHOOK_URL, json.dumps({"to": to, "text": text}, ensure_ascii=False).encode("utf-8"), headers)
        return
    if C.OTP_DEV_LOG_CODES:
        logger.warning("DEV ONLY – SMS to %s not sent (no provider): %s", to, text)
        return
    raise DeliveryNotConfigured("SMS provider is not configured")

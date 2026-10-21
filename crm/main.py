"""
FastAPI application for CRM system.
"""
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse, HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List, Optional
import hmac
import json
import logging
import os
import csv
import io
from pathlib import Path
import asyncio
import time

from .models import (
    UserCreate, UserResponse, UserUpdate, PasswordChange, LoginRequest,
    RequestPhoneCode, VerifyPhoneCode, RequestEmailCode, VerifyEmailCode,
    ProfileCreate, ProfileUpdate, ProfileResponse,
    RuleCreate, RuleUpdate, RuleResponse,
    GlobalRuleCreate, GlobalRuleUpdate, GlobalRuleResponse,
    TagRuleCreate, TagRuleUpdate, TagRuleResponse,
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
    RuleRequestCreate, RuleRequestApprove, RuleRequestUpdate, RuleRequestResponse,
    ResolverTestUrlBody, AllowedFileUrlBody,
    SiteInjectionCreate, SiteInjectionUpdate, SiteInjectionResponse,
    SupportTicketCreate, SupportTicketResponse, SupportReplyCreate, SupportReplyResponse,
    SupportTicketsBulkDeleteBody,
)
from .services import (
    create_user, setup_needed, authenticate_user, authenticate_user_by_phone, get_user_by_id, update_user, change_password, get_user_profiles,
    create_profile, get_profile, update_profile, delete_profile,
    create_rule, get_rule, get_profile_rules, update_rule, delete_rule,
    get_tag_rules, add_tag_rule, update_tag_rule, delete_tag_rule, sync_crm_rules_to_core, get_user_ids_with_profiles,
    create_schedule, get_schedule, get_profile_schedules, update_schedule, delete_schedule,
    list_users, set_user_admin, delete_user, get_locked_settings, set_locked_setting, remove_locked_setting,
    add_rule_request, list_rule_requests, get_rule_request, approve_rule_request, reject_rule_request, delete_rule_request,
    list_allowed_file_downloads, sync_allowed_file_downloads_to_core, add_allowed_file_url_crm, remove_allowed_file_url_crm,
    update_rule_request, list_all_profiles_for_admin,
    create_support_ticket, get_support_ticket, list_my_support_tickets, list_all_support_tickets,
    add_support_reply, list_support_replies, get_support_reply,
    count_my_tickets_with_replies, count_all_tickets_with_replies,
    count_my_tickets_with_unread_replies,
    count_all_tickets_with_unread_replies,
    count_all_tickets_with_unread_for_admin_group,
    mark_support_ticket_read, delete_support_ticket, delete_support_tickets_bulk,
    list_support_ticket_user_ids,
    get_global_rules, get_global_rule, create_global_rule, update_global_rule, delete_global_rule, resolve_global_rule_for_url, find_and_update_global_rule_to_block, create_or_update_global_rule_surf, check_before_create_global_rule,
    get_site_injections, get_site_injection, create_site_injection, update_site_injection, delete_site_injection,
    sync_site_injections_to_core,
    list_bindings_for_user, add_ip_binding, remove_ip_binding, sync_ip_bindings_to_core, touch_ip_binding,
    get_user_id_for_ip,
    get_proxy_credentials, rotate_proxy_credentials, sync_users_to_core,
)
from .auth import create_user_access_token, get_current_user, get_current_admin
from .security import decode_access_token
from .database import init_db_schema, db_connection
from .resolver_integration import get_rules_for_resolver, get_all_enabled_rules_for_resolver
from .verification import (
    request_phone_code,
    verify_phone_code,
    request_email_code,
    verify_email_code,
)
from .uploads import validate_avatar_file, save_avatar
from .support_uploads import save_support_file
from .security import validate_password_strength
from core.net_utils import resolve_client_ip, is_trusted_proxy
from core.proxy_identity import HEADER as PROXY_USER_HEADER, verify_user as verify_proxy_user
from data.constants import (
    CORS_ALLOW_ORIGINS,
    CRM_PROXY_SECRET,
    STORAGE_DIR,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    FILTER_CERT_DIR,
    FILTER_DIAGNOSTIC_HOST_ALIAS,
)
from data.landing_pages import DIAGNOSTIC_HTML_TEMPLATE

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="CRM - ניהול סינון",
    description="מערכת CRM לניהול פרופילי סינון",
    version="1.0.0"
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: auth is a Bearer header (not a cookie), but there is no reason to let any website call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ALLOW_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # The CRM must never be framed by another site (clickjacking / postMessage tricks).
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# Initialize database
init_db_schema()


@app.on_event("startup")
async def startup_sync_bindings():
    """Sync IP bindings and allowed file downloads to core so the proxy has current data on startup."""
    try:
        sync_ip_bindings_to_core()
    except Exception as e:
        logger.warning("Startup sync_ip_bindings_to_core failed: %s", e)
    try:
        sync_allowed_file_downloads_to_core()
    except Exception as e:
        logger.warning("Startup sync_allowed_file_downloads_to_core failed: %s", e)
    try:
        sync_users_to_core()
    except Exception as e:
        logger.warning("Startup sync_users_to_core failed: %s", e)


async def _periodic_schedule_sync():
    """Every 60 seconds, sync each user's active profile (by schedule) to core so day/hour changes apply automatically."""
    while True:
        try:
            await asyncio.sleep(60)
            # Global rules + tags once, then only the per-user layer (diff-based, cheap when unchanged).
            try:
                sync_crm_rules_to_core(None)
            except Exception as e:
                logger.debug("Periodic sync_crm_rules_to_core(None) failed: %s", e)
            for uid in get_user_ids_with_profiles():
                try:
                    sync_crm_rules_to_core(uid, set_default=False, include_global=False)
                except Exception as e:
                    logger.warning("Periodic sync for user %s failed: %s", uid, e)
            try:
                from core.policy.policy_database import purge_traffic_logs_older_than
                from data.constants import TRAFFIC_LOG_RETENTION_DAYS
                purge_traffic_logs_older_than(TRAFFIC_LOG_RETENTION_DAYS)
            except Exception as e:
                logger.debug("Traffic log retention purge failed: %s", e)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Periodic schedule sync error: %s", e)


@app.on_event("startup")
async def start_periodic_schedule_sync():
    """Start background task so profile switches by schedule (day/hour) apply within ~1 minute."""
    asyncio.create_task(_periodic_schedule_sync())


# Static files (for React build)
static_folder = Path(__file__).resolve().parent / "static"
if static_folder.exists():
    app.mount("/static", StaticFiles(directory=str(static_folder)), name="static")
    assets_folder = static_folder / "assets"
    if assets_folder.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_folder)), name="assets")

# User uploads (avatars, support attachments). Served by a route (not StaticFiles) so every file gets
# headers that stop it from running as a page on the CRM origin: an uploaded .html/.svg must never be
# able to read the admin's token from localStorage.
uploads_dir = STORAGE_DIR / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
_INLINE_UPLOAD_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}


@app.get("/uploads/{subdir}/{filename}")
async def serve_upload(subdir: str, filename: str):
    if subdir not in ("avatars", "support") or "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="Not Found")
    path = (uploads_dir / subdir / filename).resolve()
    if uploads_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    ext = path.suffix.lower()
    media_type = _INLINE_UPLOAD_TYPES.get(ext)
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self'",
        "Cache-Control": "private, max-age=3600",
    }
    if media_type is None:
        media_type = "application/octet-stream"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return FileResponse(str(path), media_type=media_type, headers=headers)


def _serve_spa():
    """Serve React SPA (index.html) for client-side routes."""
    index_file = static_folder / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "CRM API", "version": "1.0.0"}


@app.get("/")
async def root():
    """Serve React app."""
    return _serve_spa()


@app.get("/bind")
async def bind_spa():
    """Serve SPA for bind flow (proxy redirects unbound IPs here)."""
    return _serve_spa()


@app.get("/diagnostic", response_class=HTMLResponse)
async def diagnostic_page(request: Request):
    """
    דף אבחון סינון – מסך אחד. כניסה מכלים: ?from=tools מציגה לחצן חזרה לכלים.
    """
    from_tools = request.query_params.get("from") == "tools"
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if not origin and request.headers.get("referer"):
        try:
            from urllib.parse import urlparse
            origin = urlparse(request.headers["referer"]).scheme + "://" + urlparse(request.headers["referer"]).netloc
        except Exception:
            pass
    back_href = (origin + "/tools") if origin else "/tools"
    back_to_tools_html = (
        f'<div class="back-to-tools"><a href="{back_href}">← חזרה לכלים</a></div>'
        if from_tools
        else ""
    )
    server_time = int(time.time())
    connection_filtered = "true" if _filtered_user_id(request) is not None else "false"
    filter_check_url = "/diagnostic/check"
    cert_base_url = "/diagnostic/cert"
    html = DIAGNOSTIC_HTML_TEMPLATE.replace("{server_time}", str(server_time))
    html = html.replace("{connection_filtered}", connection_filtered)
    html = html.replace("{filter_check_url}", filter_check_url)
    html = html.replace("{cert_base_url}", cert_base_url)
    html = html.replace("{back_to_tools_html}", back_to_tools_html)
    return HTMLResponse(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/diagnostic/check")
async def diagnostic_check(request: Request):
    """בדיקה האם החיבור מסונן (פרטי התחברות אישיים לפרוקסי או IP משויך). מחזיר JSON עם filtered: true/false."""
    return {"filtered": _filtered_user_id(request) is not None}


def _cert_file_for_os(os_param: str, user_agent: str) -> tuple[str, str]:
    """מחזיר (filename, content_type) לפי os_param או User-Agent."""
    ua = (user_agent or "").lower()
    if os_param == "windows" or (not os_param and ("windows" in ua or "win" in ua)):
        return "mitmproxy-ca-cert.p12", "application/x-pkcs12"
    if os_param == "android" or (not os_param and "android" in ua):
        return "mitmproxy-ca-cert.cer", "application/x-x509-ca-cert"
    return "mitmproxy-ca-cert.pem", "application/x-pem-file"


@app.get("/diagnostic/cert")
async def diagnostic_cert(
    request: Request,
    os: Optional[str] = Query(None, description="windows|mac|android|ios|linux"),
):
    """הורדת תעודת האבטחה של mitmproxy לפי מערכת ההפעלה."""
    cert_dir = Path(FILTER_CERT_DIR)
    filename, content_type = _cert_file_for_os((os or "").strip().lower(), request.headers.get("user-agent") or "")
    path = cert_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="קובץ התעודה לא נמצא")
    try:
        body = path.read_bytes()
    except OSError as e:
        logger.warning("Cannot read cert file %s: %s", path, e)
        raise HTTPException(status_code=500, detail="שגיאה בקריאת קובץ התעודה")
    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# ========== Auth Endpoints ==========

def _validate_email(s: str) -> str:
    s = (s or "").strip().lower()
    if not s or "@" not in s or s.count("@") != 1:
        raise ValueError("כתובת אימייל לא תקינה")
    local, _, domain = s.partition("@")
    if not local or not domain or ".." in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("כתובת אימייל לא תקינה")
    return s


@app.get("/api/auth/setup-status")
async def get_setup_status():
    """Returns whether first-time setup is needed (no users yet). When true, first registrant becomes admin."""
    return {"needs_setup": setup_needed()}


@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(...),
    avatar: UploadFile = File(None),
):
    """Register a new user. Phone required (login is always by phone). Avatar: upload image (optional)."""
    try:
        email = _validate_email(email)
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        phone = (phone or "").strip()
        if not first_name or len(first_name) > 100:
            raise ValueError("שם פרטי לא תקין")
        if not last_name or len(last_name) > 100:
            raise ValueError("שם משפחה לא תקין")
        ok, msg = validate_password_strength(password)
        if not ok:
            raise ValueError(msg or "סיסמה לא תקינה")
        avatar_url = None
        if avatar and avatar.filename:
            content = await avatar.read()
            if content:
                ext, _ = validate_avatar_file(content, avatar.filename, avatar.content_type)
                avatar_url = save_avatar(content, ext, None)
        user = create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            avatar_url=avatar_url
        )
        return UserResponse(**{k: v for k, v in user.items() if k != "password_hash"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, login_data: LoginRequest):
    """Login by phone + password. Rate limited: 5 attempts per minute per IP."""
    user = authenticate_user_by_phone(login_data.phone, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="מספר טלפון או סיסמה שגויים"
        )
    
    full_user = get_user_by_id(user["id"])
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="משתמש לא נמצא"
        )
    
    token = create_user_access_token(user["id"], user["phone"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse(**{k: v for k, v in full_user.items() if k != "password_hash"})
    }


@app.post("/api/auth/request-phone-code")
@limiter.limit("5/minute")
async def api_request_phone_code(request: Request, data: RequestPhoneCode):
    """Request OTP sent to phone. Backend validates and rate-limits."""
    try:
        out = request_phone_code(data.phone)
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/verify-phone-code")
@limiter.limit("10/minute")
async def api_verify_phone_code(request: Request, data: VerifyPhoneCode):
    """Verify phone OTP and return access token."""
    try:
        user_dict = verify_phone_code(data.phone, data.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_user_access_token(user_dict["id"], user_dict["phone"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse(**user_dict)
    }


@app.post("/api/auth/request-email-code")
@limiter.limit("5/minute")
async def api_request_email_code(request: Request, data: RequestEmailCode):
    """Request OTP sent to email. Backend validates and rate-limits."""
    try:
        out = request_email_code(data.email)
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/verify-email-code")
@limiter.limit("10/minute")
async def api_verify_email_code(request: Request, data: VerifyEmailCode):
    """Verify email OTP and return access token."""
    try:
        user_dict = verify_email_code(data.email, data.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_user_access_token(user_dict["id"], user_dict["phone"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse(**user_dict)
    }


# ========== User Profile Endpoints ==========

@app.get("/api/user/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile."""
    user = get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return UserResponse(**{k: v for k, v in user.items() if k != "password_hash"})


@app.put("/api/user/me", response_model=UserResponse)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user profile."""
    try:
        updated = update_user(
            current_user["id"],
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            avatar_url=user_data.avatar_url
        )
        return UserResponse(**{k: v for k, v in updated.items() if k != "password_hash"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/user/me/change-password")
async def change_user_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password."""
    try:
        change_password(
            current_user["id"],
            password_data.current_password,
            password_data.new_password
        )
        return {"success": True, "message": "סיסמה עודכנה בהצלחה"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/user/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload avatar image. Validates type (images only, no executables)."""
    from data.upload_config import AVATAR_MAX_BYTES
    content = await file.read(AVATAR_MAX_BYTES + 1)
    try:
        ext, _ = validate_avatar_file(content, file.filename or "", file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    path = save_avatar(content, ext, current_user["id"])
    try:
        updated = update_user(current_user["id"], avatar_url=path)
        return UserResponse(**{k: v for k, v in updated.items() if k != "password_hash"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/user/me/locked-settings")
async def get_my_locked_settings(current_user: dict = Depends(get_current_user)):
    """Settings the admin locked for the current user (so the UI can show them as locked)."""
    return {"locked_settings": get_locked_settings(current_user["id"])}


# ---------- Helper: effective user when admin manages a client ----------
def _effective_user_id(current_user: dict, managed_user_id: Optional[int] = None) -> int:
    """If admin and managed_user_id provided, return it; else current user. Raises 403 if non-admin passes managed_user_id."""
    if managed_user_id is not None:
        if not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="גישה נדחתה")
        return managed_user_id
    return current_user["id"]


def _can_access_profile(profile: dict, current_user: dict, managed_user_id: Optional[int]) -> bool:
    """True if current user can access this profile (owner or admin managing that user)."""
    if profile["user_id"] == current_user["id"]:
        return True
    if current_user.get("is_admin") and managed_user_id is not None and profile["user_id"] == managed_user_id:
        return True
    return False


LOCKABLE_SETTINGS = ("profile_name", "profile_mode", "rules")


def _ensure_not_locked(current_user: dict, *keys: str) -> None:
    """
    Server-side enforcement of admin locks. The UI only greys out buttons; without this check any
    user could call the API directly and loosen their own filter.
    profile_mode also covers creating/deleting profiles and schedules: a second, laxer profile
    activated by a schedule would bypass a locked mode.
    """
    if current_user.get("is_admin") is True:
        return
    locked = set(get_locked_settings(current_user["id"]))
    hit = [k for k in keys if k in locked]
    if hit:
        raise HTTPException(status_code=403, detail="הגדרה זו ננעלה על ידי ההנהלה")


# ========== Profile Endpoints ==========

@app.get("/api/profiles", response_model=List[ProfileResponse])
async def list_profiles(
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None, description="When admin: manage this user's profiles"),
):
    """Get all profiles for current user (or managed user when admin)."""
    uid = _effective_user_id(current_user, managed_user_id)
    profiles = get_user_profiles(uid)
    return [ProfileResponse(**p) for p in profiles]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile_endpoint(
    profile_data: ProfileCreate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Create a new profile (for current user or managed user when admin)."""
    uid = _effective_user_id(current_user, managed_user_id)
    _ensure_not_locked(current_user, "profile_mode")
    try:
        profile = create_profile(uid, profile_data.name, profile_data.mode)
        await manager.broadcast({"type": "profile_created", "profile_id": profile["id"]})
        return ProfileResponse(**profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile_endpoint(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Get a single profile."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    return ProfileResponse(**profile)


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile_endpoint(
    profile_id: int,
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Update a profile."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    if profile_data.name is not None and profile_data.name != profile.get("name"):
        _ensure_not_locked(current_user, "profile_name")
    if profile_data.mode is not None and profile_data.mode != profile.get("mode"):
        _ensure_not_locked(current_user, "profile_mode")
    
    try:
        updated = update_profile(
            profile_id,
            name=profile_data.name,
            mode=profile_data.mode
        )
        sync_uid = managed_user_id if (current_user.get("is_admin") and managed_user_id is not None) else current_user["id"]
        sync_crm_rules_to_core(sync_uid)
        await manager.broadcast({"type": "profile_updated", "profile_id": profile_id})
        return ProfileResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_endpoint(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Delete a profile."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    _ensure_not_locked(current_user, "profile_mode")
    
    deleted = delete_profile(profile_id)
    if deleted:
        await manager.broadcast({"type": "profile_deleted", "profile_id": profile_id})
    else:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")


# ========== Rule Endpoints ==========

@app.get("/api/profiles/{profile_id}/rules", response_model=List[RuleResponse])
async def list_rules(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Get all rules for a profile."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    rules = get_profile_rules(profile_id)
    return [RuleResponse(**r) for r in rules]


@app.post("/api/profiles/{profile_id}/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_endpoint(
    profile_id: int,
    rule_data: RuleCreate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Create a new rule."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    _ensure_not_locked(current_user, "rules")
    
    try:
        rule = create_rule(
            profile_id,
            rule_data.url,
            rule_data.action,
            "*",
            rule_data.include_subdomains,
            tags=rule_data.tags,
        )
        sync_uid = managed_user_id if (current_user.get("is_admin") and managed_user_id is not None) else current_user["id"]
        sync_crm_rules_to_core(sync_uid)
        await manager.broadcast({"type": "rule_created", "profile_id": profile_id, "rule_id": rule["id"]})
        return RuleResponse(**rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rules/{rule_id}", response_model=RuleResponse)
async def get_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Get a single rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    return RuleResponse(**rule)


@app.put("/api/rules/{rule_id}", response_model=RuleResponse)
async def update_rule_endpoint(
    rule_id: int,
    rule_data: RuleUpdate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Update a rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    _ensure_not_locked(current_user, "rules")
    
    try:
        updated = update_rule(
            rule_id,
            url=rule_data.url,
            action=rule_data.action,
            include_subdomains=rule_data.include_subdomains,
            tags=rule_data.tags,
        )
        sync_uid = managed_user_id if (current_user.get("is_admin") and managed_user_id is not None) else current_user["id"]
        sync_crm_rules_to_core(sync_uid)
        await manager.broadcast({"type": "rule_updated", "rule_id": rule_id, "profile_id": rule["profile_id"]})
        return RuleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Delete a rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    _ensure_not_locked(current_user, "rules")
    
    deleted = delete_rule(rule_id)
    if deleted:
        sync_uid = managed_user_id if (current_user.get("is_admin") and managed_user_id is not None) else current_user["id"]
        sync_crm_rules_to_core(sync_uid)
        await manager.broadcast({"type": "rule_deleted", "rule_id": rule_id, "profile_id": rule["profile_id"]})
    else:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")


@app.get("/api/profiles/{profile_id}/rules/export")
async def export_rules_csv(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Export rules as CSV. Same format as import (url, action, include_subdomains, tags)."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    rules = get_profile_rules(profile_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["url", "action", "include_subdomains", "tags"])
    for r in rules:
        url = (r.get("domain_pattern") or "") + (r.get("path_pattern") or "/")
        writer.writerow([
            url,
            r.get("action", "block"),
            "true" if r.get("include_subdomains") else "false",
            ",".join(r.get("tags") or []),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rules.csv"},
    )


def _validate_rule_row(row: dict) -> Optional[str]:
    """Validate a rule row (like RuleCreate). Returns error message or None."""
    url = (row.get("url") or "").strip()
    if not url:
        return "חסר שדה url"
    from .services import parse_url
    try:
        domain, path, _ = parse_url(url)
        if not domain:
            return "כתובת לא תקינה"
    except Exception:
        return "כתובת לא תקינה"
    action = (row.get("action") or "block").strip().lower()
    if action not in ("allow", "block"):
        return "action חייב allow או block"
    return None


@app.post("/api/profiles/{profile_id}/rules/import")
async def import_rules_csv(
    profile_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Import rules from CSV. Columns: url, action, include_subdomains, tags. Validates like add rule."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    _ensure_not_locked(current_user, "rules")
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    errors = []
    for i, row in enumerate(rows):
        err = _validate_rule_row(row)
        if err:
            errors.append({"line": i + 2, "error": err})
    if errors:
        raise HTTPException(status_code=400, detail={"message": "שגיאות בתוכן הקובץ", "errors": errors})
    created = 0
    for row in rows:
        url = (row.get("url") or "").strip()
        action = (row.get("action") or "block").strip().lower()
        inc = (row.get("include_subdomains") or "false").strip().lower() in ("true", "1", "yes")
        tags_str = (row.get("tags") or "").strip()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
        try:
            create_rule(profile_id, url, action, "*", inc, tags=tags)
            created += 1
        except ValueError as e:
            errors.append({"line": "?", "error": str(e)})
    if errors:
        raise HTTPException(status_code=400, detail={"message": "שגיאות ביצירת כללים", "errors": errors})
    sync_uid = managed_user_id if (current_user.get("is_admin") and managed_user_id is not None) else current_user["id"]
    sync_crm_rules_to_core(sync_uid)
    return {"imported": created}


# ========== Tag Rules Endpoints (כללי תגיות) ==========

@app.get("/api/tag-rules", response_model=List[TagRuleResponse])
async def list_tag_rules(current_user: dict = Depends(get_current_user)):
    """Get all tag rules."""
    rules = get_tag_rules(enabled_only=False)
    return [TagRuleResponse(**r) for r in rules]


@app.post("/api/tag-rules", response_model=TagRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_tag_rule_endpoint(
    data: TagRuleCreate,
    current_user: dict = Depends(get_current_admin),
):
    """Create a tag rule (e.g. tag=ממכר -> block). Admin only: tag rules are global – they affect every user."""
    try:
        rule = add_tag_rule(data.tag, data.state, data.enabled, created_by_user_id=current_user.get("id"))
        sync_crm_rules_to_core(current_user["id"])
        return TagRuleResponse(**rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/tag-rules/{rule_id}", response_model=TagRuleResponse)
async def update_tag_rule_endpoint(
    rule_id: int,
    data: TagRuleUpdate,
    current_user: dict = Depends(get_current_admin),
):
    """Update a tag rule."""
    try:
        updated = update_tag_rule(
            rule_id,
            tag=data.tag,
            state=data.state,
            enabled=data.enabled,
            updated_by_user_id=current_user.get("id"),
        )
        sync_crm_rules_to_core(current_user["id"])
        return TagRuleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/tag-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(get_current_admin),
):
    """Delete a tag rule."""
    deleted = delete_tag_rule(rule_id)
    if deleted:
        sync_crm_rules_to_core(current_user["id"])
    else:
        raise HTTPException(status_code=404, detail="כלל תגית לא נמצא")


# ========== Schedule Endpoints ==========

@app.get("/api/profiles/{profile_id}/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Get all schedules for a profile."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    schedules = get_profile_schedules(profile_id)
    return [ScheduleResponse(**s) for s in schedules]


@app.post("/api/profiles/{profile_id}/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule_endpoint(
    profile_id: int,
    schedule_data: ScheduleCreate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Create a new schedule."""
    profile = get_profile(profile_id)
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    _ensure_not_locked(current_user, "profile_mode")
    
    try:
        schedule = create_schedule(
            profile_id,
            schedule_data.days,
            schedule_data.from_time,
            schedule_data.to_time
        )
        sync_crm_rules_to_core(profile["user_id"])
        await manager.broadcast({"type": "schedule_created", "profile_id": profile_id, "schedule_id": schedule["id"]})
        return ScheduleResponse(**schedule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_endpoint(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Update a schedule."""
    schedule = get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    profile = get_profile(schedule["profile_id"])
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    _ensure_not_locked(current_user, "profile_mode")
    
    try:
        updated = update_schedule(
            schedule_id,
            days=schedule_data.days,
            from_time=schedule_data.from_time,
            to_time=schedule_data.to_time
        )
        sync_crm_rules_to_core(profile["user_id"])
        await manager.broadcast({"type": "schedule_updated", "schedule_id": schedule_id, "profile_id": schedule["profile_id"]})
        return ScheduleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_endpoint(
    schedule_id: int,
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """Delete a schedule."""
    schedule = get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    profile = get_profile(schedule["profile_id"])
    if not profile or not _can_access_profile(profile, current_user, managed_user_id):
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    _ensure_not_locked(current_user, "profile_mode")
    
    deleted = delete_schedule(schedule_id)
    if deleted:
        sync_crm_rules_to_core(profile["user_id"])
        await manager.broadcast({"type": "schedule_deleted", "schedule_id": schedule_id, "profile_id": schedule["profile_id"]})
    else:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")


# ========== WebSocket Endpoints ==========

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for realtime updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle client messages
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/traffic")
async def websocket_traffic(websocket: WebSocket):
    """WebSocket for live traffic recording log. Client sends ?token=Bearer%20<access_token>. Server pushes new log entries."""
    token = websocket.query_params.get("token") or ""
    if token.startswith("Bearer "):
        token = token[7:].strip()
    if not token:
        await websocket.close(code=4001)
        return
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=4001)
        return
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        await websocket.close(code=4001)
        return
    user = get_user_by_id(user_id)
    if not user:
        await websocket.close(code=4001)
        return
    await websocket.accept()
    from core.policy.policy_database import get_active_traffic_session_id, get_traffic_log
    session_id = get_active_traffic_session_id(user_id)
    if session_id is None:
        await websocket.send_json({"type": "no_session", "message": "אין הקלטה פעילה"})
        await websocket.close()
        return
    await websocket.send_json({"type": "session", "session_id": session_id})
    last_count = 0
    try:
        while True:
            await asyncio.sleep(1.2)
            entries = await asyncio.to_thread(get_traffic_log, session_id, user_id)
            n = len(entries)
            if n > last_count:
                new_entries = entries[last_count:]
                last_count = n
                await websocket.send_json({"type": "traffic_log", "entries": new_entries})
    except WebSocketDisconnect:
        pass


# ========== Resolver Integration Endpoints ==========

@app.get("/api/resolver/rules")
async def get_resolver_rules(current_user: dict = Depends(get_current_user)):
    """
    Get rules in format expected by URLPolicyResolver.
    This endpoint integrates with the existing resolver system.
    """
    rules = get_rules_for_resolver(current_user["id"])
    return {"rules": rules}


@app.get("/api/resolver/rules/all")
async def get_all_resolver_rules(admin: dict = Depends(get_current_admin)):
    """Get all enabled rules of the system-default profile. Admin only."""
    rules = get_all_enabled_rules_for_resolver()
    return {"rules": rules}


def _get_core_resolver_state(user_id: Optional[int] = None):
    """Read profile mode and DB path from core. When user_id is set, return that user's mode (for bound connections)."""
    try:
        from core.policy.policy_database import get_profile_mode, get_core_resolver_db_path
        mode = get_profile_mode(user_id) if user_id is not None else get_profile_mode()
        return {"core_mode": mode, "core_db_path": get_core_resolver_db_path()}
    except Exception as e:
        return {"core_mode": None, "core_db_path": None, "error": str(e)}


# ========== Admin: Filter Switches (הפעלה/כיבוי סינונים גלובלית) ==========

@app.get("/api/admin/filter-switches")
async def admin_get_filter_switches(admin: dict = Depends(get_current_admin)):
    """Get global filter switches (url_policy, text_filter, image_filter, embedded_image_filter). Admin only."""
    from core.policy.policy_database import get_filter_switches
    return get_filter_switches()


@app.put("/api/admin/filter-switches")
async def admin_update_filter_switches(
    body: dict,
    admin: dict = Depends(get_current_admin),
):
    """Update global filter switches. Body: { "url_policy": true, "text_filter": false, ... }. Admin only."""
    from core.policy.policy_database import set_filter_switches, FILTER_SWITCH_KEYS
    allowed = set(FILTER_SWITCH_KEYS)
    switches = {}
    for k, v in (body or {}).items():
        if k in allowed and isinstance(v, bool):
            switches[k] = v
    if not switches:
        raise HTTPException(status_code=400, detail="נא לשלוח לפחות מתג אחד (url_policy, text_filter, image_filter, embedded_image_filter, file_download_filter, surf_widget)")
    set_filter_switches(switches, updated_by_user_id=admin.get("id"))
    from core.policy.policy_database import get_filter_switches
    return get_filter_switches()


@app.post("/api/resolver/sync")
async def sync_resolver_to_core(
    current_user: dict = Depends(get_current_user),
    managed_user_id: Optional[int] = Query(None),
):
    """
    Sync the currently active profile (with schedule) and its rules to core policy DB.
    When admin passes managed_user_id, sync that user's active profile.
    """
    uid = _effective_user_id(current_user, managed_user_id)
    sync_crm_rules_to_core(uid)
    core = _get_core_resolver_state()
    return {"status": "ok", "message": "סנכרון הושלם", **core}


@app.get("/api/resolver/core-mode")
async def get_core_resolver_mode(current_user: dict = Depends(get_current_user)):
    """
    Return the profile mode currently stored in core (what the proxy uses).
    Syncs this user's rules to core first so the proxy and UI stay in sync for bound connections.
    """
    sync_crm_rules_to_core(current_user["id"], set_default=False)
    return _get_core_resolver_state(current_user["id"])


@app.get("/api/resolver/active")
async def get_active_resolver_state(current_user: dict = Depends(get_current_user)):
    """
    Get the currently active profile and its mode for the current user (with schedule).
    Syncs this user's rules to core first so the proxy uses the same state for their bound connections.
    """
    sync_crm_rules_to_core(current_user["id"], set_default=False)
    from .resolver_integration import get_active_profile_id, get_system_active_profile_and_rules
    profile_id = get_active_profile_id(current_user["id"])
    if not profile_id:
        return {"profile_id": None, "mode": "whitelist", "rules": [], "tag_rules": []}
    mode, rules, tag_rules = get_system_active_profile_and_rules(user_id=current_user["id"])
    profile = get_profile(profile_id)
    return {
        "profile_id": profile_id,
        "profile_name": profile.get("name") if profile else None,
        "mode": mode,
        "rules": rules,
        "tag_rules": tag_rules,
    }


@app.post("/api/resolver/test-url")
async def resolver_test_url(
    body: ResolverTestUrlBody,
    current_user: dict = Depends(get_current_user),
):
    """
    Run the same URLPolicyResolver used by the proxy on a given URL.
    Returns state (allow/block/review) and the matching rule if any.
    """
    from core.policy.policy_loader import get_policy_resolver
    from core.policy.policy_database import get_profile_mode
    from core.policy.url_policy_resolver import URLPolicyResolverError

    url = body.url.strip()
    if "://" not in url:
        url = "https://" + url

    try:
        resolver = get_policy_resolver()
        result = resolver.resolve(url, body.type)
    except URLPolicyResolverError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result is None:
        return {"state": "review", "rule": None, "default_mode": get_profile_mode()}

    state = result.get("state", "block")
    rule = result if result.get("domain") else None
    return {"state": state, "rule": rule, "default_mode": get_profile_mode()}


# ========== Rule Requests (user requests for admin to approve) ==========
# Incoming requests are only from logged-in users (no anonymous from-blocked-page).


# Surf widget admin actions.
# The old design injected a signed token for the bound user into every page the user browsed; any script on
# that third-party page (ads, analytics) could read it and, for an admin, open sites in the global whitelist.
# Now the widget contains only links: admin actions happen on a CRM page with the admin's normal login and an
# explicit confirmation click (so merely opening a crafted link cannot change rules).

_SURF_SCOPES = ("domain_only", "domain_and_subdomains", "exact_url")


def _surf_rule_display(rule: dict) -> str:
    domain = str(rule.get("domain_pattern") or "").strip()
    path = str(rule.get("path_pattern") or "/").strip() or "/"
    action_heb = "חסימה" if rule.get("action") == "block" else "פתיחה"
    if domain.startswith("*."):
        scope_heb = "דומיין + תת-דומיינים"
    elif path != "/":
        scope_heb = "כתובת ישירה"
    else:
        scope_heb = "רק הדומיין"
    return f"{action_heb}: {domain}{path if path != '/' else ''} ({scope_heb})"


@app.post("/api/admin/surf-quick-rule")
async def admin_surf_quick_rule(request: Request, admin: dict = Depends(get_current_admin)):
    """Create or update a global rule from the surf widget: action allow/block, scope domain_only/domain_and_subdomains/exact_url."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    url = (body.get("url") or "").strip()
    action = (body.get("action") or "").strip().lower()
    scope = (body.get("scope") or "").strip().lower()
    if not url:
        raise HTTPException(status_code=400, detail="חסר url")
    if action not in ("allow", "block"):
        raise HTTPException(status_code=400, detail="action חייב להיות allow או block")
    if scope not in _SURF_SCOPES:
        raise HTTPException(status_code=400, detail="scope לא תקין")
    try:
        rule = create_or_update_global_rule_surf(url=url, action=action, scope=scope, updated_by_user_id=admin.get("id"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sync_crm_rules_to_core(None)
    return {
        "success": True,
        "rule_display": _surf_rule_display(rule),
        "rule": {
            "domain_pattern": rule.get("domain_pattern"),
            "path_pattern": rule.get("path_pattern") or "/",
            "action": rule.get("action"),
        },
    }


@app.post("/api/rule-requests", response_model=RuleRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_request(
    data: RuleRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a rule request (open, change, or file). Only pending; admin approves later."""
    try:
        req = add_rule_request(
            user_id=current_user["id"],
            request_type=data.request_type,
            url=data.url,
            domain_pattern=data.domain_pattern,
            path_pattern=data.path_pattern,
            action=data.action,
            include_subdomains=data.include_subdomains,
            tags=data.tags,
            request_url=getattr(data, "request_url", None),
            notes=data.notes,
        )
        out = dict(req)
        out["include_subdomains"] = bool(req.get("include_subdomains"))
        return RuleRequestResponse(**out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rule-requests")
async def list_rule_requests_endpoint(
    current_user: dict = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    request_type_filter: Optional[str] = Query(None),
    user_id_filter: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List rule requests with filters, search, sort and pagination. User: own only. Admin: all. Returns requests, total."""
    if current_user.get("is_admin") and user_id_filter is None:
        uid_filter = None
    elif current_user.get("is_admin"):
        uid_filter = user_id_filter
    else:
        uid_filter = current_user["id"]
    rows, total = list_rule_requests(
        status_filter=status_filter,
        request_type_filter=request_type_filter,
        user_id_filter=uid_filter,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    out = []
    for r in rows:
        user = get_user_by_id(r["user_id"])
        user_phone = user.get("phone") if user else None
        if user_phone is None and r["user_id"]:
            user_phone = "—"
        out.append(RuleRequestResponse(
            id=r["id"],
            user_id=r["user_id"],
            request_type=r["request_type"],
            url=r.get("url"),
            domain_pattern=r.get("domain_pattern"),
            path_pattern=r.get("path_pattern"),
            action=r.get("action"),
            include_subdomains=bool(r.get("include_subdomains")),
            tags=r.get("tags"),
            status=r["status"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            user_phone=user_phone,
            approved_rule_id=r.get("approved_rule_id"),
            approved_profile_id=r.get("approved_profile_id"),
            is_from_blocked_page=False,
            request_url=r.get("request_url"),
            notes=r.get("notes"),
            resolved_by_user_id=r.get("resolved_by_user_id"),
            resolved_by_name=r.get("resolved_by_name"),
            text_filter_enabled=r.get("text_filter_enabled"),
            image_filter_enabled=r.get("image_filter_enabled"),
            file_filter_enabled=r.get("file_filter_enabled"),
        ))
    return {"requests": out, "total": total}


@app.get("/api/rule-requests/{request_id}", response_model=RuleRequestResponse)
async def get_rule_request_endpoint(
    request_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get a single rule request. User: own only. Admin: any."""
    req = get_rule_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="בקשה לא נמצאה")
    if req["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=404, detail="בקשה לא נמצאה")
    user = get_user_by_id(req["user_id"])
    user_phone = user.get("phone") if user else None
    return RuleRequestResponse(
        id=req["id"],
        user_id=req["user_id"],
        request_type=req["request_type"],
        url=req.get("url"),
        domain_pattern=req.get("domain_pattern"),
        path_pattern=req.get("path_pattern"),
        action=req.get("action"),
        include_subdomains=bool(req.get("include_subdomains")),
        tags=req.get("tags"),
        status=req["status"],
        created_at=req["created_at"],
        updated_at=req["updated_at"],
        user_phone=user_phone,
        approved_rule_id=req.get("approved_rule_id"),
        approved_profile_id=req.get("approved_profile_id"),
        is_from_blocked_page=False,
        request_url=req.get("request_url"),
        notes=req.get("notes"),
        resolved_by_user_id=req.get("resolved_by_user_id"),
        resolved_by_name=req.get("resolved_by_name"),
        text_filter_enabled=req.get("text_filter_enabled"),
        image_filter_enabled=req.get("image_filter_enabled"),
        file_filter_enabled=req.get("file_filter_enabled"),
    )


@app.get("/api/admin/all-profiles")
async def admin_list_all_profiles(admin: dict = Depends(get_current_admin)):
    """List all profiles with user phone (admin only)."""
    profiles = list_all_profiles_for_admin()
    return {"profiles": profiles}


@app.put("/api/rule-requests/{request_id}", response_model=RuleRequestResponse)
async def update_rule_request_endpoint(
    request_id: int,
    body: RuleRequestUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a pending or rejected rule request. Owner or admin."""
    req = get_rule_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="בקשה לא נמצאה")
    if req["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה")
    try:
        updated = update_rule_request(
            request_id,
            url=body.url,
            action=body.action,
            include_subdomains=body.include_subdomains,
            tags=body.tags,
            text_filter_enabled=body.text_filter_enabled,
            image_filter_enabled=body.image_filter_enabled,
            file_filter_enabled=body.file_filter_enabled,
        )
        user = get_user_by_id(updated["user_id"])
        user_phone = user.get("phone") if user else None
        return RuleRequestResponse(
            id=updated["id"],
            user_id=updated["user_id"],
            request_type=updated["request_type"],
            url=updated.get("url"),
            domain_pattern=updated.get("domain_pattern"),
            path_pattern=updated.get("path_pattern"),
            action=updated.get("action"),
            include_subdomains=bool(updated.get("include_subdomains")),
            tags=updated.get("tags"),
            status=updated["status"],
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
            user_phone=user_phone,
            approved_rule_id=updated.get("approved_rule_id"),
            approved_profile_id=updated.get("approved_profile_id"),
            is_from_blocked_page=False,
            request_url=updated.get("request_url"),
            notes=updated.get("notes"),
            resolved_by_user_id=updated.get("resolved_by_user_id"),
            resolved_by_name=updated.get("resolved_by_name"),
            text_filter_enabled=updated.get("text_filter_enabled"),
            image_filter_enabled=updated.get("image_filter_enabled"),
            file_filter_enabled=updated.get("file_filter_enabled"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _rule_request_to_response(req: dict) -> RuleRequestResponse:
    """Build RuleRequestResponse from request dict, including user_phone."""
    user = get_user_by_id(req["user_id"])
    user_phone = user.get("phone") if user else None
    return RuleRequestResponse(
        id=req["id"],
        user_id=req["user_id"],
        request_type=req["request_type"],
        url=req.get("url"),
        domain_pattern=req.get("domain_pattern"),
        path_pattern=req.get("path_pattern"),
        action=req.get("action"),
        include_subdomains=bool(req.get("include_subdomains")),
        tags=req.get("tags"),
        status=req["status"],
        created_at=req["created_at"],
        updated_at=req["updated_at"],
        user_phone=user_phone,
        approved_rule_id=req.get("approved_rule_id"),
        approved_profile_id=req.get("approved_profile_id"),
        is_from_blocked_page=False,
        request_url=req.get("request_url"),
        notes=req.get("notes"),
        resolved_by_user_id=req.get("resolved_by_user_id"),
        resolved_by_name=req.get("resolved_by_name"),
        text_filter_enabled=req.get("text_filter_enabled"),
        image_filter_enabled=req.get("image_filter_enabled"),
        file_filter_enabled=req.get("file_filter_enabled"),
    )


@app.post("/api/admin/rule-requests/{request_id}/approve")
async def approve_rule_request_endpoint(
    request_id: int,
    body: RuleRequestApprove,
    admin: dict = Depends(get_current_admin),
):
    """Admin approves a request: create or update rule in global list. May return status=conflict if rule exists with different content."""
    try:
        result = approve_rule_request(
            request_id,
            profile_id=body.profile_id,
            resolved_by_user_id=admin.get("id"),
            force_update=getattr(body, "force_update", False),
            skip_rule_update=getattr(body, "skip_rule_update", False),
        )
        req = result["request"]
        if result.get("conflict"):
            return {
                "status": "conflict",
                "existing_rule": result["existing_rule"],
                "proposed_rule": result["proposed_rule"],
                "request": _rule_request_to_response(req),
            }
        return {
            "status": "approved",
            "request": _rule_request_to_response(req),
            "already_existed_identical": result.get("already_existed_identical", False),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("approve_rule_request failed: %s", e)
        raise HTTPException(status_code=500, detail="שגיאה בשרת באישור הבקשה")


@app.post("/api/admin/rule-requests/{request_id}/reject")
async def reject_rule_request_endpoint(
    request_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Admin rejects a request."""
    try:
        req = reject_rule_request(request_id, resolved_by_user_id=admin.get("id"))
        return {"status": "rejected", "request": RuleRequestResponse(**{**req, "include_subdomains": bool(req.get("include_subdomains"))})}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/rule-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_request_endpoint(
    request_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a pending request. Owner or admin."""
    req = get_rule_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="בקשה לא נמצאה")
    if req["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה")
    deleted = delete_rule_request(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="בקשה לא נמצאה")


# ========== Support tickets (פניות משתמשים) ==========

@app.post("/api/support/upload")
async def support_upload_endpoint(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a file for support ticket/reply. Returns { url, name }."""
    from data.upload_config import SUPPORT_MAX_BYTES
    try:
        content = await file.read(SUPPORT_MAX_BYTES + 1)
        info = save_support_file(content, file.filename or "file", current_user["id"])
        return info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/support/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_support_ticket_endpoint(
    data: SupportTicketCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new support ticket (subject + content, optional attachments). Optional attached_request: creates rule request and links to ticket."""
    if not (data.content or (data.attached_request is not None)):
        raise HTTPException(status_code=400, detail="נא להזין תוכן או לצרף בקשה לפתיחה")
    try:
        attachments = [{"name": a.name, "url": a.url} for a in (data.attachments or [])]
        rid = None
        snapshot_json = None
        if data.attached_request:
            req = add_rule_request(
                user_id=current_user["id"],
                request_type=data.attached_request.request_type,
                url=data.attached_request.url,
                domain_pattern=data.attached_request.domain_pattern,
                path_pattern=data.attached_request.path_pattern,
                action=data.attached_request.action,
                include_subdomains=data.attached_request.include_subdomains or False,
                tags=data.attached_request.tags,
                request_url=getattr(data.attached_request, "request_url", None),
                notes=data.attached_request.notes,
            )
            rid = req["id"]
            snapshot_json = json.dumps(data.attached_request.model_dump(), ensure_ascii=False)
        ticket = create_support_ticket(
            user_id=current_user["id"],
            subject=data.subject,
            content=data.content or "",
            attachments=attachments or None,
            attached_rule_request_id=rid,
            request_snapshot_for_client=snapshot_json,
        )
        return _support_ticket_to_response(ticket)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _support_ticket_to_response(ticket: dict, user: Optional[dict] = None) -> SupportTicketResponse:
    """Build SupportTicketResponse from ticket dict. If user not provided, fetches by ticket['user_id']."""
    u = user if user is not None else get_user_by_id(ticket["user_id"])
    return SupportTicketResponse(
        id=ticket["id"],
        user_id=ticket["user_id"],
        subject=ticket["subject"],
        content=ticket.get("content", ""),
        created_at=ticket["created_at"],
        updated_at=ticket["updated_at"],
        content_preview=ticket.get("content_preview"),
        user_first_name=u.get("first_name") if u else None,
        user_last_name=u.get("last_name") if u else None,
        user_phone=u.get("phone") if u else None,
        user_avatar_url=u.get("avatar_url") if u else None,
        replies_count=ticket.get("replies_count"),
        unread_replies_count=ticket.get("unread_replies_count"),
        attachments=ticket.get("attachments"),
        attached_rule_request_id=ticket.get("attached_rule_request_id"),
        request_snapshot_for_client=ticket.get("request_snapshot_for_client"),
        attached_request_status=ticket.get("attached_request_status"),
    )


@app.get("/api/support/tickets")
async def list_support_tickets_endpoint(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_order: str = Query("desc"),
    search: Optional[str] = Query(None),
    scope: Optional[str] = Query(None, description="mine = רק הפניות שלי (גם לאדמין); all או לא מועבר = לאדמין כל הפניות"),
    read_filter: Optional[str] = Query(None, description="admin: all | unread | read"),
    user_id: Optional[int] = Query(None, description="admin: filter by ticket owner user_id"),
):
    """List support tickets. scope=mine: only current user's tickets (also for admin). Otherwise: user gets own, admin gets all."""
    if scope == "mine":
        rows, total = list_my_support_tickets(
            user_id=current_user["id"], page=page, page_size=page_size, sort_order=sort_order
        )
    elif current_user.get("is_admin"):
        rows, total = list_all_support_tickets(
            page=page, page_size=page_size, sort_order=sort_order, search=search, viewer_id=current_user["id"],
            read_filter=read_filter if read_filter in ("unread", "read") else None,
            user_id_filter=user_id,
        )
    else:
        rows, total = list_my_support_tickets(
            user_id=current_user["id"], page=page, page_size=page_size, sort_order=sort_order
        )
    out = [
        SupportTicketResponse(
            id=r["id"],
            user_id=r["user_id"],
            subject=r["subject"],
            content=r.get("content", ""),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            content_preview=r.get("content_preview"),
            user_first_name=r.get("user_first_name"),
            user_phone=r.get("user_phone"),
            replies_count=r.get("replies_count", 0),
            unread_replies_count=r.get("unread_replies_count", 0),
            unread_support_replies_for_owner=r.get("unread_support_replies_for_owner"),
            unread_user_replies_for_admin=r.get("unread_user_replies_for_admin"),
            attached_rule_request_id=r.get("attached_rule_request_id"),
            request_snapshot_for_client=r.get("request_snapshot_for_client"),
            attached_request_status=r.get("attached_request_status"),
        )
        for r in rows
    ]
    return {"tickets": out, "total": total}


@app.get("/api/support/tickets/users")
async def list_support_ticket_users_endpoint(current_user: dict = Depends(get_current_user)):
    """List users that have at least one support ticket (for admin filter dropdown). Admin only."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה")
    users = list_support_ticket_user_ids()
    return {"users": users}


@app.post("/api/support/tickets/bulk-delete")
async def bulk_delete_support_tickets_endpoint(
    body: SupportTicketsBulkDeleteBody,
    current_user: dict = Depends(get_current_user),
):
    """Delete multiple support tickets. Admin only. Returns number deleted."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה")
    deleted = delete_support_tickets_bulk(body.ticket_ids)
    return {"deleted": deleted}


@app.get("/api/support/stats")
async def support_stats_endpoint(current_user: dict = Depends(get_current_user)):
    """Return counts for sidebar: tickets_with_replies = my tickets with unread replies; admin = all with unread (for owner)."""
    tickets_with_replies = count_my_tickets_with_unread_replies(current_user["id"])
    out = {"tickets_with_replies": tickets_with_replies}
    if current_user.get("is_admin"):
        out["admin_tickets_with_replies"] = count_all_tickets_with_unread_for_admin_group()
    return out


@app.get("/api/support/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_support_ticket_endpoint(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get a single support ticket. User: own only. Admin: any."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    if ticket["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    return _support_ticket_to_response(ticket)


@app.get("/api/support/tickets/{ticket_id}/replies", response_model=List[SupportReplyResponse])
async def list_support_replies_endpoint(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
):
    """List replies for a ticket. User: own ticket only. Admin: any."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    if ticket["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    # Mark ticket as read for this viewer
    mark_support_ticket_read(ticket_id, current_user["id"])
    # For admins, also update a shared "admin group" view (user_id=0) so unread user replies are shared across all managers
    if current_user.get("is_admin"):
        mark_support_ticket_read(ticket_id, 0)
    replies = list_support_replies(ticket_id, viewer_id=current_user["id"])
    return [
        SupportReplyResponse(
            id=r["id"],
            ticket_id=r["ticket_id"],
            author_id=r["author_id"],
            content=r["content"],
            created_at=r["created_at"],
            author_first_name=r.get("author_first_name"),
            author_last_name=r.get("author_last_name"),
            author_avatar_url=r.get("author_avatar_url"),
            is_unread=r.get("is_unread", False),
            attachments=r.get("attachments"),
            attached_request_snapshot=r.get("attached_request_snapshot"),
            is_support_reply=r.get("is_support_reply", False),
        )
        for r in replies
    ]


@app.post("/api/support/tickets/{ticket_id}/replies", response_model=SupportReplyResponse, status_code=status.HTTP_201_CREATED)
async def create_support_reply_endpoint(
    ticket_id: int,
    data: SupportReplyCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a reply to a ticket. User: own ticket. Admin: any. Content is markdown."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    if ticket["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה להגיב על פנייה זו")
    if not (data.content or (data.attachments and len(data.attachments) > 0) or ((data.attached_request_snapshot or "").strip())):
        raise HTTPException(status_code=400, detail="נא להזין תוכן, לצרף קובץ או לצרף עותק ערוך של הבקשה")
    try:
        attachments = [{"name": a.name, "url": a.url} for a in (data.attachments or [])]
        # נשמר לפי מקום השליחה (הלקוח שולח): פניות שלי = תגובת משתמש, פניות שהתקבלו = תגובת תמיכה
        is_support_reply = data.is_support_reply if data.is_support_reply is not None else False
        reply = add_support_reply(
            ticket_id=ticket_id,
            author_id=current_user["id"],
            content=data.content or "",
            attachments=attachments or None,
            attached_request_snapshot=data.attached_request_snapshot.strip() if data.attached_request_snapshot else None,
            is_support_reply=is_support_reply,
        )
        return SupportReplyResponse(
            id=reply["id"],
            ticket_id=reply["ticket_id"],
            author_id=reply["author_id"],
            content=reply["content"],
            created_at=reply["created_at"],
            author_first_name=reply.get("author_first_name"),
            author_last_name=reply.get("author_last_name"),
            author_avatar_url=reply.get("author_avatar_url"),
            is_unread=False,
            attachments=reply.get("attachments"),
            attached_request_snapshot=reply.get("attached_request_snapshot"),
            is_support_reply=reply.get("is_support_reply", False),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/support/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_support_ticket_endpoint(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Close/delete a support ticket. Owner or admin only."""
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")
    if ticket["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="אין הרשאה לסגור פנייה זו")
    if not delete_support_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="פנייה לא נמצאה")


# ========== Admin Endpoints ==========

# ---------- Global rules (רשימה גלובלית – רק אדמין) ----------

@app.get("/api/admin/global-rules", response_model=List[GlobalRuleResponse])
async def admin_list_global_rules(admin: dict = Depends(get_current_admin)):
    """List all global rules (base whitelist). Admin only."""
    rules = get_global_rules()
    return [GlobalRuleResponse(**r) for r in rules]


@app.get("/api/admin/global-rules/resolve")
async def admin_resolve_global_rule(
    url: str = Query(..., description="URL to check which global rule applies"),
    admin: dict = Depends(get_current_admin),
):
    """Return the global rule that applies to the given URL, or null. Admin only."""
    rule = resolve_global_rule_for_url(url)
    if not rule:
        return {"rule": None}
    return {"rule": GlobalRuleResponse(**rule)}


@app.post("/api/admin/global-rules/check-create")
async def admin_check_create_global_rule(
    data: GlobalRuleCreate,
    admin: dict = Depends(get_current_admin),
):
    """Check before creating: exact match and same-domain rules. Returns exact_match (rule + identical) and same_domain_rules list."""
    try:
        action_val = data.action or "allow"
        tf = getattr(data, "text_filter_enabled", True) if action_val == "allow" else False
        imgf = getattr(data, "image_filter_enabled", True) if action_val == "allow" else False
        filef = getattr(data, "file_filter_enabled", True) if action_val == "allow" else False
        pdff = getattr(data, "pdf_filter_enabled", True) if action_val == "allow" else False
        videof = getattr(data, "video_filter_enabled", True) if action_val == "allow" else False
        surfw = getattr(data, "surf_widget_enabled", True) if action_val == "allow" else False
        result = check_before_create_global_rule(
            url=data.url,
            action=action_val,
            include_subdomains=data.include_subdomains or False,
            tags=data.tags,
            text_filter_enabled=tf,
            image_filter_enabled=imgf,
            file_filter_enabled=filef,
            pdf_filter_enabled=pdff,
            video_filter_enabled=videof,
            surf_widget_enabled=surfw,
        )
        out = {
            "exact_match": None,
            "same_domain_rules": [GlobalRuleResponse(**r) for r in result["same_domain_rules"]],
            "proposed_rule": result["proposed_rule"],
        }
        if result.get("exact_match"):
            em = result["exact_match"]
            out["exact_match"] = {"rule": GlobalRuleResponse(**em["rule"]), "identical": em["identical"]}
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/global-rules", response_model=GlobalRuleResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_global_rule(
    data: GlobalRuleCreate,
    admin: dict = Depends(get_current_admin),
):
    """Create a global rule. Admin only."""
    try:
        action_val = data.action or "allow"
        # When action=block, filter toggles are not applicable (stored as False)
        tf = getattr(data, "text_filter_enabled", True) if action_val == "allow" else False
        imgf = getattr(data, "image_filter_enabled", True) if action_val == "allow" else False
        filef = getattr(data, "file_filter_enabled", True) if action_val == "allow" else False
        pdff = getattr(data, "pdf_filter_enabled", True) if action_val == "allow" else False
        videof = getattr(data, "video_filter_enabled", True) if action_val == "allow" else False
        surfw = getattr(data, "surf_widget_enabled", True) if action_val == "allow" else False
        rule = create_global_rule(
            url=data.url,
            action=action_val,
            include_subdomains=data.include_subdomains,
            tags=data.tags,
            text_filter_enabled=tf,
            image_filter_enabled=imgf,
            file_filter_enabled=filef,
            pdf_filter_enabled=pdff,
            video_filter_enabled=videof,
            surf_widget_enabled=surfw,
            created_by_user_id=admin.get("id"),
        )
        sync_crm_rules_to_core(None)
        return GlobalRuleResponse(**rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/global-rules/{rule_id}", response_model=GlobalRuleResponse)
async def admin_get_global_rule(
    rule_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Get a single global rule. Admin only."""
    rule = get_global_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל גלובלי לא נמצא")
    return GlobalRuleResponse(**rule)


@app.put("/api/admin/global-rules/{rule_id}", response_model=GlobalRuleResponse)
async def admin_update_global_rule(
    rule_id: int,
    data: GlobalRuleUpdate,
    admin: dict = Depends(get_current_admin),
):
    """Update a global rule. Admin only."""
    rule = get_global_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל גלובלי לא נמצא")
    try:
        action_val = data.action if data.action is not None else rule.get("action", "allow")
        if action_val == "block":
            tf, imgf, filef, pdff, videof, surfw = False, False, False, False, False, False
        else:
            tf = data.text_filter_enabled if data.text_filter_enabled is not None else rule.get("text_filter_enabled", True)
            imgf = data.image_filter_enabled if data.image_filter_enabled is not None else rule.get("image_filter_enabled", True)
            filef = data.file_filter_enabled if data.file_filter_enabled is not None else rule.get("file_filter_enabled", True)
            pdff = data.pdf_filter_enabled if data.pdf_filter_enabled is not None else rule.get("pdf_filter_enabled", True)
            videof = data.video_filter_enabled if data.video_filter_enabled is not None else rule.get("video_filter_enabled", True)
            surfw = data.surf_widget_enabled if data.surf_widget_enabled is not None else rule.get("surf_widget_enabled", True)
        updated = update_global_rule(
            rule_id,
            url=data.url,
            action=data.action,
            include_subdomains=data.include_subdomains,
            tags=data.tags,
            text_filter_enabled=tf,
            image_filter_enabled=imgf,
            file_filter_enabled=filef,
            pdf_filter_enabled=pdff,
            video_filter_enabled=videof,
            surf_widget_enabled=surfw,
            updated_by_user_id=admin.get("id"),
        )
        sync_crm_rules_to_core(None)
        return GlobalRuleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/global-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_global_rule(
    rule_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Delete a global rule. Admin only."""
    rule = get_global_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל גלובלי לא נמצא")
    deleted = delete_global_rule(rule_id)
    if deleted:
        sync_crm_rules_to_core(None)
    else:
        raise HTTPException(status_code=404, detail="כלל גלובלי לא נמצא")


# Allowed file downloads (רשימת קבצים מאושרים – אדמין)
@app.get("/api/admin/allowed-file-downloads")
async def admin_list_allowed_file_downloads(admin: dict = Depends(get_current_admin)):
    """List global allowed file download URLs. Admin only."""
    return {"items": list_allowed_file_downloads()}


@app.post("/api/admin/allowed-file-downloads", status_code=status.HTTP_201_CREATED)
async def admin_add_allowed_file_download(
    body: AllowedFileUrlBody,
    admin: dict = Depends(get_current_admin),
):
    """Add a URL to the global allowed file list. Admin only."""
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="חסר כתובת קובץ")
    add_allowed_file_url_crm(url)
    return {"url": url}


@app.delete("/api/admin/allowed-file-downloads", status_code=status.HTTP_204_NO_CONTENT)
async def admin_remove_allowed_file_download(
    body: AllowedFileUrlBody,
    admin: dict = Depends(get_current_admin),
):
    """Remove a URL from the global allowed file list. Admin only."""
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="חסר כתובת קובץ")
    deleted = remove_allowed_file_url_crm(url)
    if not deleted:
        raise HTTPException(status_code=404, detail="הכתובת לא נמצאה ברשימה")


# Site injections (הזרקת קוד והסתרת תוכן לאתר – אדמין)
@app.get("/api/admin/site-injections", response_model=List[SiteInjectionResponse])
async def admin_list_site_injections(admin: dict = Depends(get_current_admin)):
    """List all site injection rules. Admin only."""
    rules = get_site_injections()
    return [SiteInjectionResponse(**r) for r in rules]


@app.post("/api/admin/site-injections", response_model=SiteInjectionResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_site_injection(
    data: SiteInjectionCreate,
    admin: dict = Depends(get_current_admin),
):
    """Create a site injection rule. Admin only."""
    try:
        rule = create_site_injection(
            url=data.url,
            head_code=data.head_code,
            body_code=data.body_code,
            hide_selectors=data.hide_selectors,
            include_subdomains=data.include_subdomains,
            path_exact_only=data.path_exact_only,
            enabled=data.enabled,
        )
        sync_site_injections_to_core()
        return SiteInjectionResponse(**rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/site-injections/{injection_id}", response_model=SiteInjectionResponse)
async def admin_get_site_injection(
    injection_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Get a single site injection rule. Admin only."""
    rule = get_site_injection(injection_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל הזרקה לא נמצא")
    return SiteInjectionResponse(**rule)


@app.put("/api/admin/site-injections/{injection_id}", response_model=SiteInjectionResponse)
async def admin_update_site_injection(
    injection_id: int,
    data: SiteInjectionUpdate,
    admin: dict = Depends(get_current_admin),
):
    """Update a site injection rule. Admin only."""
    rule = get_site_injection(injection_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל הזרקה לא נמצא")
    try:
        updated = update_site_injection(
            injection_id,
            url=data.url,
            head_code=data.head_code,
            body_code=data.body_code,
            hide_selectors=data.hide_selectors,
            include_subdomains=data.include_subdomains,
            path_exact_only=data.path_exact_only,
            enabled=data.enabled,
        )
        sync_site_injections_to_core()
        return SiteInjectionResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/site-injections/{injection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_site_injection(
    injection_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Delete a site injection rule. Admin only."""
    rule = get_site_injection(injection_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל הזרקה לא נמצא")
    deleted = delete_site_injection(injection_id)
    if deleted:
        sync_site_injections_to_core()
    else:
        raise HTTPException(status_code=404, detail="כלל הזרקה לא נמצא")


@app.post("/api/admin/surf-update-rule-to-block")
async def admin_surf_update_rule_to_block(
    request: Request,
    admin: dict = Depends(get_current_admin),
):
    """Find global rule by domain_pattern and path_pattern, update to block. Admin only (session)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    rule_domain = (body.get("rule_domain") or "").strip().lower()
    if rule_domain.startswith("www."):
        rule_domain = rule_domain[4:]
    rule_path = (body.get("rule_path") or "/").strip() or "/"
    if not rule_domain:
        raise HTTPException(status_code=400, detail="חסר rule_domain")
    try:
        rule = find_and_update_global_rule_to_block(
            rule_domain, rule_path, updated_by_user_id=admin.get("id")
        )
        sync_crm_rules_to_core(None)
        return {"success": True, "rule": GlobalRuleResponse(**rule)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/admin/users")
async def admin_list_users(
    admin: dict = Depends(get_current_admin),
    sort_by: str = Query("id"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
):
    """List users with sort, pagination and optional search (admin). Returns users, total."""
    users, total = list_users(sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size, search=search)
    return {"users": users, "total": total}


@app.put("/api/admin/users/{user_id}/admin")
async def admin_set_user_admin(
    user_id: int,
    body: dict,
    admin: dict = Depends(get_current_admin),
):
    """Set user admin flag (admin). Body: { \"is_admin\": true }."""
    is_admin = body.get("is_admin", False)
    try:
        updated = set_user_admin(user_id, bool(is_admin))
        return {"user_id": updated["id"], "is_admin": updated.get("is_admin", False)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Delete a user and all their data (admin). Cannot delete yourself."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="לא ניתן למחוק את עצמך")
    try:
        delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/users/{user_id}/locked-settings")
async def admin_get_locked_settings(
    user_id: int,
    admin: dict = Depends(get_current_admin),
):
    """Get locked settings for a user (admin)."""
    keys = get_locked_settings(user_id)
    return {"locked_settings": keys}


@app.post("/api/admin/users/{user_id}/locked-settings")
async def admin_add_locked_setting(
    user_id: int,
    body: dict,
    admin: dict = Depends(get_current_admin),
):
    """Lock a setting for a user (admin). body: { \"setting_key\": \"profile_name\" }."""
    key = body.get("setting_key")
    if not key:
        raise HTTPException(status_code=400, detail="חסר setting_key")
    if key not in LOCKABLE_SETTINGS:
        raise HTTPException(status_code=400, detail=f"setting_key לא מוכר. אפשרויות: {', '.join(LOCKABLE_SETTINGS)}")
    try:
        set_locked_setting(user_id, key)
        return {"locked_settings": get_locked_settings(user_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/users/{user_id}/locked-settings/{setting_key}")
async def admin_remove_locked_setting(
    user_id: int,
    setting_key: str,
    admin: dict = Depends(get_current_admin),
):
    """Unlock a setting for a user (admin)."""
    remove_locked_setting(user_id, setting_key)
    return {"locked_settings": get_locked_settings(user_id)}


@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return current user (id, phone, email, is_admin)."""
    user = get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    return {
        "id": user["id"],
        "phone": user.get("phone"),
        "email": user.get("email"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "is_admin": user.get("is_admin", False),
    }


def _filtered_user_id(request: Request) -> Optional[int]:
    """User whose filtered connection this request came through: signed header from our proxy
    (personal credentials), else the user bound to the client IP."""
    uid = verify_proxy_user(request.headers.get(PROXY_USER_HEADER))
    if uid is not None:
        return uid
    ip = _client_ip(request)
    return get_user_id_for_ip(ip) if ip else None


def _client_ip(request: Request) -> str:
    """Real client IP. X-Forwarded-For is honored only from TRUSTED_PROXY_IPS (anyone can send the header)."""
    peer = request.client.host if request.client else None
    ip = resolve_client_ip(
        peer,
        request.headers.get("x-forwarded-for"),
        request.headers.get("x-real-ip"),
    )
    return ip or ""


# ---------- IP bindings (שיוך כתובת IP לחשבון – לסינון לפי משתמש) ----------

@app.get("/api/me/bindings")
async def list_my_bindings(current_user: dict = Depends(get_current_user)):
    """List IP addresses bound to the current user's account (with last_used_at)."""
    bindings = list_bindings_for_user(current_user["id"])
    return [
        {"id": b["id"], "ip": b["ip"], "created_at": b["created_at"], "last_used_at": b.get("last_used_at")}
        for b in bindings
    ]


@app.post("/api/me/bindings", status_code=status.HTTP_201_CREATED)
async def bind_my_ip(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Bind the request's client IP to the current user. Used after login on the bind flow."""
    ip = _client_ip(request)
    if not ip:
        raise HTTPException(status_code=400, detail="לא ניתן לזהות את כתובת ה-IP")
    if is_trusted_proxy(ip):
        # Never bind the address of our own proxy / reverse proxy (would capture everyone's traffic).
        raise HTTPException(status_code=400, detail="לא ניתן לשייך כתובת זו. התחבר דרך הפרוקסי או השתמש בפרטי התחברות אישיים.")
    try:
        binding = add_ip_binding(current_user["id"], ip)
        sync_ip_bindings_to_core()
        sync_crm_rules_to_core(current_user["id"])
        return {"id": binding["id"], "ip": binding["ip"], "created_at": binding["created_at"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/me/client-ip")
async def get_my_client_ip(request: Request, current_user: dict = Depends(get_current_user)):
    """Return the client IP as seen by the server (for showing in bind flow)."""
    return {"ip": _client_ip(request)}


@app.delete("/api/me/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_binding(
    binding_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Remove an IP binding. Only the owner can remove."""
    removed = remove_ip_binding(binding_id, current_user["id"])
    if not removed:
        raise HTTPException(status_code=404, detail="שיוך לא נמצא")
    sync_ip_bindings_to_core()
    sync_crm_rules_to_core(current_user["id"])


# ---------- Personal proxy credentials (זיהוי לפי פרטי התחברות – לא לפי IP) ----------

def _proxy_endpoint_info() -> dict:
    from urllib.parse import urlparse
    from data.constants import CRM_BASE_URL, PROXY_PUBLIC_HOST, PROXY_PUBLIC_PORT
    host = PROXY_PUBLIC_HOST or (urlparse(CRM_BASE_URL).hostname or "")
    return {"proxy_host": host, "proxy_port": PROXY_PUBLIC_PORT}


@app.get("/api/me/proxy-credentials")
async def my_proxy_credentials(current_user: dict = Depends(get_current_user)):
    """Username + whether a password exists (the password itself is shown only once, on creation)."""
    try:
        creds = get_proxy_credentials(current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**creds, **_proxy_endpoint_info()}


@app.post("/api/me/proxy-credentials/rotate")
@limiter.limit("10/hour")
async def rotate_my_proxy_credentials(request: Request, current_user: dict = Depends(get_current_user)):
    """Create or replace the personal proxy password. Devices using the old password must be updated."""
    try:
        creds = rotate_proxy_credentials(current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**creds, **_proxy_endpoint_info()}


# ---------- Traffic recording (הקלטת תעבורה – התחל/סיום/קבלת לוג) ----------

@app.post("/api/traffic/start", status_code=status.HTTP_201_CREATED)
async def traffic_start(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Start traffic recording for the current user. Proxy will log requests until stop.
    Only allowed when the client IP is bound to some account (traffic goes through the proxy)."""
    from core.policy.policy_database import start_traffic_session, get_active_traffic_session_id
    bound_user_id = _filtered_user_id(request)
    if bound_user_id is None:
        raise HTTPException(
            status_code=403,
            detail="החיבור ממנו הינך גולש אינו מסונן.",
        )
    if get_active_traffic_session_id(current_user["id"]) is not None:
        raise HTTPException(status_code=400, detail="הקלטה כבר פעילה. סיים הקלטה קיימת לפני התחלה חדשה.")
    session_id = start_traffic_session(current_user["id"])
    return {"session_id": session_id, "message": "ההקלטה החלה. גלוש דרך המכשירים המשויכים לחשבון."}


@app.post("/api/traffic/stop")
async def traffic_stop(current_user: dict = Depends(get_current_user)):
    """Stop traffic recording and return session_id and share_token (link for anyone to view).
    If no traffic was captured, returns 400 and does not close the session."""
    from core.policy.policy_database import stop_traffic_session
    result = stop_traffic_session(current_user["id"])
    if result is None:
        raise HTTPException(status_code=400, detail="אין הקלטה פעילה.")
    session_id, share_token = result
    if share_token is None:
        raise HTTPException(status_code=400, detail="לא נקלטה תעבורה.")
    return {"session_id": session_id, "share_token": share_token, "message": "ההקלטה הסתיימה."}


@app.get("/api/traffic/status")
async def traffic_status(current_user: dict = Depends(get_current_user)):
    """Return whether the user is currently recording and active session_id if any."""
    from core.policy.policy_database import get_active_traffic_session_id
    session_id = get_active_traffic_session_id(current_user["id"])
    return {"recording": session_id is not None, "session_id": session_id}


@app.get("/api/traffic/sessions")
async def traffic_sessions(current_user: dict = Depends(get_current_user)):
    """List traffic recording sessions for the current user."""
    from core.policy.policy_database import get_traffic_sessions
    sessions = get_traffic_sessions(current_user["id"])
    return {"sessions": sessions}


@app.get("/api/traffic/log")
async def traffic_log(
    session_id: int = Query(..., description="Session id to fetch log for"),
    current_user: dict = Depends(get_current_user),
):
    """Get traffic log entries for a recording session. Session must belong to current user."""
    from core.policy.policy_database import get_traffic_log
    entries = get_traffic_log(session_id, current_user["id"])
    return {"session_id": session_id, "entries": entries}


@app.get("/api/traffic/view/{token}")
async def traffic_view_by_token(
    token: str,
    current_user: dict = Depends(get_current_user),
):
    """צפייה בהקלטה לפי קישור – דורש התחברות. כל משתמש מחובר יכול לצפות. הצפייה נרשמת ללוג אבטחה."""
    from core.policy.policy_database import get_traffic_session_by_token, get_traffic_log_by_session_id
    from crm.database import log_traffic_recording_view
    session = get_traffic_session_by_token(token)
    if not session:
        raise HTTPException(status_code=404, detail="הקלטה לא נמצאה או שהקישור לא תקין.")
    log_traffic_recording_view(session["id"], current_user["id"])
    entries = get_traffic_log_by_session_id(session["id"])
    return {
        "session_id": session["id"],
        "started_at": session["started_at"],
        "ended_at": session["ended_at"],
        "share_token": session["share_token"],
        "entries": entries,
    }


@app.get("/api/admin/traffic-recording-views")
async def admin_list_traffic_recording_views(
    session_id: Optional[int] = None,
    admin: dict = Depends(get_current_admin),
):
    """לוג אבטחה: רשימת משתמשים שצפו בהקלטות תעבורה, עם זמני צפייה. אפשר לסנן לפי session_id."""
    from crm.database import get_traffic_recording_views
    rows = get_traffic_recording_views(session_id=session_id)
    return {"views": rows}


@app.post("/api/internal/touch-ip")
async def internal_touch_ip(request: Request):
    """Update last_used_at for an IP binding. Called by proxy. Requires CRM_PROXY_SECRET."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    secret = body.get("secret")
    if not CRM_PROXY_SECRET or not isinstance(secret, str) or not hmac.compare_digest(secret, CRM_PROXY_SECRET):
        raise HTTPException(status_code=403, detail="גישה נדחתה")
    ip = (body.get("ip") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="חסר ip")
    touch_ip_binding(ip)
    return {"status": "ok"}


# ---------- Per-video review (בדיקת סרטון בודד) ----------

def _video_review_out(r: Optional[dict]) -> dict:
    if not r:
        return {"status": None}
    return {k: r.get(k) for k in ("video_key", "source_url", "page_url", "status", "requested_at", "updated_at",
                                   "duration_sec", "frames_sampled", "frames_analyzed", "blocked_at_sec", "reason")}


@app.post("/api/video-reviews")
@limiter.limit("30/hour")
async def request_video_review_endpoint(request: Request, current_user: dict = Depends(get_current_user)):
    """Send a video for review. Once approved it is open for every user (like NetFree)."""
    from urllib.parse import urlsplit
    from core.policy.policy_database import request_video_review
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    url = (body.get("url") or "").strip()
    page_url = (body.get("page_url") or "").strip() or None
    if urlsplit(url).scheme not in ("http", "https") or len(url) > 4000:
        raise HTTPException(status_code=400, detail="כתובת וידאו לא תקינה (http/https בלבד)")
    return _video_review_out(request_video_review(url, page_url, current_user["id"]))


@app.get("/api/video-reviews/status")
async def video_review_status_endpoint(url: str = Query(...), current_user: dict = Depends(get_current_user)):
    from core.policy.policy_database import canonical_media_key, get_video_review
    return _video_review_out(get_video_review(canonical_media_key(url)))


@app.get("/api/video-reviews/recent-blocked")
async def recent_blocked_media_endpoint(page_url: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    """Videos the filter blocked for this user in the last 24h (optionally on one page)."""
    from core.policy.policy_database import list_recent_blocked_media
    return {"items": list_recent_blocked_media(current_user["id"], page_url)}


# ---------- Admin: human review queue (images the model was unsure about, failed analyses, videos) ----------

_HASH_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


@app.get("/api/admin/review/summary")
async def admin_review_summary(admin: dict = Depends(get_current_admin)):
    from core.filters.image.image_status_db import count_by_status, list_images_by_status
    from core.policy.policy_database import list_video_reviews
    from data.constants import MAX_ANALYSIS_ATTEMPTS
    images = count_by_status()
    failed = len(list_images_by_status("error", limit=1000, min_attempts=MAX_ANALYSIS_ATTEMPTS))
    videos = {st: len(list_video_reviews(st, limit=1000)) for st in ("pending", "processing", "review", "error")}
    return {"images_review": images.get("review", 0), "images_failed": failed, "videos": videos}


@app.get("/api/admin/review/images")
async def admin_review_images(
    status_filter: str = Query("review", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(get_current_admin),
):
    from core.filters.image.image_status_db import list_images_by_status
    from core.filters.review_store import thumbnail_path
    from data.constants import MAX_ANALYSIS_ATTEMPTS
    try:
        rows = list_images_by_status(
            status_filter, limit=limit, offset=offset,
            min_attempts=MAX_ANALYSIS_ATTEMPTS if status_filter == "error" else 0,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    for r in rows:
        r["has_thumb"] = thumbnail_path("images", r["image_hash"]) is not None
    return {"items": rows}


@app.get("/api/admin/review/images/{image_hash}/thumb")
async def admin_review_image_thumb(image_hash: str, admin: dict = Depends(get_current_admin)):
    from core.filters.review_store import thumbnail_path
    path = thumbnail_path("images", image_hash) if _HASH_RE.match(image_hash) else None
    if not path:
        raise HTTPException(status_code=404, detail="אין תמונה שמורה")
    return FileResponse(str(path), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/admin/review/images/{image_hash}")
async def admin_review_image_decide(image_hash: str, request: Request, admin: dict = Depends(get_current_admin)):
    from core.filters.image.image_status_db import set_image_status
    from core.filters.review_store import delete_thumbnail
    body = await request.json()
    decision = (body.get("decision") or "").strip()
    if decision not in ("allow", "block") or not _HASH_RE.match(image_hash):
        raise HTTPException(status_code=400, detail="decision חייב להיות allow או block")
    if not set_image_status(image_hash, "allowed" if decision == "allow" else "blocked"):
        raise HTTPException(status_code=404, detail="תמונה לא נמצאה")
    delete_thumbnail("images", image_hash)
    logger.info("Admin %s decided image %s → %s", admin.get("id"), image_hash[:12], decision)
    return {"ok": True}


@app.get("/api/admin/review/videos")
async def admin_review_videos(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
):
    from core.filters.review_store import thumbnail_path
    from core.policy.policy_database import list_video_reviews
    items = [_video_review_out(r) for r in list_video_reviews(status_filter or None, limit=limit)]
    for it in items:
        it["has_thumb"] = thumbnail_path("videos", it["video_key"]) is not None
    return {"items": items}


@app.get("/api/admin/review/videos/thumb")
async def admin_review_video_thumb(key: str = Query(...), admin: dict = Depends(get_current_admin)):
    from core.filters.review_store import thumbnail_path
    path = thumbnail_path("videos", key)
    if not path:
        raise HTTPException(status_code=404, detail="אין פריים שמור")
    return FileResponse(str(path), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/admin/review/videos/decide")
async def admin_review_video_decide(request: Request, admin: dict = Depends(get_current_admin)):
    """Admin override: allow / block a video, or send it back to the automatic queue."""
    from core.filters.review_store import delete_thumbnail
    from core.policy.policy_database import finish_video_review, get_video_review
    body = await request.json()
    key = (body.get("key") or "").strip()
    decision = (body.get("decision") or "").strip()
    review = get_video_review(key)
    if not review:
        raise HTTPException(status_code=404, detail="סרטון לא נמצא")
    if decision == "allow":
        finish_video_review(key, "allowed", reason="אושר ידנית", decided_by=admin["id"])
        delete_thumbnail("videos", key)
    elif decision == "block":
        finish_video_review(key, "blocked", reason="נחסם ידנית", decided_by=admin["id"], blocked_at_sec=review.get("blocked_at_sec"))
    elif decision == "requeue":
        finish_video_review(key, "pending", reason=None)
    else:
        raise HTTPException(status_code=400, detail="decision חייב להיות allow / block / requeue")
    logger.info("Admin %s decided video %s → %s", admin.get("id"), key, decision)
    return _video_review_out(get_video_review(key))


# ---------- Admin: hosts passed through because their apps reject the proxy certificate (pinning) ----------

@app.get("/api/admin/learned-passthrough")
async def admin_list_learned_passthrough(admin: dict = Depends(get_current_admin)):
    from core.policy.policy_database import get_learned_passthrough_hosts
    from data.constants import AUTO_PASSTHROUGH_PINNED_APPS
    return {"enabled": AUTO_PASSTHROUGH_PINNED_APPS, "hosts": sorted(get_learned_passthrough_hosts())}


@app.delete("/api/admin/learned-passthrough/{host}")
async def admin_forget_learned_passthrough(host: str, admin: dict = Depends(get_current_admin)):
    from core.policy.policy_database import forget_learned_passthrough
    forget_learned_passthrough(host)
    logger.info("Admin %s removed learned passthrough host %s", admin.get("id"), host)
    return {"ok": True}


# ---------- SPA catch-all (for React router paths like /schedules, /rules, etc.) ----------
@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str, request: Request):
    """
    Serve the React SPA for any non-API path.
    This allows direct navigation / refresh on routes like /schedules to work.
    """
    # Do NOT intercept API / static / uploads / websocket / internal paths
    # Note: /diagnostic is handled by a specific route above, so it won't reach here
    protected_prefixes = (
        "api/",
        "static/",
        "assets/",
        "uploads/",
        "ws",
        "api/internal/",
    )
    for prefix in protected_prefixes:
        if full_path.startswith(prefix):
            # Let FastAPI return the normal 404 for unknown API/static paths
            raise HTTPException(status_code=404, detail="Not Found")
    return _serve_spa()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=DEFAULT_API_HOST, port=DEFAULT_API_PORT)

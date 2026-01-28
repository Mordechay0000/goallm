"""
FastAPI application for CRM system.
"""
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List
import json
import logging
from pathlib import Path

from .models import (
    UserCreate, UserResponse, UserUpdate, PasswordChange, LoginRequest,
    RequestPhoneCode, VerifyPhoneCode, RequestEmailCode, VerifyEmailCode,
    ProfileCreate, ProfileUpdate, ProfileResponse,
    RuleCreate, RuleUpdate, RuleResponse,
    ScheduleCreate, ScheduleUpdate, ScheduleResponse
)
from .services import (
    create_user, authenticate_user, authenticate_user_by_phone, get_user_by_id, update_user, change_password, get_user_profiles,
    create_profile, get_profile, update_profile, delete_profile,
    create_rule, get_rule, get_profile_rules, update_rule, delete_rule,
    create_schedule, get_schedule, get_profile_schedules, update_schedule, delete_schedule
)
from .auth import create_user_access_token, get_current_user
from .database import init_db_schema, db_connection
from .resolver_integration import get_rules_for_resolver, get_all_enabled_rules_for_resolver
from .verification import (
    request_phone_code,
    verify_phone_code,
    request_email_code,
    verify_email_code,
)
from .uploads import validate_avatar_file, save_avatar
from .security import validate_password_strength

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# Static files (for React build)
static_folder = Path(__file__).resolve().parent / "static"
if static_folder.exists():
    app.mount("/static", StaticFiles(directory=str(static_folder)), name="static")

# User uploads (avatars)
uploads_dir = Path(__file__).resolve().parent.parent / ".storage" / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/")
async def root():
    """Serve React app."""
    index_file = static_folder / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "CRM API", "version": "1.0.0"}


# ========== Auth Endpoints ==========

def _validate_email(s: str) -> str:
    s = (s or "").strip().lower()
    if not s or "@" not in s or s.count("@") != 1:
        raise ValueError("כתובת אימייל לא תקינה")
    local, _, domain = s.partition("@")
    if not local or not domain or ".." in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("כתובת אימייל לא תקינה")
    return s


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
    content = await file.read()
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


# ========== Profile Endpoints ==========

@app.get("/api/profiles", response_model=List[ProfileResponse])
async def list_profiles(current_user: dict = Depends(get_current_user)):
    """Get all profiles for current user."""
    profiles = get_user_profiles(current_user["id"])
    return [ProfileResponse(**p) for p in profiles]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile_endpoint(
    profile_data: ProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new profile."""
    try:
        profile = create_profile(current_user["id"], profile_data.name, profile_data.mode)
        await manager.broadcast({"type": "profile_created", "profile_id": profile["id"]})
        return ProfileResponse(**profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile_endpoint(
    profile_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a single profile."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    return ProfileResponse(**profile)


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile_endpoint(
    profile_id: int,
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a profile."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    try:
        updated = update_profile(
            profile_id,
            name=profile_data.name,
            mode=profile_data.mode
        )
        await manager.broadcast({"type": "profile_updated", "profile_id": profile_id})
        return ProfileResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_endpoint(
    profile_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a profile."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    deleted = delete_profile(profile_id)
    if deleted:
        await manager.broadcast({"type": "profile_deleted", "profile_id": profile_id})
    else:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")


# ========== Rule Endpoints ==========

@app.get("/api/profiles/{profile_id}/rules", response_model=List[RuleResponse])
async def list_rules(
    profile_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all rules for a profile."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    rules = get_profile_rules(profile_id)
    return [RuleResponse(**r) for r in rules]


@app.post("/api/profiles/{profile_id}/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_endpoint(
    profile_id: int,
    rule_data: RuleCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new rule."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    try:
        rule = create_rule(
            profile_id,
            rule_data.url,
            rule_data.action,
            rule_data.type,
            rule_data.include_subdomains
        )
        await manager.broadcast({"type": "rule_created", "profile_id": profile_id, "rule_id": rule["id"]})
        return RuleResponse(**rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rules/{rule_id}", response_model=RuleResponse)
async def get_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a single rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    return RuleResponse(**rule)


@app.put("/api/rules/{rule_id}", response_model=RuleResponse)
async def update_rule_endpoint(
    rule_id: int,
    rule_data: RuleUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    try:
        updated = update_rule(
            rule_id,
            url=rule_data.url,
            action=rule_data.action,
            rule_type=rule_data.type,
            include_subdomains=rule_data.include_subdomains
        )
        await manager.broadcast({"type": "rule_updated", "rule_id": rule_id, "profile_id": rule["profile_id"]})
        return RuleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_endpoint(
    rule_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a rule."""
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    profile = get_profile(rule["profile_id"])
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")
    
    deleted = delete_rule(rule_id)
    if deleted:
        await manager.broadcast({"type": "rule_deleted", "rule_id": rule_id, "profile_id": rule["profile_id"]})
    else:
        raise HTTPException(status_code=404, detail="כלל לא נמצא")


# ========== Schedule Endpoints ==========

@app.get("/api/profiles/{profile_id}/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    profile_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all schedules for a profile."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    schedules = get_profile_schedules(profile_id)
    return [ScheduleResponse(**s) for s in schedules]


@app.post("/api/profiles/{profile_id}/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule_endpoint(
    profile_id: int,
    schedule_data: ScheduleCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new schedule."""
    profile = get_profile(profile_id)
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="פרופיל לא נמצא")
    
    try:
        schedule = create_schedule(
            profile_id,
            schedule_data.days,
            schedule_data.from_time,
            schedule_data.to_time
        )
        await manager.broadcast({"type": "schedule_created", "profile_id": profile_id, "schedule_id": schedule["id"]})
        return ScheduleResponse(**schedule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_endpoint(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a schedule."""
    schedule = get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    profile = get_profile(schedule["profile_id"])
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    try:
        updated = update_schedule(
            schedule_id,
            days=schedule_data.days,
            from_time=schedule_data.from_time,
            to_time=schedule_data.to_time
        )
        await manager.broadcast({"type": "schedule_updated", "schedule_id": schedule_id, "profile_id": schedule["profile_id"]})
        return ScheduleResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_endpoint(
    schedule_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a schedule."""
    schedule = get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    profile = get_profile(schedule["profile_id"])
    if not profile or profile["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")
    
    deleted = delete_schedule(schedule_id)
    if deleted:
        await manager.broadcast({"type": "schedule_deleted", "schedule_id": schedule_id, "profile_id": schedule["profile_id"]})
    else:
        raise HTTPException(status_code=404, detail="תזמון לא נמצא")


# ========== WebSocket Endpoint ==========

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
async def get_all_resolver_rules():
    """
    Get all enabled rules for system-wide resolver (for proxy addon).
    No auth required - used by internal systems.
    """
    rules = get_all_enabled_rules_for_resolver()
    return {"rules": rules}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

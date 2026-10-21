"""
Pydantic models for CRM API.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# User models
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="סיסמה חייבת להכיל לפחות 8 תווים, ספרה ואות")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20, pattern="^[0-9\\-\\+\\s\\(\\)]+$")
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20, pattern="^[0-9\\-\\+\\s\\(\\)]+$")
    # Only our own uploaded avatars (or "" to clear). An arbitrary URL would let a user make every admin
    # who opens their ticket load an external tracker.
    avatar_url: Optional[str] = Field(None, max_length=500, pattern=r"^(|/uploads/avatars/[A-Za-z0-9_.\-]+)$")


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    avatar_url: Optional[str]
    created_at: int
    updated_at: int
    is_admin: bool = False

    class Config:
        from_attributes = True


class RequestPhoneCode(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)


class VerifyPhoneCode(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]+$")


class RequestEmailCode(BaseModel):
    email: EmailStr


class VerifyEmailCode(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]+$")


# Profile models
class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1)
    mode: str = Field(default="whitelist", pattern="^(whitelist|blacklist)$")


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    mode: Optional[str] = Field(None, pattern="^(whitelist|blacklist)$")


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    mode: str
    is_default: bool
    created_at: int
    updated_at: int
    
    class Config:
        from_attributes = True


# Rule models
class RuleCreate(BaseModel):
    url: str = Field(..., min_length=1)
    action: str = Field(default="block", pattern="^(allow|block)$")
    include_subdomains: bool = Field(default=False)
    tags: Optional[List[str]] = Field(default=None, description="תגיות לאתר (למשל ממכר, בידור)")
    
    @validator('url')
    def validate_url(cls, v):
        """Remove protocol, strip www. from domain, and normalize URL."""
        v = v.strip()
        if v.startswith('http://'):
            v = v[7:]
        elif v.startswith('https://'):
            v = v[8:]
        if v.startswith('*.'):
            v = v[2:]
            prefix = '*.'
        else:
            prefix = ''
        if '/' in v:
            parts = v.split('/', 1)
            domain = parts[0].lower().rstrip('.')
            path = '/' + parts[1] if parts[1] else '/'
        else:
            domain = v.lower().rstrip('.')
            path = None
        if not domain:
            raise ValueError("URL חייב לכלול דומיין")
        if domain.startswith('www.'):
            domain = domain[4:]
        v = prefix + domain + (path or '')
        return v


def _normalize_rule_url(v: str) -> str:
    """Strip protocol and www. from URL for rule storage."""
    v = v.strip()
    if v.startswith("http://"):
        v = v[7:]
    elif v.startswith("https://"):
        v = v[8:]
    prefix = "*." if v.startswith("*.") else ""
    if v.startswith("*."):
        v = v[2:]
    if "/" in v:
        parts = v.split("/", 1)
        domain = parts[0].lower().rstrip(".")
        path = "/" + parts[1] if parts[1] else "/"
    else:
        domain = v.lower().rstrip(".")
        path = ""
    if domain.startswith("www."):
        domain = domain[4:]
    return prefix + domain + path


class RuleUpdate(BaseModel):
    url: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|block)$")
    include_subdomains: Optional[bool] = None
    tags: Optional[List[str]] = None

    @validator("url")
    def normalize_url(cls, v):
        if v is None or not str(v).strip():
            return v
        return _normalize_rule_url(str(v))


class RuleResponse(BaseModel):
    id: int
    profile_id: int
    domain_pattern: str
    path_pattern: Optional[str]
    action: str
    include_subdomains: bool
    tags: Optional[List[str]] = None
    created_at: int
    updated_at: int
    
    @property
    def display_url(self) -> str:
        """Format URL for display."""
        url = self.domain_pattern
        if self.include_subdomains and not url.startswith('*.'):
            url = f"*.{url}"
        if self.path_pattern:
            url += self.path_pattern
        return url
    
    class Config:
        from_attributes = True


# Global rule models (רשימה גלובלית – רק אדמין)
class GlobalRuleCreate(BaseModel):
    url: str = Field(..., min_length=1)
    action: str = Field(default="allow", pattern="^(allow|block)$")
    include_subdomains: bool = Field(default=False)
    tags: Optional[List[str]] = Field(default=None)
    text_filter_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")
    image_filter_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")
    file_filter_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")
    pdf_filter_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")
    video_filter_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")
    surf_widget_enabled: Optional[bool] = Field(default=None, description="Only when action=allow; ignored when action=block")

    @validator('url')
    def validate_url(cls, v):
        """Remove protocol, strip www. from domain, and normalize URL."""
        v = v.strip()
        if v.startswith('http://'):
            v = v[7:]
        elif v.startswith('https://'):
            v = v[8:]
        if v.startswith('*.'):
            v = v[2:]
            prefix = '*.'
        else:
            prefix = ''
        if '/' in v:
            parts = v.split('/', 1)
            domain = parts[0].lower().rstrip('.')
            path = '/' + parts[1] if parts[1] else '/'
        else:
            domain = v.lower().rstrip('.')
            path = None
        if not domain:
            raise ValueError("URL חייב לכלול דומיין")
        if domain.startswith('www.'):
            domain = domain[4:]
        v = prefix + domain + (path or '')
        return v


class GlobalRuleUpdate(BaseModel):
    url: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|block)$")
    include_subdomains: Optional[bool] = None
    tags: Optional[List[str]] = None
    text_filter_enabled: Optional[bool] = None
    image_filter_enabled: Optional[bool] = None
    file_filter_enabled: Optional[bool] = None
    pdf_filter_enabled: Optional[bool] = None
    video_filter_enabled: Optional[bool] = None
    surf_widget_enabled: Optional[bool] = None

    @validator("url")
    def normalize_url(cls, v):
        if v is None or not str(v).strip():
            return v
        return _normalize_rule_url(str(v))


class GlobalRuleResponse(BaseModel):
    id: int
    domain_pattern: str
    path_pattern: Optional[str]
    action: str
    include_subdomains: bool
    tags: Optional[List[str]] = None
    text_filter_enabled: bool = True
    image_filter_enabled: bool = True
    file_filter_enabled: bool = True
    pdf_filter_enabled: bool = True
    video_filter_enabled: bool = True
    surf_widget_enabled: bool = True
    created_at: int
    updated_at: int

    @property
    def display_url(self) -> str:
        url = self.domain_pattern
        if self.include_subdomains and not url.startswith('*.'):
            url = f"*.{url}"
        if self.path_pattern:
            url += self.path_pattern
        return url

    class Config:
        from_attributes = True


# Tag rule models (כללי תגיות)
class TagRuleCreate(BaseModel):
    tag: str = Field(..., min_length=1)
    state: str = Field(default="block", pattern="^(allow|block)$")
    enabled: bool = Field(default=True)


class TagRuleUpdate(BaseModel):
    tag: Optional[str] = Field(None, min_length=1)
    state: Optional[str] = Field(None, pattern="^(allow|block)$")
    enabled: Optional[bool] = None


class TagRuleResponse(BaseModel):
    id: int
    tag: str
    state: str
    enabled: bool
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True


# Schedule models
class ScheduleCreate(BaseModel):
    days: List[int] = Field(..., min_items=1, max_items=7)  # 0-6 for א-ש
    from_time: Optional[str] = Field(None, pattern="^\\d{2}:\\d{2}$")
    to_time: Optional[str] = Field(None, pattern="^\\d{2}:\\d{2}$")
    
    def to_bitmask(self) -> int:
        """Convert days list to bitmask."""
        bitmask = 0
        for day in self.days:
            if 0 <= day <= 6:
                bitmask |= (1 << day)
        return bitmask


class ScheduleUpdate(BaseModel):
    days: Optional[List[int]] = None
    from_time: Optional[str] = Field(None, pattern="^\\d{2}:\\d{2}$")
    to_time: Optional[str] = Field(None, pattern="^\\d{2}:\\d{2}$")


class ScheduleResponse(BaseModel):
    id: int
    profile_id: int
    days_bitmask: int
    from_time: Optional[str]
    to_time: Optional[str]
    created_at: int
    updated_at: int
    
    @property
    def days_list(self) -> List[int]:
        """Convert bitmask to days list."""
        days = []
        for i in range(7):
            if self.days_bitmask & (1 << i):
                days.append(i)
        return days
    
    class Config:
        from_attributes = True


# Login model (always phone + password)
class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    password: str


# Rule request models (user requests for admin to approve)
class RuleRequestCreate(BaseModel):
    request_type: str = Field(..., pattern="^(open|change|file)$")
    url: Optional[str] = None
    domain_pattern: Optional[str] = None
    path_pattern: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|block)$")
    include_subdomains: bool = False
    tags: Optional[List[str]] = None
    notes: Optional[str] = None  # for file requests: user description of the file
    request_url: Optional[str] = None  # full URL user tried to access (e.g. from surf widget)


class RuleRequestApprove(BaseModel):
    """Optional; approval adds rule to global list only. profile_id kept for API compatibility, ignored."""
    profile_id: Optional[int] = None
    force_update: bool = False  # when conflict: update existing rule with request data
    skip_rule_update: bool = False  # when conflict: leave existing rule as-is, only link request to it


class RuleRequestResponse(BaseModel):
    id: int
    user_id: int
    request_type: str
    url: Optional[str]
    domain_pattern: Optional[str]
    path_pattern: Optional[str]
    action: Optional[str]
    include_subdomains: bool
    tags: Optional[List[str]]
    status: str
    created_at: int
    updated_at: int
    user_phone: Optional[str] = None
    approved_rule_id: Optional[int] = None
    approved_profile_id: Optional[int] = None
    is_from_blocked_page: bool = False
    request_url: Optional[str] = None  # full URL user tried to access (read-only)
    notes: Optional[str] = None  # for file requests: user description of the file
    resolved_by_user_id: Optional[int] = None
    resolved_by_name: Optional[str] = None  # display name of admin who approved/rejected (last resolver)
    text_filter_enabled: Optional[bool] = None  # for allow rules: enable text filter (only for open/change)
    image_filter_enabled: Optional[bool] = None
    file_filter_enabled: Optional[bool] = None

    class Config:
        from_attributes = True


class RuleRequestUpdate(BaseModel):
    url: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|block)$")
    include_subdomains: Optional[bool] = None
    tags: Optional[List[str]] = None
    text_filter_enabled: Optional[bool] = None
    image_filter_enabled: Optional[bool] = None
    file_filter_enabled: Optional[bool] = None


class ResolverTestUrlBody(BaseModel):
    """Request body for POST /api/resolver/test-url."""
    url: str = Field(..., min_length=1)
    type: str = Field(default="html", pattern="^(html|image)$")


class AllowedFileUrlBody(BaseModel):
    """Request body for add/remove allowed file download URL. Admin only."""
    url: str = Field(..., min_length=1)


# Site injections (הזרקת קוד והסתרת תוכן לאתר – אדמין)
class SiteInjectionCreate(BaseModel):
    """Create site injection: URL pattern (like global rules), optional head/body code, hide selectors."""
    url: str = Field(..., min_length=1, description="כתובת אתר (דומיין או דומיין/נתיב)")
    head_code: Optional[str] = Field(None, description="קוד להזרקה ל־<head>")
    body_code: Optional[str] = Field(None, description="קוד להזרקה לפני </body>")
    hide_selectors: Optional[List[str]] = Field(None, description="בוררים CSS להסתרת רכיבים (למשל ['.ad', '#sidebar'])")
    include_subdomains: bool = Field(default=False, description="כלול תת־דומיינים")
    path_exact_only: bool = Field(default=True, description="True=רק הכתובת הזו, False=גם כל הנתיבים מתחת")
    enabled: bool = Field(default=True)


class SiteInjectionUpdate(BaseModel):
    """Update site injection."""
    url: Optional[str] = Field(None, min_length=1)
    head_code: Optional[str] = None
    body_code: Optional[str] = None
    hide_selectors: Optional[List[str]] = None
    include_subdomains: Optional[bool] = None
    path_exact_only: Optional[bool] = None
    enabled: Optional[bool] = None


class SiteInjectionResponse(BaseModel):
    """Site injection rule for API response."""
    id: int
    domain_pattern: str
    path_pattern: Optional[str]
    include_subdomains: bool
    path_exact_only: bool = True
    head_code: Optional[str]
    body_code: Optional[str]
    hide_selectors_list: List[str]  # parsed from hide_selectors JSON
    enabled: bool
    created_at: int
    updated_at: int

    @property
    def display_url(self) -> str:
        url = self.domain_pattern or ""
        if self.path_pattern:
            url += self.path_pattern
        return url

    class Config:
        from_attributes = True


# Support tickets (פניות משתמשים)
class SupportAttachmentItem(BaseModel):
    name: str
    url: str


class SupportAttachmentInput(BaseModel):
    name: str = Field(..., max_length=200)
    # Must point at a file uploaded through /api/support/upload – never javascript:, data: or external links.
    url: str = Field(..., max_length=300, pattern=r"^/uploads/support/[A-Za-z0-9_.\-]+$")


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="")
    attachments: Optional[List[SupportAttachmentInput]] = None
    """Optional: attach a rule request (בקשה לפתיחה). Creates rule_request and ticket with snapshot for client."""
    attached_request: Optional[RuleRequestCreate] = None


class SupportTicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    content: str
    created_at: int
    updated_at: int
    content_preview: Optional[str] = None  # first ~200 chars for list views
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_avatar_url: Optional[str] = None
    replies_count: Optional[int] = None
    unread_replies_count: Optional[int] = None  # for ticket owner: replies not yet read
    # For ticket owner: number of support (system) replies not yet read by the user
    unread_support_replies_for_owner: Optional[int] = None
    # For admins: number of user replies that have not yet been read by any admin (shared across all admins)
    unread_user_replies_for_admin: Optional[int] = None
    attachments: Optional[List[SupportAttachmentItem]] = None
    attached_rule_request_id: Optional[int] = None
    """Request as the user sent it (for client display). Admin edits are not shown to client."""
    request_snapshot_for_client: Optional[str] = None  # JSON
    """Current status of the attached request: pending / approved / rejected."""
    attached_request_status: Optional[str] = None

    class Config:
        from_attributes = True


class SupportReplyCreate(BaseModel):
    content: str = Field(default="")
    attachments: Optional[List[SupportAttachmentInput]] = None
    """Optional: user sends edited copy of request as reply (JSON snapshot)."""
    attached_request_snapshot: Optional[str] = None
    """True = תגובת תמיכה (נשלח מפניות שהתקבלו), False = תגובת משתמש (נשלח מפניות שלי)."""
    is_support_reply: Optional[bool] = None


class SupportReplyResponse(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    content: str
    created_at: int
    author_first_name: Optional[str] = None
    author_last_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    is_unread: Optional[bool] = None  # True if ticket owner has not read this reply
    attachments: Optional[List[SupportAttachmentItem]] = None
    attached_request_snapshot: Optional[str] = None  # JSON when reply is "edited copy" of request
    is_support_reply: bool = False  # True = תגובת תמיכה, False = תגובת משתמש (נשמר לפי מקום השליחה)

    class Config:
        from_attributes = True


class SupportTicketsBulkDeleteBody(BaseModel):
    """Admin: delete multiple support tickets."""
    ticket_ids: List[int] = Field(..., min_length=1, description="רשימת מזהה פניות למחיקה")

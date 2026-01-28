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
    phone: str = Field(..., min_length=8, max_length=20, pattern="^[0-9\\-\\+\\s\\(\\)]+$")
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20, pattern="^[0-9\\-\\+\\s\\(\\)]+$")
    avatar_url: Optional[str] = Field(None, max_length=500)


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
    
    class Config:
        from_attributes = True


class RequestPhoneCode(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)


class VerifyPhoneCode(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
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
    type: str = Field(default="*", pattern="^(\\*|image|video)$")
    include_subdomains: bool = Field(default=False)
    
    @validator('url')
    def validate_url(cls, v):
        """Remove protocol and normalize URL."""
        # Remove http:// or https://
        v = v.strip()
        if v.startswith('http://'):
            v = v[7:]
        elif v.startswith('https://'):
            v = v[8:]
        
        # Check if starts with *.
        if v.startswith('*.'):
            # This will be handled by include_subdomains
            pass
        
        # Split domain and path
        if '/' in v:
            parts = v.split('/', 1)
            domain = parts[0]
            path = '/' + parts[1] if parts[1] else '/'
        else:
            domain = v
            path = None
        
        if not domain:
            raise ValueError("URL חייב לכלול דומיין")
        
        return v


class RuleUpdate(BaseModel):
    url: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|block)$")
    type: Optional[str] = Field(None, pattern="^(\\*|image|video)$")
    include_subdomains: Optional[bool] = None


class RuleResponse(BaseModel):
    id: int
    profile_id: int
    domain_pattern: str
    path_pattern: Optional[str]
    action: str
    type: str
    include_subdomains: bool
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
    phone: str = Field(..., min_length=8, max_length=20)
    password: str

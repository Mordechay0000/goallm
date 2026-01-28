"""
Authentication utilities for FastAPI.
Uses python-jose for JWT and security.py for password verification.
Phone is the unique identifier (not email).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import timedelta

from .services import get_user_by_id, get_user_by_phone
from .security import create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

security = HTTPBearer()


def create_user_access_token(user_id: int, phone: str) -> str:
    """Create JWT access token for a user. Phone is the unique identifier."""
    data = {
        "sub": str(user_id),
        "phone": phone,
    }
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(data=data, expires_delta=expires_delta)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Get current authenticated user from token. Phone is the unique identifier."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token לא תקין או פג תוקף",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = int(payload["sub"])
    phone: str = payload.get("phone")
    
    # Backward compatibility: check for email in old tokens
    if not phone:
        email: str = payload.get("email")
        if email:
            # Old token format - get user by email and verify
            from .services import get_user_by_email
            user = get_user_by_email(email)
            if user and user["id"] == user_id:
                return {
                    "id": user["id"],
                    "email": user.get("email"),
                    "phone": user.get("phone")
                }
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token לא תקין",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user by ID (phone is unique, but we use ID for lookup)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="משתמש לא נמצא",
        )
    
    # Verify phone matches (if provided in token)
    if user.get("phone") and phone and user["phone"] != phone:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token לא תקין",
        )
    
    return {
        "id": user["id"],
        "email": user.get("email"),
        "phone": user.get("phone")
    }

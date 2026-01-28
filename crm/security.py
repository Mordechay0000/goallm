"""
Security utilities using official libraries for authentication and password management.
Uses passlib with bcrypt for password hashing and python-jose for JWT tokens.
"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import bcrypt
from fastapi import HTTPException, status
import os

# Bcrypt rounds (higher = more secure but slower, 12 is recommended)
BCRYPT_ROUNDS = 12

# JWT Configuration
# In production, set SECRET_KEY as environment variable
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production-use-secrets-token-urlsafe-32")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash using bcrypt.
    Uses bcrypt library directly (industry standard).
    """
    try:
        # Encode password to bytes
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Uses bcrypt library directly (industry standard).
    Bcrypt automatically handles salt generation.
    """
    # Encode password to bytes
    password_bytes = password.encode('utf-8')
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token using python-jose.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token using PyJWT.
    Returns None if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (InvalidTokenError, ExpiredSignatureError):
        return None


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "סיסמה חייבת להכיל לפחות 8 תווים"
    
    if len(password) > 128:
        return False, "סיסמה לא יכולה להכיל יותר מ-128 תווים"
    
    # Check for at least one digit
    if not any(char.isdigit() for char in password):
        return False, "סיסמה חייבת להכיל לפחות ספרה אחת"
    
    # Check for at least one letter
    if not any(char.isalpha() for char in password):
        return False, "סיסמה חייבת להכיל לפחות אות אחת"
    
    return True, None

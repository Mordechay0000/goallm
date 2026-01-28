"""
Rate limiting using slowapi (official Flask-Limiter port for FastAPI).
Prevents brute force attacks and abuse.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Create limiter instance
limiter = Limiter(key_func=get_remote_address)


def get_rate_limiter():
    """Get the rate limiter instance."""
    return limiter


# Rate limit decorators for different endpoints
def rate_limit_login():
    """Rate limit for login attempts: 5 per minute per IP."""
    return limiter.limit("5/minute")


def rate_limit_register():
    """Rate limit for registration: 3 per hour per IP."""
    return limiter.limit("3/hour")


def rate_limit_api():
    """Rate limit for API calls: 100 per minute per IP."""
    return limiter.limit("100/minute")


def rate_limit_strict():
    """Strict rate limit: 10 per minute per IP."""
    return limiter.limit("10/minute")

"""Framework integrations for FastAPI."""

from .decorator import (
    create_api_key_fallback,
    create_auth_header_fallback,
    create_user_id_fallback,
    throttle,
)
from .middleware import RateLimitMiddleware

__all__ = [
    "throttle",
    "RateLimitMiddleware",
    "create_auth_header_fallback",
    "create_api_key_fallback",
    "create_user_id_fallback",
]

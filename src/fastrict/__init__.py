"""FastAPI Rate Limiter - A comprehensive rate limiting system for FastAPI.

This package provides:
- Middleware for global rate limiting
- Decorators for route-specific rate limiting
- Flexible key extraction strategies
- Redis-backed sliding window rate limiting
- Production-ready performance and monitoring

Example usage:
    from fastrict import RateLimitMiddleware, throttle
    from fastrict.strategies import RateLimitStrategyName

    # Add middleware
    app.add_middleware(RateLimitMiddleware)

    # Use decorator
    @throttle(strategy=RateLimitStrategyName.SHORT)
    async def my_endpoint():
        return {"data": "limited"}
"""

from .adapters import MemoryRateLimitRepository, RedisRateLimitRepository
from .entities import (
    KeyExtractionStrategy,
    KeyExtractionType,
    RateLimitConfig,
    RateLimitMode,
    RateLimitResult,
    RateLimitStrategy,
    RateLimitStrategyName,
)
from .frameworks import RateLimitMiddleware, throttle
from .use_cases import KeyExtractionUseCase, RateLimitUseCase

__version__ = "0.0.3"
__author__ = "Mohammad Mahdi Samei"
__email__ = "9259samei@gmail.com"

__all__ = [
    # Core entities
    "KeyExtractionStrategy",
    "KeyExtractionType",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStrategy",
    "RateLimitStrategyName",
    "RateLimitMode",
    # Framework components
    "RateLimitMiddleware",
    "throttle",
    # Use cases
    "KeyExtractionUseCase",
    "RateLimitUseCase",
    # Adapters
    "RedisRateLimitRepository",
    "MemoryRateLimitRepository",
]

"""Adapters for external systems integration."""

from ..use_cases.interface.interface import IRateLimitRepository
from .redis_repository import RedisRateLimitRepository
from .memory_repository import MemoryRateLimitRepository

__all__ = [
    "IRateLimitRepository",
    "RedisRateLimitRepository",
    "MemoryRateLimitRepository",
]

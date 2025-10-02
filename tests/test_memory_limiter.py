#!/usr/bin/env python3
"""
Test rate limiting functionality using memory repository.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import the rate limiter components
from fastrict import (
    KeyExtractionUseCase,
    MemoryRateLimitRepository,
    RateLimitMiddleware,
    RateLimitStrategy,
    RateLimitStrategyName,
    RateLimitUseCase,
    throttle,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Rate Limiter Test", version="1.0.0")

# Setup rate limiting components with memory repository
repository = MemoryRateLimitRepository(key_prefix="test", logger=logger)
key_extraction = KeyExtractionUseCase(logger=logger)
rate_limiter = RateLimitUseCase(
    rate_limit_repository=repository,
    key_extraction_use_case=key_extraction,
    logger=logger,
)

# Define custom strategies for testing
custom_strategies = [
    RateLimitStrategy(
        name=RateLimitStrategyName.SHORT, limit=2, ttl=30
    ),  # 2/30sec for testing
    RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=5, ttl=60),  # 5/min
    RateLimitStrategy(name=RateLimitStrategyName.LONG, limit=10, ttl=120),  # 10/2min
]

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    rate_limit_use_case=rate_limiter,
    default_strategies=custom_strategies,
    default_strategy_name=RateLimitStrategyName.MEDIUM,
    excluded_paths=["/", "/health", "/docs", "/openapi.json"],
)


# Health check (excluded from rate limiting)
@app.get("/")
async def root():
    return {"message": "Rate Limiter Test", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Default rate limited endpoint
@app.get("/api/data")
async def get_data():
    """Default endpoint with medium rate limiting (5 requests per minute)."""
    return {
        "data": "This endpoint uses default rate limiting",
        "timestamp": "2024-01-01T00:00:00Z",
    }


# Strict rate limiting
@app.post("/api/strict")
@throttle(strategy=RateLimitStrategyName.SHORT)
async def strict_endpoint():
    """Strict endpoint with very low limits (2 requests per 30 seconds)."""
    return {"message": "This is a strict endpoint", "limit": "2/30s"}


# Rate limit status endpoint
@app.get("/api/status")
async def rate_limit_status(request: Request):
    """Get current rate limit status."""
    try:
        result = rate_limiter.get_current_usage(request)
        return {
            "allowed": result.allowed,
            "current_count": result.current_count,
            "limit": result.limit,
            "remaining": result.remaining_requests,
            "reset_in_seconds": result.ttl,
            "usage_percentage": result.usage_percentage,
            "strategy": result.strategy_name,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get rate limit status", "detail": str(e)},
        )


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Rate Limiter Test with Memory Repository")
    print("📋 Available endpoints:")
    print("  GET  /api/data    - Default rate limiting (5/min)")
    print("  POST /api/strict  - Strict rate limiting (2/30s)")
    print("  GET  /api/status  - Check current rate limit status")
    print()
    print("🧪 Test commands:")
    print("  curl http://localhost:8000/api/data")
    print("  curl -X POST http://localhost:8000/api/strict")
    print("  curl http://localhost:8000/api/status")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")

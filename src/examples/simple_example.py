#!/usr/bin/env python3
"""
Simple example demonstrating fastrict usage.

Run with: python examples/simple_example.py
Then test with: curl http://localhost:8000/api/data
"""

from chromatrace import LoggingConfig, LoggingSettings
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import the rate limiter components
from fastrict import (
    KeyExtractionType,
    KeyExtractionUseCase,
    RateLimitMiddleware,
    RateLimitMode,
    RateLimitStrategy,
    RateLimitStrategyName,
    RateLimitUseCase,
    RedisRateLimitRepository,
    throttle,
)

# Configure logging
logging_config = LoggingConfig(LoggingSettings(application_level="LimitGuard"))
logger = logging_config.get_logger("fastrict")

# Create FastAPI app
app = FastAPI(title="Rate Limiter Example", version="1.0.0")


# Setup rate limiting components
repository = RedisRateLimitRepository.from_url(
    redis_url="redis://:SillyPasswordsAreNotSecure@localhost:46379/5",
    logger=logger,
    key_prefix="example",
)
key_extraction = KeyExtractionUseCase(logger=logger)
rate_limiter = RateLimitUseCase(
    rate_limit_repository=repository,
    key_extraction_use_case=key_extraction,
    logger=logger,
)

# Define custom strategies
custom_strategies = [
    RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=3, ttl=60),  # 3/min
    RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=5, ttl=120),  # 5/2min
    RateLimitStrategy(name=RateLimitStrategyName.LONG, limit=50, ttl=3600),  # 50/hour
]

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    rate_limit_use_case=rate_limiter,
    default_strategies=custom_strategies,
    default_strategy_name=RateLimitStrategyName.MEDIUM,
    excluded_paths=["/health", "/docs", "/openapi.json"],
    rate_limit_mode=RateLimitMode.GLOBAL,  # Default to global rate limiting
)


# Health check (excluded from rate limiting)
@app.get("/")
async def root():
    return {"message": "FastAPI Rate Limiter Example", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Default rate limited endpoint
@app.get("/api/data")
async def get_data():
    """Default endpoint with medium rate limiting (10 requests per 5 minutes)."""
    return {
        "data": "This endpoint uses default rate limiting",
        "timestamp": "2024-01-01T00:00:00Z",
    }


# Strict rate limiting
@app.post("/api/login")
@throttle(strategy=RateLimitStrategyName.SHORT)
async def login():
    """Login endpoint with strict rate limiting (3 requests per minute)."""
    return {"message": "Login successful", "token": "fake-jwt-token"}


# Custom rate limiting
@app.post("/api/upload")
@throttle(limit=2, ttl=60)  # 2 requests per minute
async def upload_file():
    """File upload with custom rate limiting."""
    return {"message": "File uploaded successfully", "file_id": "12345"}


# API key based rate limiting
@app.get("/api/premium")
@throttle(
    limit=20,
    ttl=3600,
    key_type=KeyExtractionType.HEADER,
    key_field="X-API-Key",
    key_default="anonymous",
)
async def premium_endpoint():
    """Premium endpoint using API key for rate limiting."""
    return {"data": "Premium content", "features": ["advanced", "priority"]}


# User ID based rate limiting
@app.get("/api/user-data")
@throttle(
    limit=15,
    ttl=600,
    key_type=KeyExtractionType.QUERY_PARAM,
    key_field="user_id",
    key_default="anonymous",
)
async def get_user_data():
    """User-specific endpoint with query parameter rate limiting."""
    return {"data": "User-specific data", "preferences": {}}


# Custom key extraction
def extract_session_key(request: Request) -> str:
    """Custom function to extract session-based key."""
    session_id = request.headers.get("Session-ID")
    user_id = request.headers.get("User-ID")

    if session_id and user_id:
        return f"session:{session_id}:user:{user_id}"
    elif session_id:
        return f"session:{session_id}"
    else:
        return request.client.host


@app.get("/api/session-data")
@throttle(
    limit=25,
    ttl=600,
    key_type=KeyExtractionType.CUSTOM,
    key_extractor=extract_session_key,
)
async def session_data():
    """Endpoint using custom session-based rate limiting."""
    return {"data": "Session-specific data", "session_info": {}}


# Admin bypass example
def bypass_for_admins(request: Request) -> bool:
    """Bypass rate limiting for admin users."""
    return request.headers.get("User-Role") == "admin"


@app.get("/api/admin")
@throttle(
    limit=5,
    ttl=60,
    bypass_function=bypass_for_admins,
    custom_error_message="Admin endpoint is rate limited for non-admin users",
)
async def admin_endpoint():
    """Admin endpoint with bypass function."""
    return {"data": "Admin-only data", "admin_features": []}


# Global rate limiting example (shares limit with all other global endpoints)
@app.get("/api/global-data")
@throttle(
    limit=5,
    ttl=300,
    rate_limit_mode=RateLimitMode.GLOBAL,
)
async def global_data():
    """This endpoint shares rate limit globally (affects all global endpoints)."""
    return {
        "data": "Global rate limited data",
        "note": "Shares limits with other global endpoints",
    }


# Per-route rate limiting example (independent limit per route)
@app.get("/api/per-route-data")
@throttle(
    limit=5,
    ttl=60,
    rate_limit_mode=RateLimitMode.PER_ROUTE,
)
async def per_route_data():
    """This endpoint has its own independent rate limit pool."""
    return {
        "data": "Per-route rate limited data",
        "note": "Independent limits per route",
    }


# Another per-route endpoint to demonstrate independence
@app.get("/api/another-route")
@throttle(
    limit=5,
    ttl=60,
    rate_limit_mode=RateLimitMode.PER_ROUTE,
)
async def another_per_route():
    """Another per-route endpoint with independent limits."""
    return {"data": "Another route data", "note": "Independent from other routes"}


# Demonstrate default behavior (decorated routes use PER_ROUTE by default)
@app.get("/api/default-behavior")
@throttle(limit=3, ttl=60)
async def default_behavior():
    """Decorated routes default to PER_ROUTE mode when not specified."""
    return {
        "data": "Default behavior",
        "note": "Defaults to PER_ROUTE for decorated routes",
    }


@app.get("/api/rate-limit-status")
@throttle(bypass=True)
async def rate_limit_status(request: Request):
    """Get current rate limit status without incrementing counter."""

    try:
        result = rate_limiter.get_current_usage(
            request=request,
            middleware_rate_limit_mode=RateLimitMode.GLOBAL,
            route_path=request.url.path,
        )
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

    print("🚀 Starting FastAPI Rate Limiter Example")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🏥 Health Check: http://localhost:8000/health")
    print()
    print("📋 Available endpoints:")
    print("  GET  /api/data            - Default rate limiting (10/5min)")
    print("  POST /api/login           - Strict rate limiting (3/min)")
    print("  POST /api/upload          - Custom rate limiting (2/min)")
    print("  GET  /api/premium         - API key rate limiting (20/hour)")
    print("  GET  /api/user-data       - User ID rate limiting (15/10min)")
    print("  GET  /api/session-data    - Custom session rate limiting (25/10min)")
    print("  GET  /api/admin           - Admin bypass (5/min for non-admins)")
    print("  GET  /api/global-data     - Global shared rate limiting (20/5min)")
    print("  GET  /api/per-route-data  - Per-route independent limiting (5/min)")
    print("  GET  /api/another-route   - Another per-route independent (5/min)")
    print("  GET  /api/default-behavior - Default per-route for decorated (3/min)")
    print("  GET  /api/rate-limit-status - Check current rate limit status")
    print()
    print("🧪 Test commands:")
    print("  curl http://localhost:8000/api/data")
    print("  curl -H 'X-API-Key: test123' http://localhost:8000/api/premium")
    print("  curl -H 'User-Role: admin' http://localhost:8000/api/admin")
    print("  curl 'http://localhost:8000/api/user-data?user_id=123'")
    print("  curl http://localhost:8000/api/rate-limit-status")
    print("  # Test per-route independence:")
    print("  curl http://localhost:8000/api/per-route-data")
    print("  curl http://localhost:8000/api/another-route")
    print()
    print("💡 Rate Limiting Modes:")
    print("  - GLOBAL: All endpoints share the same rate limit pool")
    print("  - PER_ROUTE: Each route has independent rate limit pools")
    print("  - Decorated routes default to PER_ROUTE unless overridden")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

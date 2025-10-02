#!/usr/bin/env python3
"""Example demonstrating memory repository usage for FastAPI rate limiting."""

from fastapi import FastAPI, HTTPException
from fastrict.adapters import MemoryRateLimitRepository
from fastrict.use_cases import RateLimitUseCase, KeyExtractionUseCase
from fastrict.entities import (
    RateLimitStrategy,
    KeyExtractionStrategy,
    KeyExtractionType,
)

app = FastAPI()

# Initialize memory repository for caching
memory_repo = MemoryRateLimitRepository(
    key_prefix="api_rate_limit",
    cleanup_interval=60,  # Cleanup expired keys every 60 seconds
    auto_cleanup=True,
)

# Initialize use cases
key_extraction = KeyExtractionUseCase()
rate_limiter = RateLimitUseCase(repository=memory_repo)

# Define rate limiting strategies
strategies = {
    "strict": RateLimitStrategy(
        max_requests=10, window_seconds=60, strategy_name="strict"
    ),
    "moderate": RateLimitStrategy(
        max_requests=100, window_seconds=60, strategy_name="moderate"
    ),
    "lenient": RateLimitStrategy(
        max_requests=1000, window_seconds=60, strategy_name="lenient"
    ),
}


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Simple rate limiting middleware using memory repository."""

    # Extract key based on IP address
    key_strategy = KeyExtractionStrategy(
        key_type=KeyExtractionType.IP_ADDRESS, custom_key_func=None
    )

    try:
        # Extract rate limiting key
        rate_limit_key = await key_extraction.extract_key(request, key_strategy)

        # Apply moderate rate limiting strategy
        strategy = strategies["moderate"]

        # Check rate limit
        result = await rate_limiter.check_rate_limit(rate_limit_key, strategy)

        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": strategy.max_requests,
                    "window": strategy.window_seconds,
                    "current_count": result.current_count,
                    "retry_after": result.retry_after,
                },
            )

        # Add rate limiting headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(strategy.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, strategy.max_requests - result.current_count)
        )
        response.headers["X-RateLimit-Reset"] = str(result.reset_time)

        return response

    except HTTPException:
        raise
    except Exception as e:
        # Log error and allow request to proceed
        print(f"Rate limiting error: {e}")
        return await call_next(request)


@app.get("/")
async def root():
    """Basic endpoint."""
    return {"message": "Hello World!"}


@app.get("/api/data")
async def get_data():
    """API endpoint with rate limiting."""
    return {"data": "This endpoint is rate limited using memory repository"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "cache": "memory"}


@app.get("/admin/rate-limit-stats")
async def rate_limit_stats():
    """Get rate limiting statistics from memory repository."""
    try:
        # Get memory statistics
        stats = memory_repo.get_memory_stats()

        # Get all active keys
        active_keys = memory_repo.get_all_keys(cleanup_first=True)

        # Get detailed info for a few keys (limit to prevent overwhelming response)
        key_details = {}
        for key in active_keys[:10]:  # Limit to first 10 keys
            info = memory_repo.get_rate_limit_info(key, 60)  # Use 60s window
            key_details[key] = {
                "count": info.get("current_count", 0),
                "oldest_entry": info.get("oldest_entry"),
                "newest_entry": info.get("newest_entry"),
                "ttl": memory_repo.get_ttl(key),
            }

        return {
            "repository_type": "memory",
            "statistics": stats,
            "active_keys_count": len(active_keys),
            "sample_keys": key_details,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.post("/admin/cleanup")
async def cleanup_expired():
    """Manually trigger cleanup of expired rate limit keys."""
    try:
        cleaned_count = memory_repo.cleanup_expired_keys()
        return {"message": "Cleanup completed", "cleaned_keys": cleaned_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.delete("/admin/clear-all")
async def clear_all_rate_limits():
    """Clear all rate limiting data (use with caution!)."""
    try:
        success = memory_repo.clear_all()
        if success:
            return {"message": "All rate limit data cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI server with Memory Rate Limiting...")
    print("Features:")
    print("- In-memory rate limiting (no Redis required)")
    print("- Sliding window rate limiting")
    print("- Automatic cleanup of expired entries")
    print("- Thread-safe operations")
    print("- Admin endpoints for monitoring")
    print("\nEndpoints:")
    print("- GET /: Basic endpoint")
    print("- GET /api/data: Rate limited API endpoint")
    print("- GET /health: Health check")
    print("- GET /admin/rate-limit-stats: View rate limiting statistics")
    print("- POST /admin/cleanup: Manually cleanup expired keys")
    print("- DELETE /admin/clear-all: Clear all rate limiting data")

    uvicorn.run(app, host="0.0.0.0", port=8000)

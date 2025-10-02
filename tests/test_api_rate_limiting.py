"""
Comprehensive tests for the FastAPI rate limiter using httpx test client.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.fastrict import (
    RateLimitMiddleware,
    throttle,
    MemoryRateLimitRepository,
    RateLimitUseCase,
    KeyExtractionUseCase,
    RateLimitStrategy,
    RateLimitStrategyName,
    KeyExtractionType,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with rate limiting."""
    test_app = FastAPI(title="Test Rate Limiter", version="1.0.0")

    # Setup rate limiting components with unique prefix for each test
    import time

    repository = MemoryRateLimitRepository(key_prefix=f"test_{int(time.time() * 1000)}")
    key_extraction = KeyExtractionUseCase()
    rate_limiter = RateLimitUseCase(
        rate_limit_repository=repository,
        key_extraction_use_case=key_extraction,
    )

    # Define test strategies with low limits for easy testing
    test_strategies = [
        RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=2, ttl=60),  # 2/min
        RateLimitStrategy(
            name=RateLimitStrategyName.MEDIUM, limit=5, ttl=300
        ),  # 5/5min
        RateLimitStrategy(
            name=RateLimitStrategyName.LONG, limit=10, ttl=3600
        ),  # 10/hour
    ]

    # Add rate limiting middleware
    test_app.add_middleware(
        RateLimitMiddleware,
        rate_limit_use_case=rate_limiter,
        default_strategies=test_strategies,
        default_strategy_name=RateLimitStrategyName.MEDIUM,
        excluded_paths=["/health", "/status", "/api/rate-limit-status"],
    )

    # Health check (excluded from rate limiting)
    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    # Status check (excluded from rate limiting)
    @test_app.get("/status")
    async def status():
        return {"status": "ok"}

    # Default rate limited endpoint
    @test_app.get("/api/data")
    async def get_data():
        return {"data": "This endpoint uses default rate limiting"}

    # Strict rate limiting
    @test_app.post("/api/login")
    @throttle(strategy=RateLimitStrategyName.SHORT)
    async def login():
        return {"message": "Login successful"}

    # Custom rate limiting
    @test_app.post("/api/upload")
    @throttle(limit=3, ttl=60)  # 3 requests per minute
    async def upload_file():
        return {"message": "File uploaded successfully"}

    # API key based rate limiting
    @test_app.get("/api/premium")
    @throttle(
        limit=4,
        ttl=300,
        key_type=KeyExtractionType.HEADER,
        key_field="X-API-Key",
        key_default="anonymous",
    )
    async def premium_endpoint():
        return {"data": "Premium content"}

    # User ID based rate limiting
    @test_app.get("/api/user-data")
    @throttle(
        limit=3,
        ttl=600,
        key_type=KeyExtractionType.QUERY_PARAM,
        key_field="user_id",
        key_default="anonymous",
    )
    async def get_user_data():
        return {"data": "User-specific data"}

    # Admin bypass example
    def bypass_for_admins(request: Request) -> bool:
        return request.headers.get("User-Role") == "admin"

    @test_app.get("/api/admin")
    @throttle(
        limit=2,
        ttl=60,
        bypass_function=bypass_for_admins,
        custom_error_message="Admin endpoint is rate limited for non-admin users",
    )
    async def admin_endpoint():
        return {"data": "Admin-only data"}

    # Rate limit status endpoint
    @test_app.get("/api/rate-limit-status")
    async def rate_limit_status(request: Request):
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

    return test_app


@pytest.fixture
async def client(app):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestBasicRateLimiting:
    """Test basic rate limiting functionality."""

    async def test_excluded_paths_not_rate_limited(self, client):
        """Test that excluded paths are not rate limited."""
        # Make many requests to excluded paths - should all succeed
        for i in range(10):
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

        for i in range(10):
            response = await client.get("/status")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    async def test_default_rate_limiting(self, client):
        """Test default rate limiting on /api/data endpoint."""
        # First 5 requests should succeed (limit is 5)
        for i in range(5):
            response = await client.get("/api/data")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Window" in response.headers

        # 6th request should be rate limited
        response = await client.get("/api/data")
        assert response.status_code == 429
        assert "message" in response.json()
        assert "retry_after" in response.json()

    async def test_decorator_rate_limiting(self, client):
        """Test rate limiting with throttle decorator."""
        # Test SHORT strategy (limit=2)
        # First 2 requests should succeed
        for i in range(2):
            response = await client.post("/api/login")
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = await client.post("/api/login")
        assert response.status_code == 429

    async def test_custom_rate_limiting(self, client):
        """Test custom rate limiting with inline limit/ttl."""
        # Test custom limit (3 requests per minute)
        for i in range(3):
            response = await client.post("/api/upload")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = await client.post("/api/upload")
        assert response.status_code == 429


class TestKeyExtractionTypes:
    """Test different key extraction strategies."""

    async def test_ip_based_rate_limiting(self, client):
        """Test IP-based rate limiting (default)."""
        # All requests from same client should be counted together
        for i in range(5):
            response = await client.get("/api/data")
            assert response.status_code == 200

        # Next request should be rate limited
        response = await client.get("/api/data")
        assert response.status_code == 429

    async def test_header_based_rate_limiting(self, client):
        """Test header-based rate limiting."""
        # Test with API key header
        headers = {"X-API-Key": "test-key-123"}

        # First 4 requests with same API key should succeed
        for i in range(4):
            response = await client.get("/api/premium", headers=headers)
            assert response.status_code == 200

        # 5th request should be rate limited
        response = await client.get("/api/premium", headers=headers)
        assert response.status_code == 429

        # But requests with different API key should still work
        different_headers = {"X-API-Key": "different-key-456"}
        response = await client.get("/api/premium", headers=different_headers)
        assert response.status_code == 200

    async def test_query_param_based_rate_limiting(self, client):
        """Test query parameter-based rate limiting."""
        # Test with user_id parameter
        params = {"user_id": "user123"}

        # First 3 requests for same user should succeed
        for i in range(3):
            response = await client.get("/api/user-data", params=params)
            assert response.status_code == 200

        # 4th request should be rate limited
        response = await client.get("/api/user-data", params=params)
        assert response.status_code == 429

        # But requests for different user should still work
        different_params = {"user_id": "user456"}
        response = await client.get("/api/user-data", params=different_params)
        assert response.status_code == 200


class TestBypassFunctionality:
    """Test bypass functionality."""

    async def test_admin_bypass(self, client):
        """Test that admin users can bypass rate limits."""
        # Regular user should be rate limited after 2 requests
        for i in range(2):
            response = await client.get("/api/admin")
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = await client.get("/api/admin")
        assert response.status_code == 429

        # But admin user should bypass rate limiting
        admin_headers = {"User-Role": "admin"}
        for i in range(10):  # Make many requests as admin
            response = await client.get("/api/admin", headers=admin_headers)
            assert response.status_code == 200


class TestRateLimitHeaders:
    """Test rate limit headers in responses."""

    async def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are present in responses."""
        response = await client.get("/api/data")
        assert response.status_code == 200

        # Check required headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Window" in response.headers
        assert "X-RateLimit-Used" in response.headers

        # Check header values
        assert int(response.headers["X-RateLimit-Limit"]) == 5
        assert int(response.headers["X-RateLimit-Used"]) == 1
        assert int(response.headers["X-RateLimit-Remaining"]) == 4

    async def test_rate_limit_headers_decrease(self, client):
        """Test that rate limit headers decrease with each request."""
        # First request
        response = await client.get("/api/data")
        assert int(response.headers["X-RateLimit-Remaining"]) == 4
        assert int(response.headers["X-RateLimit-Used"]) == 1

        # Second request
        response = await client.get("/api/data")
        assert int(response.headers["X-RateLimit-Remaining"]) == 3
        assert int(response.headers["X-RateLimit-Used"]) == 2

        # Third request
        response = await client.get("/api/data")
        assert int(response.headers["X-RateLimit-Remaining"]) == 2
        assert int(response.headers["X-RateLimit-Used"]) == 3


class TestStatusEndpoint:
    """Test the rate limit status endpoint."""

    async def test_status_endpoint_shows_usage(self, client):
        """Test that status endpoint shows current usage."""
        # Make some requests first
        await client.get("/api/data")
        await client.get("/api/data")

        # Check status
        response = await client.get("/api/rate-limit-status")
        assert response.status_code == 200

        status = response.json()
        assert "current_count" in status
        assert "limit" in status
        assert "remaining" in status
        assert "strategy" in status

        # Should show 2 requests used (status endpoint is excluded from counting)
        assert status["current_count"] == 2
        assert status["limit"] == 5
        assert status["remaining"] == 3
        assert status["strategy"] == "medium"

    async def test_status_endpoint_not_counted(self, client):
        """Test that status endpoint requests are not counted against limit."""
        # Make many requests to status endpoint
        for i in range(10):
            response = await client.get("/api/rate-limit-status")
            assert response.status_code == 200

        # Should still be able to make requests to rate-limited endpoints
        response = await client.get("/api/data")
        assert response.status_code == 200


class TestErrorMessages:
    """Test error messages and response format."""

    async def test_rate_limit_error_format(self, client):
        """Test the format of rate limit error responses."""
        # Exhaust rate limit
        for i in range(5):
            await client.get("/api/data")

        # Next request should return proper error format
        response = await client.get("/api/data")
        assert response.status_code == 429

        error = response.json()
        assert "message" in error
        assert "retry_after" in error
        assert "limit" in error
        assert "window" in error

        assert error["limit"] == 5
        assert error["window"] == 300

    async def test_custom_error_message(self, client):
        """Test custom error messages."""
        # Exhaust rate limit for admin endpoint
        for i in range(2):
            await client.get("/api/admin")

        # Next request should return custom error message
        response = await client.get("/api/admin")
        assert response.status_code == 429

        error = response.json()
        assert "Admin endpoint is rate limited for non-admin users" in error["message"]


class TestConcurrency:
    """Test concurrent requests."""

    async def test_concurrent_requests(self, client):
        """Test that concurrent requests are properly rate limited."""
        import asyncio

        # Make 10 concurrent requests
        tasks = [client.get("/api/data") for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful and rate-limited responses
        successful = sum(
            1 for r in responses if hasattr(r, "status_code") and r.status_code == 200
        )
        rate_limited = sum(
            1 for r in responses if hasattr(r, "status_code") and r.status_code == 429
        )

        # Should have exactly 5 successful and 5 rate-limited
        assert successful == 5
        assert rate_limited == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

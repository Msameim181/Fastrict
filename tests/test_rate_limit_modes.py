#!/usr/bin/env python3
"""
Test the new rate limiting modes functionality.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastrict import (
    KeyExtractionUseCase,
    MemoryRateLimitRepository,
    RateLimitMiddleware,
    RateLimitMode,
    RateLimitStrategy,
    RateLimitStrategyName,
    RateLimitUseCase,
    throttle,
)


@pytest.fixture
def app_global_mode():
    """Create a test FastAPI app with GLOBAL rate limiting mode."""
    test_app = FastAPI(title="Test Global Rate Limiter", version="1.0.0")

    # Setup rate limiting components
    repository = MemoryRateLimitRepository(key_prefix="test_global")
    key_extraction = KeyExtractionUseCase()
    rate_limiter = RateLimitUseCase(
        rate_limit_repository=repository,
        key_extraction_use_case=key_extraction,
    )

    # Define test strategies with low limits for easy testing
    test_strategies = [
        RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=2, ttl=60),
        RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=5, ttl=300),
    ]

    # Add rate limiting middleware with GLOBAL mode
    test_app.add_middleware(
        RateLimitMiddleware,
        rate_limit_use_case=rate_limiter,
        default_strategies=test_strategies,
        default_strategy_name=RateLimitStrategyName.MEDIUM,
        rate_limit_mode=RateLimitMode.GLOBAL,
        excluded_paths=["/health"],
    )

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    @test_app.get("/api/endpoint1")
    async def endpoint1():
        return {"data": "endpoint1"}

    @test_app.get("/api/endpoint2")
    async def endpoint2():
        return {"data": "endpoint2"}

    # Route with decorator (should force PER_ROUTE mode)
    @test_app.get("/api/decorated")
    @throttle(limit=3, ttl=60)
    async def decorated_endpoint():
        return {"data": "decorated"}

    return test_app


@pytest.fixture
def app_per_route_mode():
    """Create a test FastAPI app with PER_ROUTE rate limiting mode."""
    test_app = FastAPI(title="Test Per-Route Rate Limiter", version="1.0.0")

    # Setup rate limiting components
    repository = MemoryRateLimitRepository(key_prefix="test_per_route")
    key_extraction = KeyExtractionUseCase()
    rate_limiter = RateLimitUseCase(
        rate_limit_repository=repository,
        key_extraction_use_case=key_extraction,
    )

    # Define test strategies
    test_strategies = [
        RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=3, ttl=300),
    ]

    # Add rate limiting middleware with PER_ROUTE mode
    test_app.add_middleware(
        RateLimitMiddleware,
        rate_limit_use_case=rate_limiter,
        default_strategies=test_strategies,
        default_strategy_name=RateLimitStrategyName.MEDIUM,
        rate_limit_mode=RateLimitMode.PER_ROUTE,
        excluded_paths=["/health"],
    )

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    @test_app.get("/api/endpoint1")
    async def endpoint1():
        return {"data": "endpoint1"}

    @test_app.get("/api/endpoint2")
    async def endpoint2():
        return {"data": "endpoint2"}

    return test_app


@pytest.fixture
async def client_global(app_global_mode):
    """Create an async test client for global mode app."""
    transport = ASGITransport(app=app_global_mode)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_per_route(app_per_route_mode):
    """Create an async test client for per-route mode app."""
    transport = ASGITransport(app=app_per_route_mode)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestGlobalRateLimiting:
    """Test global rate limiting behavior."""

    async def test_global_mode_shares_limits_across_routes(self, client_global):
        """Test that global mode shares rate limits across different routes."""
        # Make requests to endpoint1 (should use up the global limit)
        for i in range(5):  # limit is 5
            response = await client_global.get("/api/endpoint1")
            assert response.status_code == 200

        # Now endpoint2 should be rate limited because global limit is exceeded
        response = await client_global.get("/api/endpoint2")
        assert response.status_code == 429

    async def test_decorated_route_uses_per_route_mode(self, client_global):
        """Test that decorated routes use PER_ROUTE mode even in global middleware."""
        # First exhaust the global limit
        for i in range(5):
            response = await client_global.get("/api/endpoint1")
            assert response.status_code == 200

        # Regular endpoint should be blocked
        response = await client_global.get("/api/endpoint2")
        assert response.status_code == 429

        # But decorated endpoint should still work (has its own limit of 3)
        response = await client_global.get("/api/decorated")
        assert response.status_code == 200

        # Can make 2 more requests to decorated endpoint
        for i in range(2):
            response = await client_global.get("/api/decorated")
            assert response.status_code == 200

        # 4th request to decorated endpoint should be rate limited
        response = await client_global.get("/api/decorated")
        assert response.status_code == 429


class TestPerRouteRateLimiting:
    """Test per-route rate limiting behavior."""

    async def test_per_route_mode_separate_limits(self, client_per_route):
        """Test that per-route mode maintains separate limits for each route."""
        # Make requests to endpoint1 (should use up its individual limit)
        for i in range(3):  # limit is 3 per route
            response = await client_per_route.get("/api/endpoint1")
            assert response.status_code == 200

        # endpoint1 should now be rate limited
        response = await client_per_route.get("/api/endpoint1")
        assert response.status_code == 429

        # But endpoint2 should still work (separate limit)
        for i in range(3):
            response = await client_per_route.get("/api/endpoint2")
            assert response.status_code == 200

        # Now endpoint2 should also be rate limited
        response = await client_per_route.get("/api/endpoint2")
        assert response.status_code == 429


class TestRateLimitHeaders:
    """Test that rate limit headers are correctly set."""

    async def test_global_mode_headers(self, client_global):
        """Test headers in global mode."""
        response = await client_global.get("/api/endpoint1")
        assert response.status_code == 200

        # Check rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Used" in response.headers

        # Limit should be 5 (global)
        assert int(response.headers["X-RateLimit-Limit"]) == 5

    async def test_per_route_mode_headers(self, client_per_route):
        """Test headers in per-route mode."""
        response = await client_per_route.get("/api/endpoint1")
        assert response.status_code == 200

        # Check rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Used" in response.headers

        # Limit should be 3 (per route)
        assert int(response.headers["X-RateLimit-Limit"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

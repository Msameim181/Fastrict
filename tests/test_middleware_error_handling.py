"""
Tests for middleware error handling and fail-closed behavior.

This test suite validates:
1. Fail-closed behavior when rate limiting errors occur
2. Fail-open behavior when configured
3. Proper error responses and logging
4. Different error scenarios (Redis failure, key extraction errors, etc.)
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastrict import (
    KeyExtractionUseCase,
    MemoryRateLimitRepository,
    RateLimitMiddleware,
    RateLimitUseCase,
)
from fastrict.entities import (
    RateLimitStrategy,
    RateLimitStrategyName,
)


@pytest.fixture
def rate_limiter():
    """Create a rate limiter for testing."""
    repository = MemoryRateLimitRepository()
    key_extraction = KeyExtractionUseCase()
    return RateLimitUseCase(repository, key_extraction)


class TestFailClosedBehavior:
    """Test that middleware fails closed (rejects requests) on errors by default."""

    def test_redis_connection_failure_fails_closed(self, rate_limiter):
        """Test that Redis connection failures reject requests when fail_on_error=True."""
        app = FastAPI()

        # Add middleware with fail_on_error=True (default)
        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock the repository to raise an exception (simulating Redis failure)
        with patch.object(
            rate_limiter.rate_limit_repository,
            "increment_counter",
            side_effect=Exception("Redis connection failed"),
        ):
            response = client.get("/test")

            # Should reject request with 503
            assert response.status_code == 503
            assert response.json()["error"] == "Service Temporarily Unavailable"
            assert "Retry-After" in response.headers

    def test_key_extraction_failure_fails_closed(self, rate_limiter):
        """Test that key extraction failures reject requests when fail_on_error=True."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock key extraction to raise an exception
        with patch.object(
            rate_limiter.key_extraction_use_case,
            "extract_key",
            side_effect=Exception("Key extraction error"),
        ):
            response = client.get("/test")

            # Should reject request with 503
            assert response.status_code == 503
            assert response.json()["error"] == "Service Temporarily Unavailable"

    def test_corrupted_strategy_fails_closed(self, rate_limiter):
        """Test that corrupted strategy data rejects requests."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
            default_strategy_name=RateLimitStrategyName.MEDIUM,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock strategy lookup to return None (corrupted/missing strategy)
        with patch.object(
            rate_limiter,
            "_strategy_map",
            {},
        ):
            response = client.get("/test")

            # Should reject request with 503
            assert response.status_code == 503

    def test_memory_overflow_fails_closed(self, rate_limiter):
        """Test that memory errors reject requests."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock to raise MemoryError
        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=MemoryError("Out of memory"),
        ):
            response = client.get("/test")

            # Should reject request with 503
            assert response.status_code == 503


class TestFailOpenBehavior:
    """Test that middleware can fail open (allow requests) when configured."""

    def test_redis_failure_fails_open_when_configured(self, rate_limiter):
        """Test that Redis failures allow requests through when fail_on_error=False."""
        app = FastAPI()

        # Add middleware with fail_on_error=False
        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=False,  # Fail open
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock the repository to raise an exception
        with patch.object(
            rate_limiter.rate_limit_repository,
            "increment_counter",
            side_effect=Exception("Redis connection failed"),
        ):
            response = client.get("/test")

            # Should allow request through
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    def test_key_extraction_failure_fails_open_when_configured(self, rate_limiter):
        """Test that key extraction failures allow requests through when fail_on_error=False."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=False,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock key extraction to raise an exception
        with patch.object(
            rate_limiter.key_extraction_use_case,
            "extract_key",
            side_effect=Exception("Key extraction error"),
        ):
            response = client.get("/test")

            # Should allow request through
            assert response.status_code == 200
            assert response.json() == {"message": "success"}


class TestErrorLogging:
    """Test that errors are properly logged."""

    def test_error_logging_includes_context(self, rate_limiter, caplog):
        """Test that error logs include request context."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock to raise an exception
        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=Exception("Test error"),
        ):
            with caplog.at_level("ERROR"):
                client.get("/api/test")

                # Check that error was logged with context
                assert "Rate limiting middleware error" in caplog.text
                assert "/api/test" in caplog.text
                assert "GET" in caplog.text

    def test_fail_open_logs_warning(self, rate_limiter, caplog):
        """Test that fail-open behavior logs a warning."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=False,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock to raise an exception
        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=Exception("Test error"),
        ):
            with caplog.at_level("WARNING"):
                client.get("/test")

                # Check that warning was logged
                assert (
                    "Allowing request through despite rate limiting error"
                    in caplog.text
                )


class TestErrorResponseFormat:
    """Test that error responses have proper format."""

    def test_error_response_format(self, rate_limiter):
        """Test that 503 error responses have correct format."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock to raise an exception
        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=Exception("Test error"),
        ):
            response = client.get("/test")

            # Verify response format
            assert response.status_code == 503
            data = response.json()
            assert "error" in data
            assert "detail" in data
            assert "type" in data
            assert data["type"] == "rate_limit_system_error"
            assert response.headers["Retry-After"] == "60"

    def test_retry_after_header_present(self, rate_limiter):
        """Test that Retry-After header is included in error responses."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=Exception("Test error"),
        ):
            response = client.get("/test")

            assert "Retry-After" in response.headers
            assert int(response.headers["Retry-After"]) > 0


class TestNormalOperationUnaffected:
    """Test that normal operation is unaffected by error handling changes."""

    def test_successful_requests_work_normally(self, rate_limiter):
        """Test that successful requests work as before."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
            default_strategy_name=RateLimitStrategyName.SHORT,  # Use SHORT since that's what we provide
            default_strategies=[
                RateLimitStrategy(
                    name=RateLimitStrategyName.SHORT,
                    limit=5,
                    ttl=60,
                )
            ],
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Make successful requests
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200

        # 6th request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429

    def test_rate_limit_headers_still_added(self, rate_limiter):
        """Test that rate limit headers are still added on success."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
        )

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert (
            "X-RateLimit-Window" in response.headers
        )  # Fixed: actual header is Window not Reset
        assert "X-RateLimit-Used" in response.headers


class TestExcludedPathsUnaffected:
    """Test that excluded paths are not affected by error handling."""

    def test_excluded_paths_bypass_even_on_errors(self, rate_limiter):
        """Test that excluded paths work even when rate limiting fails."""
        app = FastAPI()

        app.add_middleware(
            RateLimitMiddleware,
            rate_limit_use_case=rate_limiter,
            fail_on_error=True,
            excluded_paths=["/health", "/docs"],
        )

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/test")
        async def test_route():
            return {"message": "success"}

        client = TestClient(app)

        # Mock to raise an exception
        with patch.object(
            rate_limiter,
            "check_rate_limit",
            side_effect=Exception("Test error"),
        ):
            # Excluded path should work
            response = client.get("/health")
            assert response.status_code == 200

            # Non-excluded path should fail
            response = client.get("/test")
            assert response.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

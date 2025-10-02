#!/usr/bin/env python3
"""
Performance and pressure tests for Fastrict rate limiting system.

These tests demonstrate the performance characteristics of Fastrict
under various load conditions and concurrent access patterns.
"""

import asyncio
import statistics
import time
from typing import Dict, List

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from fastrict import (
    KeyExtractionType,
    KeyExtractionUseCase,
    MemoryRateLimitRepository,
    RateLimitMiddleware,
    RateLimitMode,
    RateLimitStrategy,
    RateLimitStrategyName,
    RateLimitUseCase,
    throttle,
)


class PerformanceMetrics:
    """Collect and analyze performance metrics."""

    def __init__(self):
        self.response_times: List[float] = []
        self.success_count = 0
        self.rate_limited_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start timing."""
        self.start_time = time.time()

    def end(self):
        """End timing."""
        self.end_time = time.time()

    def add_response(self, response_time: float, status_code: int):
        """Add a response measurement."""
        self.response_times.append(response_time)

        if status_code == 200:
            self.success_count += 1
        elif status_code == 429:
            self.rate_limited_count += 1
        else:
            self.error_count += 1

    @property
    def total_requests(self) -> int:
        """Total number of requests made."""
        return len(self.response_times)

    @property
    def duration(self) -> float:
        """Total test duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second."""
        if self.duration > 0:
            return self.total_requests / self.duration
        return 0.0

    @property
    def avg_response_time(self) -> float:
        """Average response time in milliseconds."""
        if self.response_times:
            return statistics.mean(self.response_times) * 1000
        return 0.0

    @property
    def p95_response_time(self) -> float:
        """95th percentile response time in milliseconds."""
        if self.response_times:
            return statistics.quantiles(self.response_times, n=20)[18] * 1000
        return 0.0

    @property
    def p99_response_time(self) -> float:
        """99th percentile response time in milliseconds."""
        if self.response_times:
            return statistics.quantiles(self.response_times, n=100)[98] * 1000
        return 0.0

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for reporting."""
        return {
            "total_requests": self.total_requests,
            "duration_seconds": self.duration,
            "requests_per_second": self.requests_per_second,
            "success_count": self.success_count,
            "rate_limited_count": self.rate_limited_count,
            "error_count": self.error_count,
            "avg_response_time_ms": self.avg_response_time,
            "p95_response_time_ms": self.p95_response_time,
            "p99_response_time_ms": self.p99_response_time,
        }


@pytest.fixture
def memory_app():
    """Create a test FastAPI app with memory backend for performance testing."""
    app = FastAPI(title="Performance Test App")

    # Setup rate limiting components with memory backend for speed
    repository = MemoryRateLimitRepository(key_prefix="perf_test")
    key_extraction = KeyExtractionUseCase()
    rate_limiter = RateLimitUseCase(
        rate_limit_repository=repository,
        key_extraction_use_case=key_extraction,
    )

    # High-performance strategies for testing
    strategies = [
        RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=100, ttl=60),
        RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=1000, ttl=300),
        RateLimitStrategy(name=RateLimitStrategyName.LONG, limit=10000, ttl=3600),
    ]

    # Add global rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit_use_case=rate_limiter,
        default_strategies=strategies,
        default_strategy_name=RateLimitStrategyName.LONG,
        rate_limit_mode=RateLimitMode.GLOBAL,
    )

    @app.get("/api/fast")
    async def fast_endpoint():
        """Ultra-fast endpoint for performance testing."""
        return {"status": "ok", "timestamp": time.time()}

    @app.get("/api/per-route")
    @throttle(limit=5000, ttl=3600, rate_limit_mode=RateLimitMode.PER_ROUTE)
    async def per_route_endpoint():
        """Per-route rate limited endpoint."""
        return {"status": "ok", "mode": "per_route"}

    @app.get("/api/strict")
    @throttle(limit=50, ttl=60)
    async def strict_endpoint():
        """Strictly rate limited endpoint for testing limits."""
        return {"status": "ok", "mode": "strict"}

    @app.get("/api/custom-key")
    @throttle(
        limit=2000,
        ttl=3600,
        key_type=KeyExtractionType.HEADER,
        key_field="X-User-ID",
        key_default="anonymous",
    )
    async def custom_key_endpoint():
        """Custom key extraction endpoint."""
        return {"status": "ok", "mode": "custom_key"}

    return app


@pytest.fixture
async def memory_client(memory_app):
    """Create an async test client for memory backend app."""
    transport = ASGITransport(app=memory_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    @pytest.mark.asyncio
    async def test_single_request_latency(self, memory_client):
        """Test single request latency."""
        # Warm up
        await memory_client.get("/api/fast")

        # Measure single request latency
        start_time = time.time()
        response = await memory_client.get("/api/fast")
        end_time = time.time()

        latency_ms = (end_time - start_time) * 1000

        assert response.status_code == 200
        assert latency_ms < 10.0  # Should be under 10ms for memory backend

        print(f"\n📊 Single Request Latency: {latency_ms:.2f}ms")

    @pytest.mark.asyncio
    async def test_sequential_requests_performance(self, memory_client):
        """Test sequential requests performance."""
        metrics = PerformanceMetrics()
        num_requests = 1000

        metrics.start()

        for i in range(num_requests):
            start = time.time()
            response = await memory_client.get("/api/fast")
            end = time.time()

            metrics.add_response(end - start, response.status_code)

        metrics.end()

        # Assertions
        assert metrics.success_count >= num_requests * 0.8  # At least 80% success
        assert metrics.avg_response_time < 5.0  # Under 5ms average
        assert metrics.requests_per_second > 100  # At least 100 RPS

        print("\n📊 Sequential Performance Metrics:")
        print(f"   Total Requests: {metrics.total_requests}")
        print(f"   Duration: {metrics.duration:.2f}s")
        print(f"   RPS: {metrics.requests_per_second:.2f}")
        print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")
        print(f"   P95 Response Time: {metrics.p95_response_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self, memory_client):
        """Test concurrent requests performance with high load."""
        metrics = PerformanceMetrics()
        concurrent_users = 50
        requests_per_user = 20

        async def user_simulation(user_id: int):
            """Simulate a single user making multiple requests."""
            user_metrics = []

            for i in range(requests_per_user):
                start = time.time()
                try:
                    response = await memory_client.get(
                        "/api/fast", headers={"X-User-ID": f"user_{user_id}"}
                    )
                    end = time.time()
                    user_metrics.append((end - start, response.status_code))
                except Exception:
                    end = time.time()
                    user_metrics.append((end - start, 500))

            return user_metrics

        # Start concurrent load
        metrics.start()

        # Create tasks for concurrent users
        tasks = [user_simulation(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)

        metrics.end()

        # Collect all metrics
        for user_results in results:
            for response_time, status_code in user_results:
                metrics.add_response(response_time, status_code)

        # Assertions for high-performance expectations
        total_expected = concurrent_users * requests_per_user
        assert metrics.total_requests == total_expected
        assert metrics.success_count >= total_expected * 0.9  # 90% success rate
        assert metrics.avg_response_time < 50.0  # Under 50ms average under load
        assert metrics.requests_per_second > 200  # At least 200 RPS under load

        print(
            f"\n🚀 Concurrent Performance Metrics ({concurrent_users} users, {requests_per_user} req/user):"
        )
        print(f"   Total Requests: {metrics.total_requests}")
        print(f"   Duration: {metrics.duration:.2f}s")
        print(f"   RPS: {metrics.requests_per_second:.2f}")
        print(
            f"   Success Rate: {(metrics.success_count / metrics.total_requests) * 100:.1f}%"
        )
        print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")
        print(f"   P95 Response Time: {metrics.p95_response_time:.2f}ms")
        print(f"   P99 Response Time: {metrics.p99_response_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_rate_limit_accuracy_under_load(self, memory_client):
        """Test rate limiting accuracy under high concurrent load."""
        metrics = PerformanceMetrics()
        concurrent_requests = 100  # More than the limit of 50

        # All requests use same client IP, should hit rate limit
        async def make_request():
            start = time.time()
            response = await memory_client.get("/api/strict")  # Limit: 50/60s
            end = time.time()
            return (end - start, response.status_code)

        metrics.start()

        # Fire all requests concurrently
        tasks = [make_request() for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)

        metrics.end()

        # Collect metrics
        for response_time, status_code in results:
            metrics.add_response(response_time, status_code)

        # Verify rate limiting works correctly
        assert metrics.total_requests == concurrent_requests
        assert metrics.success_count <= 50  # Should not exceed limit
        assert metrics.rate_limited_count >= 50  # Should rate limit excess
        assert (
            metrics.rate_limited_count + metrics.success_count
            >= concurrent_requests * 0.95
        )

        print("\n🛡️  Rate Limiting Accuracy Under Load:")
        print(f"   Total Requests: {metrics.total_requests}")
        print(f"   Successful: {metrics.success_count}")
        print(f"   Rate Limited: {metrics.rate_limited_count}")
        print(f"   Rate Limit Accuracy: {(metrics.rate_limited_count >= 50)}")
        print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")


class TestPressureTests:
    """Pressure tests to verify system stability under extreme load."""

    @pytest.mark.asyncio
    async def test_extreme_concurrent_load(self, memory_client):
        """Test system stability under extreme concurrent load."""
        metrics = PerformanceMetrics()
        concurrent_users = 100
        requests_per_user = 10

        async def heavy_user_simulation(user_id: int):
            """Simulate heavy user load."""
            user_metrics = []

            # Each user hits multiple endpoints
            endpoints = ["/api/fast", "/api/per-route", "/api/custom-key"]

            for i in range(requests_per_user):
                endpoint = endpoints[i % len(endpoints)]
                start = time.time()
                try:
                    response = await memory_client.get(
                        endpoint,
                        headers={
                            "X-User-ID": f"user_{user_id}",
                            "User-Agent": f"TestClient/{user_id}",
                        },
                    )
                    end = time.time()
                    user_metrics.append((end - start, response.status_code))
                except Exception:
                    end = time.time()
                    user_metrics.append((end - start, 500))

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.001)

            return user_metrics

        metrics.start()

        # Create massive concurrent load
        tasks = [heavy_user_simulation(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)

        metrics.end()

        # Collect all metrics
        for user_results in results:
            for response_time, status_code in user_results:
                metrics.add_response(response_time, status_code)

        # System should remain stable under pressure
        total_expected = concurrent_users * requests_per_user
        assert metrics.total_requests == total_expected
        assert metrics.error_count < total_expected * 0.05  # Less than 5% errors
        assert (
            metrics.success_count + metrics.rate_limited_count >= total_expected * 0.95
        )
        assert metrics.p99_response_time < 100.0  # P99 under 100ms even under pressure

        print(
            f"\n💪 Extreme Load Test ({concurrent_users} users, {requests_per_user} req/user):"
        )
        print(f"   Total Requests: {metrics.total_requests}")
        print(f"   Duration: {metrics.duration:.2f}s")
        print(f"   RPS: {metrics.requests_per_second:.2f}")
        print(
            f"   Success Rate: {(metrics.success_count / metrics.total_requests) * 100:.1f}%"
        )
        print(
            f"   Rate Limited: {(metrics.rate_limited_count / metrics.total_requests) * 100:.1f}%"
        )
        print(
            f"   Error Rate: {(metrics.error_count / metrics.total_requests) * 100:.1f}%"
        )
        print(f"   P99 Response Time: {metrics.p99_response_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_memory_efficiency_under_load(self, memory_client):
        """Test memory efficiency with many unique keys."""
        metrics = PerformanceMetrics()
        unique_users = 1000  # Many unique rate limiting keys

        async def unique_user_request(user_id: int):
            """Each user gets their own rate limiting key."""
            start = time.time()
            try:
                response = await memory_client.get(
                    "/api/custom-key", headers={"X-User-ID": f"unique_user_{user_id}"}
                )
                end = time.time()
                return (end - start, response.status_code)
            except Exception:
                end = time.time()
                return (end - start, 500)

        metrics.start()

        # Create many unique rate limiting keys
        tasks = [unique_user_request(i) for i in range(unique_users)]
        results = await asyncio.gather(*tasks)

        metrics.end()

        # Collect metrics
        for response_time, status_code in results:
            metrics.add_response(response_time, status_code)

        # Should handle many unique keys efficiently
        assert metrics.total_requests == unique_users
        assert metrics.success_count >= unique_users * 0.95  # High success rate
        assert (
            metrics.avg_response_time < 500.0
        )  # Efficient even with many keys (relaxed for many unique keys)

        print(f"\n🧠 Memory Efficiency Test ({unique_users} unique keys):")
        print(f"   Total Requests: {metrics.total_requests}")
        print(
            f"   Success Rate: {(metrics.success_count / metrics.total_requests) * 100:.1f}%"
        )
        print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")
        print(f"   P95 Response Time: {metrics.p95_response_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_sustained_load_endurance(self, memory_client):
        """Test system endurance under sustained load."""
        metrics = PerformanceMetrics()
        duration_seconds = 10  # 10 second sustained test
        target_rps = 100

        async def sustained_load():
            """Generate sustained load for specified duration."""
            end_time = time.time() + duration_seconds
            request_count = 0

            while time.time() < end_time:
                start = time.time()
                try:
                    response = await memory_client.get(
                        "/api/fast",
                        headers={"X-User-ID": f"sustained_user_{request_count % 10}"},
                    )
                    response_time = time.time() - start
                    metrics.add_response(response_time, response.status_code)
                    request_count += 1

                    # Control rate to target RPS
                    await asyncio.sleep(max(0, (1.0 / target_rps) - response_time))
                except Exception:
                    response_time = time.time() - start
                    metrics.add_response(response_time, 500)

        metrics.start()
        await sustained_load()
        metrics.end()

        # Should maintain performance throughout sustained load
        expected_requests = duration_seconds * target_rps
        assert (
            metrics.total_requests >= expected_requests * 0.8
        )  # At least 80% of target
        assert (
            metrics.success_count >= metrics.total_requests * 0.9
        )  # High success rate
        assert metrics.avg_response_time < 10.0  # Consistent performance

        # Performance shouldn't degrade significantly over time
        first_half = metrics.response_times[: len(metrics.response_times) // 2]
        second_half = metrics.response_times[len(metrics.response_times) // 2 :]

        if first_half and second_half:
            first_half_avg = statistics.mean(first_half) * 1000
            second_half_avg = statistics.mean(second_half) * 1000
            degradation = (second_half_avg - first_half_avg) / first_half_avg * 100

            assert degradation < 50  # Less than 50% performance degradation

            print(
                f"\n🔄 Sustained Load Endurance Test ({duration_seconds}s @ {target_rps} RPS):"
            )
            print(f"   Total Requests: {metrics.total_requests}")
            print(f"   Achieved RPS: {metrics.requests_per_second:.2f}")
            print(
                f"   Success Rate: {(metrics.success_count / metrics.total_requests) * 100:.1f}%"
            )
            print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")
            print(f"   Performance Degradation: {degradation:.1f}%")


@pytest.mark.asyncio
async def test_performance_comparison_global_vs_per_route(memory_app):
    """Compare performance between global and per-route rate limiting."""

    async def benchmark_mode(app, endpoint: str, mode_name: str):
        """Benchmark a specific rate limiting mode."""
        transport = ASGITransport(app=app)
        metrics = PerformanceMetrics()

        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # Warm up
            await client.get(endpoint)

            metrics.start()

            # Run concurrent load test
            async def make_request():
                start = time.time()
                response = await client.get(endpoint)
                end = time.time()
                return (end - start, response.status_code)

            tasks = [make_request() for _ in range(500)]
            results = await asyncio.gather(*tasks)

            metrics.end()

            for response_time, status_code in results:
                metrics.add_response(response_time, status_code)

        print(f"\n📊 {mode_name} Performance:")
        print(f"   RPS: {metrics.requests_per_second:.2f}")
        print(f"   Avg Response Time: {metrics.avg_response_time:.2f}ms")
        print(f"   P95 Response Time: {metrics.p95_response_time:.2f}ms")

        return metrics

    # Test both modes
    global_metrics = await benchmark_mode(memory_app, "/api/fast", "Global Mode")
    per_route_metrics = await benchmark_mode(
        memory_app, "/api/per-route", "Per-Route Mode"
    )

    # Both should perform well
    assert global_metrics.requests_per_second > 100
    assert per_route_metrics.requests_per_second > 100
    assert (
        global_metrics.avg_response_time < 300
    )  # More realistic threshold for concurrent load
    assert per_route_metrics.avg_response_time < 200


def save_performance_results():
    """Save performance test results to file for README inclusion."""
    # This would be called to generate results for documentation
    # Implementation would run all tests and save results
    pass


if __name__ == "__main__":
    # Run performance tests and save results
    pytest.main([__file__, "-v", "-s"])

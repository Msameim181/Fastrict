# Fastrict - FastAPI Rate Limiter Striction

A comprehensive, production-ready rate limiting system for FastAPI applications with Redis backend support.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-4.0+-red.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🚀 **High Performance**: Supports 1K-30K concurrent connections
- 🎯 **Flexible Strategies**: Multiple built-in strategies (short, medium, long-term limits)
- 🔧 **Easy Integration**: Drop-in middleware with decorator overrides
- 🔑 **Advanced Key Extraction**: IP, headers, query params, custom functions, combined keys
- 💾 **Redis Backend**: Efficient sliding window implementation with automatic cleanup
- 📊 **Monitoring Ready**: Standard rate limit headers and comprehensive logging
- 🛡️ **Production Ready**: Graceful error handling, fallbacks, and bypass functions
- 🎨 **Clean Architecture**: Well-structured, testable, and maintainable code

## Installation

```bash
pip install fastrict
```

### Dependencies

- Python 3.8+
- FastAPI 0.68+
- Redis 4.0+
- Pydantic 1.8+

## Quick Start

### 1. Basic Setup

```python
from fastapi import FastAPI
from fastrict import RateLimitMiddleware, throttle
from fastrict import RedisRateLimitRepository, RateLimitUseCase, KeyExtractionUseCase
import redis

# Create FastAPI app
app = FastAPI()

# Setup Redis
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

# Setup rate limiting components
repository = RedisRateLimitRepository(redis_client)
key_extraction = KeyExtractionUseCase()
rate_limiter = RateLimitUseCase(repository, key_extraction)

# Add middleware
app.add_middleware(
    RateLimitMiddleware,
    rate_limit_use_case=rate_limiter,
    excluded_paths=["/health", "/docs"]
)

# Basic endpoint (uses default rate limiting)
@app.get("/api/data")
async def get_data():
    return {"data": "This endpoint is rate limited"}
```

### 2. Route-Specific Rate Limiting

```python
from fastrict import RateLimitStrategyName, KeyExtractionType

# Strict rate limiting for login
@app.post("/auth/login")
@throttle(strategy=RateLimitStrategyName.SHORT)  # 3 requests per minute
async def login():
    return {"message": "Login endpoint"}

# Custom rate limiting
@app.post("/api/upload")
@throttle(limit=5, ttl=300)  # 5 requests per 5 minutes
async def upload_file():
    return {"message": "File uploaded"}

# API key-based rate limiting
@app.get("/api/premium")
@throttle(
    limit=100, 
    ttl=3600,
    key_type=KeyExtractionType.HEADER,
    key_field="X-API-Key"
)
async def premium_endpoint():
    return {"data": "Premium content"}
```

### 3. Advanced Key Strategies

```python
# Combined key (IP + User-Agent)
@app.get("/api/sensitive")
@throttle(
    limit=10,
    ttl=300,
    key_type=KeyExtractionType.COMBINED,
    key_combination=["ip", "header:User-Agent"]
)
async def sensitive_endpoint():
    return {"data": "Sensitive information"}

# Custom key extraction
def extract_user_key(request):
    user_id = request.headers.get("User-ID")
    return f"user:{user_id}" if user_id else request.client.host

@app.get("/api/user-data")
@throttle(
    limit=50,
    ttl=3600,
    key_type=KeyExtractionType.CUSTOM,
    key_extractor=extract_user_key
)
async def user_data():
    return {"data": "User-specific data"}

# Bypass for admin users
def bypass_for_admins(request):
    return request.headers.get("Role") == "admin"

@app.get("/api/admin")
@throttle(
    limit=5,
    ttl=60,
    bypass_function=bypass_for_admins
)
async def admin_endpoint():
    return {"data": "Admin data"}
```

## Configuration

### Built-in Strategies

```python
from fastrict import RateLimitStrategy, RateLimitStrategyName

strategies = [
    RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=3, ttl=60),      # 3/min
    RateLimitStrategy(name=RateLimitStrategyName.MEDIUM, limit=20, ttl=600),   # 20/10min
    RateLimitStrategy(name=RateLimitStrategyName.LONG, limit=100, ttl=3600),   # 100/hour
]

app.add_middleware(
    RateLimitMiddleware,
    rate_limit_use_case=rate_limiter,
    default_strategies=strategies,
    default_strategy_name=RateLimitStrategyName.MEDIUM
)
```

### Key Extraction Types

- **IP**: Client IP address (default)
- **HEADER**: HTTP header value
- **QUERY_PARAM**: Query parameter value  
- **FORM_FIELD**: Form field value
- **CUSTOM**: Custom extraction function
- **COMBINED**: Multiple extraction methods

### Environment Configuration

```python
import os
from fastrict import RedisRateLimitRepository

# Redis configuration
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
repository = RedisRateLimitRepository.from_url(
    redis_url=redis_url,
    key_prefix="myapp_rate_limit"
)
```

## Response Headers

The middleware automatically adds standard rate limiting headers:

```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Used: 5
X-RateLimit-Window: 600
Retry-After: 300  # Only when rate limited
```

## Error Responses

When rate limits are exceeded, the API returns HTTP 429:

```json
{
  "message": "Rate limit exceeded. Maximum 20 requests per 600 seconds. Please try again in 300 seconds.",
  "retry_after": 300,
  "limit": 20,
  "window": 600
}
```

## Advanced Usage

### Custom Redis Configuration

```python
import redis
from fastrict import RedisRateLimitRepository

# Custom Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    password="secret",
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

repository = RedisRateLimitRepository(
    redis_client=redis_client,
    key_prefix="myapp_limits"
)
# or
repository = RedisRateLimitRepository(redis_url="redis://:secret@localhost:6379/0")
```

### Multiple Rate Limiters

```python
# Different limiters for different API versions
v1_limiter = RateLimitUseCase(repository, key_extraction)
v2_limiter = RateLimitUseCase(repository, key_extraction)

# Apply to route groups
from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1")
v2_router = APIRouter(prefix="/v2")

# Different strategies for each version
v1_router.add_middleware(RateLimitMiddleware, rate_limit_use_case=v1_limiter)
v2_router.add_middleware(RateLimitMiddleware, rate_limit_use_case=v2_limiter)
```

### Monitoring and Metrics

```python
# Get current usage without incrementing
@app.get("/api/rate-limit-status")
async def rate_limit_status(request: Request):
    result = rate_limiter.get_current_usage(request)
    return {
        "allowed": result.allowed,
        "current_count": result.current_count,
        "limit": result.limit,
        "remaining": result.remaining_requests,
        "usage_percentage": result.usage_percentage
    }

# Cleanup expired keys (maintenance)
@app.post("/admin/cleanup-rate-limits")
async def cleanup_rate_limits():
    cleaned = repository.cleanup_expired_keys()
    return {"cleaned_keys": cleaned}
```

## Testing

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

def test_rate_limiting():
    # Mock Redis for testing
    mock_redis = Mock()
    repository = RedisRateLimitRepository(mock_redis)
    
    # Test your endpoints
    with TestClient(app) as client:
        # First request should succeed
        response = client.get("/api/data")
        assert response.status_code == 200
        
        # Simulate rate limit exceeded
        mock_redis.zcard.return_value = 100  # Over limit
        response = client.get("/api/data")
        assert response.status_code == 429
```

## Performance

- **Throughput**: Supports 1K-30K concurrent requests
- **Latency**: Sub-millisecond rate limit checks
- **Memory**: Efficient Redis sorted sets with automatic cleanup
- **Scalability**: Horizontal scaling with Redis cluster

## Architecture

The library follows Clean Architecture principles:

```
fastrict/
├── entities/          # Core business models
├── use_cases/         # Business logic
├── adapters/          # External integrations (Redis)
└── frameworks/        # FastAPI middleware & decorators
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Support

- 📖 [Documentation](https://fastrict.readthedocs.io/)
- 🐛 [Issue Tracker](https://github.com/msameim181/fastrict/issues)
- 💬 [Discussions](https://github.com/msameim181/fastrict/discussions)

## Related Projects

- [FastAPI](https://fastapi.tiangolo.com/) - The web framework
- [Redis](https://redis.io/) - In-memory data store
- [Starlette](https://www.starlette.io/) - ASGI framework
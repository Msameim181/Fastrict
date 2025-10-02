from enum import Enum


class KeyExtractionType(str, Enum):
    """Types of key extraction strategies for rate limiting.

    This enum defines how the rate limiting key should be extracted
    from the incoming request.
    """

    IP = "ip"  # Extract from client IP address
    HEADER = "header"  # Extract from specific header value
    QUERY_PARAM = "query_param"  # Extract from query parameter
    FORM_FIELD = "form_field"  # Extract from form field
    CUSTOM = "custom"  # Use custom key extraction function
    COMBINED = "combined"  # Combine multiple extraction methods


class RateLimitStrategyName(str, Enum):
    """Predefined rate limiting strategy names.

    These correspond to common rate limiting patterns that can be
    configured at the middleware level.
    """

    SHORT = "short"  # Short-term strict limits (e.g., 3 requests per minute)
    MEDIUM = "medium"  # Medium-term moderate limits (e.g., 20 requests per 10 minutes)
    LONG = "long"  # Long-term generous limits (e.g., 100 requests per hour)
    CUSTOM = "custom"  # Custom strategy defined via decorator


class RateLimitMode(str, Enum):
    """Rate limiting application modes.

    This enum defines how rate limits are applied across the application:
    - GLOBAL: All routes share the same rate limit pool globally
    - PER_ROUTE: Each route has its own independent rate limit pool
    """

    GLOBAL = "global"  # Global rate limiting across all routes
    PER_ROUTE = "per_route"  # Per-route rate limiting (route-specific pools)

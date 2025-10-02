import functools
from typing import Callable, Optional, Union

from ..entities import (
    KeyExtractionStrategy,
    KeyExtractionType,
    RateLimitConfig,
    RateLimitMode,
    RateLimitStrategy,
    RateLimitStrategyName,
)


def throttle(
    strategy: Optional[Union[RateLimitStrategy, RateLimitStrategyName]] = None,
    limit: Optional[int] = None,
    ttl: Optional[int] = None,
    key_type: KeyExtractionType = KeyExtractionType.IP,
    key_field: Optional[str] = None,
    key_default: Optional[str] = None,
    key_extractor: Optional[Callable] = None,
    key_combination: Optional[list] = None,
    bypass: bool = False,
    bypass_function: Optional[Callable] = None,
    custom_error_message: Optional[str] = None,
    enabled: bool = True,
    rate_limit_mode: Optional[RateLimitMode] = RateLimitMode.PER_ROUTE,
):
    """Decorator for applying rate limiting to FastAPI route handlers.

    This decorator allows fine-grained control over rate limiting for specific routes,
    overriding any global middleware settings.

    Args:
        strategy: Predefined strategy name or custom strategy object
        limit: Custom limit (used with ttl to create inline strategy)
        ttl: Custom time window (used with limit to create inline strategy)
        key_type: Type of key extraction (IP, HEADER, QUERY_PARAM, etc.)
        key_field: Field name for HEADER/QUERY_PARAM extraction
        key_default: Default value if extraction fails
        key_extractor: Custom function for key extraction
        key_combination: List of keys for combined extraction
        bypass: Whether to completely bypass rate limiting for this route
        bypass_function: Function to bypass rate limiting based on request
        custom_error_message: Custom error message for rate limit violations
        enabled: Whether rate limiting is enabled for this route
        rate_limit_mode: Override rate limiting mode (GLOBAL or PER_ROUTE).
                        If not specified, decorated routes default to PER_ROUTE.

    Examples:
        @throttle(strategy=RateLimitStrategyName.SHORT)
        async def my_endpoint():
            pass

        @throttle(limit=5, ttl=60, key_type=KeyExtractionType.HEADER, key_field="API-Key")
        async def api_endpoint():
            pass

        @throttle(
            limit=10,
            ttl=300,
            rate_limit_mode=RateLimitMode.GLOBAL
        )
        async def global_shared_endpoint():
            pass

        @throttle(bypass=True)
        async def unrestricted_endpoint():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # The actual rate limiting logic will be handled by the middleware
            # This decorator just attaches the configuration to the function
            return await func(*args, **kwargs)

        # Create rate limit configuration
        rate_limit_strategy = None
        strategy_name = None

        if isinstance(strategy, RateLimitStrategy):
            rate_limit_strategy = strategy
        elif isinstance(strategy, RateLimitStrategyName):
            strategy_name = strategy
        elif limit is not None and ttl is not None:
            # Create inline strategy
            rate_limit_strategy = RateLimitStrategy(
                name=RateLimitStrategyName.CUSTOM, limit=limit, ttl=ttl
            )
        else:
            # Use default strategy name if nothing specified
            strategy_name = RateLimitStrategyName.MEDIUM

        # Create key extraction strategy
        key_extraction = KeyExtractionStrategy(
            type=key_type,
            field_name=key_field,
            default_value=key_default,
            extractor_function=key_extractor,
            combination_keys=key_combination,
        )

        # Create configuration
        config = RateLimitConfig(
            strategy=rate_limit_strategy,
            strategy_name=strategy_name,
            key_extraction=key_extraction,
            enabled=enabled,
            bypass=bypass,
            bypass_function=bypass_function,
            custom_error_message=custom_error_message,
            rate_limit_mode=rate_limit_mode,
        )

        # Attach configuration to the wrapped function
        wrapper._rate_limit_config = config
        wrapper._original_func = func

        return wrapper

    return decorator


def get_rate_limit_config(func: Callable) -> Optional[RateLimitConfig]:
    """Extract rate limit configuration from a decorated function.

    Args:
        func: Function that may have rate limit configuration

    Returns:
        RateLimitConfig or None if not configured
    """
    return getattr(func, "_rate_limit_config", None)


def is_rate_limited(func: Callable) -> bool:
    """Check if a function has rate limiting configured.

    Args:
        func: Function to check

    Returns:
        bool: True if rate limiting is configured
    """
    config = get_rate_limit_config(func)
    return config is not None and config.enabled

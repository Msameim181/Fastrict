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
    key_extraction_strategy: Optional[KeyExtractionStrategy] = None,
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
        key_extraction_strategy: Complete KeyExtractionStrategy object (overrides other key_* params)
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

        @throttle(limit=10, ttl=300, key_extraction_strategy=create_auth_header_fallback())
        async def fallback_endpoint():
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
        # Create rate limit configuration first
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
        key_extraction = None
        if key_extraction_strategy:
            # Use provided KeyExtractionStrategy object directly
            key_extraction = key_extraction_strategy
        else:
            # Build from individual parameters
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

        # Instead of creating wrapper functions that can interfere with FastAPI's type introspection,
        # we'll just attach the configuration directly to the original function.
        # This prevents any signature modification that could cause TypeAdapter issues.

        func._rate_limit_config = config
        func._original_func = func

        return func

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


# Helper functions for creating common fallback strategies
def create_auth_header_fallback(
    header_name: str = "Authorization", default_value: Optional[str] = None
) -> KeyExtractionStrategy:
    """Create a fallback strategy that tries auth header first, then IP.

    Args:
        header_name: Name of the authorization header (default: "Authorization")
        default_value: Default value if header extraction fails

    Returns:
        KeyExtractionStrategy: Fallback strategy
    """
    return KeyExtractionStrategy(
        type=KeyExtractionType.FALLBACK,
        fallback_strategies=[
            KeyExtractionStrategy(
                type=KeyExtractionType.HEADER,
                field_name=header_name,
                default_value=default_value,
            ),
            KeyExtractionStrategy(type=KeyExtractionType.IP),
        ],
    )


def create_api_key_fallback(
    api_key_header: str = "X-API-Key",
    auth_header: str = "Authorization",
    default_value: Optional[str] = None,
) -> KeyExtractionStrategy:
    """Create a fallback strategy that tries API key, then auth header, then IP.

    Args:
        api_key_header: Name of the API key header (default: "X-API-Key")
        auth_header: Name of the authorization header (default: "Authorization")
        default_value: Default value if all header extractions fail

    Returns:
        KeyExtractionStrategy: Fallback strategy
    """
    return KeyExtractionStrategy(
        type=KeyExtractionType.FALLBACK,
        fallback_strategies=[
            KeyExtractionStrategy(
                type=KeyExtractionType.HEADER,
                field_name=api_key_header,
                default_value=default_value,
            ),
            KeyExtractionStrategy(
                type=KeyExtractionType.HEADER,
                field_name=auth_header,
                default_value=default_value,
            ),
            KeyExtractionStrategy(type=KeyExtractionType.IP),
        ],
    )


def create_user_id_fallback(
    user_id_param: str = "user_id",
    user_id_header: str = "X-User-ID",
    default_value: Optional[str] = None,
) -> KeyExtractionStrategy:
    """Create a fallback strategy that tries user ID from query param, then header, then IP.

    Args:
        user_id_param: Name of the user ID query parameter (default: "user_id")
        user_id_header: Name of the user ID header (default: "X-User-ID")
        default_value: Default value if user ID extraction fails

    Returns:
        KeyExtractionStrategy: Fallback strategy
    """
    return KeyExtractionStrategy(
        type=KeyExtractionType.FALLBACK,
        fallback_strategies=[
            KeyExtractionStrategy(
                type=KeyExtractionType.QUERY_PARAM,
                field_name=user_id_param,
                default_value=default_value,
            ),
            KeyExtractionStrategy(
                type=KeyExtractionType.HEADER,
                field_name=user_id_header,
                default_value=default_value,
            ),
            KeyExtractionStrategy(type=KeyExtractionType.IP),
        ],
    )

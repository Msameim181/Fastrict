import logging
from typing import Dict, List, Optional

from fastapi import Request

from ..entities import (
    KeyExtractionStrategy,
    KeyExtractionType,
    RateLimitConfig,
    RateLimitMode,
    RateLimitResult,
    RateLimitStrategy,
    RateLimitStrategyName,
)
from .interface.repository import IRateLimitRepository
from .key_extraction import KeyExtractionUseCase, RateLimitException


class RateLimitHTTPException(Exception):
    """HTTP exception for rate limiting."""

    def __init__(self, status_code: int, detail: dict, headers: dict = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}
        super().__init__(detail)


class RateLimitUseCase:
    """Use case for rate limiting functionality.

    This use case orchestrates rate limiting checks, key extraction,
    and result formatting according to business rules.
    """

    def __init__(
        self,
        rate_limit_repository: IRateLimitRepository,  # Will be injected
        key_extraction_use_case: KeyExtractionUseCase,
        logger: Optional[logging.Logger] = None,
        default_strategies: Optional[List[RateLimitStrategy]] = None,
    ):
        self.rate_limit_repository = rate_limit_repository
        self.key_extraction_use_case = key_extraction_use_case
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Set default strategies if not provided
        self.default_strategies = default_strategies or self._get_default_strategies()
        self._strategy_map = {
            strategy.name: strategy for strategy in self.default_strategies
        }

    def _get_default_strategies(self) -> List[RateLimitStrategy]:
        """Get default rate limiting strategies."""
        return [
            RateLimitStrategy(
                name=RateLimitStrategyName.SHORT,
                limit=3,
                ttl=60,  # 3 requests per minute
            ),
            RateLimitStrategy(
                name=RateLimitStrategyName.MEDIUM,
                limit=20,
                ttl=600,  # 20 requests per 10 minutes
            ),
            RateLimitStrategy(
                name=RateLimitStrategyName.LONG,
                limit=100,
                ttl=3600,  # 100 requests per hour
            ),
        ]

    def check_rate_limit(
        self,
        request: Request,
        config: Optional[RateLimitConfig] = None,
        default_strategy_name: RateLimitStrategyName = RateLimitStrategyName.MEDIUM,
        middleware_rate_limit_mode: RateLimitMode = RateLimitMode.GLOBAL,
        route_path: Optional[str] = None,
        middleware_default_key_extraction: Optional[KeyExtractionStrategy] = None,
    ) -> RateLimitResult:
        """Check if request should be rate limited.

        Args:
            request: FastAPI request object
            config: Optional route-specific configuration
            default_strategy_name: Default strategy if none specified
            middleware_rate_limit_mode: How rate limits are applied globally
            route_path: The route path for per-route limiting
            middleware_default_key_extraction: Default key extraction strategy from middleware

        Returns:
            RateLimitResult: Result of rate limit check

        Raises:
            RateLimitHTTPException: If rate limit is exceeded
        """
        try:
            # Determine strategy to use
            strategy = self._determine_strategy(config, default_strategy_name)

            # Determine effective rate limiting mode
            effective_mode = self._determine_rate_limit_mode(
                config, middleware_rate_limit_mode
            )

            # Determine key extraction strategy
            key_strategy = self._determine_key_strategy(
                config, middleware_default_key_extraction
            )

            # Extract rate limiting key (now considering the rate limiting mode)
            rate_limit_key = self._build_rate_limit_key(
                request, key_strategy, effective_mode, route_path
            )

            # Check if route is configured to bypass rate limiting
            if config and config.bypass:
                return RateLimitResult(
                    allowed=True,
                    key=rate_limit_key,
                    current_count=0,
                    limit=strategy.limit,
                    ttl=strategy.ttl,
                    strategy_name=strategy.name,
                )

            # Check bypass function if provided
            if config and config.bypass_function:
                try:
                    if config.bypass_function(request):
                        return RateLimitResult(
                            allowed=True,
                            key=rate_limit_key,
                            current_count=0,
                            limit=strategy.limit,
                            ttl=strategy.ttl,
                            strategy_name=strategy.name,
                        )
                except Exception as e:
                    self.logger.warning(f"Bypass function failed: {str(e)}")

            # Perform rate limit check
            current_count = self.rate_limit_repository.increment_counter(
                key=rate_limit_key, ttl=strategy.ttl
            )

            allowed = current_count <= strategy.limit
            retry_after = strategy.ttl if not allowed else None

            result = RateLimitResult(
                allowed=allowed,
                key=rate_limit_key,
                current_count=current_count,
                limit=strategy.limit,
                ttl=strategy.ttl,
                retry_after=retry_after,
                strategy_name=strategy.name,
            )

            # If rate limit exceeded, raise exception
            if not allowed:
                error_message = self._get_error_message(config, result)
                raise RateLimitHTTPException(
                    status_code=429,
                    detail={
                        "message": error_message,
                        "retry_after": retry_after,
                        "limit": strategy.limit,
                        "window": strategy.ttl,
                    },
                    headers=result.to_headers(),
                )

            return result

        except RateLimitHTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {str(e)}")
            raise RateLimitException(message="Rate limit check failed", status_code=500)

    def _determine_strategy(
        self,
        config: Optional[RateLimitConfig],
        default_strategy_name: RateLimitStrategyName,
    ) -> RateLimitStrategy:
        """Determine which rate limiting strategy to use."""
        if config:
            if config.strategy:
                return config.strategy
            elif config.strategy_name:
                strategy = self._strategy_map.get(config.strategy_name)
                if not strategy:
                    raise RateLimitException(
                        message=f"Unknown strategy name: {config.strategy_name}",
                        status_code=500,
                    )
                return strategy

        # Use default strategy
        strategy = self._strategy_map.get(default_strategy_name)
        if not strategy:
            raise RateLimitException(
                message=f"Default strategy not found: {default_strategy_name}",
                status_code=500,
            )
        return strategy

    def _determine_key_strategy(
        self,
        config: Optional[RateLimitConfig],
        middleware_default: Optional[KeyExtractionStrategy] = None,
    ) -> KeyExtractionStrategy:
        """Determine key extraction strategy to use.

        Priority:
        1. Route-specific configuration (from decorator)
        2. Middleware default key extraction strategy
        3. IP-based fallback
        """
        if config and config.key_extraction:
            return config.key_extraction

        if middleware_default:
            return middleware_default

        # Default to IP-based key extraction
        return KeyExtractionStrategy(type=KeyExtractionType.IP)

    def _determine_rate_limit_mode(
        self, config: Optional[RateLimitConfig], middleware_mode: RateLimitMode
    ) -> RateLimitMode:
        """Determine the effective rate limiting mode to use.

        Priority:
        1. Route-specific configuration (from decorator)
        2. If decorator is used without explicit mode, force PER_ROUTE
        3. Middleware default mode
        """
        if config:
            # If route config has explicit mode, use it
            if config.rate_limit_mode:
                return config.rate_limit_mode
            # If route config exists (decorator was used) but no explicit mode,
            # default to PER_ROUTE for decorated routes
            return RateLimitMode.PER_ROUTE

        # No route config, use middleware mode
        return middleware_mode

    def _build_rate_limit_key(
        self,
        request: Request,
        key_strategy: KeyExtractionStrategy,
        rate_limit_mode: RateLimitMode,
        route_path: Optional[str] = None,
    ) -> str:
        """Build the complete rate limiting key based on mode and extraction strategy."""
        # Extract the base key using the extraction strategy
        base_key = self.key_extraction_use_case.extract_key(request, key_strategy)

        if rate_limit_mode == RateLimitMode.PER_ROUTE:
            # For per-route limiting, include the route path in the key
            route_identifier = route_path or request.url.path
            # Clean the route path for use in key (remove special characters, normalize)
            clean_route = (
                route_identifier.replace("/", "_")
                .replace("?", "")
                .replace("&", "")
                .strip("_")
            )
            if not clean_route:
                clean_route = "root"
            return f"route:{clean_route}:{base_key}"
        else:
            # For global limiting, use the base key as-is
            return f"global:{base_key}"

    def _get_error_message(
        self, config: Optional[RateLimitConfig], result: RateLimitResult
    ) -> str:
        """Get appropriate error message for rate limit violation."""
        if config and config.custom_error_message:
            return config.custom_error_message

        return (
            f"Rate limit exceeded. Maximum {result.limit} requests per {result.ttl} seconds. "
            f"Please try again in {result.retry_after} seconds."
        )

    def get_current_usage(
        self,
        request: Request,
        config: Optional[RateLimitConfig] = None,
        default_strategy_name: RateLimitStrategyName = RateLimitStrategyName.MEDIUM,
        middleware_rate_limit_mode: RateLimitMode = RateLimitMode.GLOBAL,
        route_path: Optional[str] = None,
        middleware_default_key_extraction: Optional[KeyExtractionStrategy] = None,
    ) -> RateLimitResult:
        """Get current rate limit usage without incrementing counter.

        Args:
            request: FastAPI request object
            config: Optional route-specific configuration
            default_strategy_name: Default strategy if none specified
            middleware_rate_limit_mode: How rate limits are applied globally
            route_path: The route path for per-route limiting
            middleware_default_key_extraction: Default key extraction strategy from middleware

        Returns:
            RateLimitResult: Current usage information
        """
        try:
            strategy = self._determine_strategy(config, default_strategy_name)
            effective_mode = self._determine_rate_limit_mode(
                config, middleware_rate_limit_mode
            )
            key_strategy = self._determine_key_strategy(
                config, middleware_default_key_extraction
            )
            rate_limit_key = self._build_rate_limit_key(
                request, key_strategy, effective_mode, route_path
            )

            current_count = self.rate_limit_repository.get_current_count(
                key=rate_limit_key
            )

            allowed = current_count < strategy.limit
            retry_after = strategy.ttl if not allowed else None

            return RateLimitResult(
                allowed=allowed,
                key=rate_limit_key,
                current_count=current_count,
                limit=strategy.limit,
                ttl=strategy.ttl,
                retry_after=retry_after,
                strategy_name=strategy.name,
            )

        except Exception as e:
            self.logger.error(f"Usage check failed: {str(e)}")
            raise RateLimitException(message="Usage check failed", status_code=500)

    def update_strategies(self, strategies: List[RateLimitStrategy]) -> None:
        """Update the available rate limiting strategies.

        Args:
            strategies: New list of rate limiting strategies
        """
        self.default_strategies = strategies
        self._strategy_map = {strategy.name: strategy for strategy in strategies}
        message = "Updated rate limiting strategies:"
        for strategy in strategies:
            message += f"\n- {strategy.name}: {strategy.limit} requests per {strategy.ttl} seconds"
        self.logger.info(message)

    def get_strategy(self, name: RateLimitStrategyName) -> Optional[RateLimitStrategy]:
        """Get a specific rate limiting strategy by name.

        Args:
            name: Strategy name to retrieve

        Returns:
            RateLimitStrategy or None if not found
        """
        return self._strategy_map.get(name)

    def list_strategies(self) -> Dict[RateLimitStrategyName, RateLimitStrategy]:
        """List all available rate limiting strategies.

        Returns:
            Dictionary of strategy name to strategy mapping
        """
        return self._strategy_map.copy()

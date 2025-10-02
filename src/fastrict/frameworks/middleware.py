from typing import List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..entities import RateLimitStrategy, RateLimitStrategyName
from ..use_cases import RateLimitUseCase
from ..use_cases.rate_limit import RateLimitHTTPException
from .decorator import get_rate_limit_config


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for global rate limiting.

    This middleware applies rate limiting to all requests unless overridden
    by route-specific decorators. It supports multiple named strategies and
    can be configured with default behavior.
    """

    def __init__(
        self,
        app,
        rate_limit_use_case: RateLimitUseCase,
        default_strategies: Optional[List[RateLimitStrategy]] = None,
        default_strategy_name: RateLimitStrategyName = RateLimitStrategyName.MEDIUM,
        excluded_paths: Optional[List[str]] = None,
        enabled: bool = True,
    ):
        """
        Initialize rate limiting middleware.

        Args:
            app: FastAPI application instance
            rate_limit_use_case: Rate limiting business logic
            default_strategies: List of available strategies
            default_strategy_name: Default strategy to use
            excluded_paths: Paths to exclude from rate limiting
            enabled: Whether rate limiting is globally enabled
        """
        super().__init__(app)
        self.rate_limit_use_case = rate_limit_use_case
        self.default_strategy_name = default_strategy_name
        self.excluded_paths = excluded_paths or []
        self.enabled = enabled

        # Update strategies if provided
        if default_strategies:
            self.rate_limit_use_case.update_strategies(default_strategies)

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting middleware.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain

        Returns:
            Response: HTTP response with rate limiting headers
        """
        # Skip if rate limiting is disabled
        if not self.enabled:
            return await call_next(request)

        # Skip excluded paths
        if self._is_path_excluded(request.url.path):
            return await call_next(request)

        try:
            # Get route-specific configuration
            endpoint = request.scope.get("endpoint")
            route_config = None

            if endpoint:
                route_config = get_rate_limit_config(endpoint)

                # Skip if route has rate limiting disabled
                if route_config and not route_config.enabled:
                    return await call_next(request)

            # Perform rate limit check
            try:
                result = self.rate_limit_use_case.check_rate_limit(
                    request=request, config=route_config, default_strategy_name=self.default_strategy_name
                )

                # Continue to next handler
                response = await call_next(request)

                # Add rate limiting headers to response
                self._add_rate_limit_headers(response, result)

                return response

            except RateLimitHTTPException as e:
                # Rate limit exceeded - return error response
                return JSONResponse(status_code=e.status_code, content=e.detail, headers=e.headers)

        except Exception as e:
            # Log error but don't block request on middleware failure
            print(f"Rate limiting middleware error: {str(e)}")
            return await call_next(request)

    def _is_path_excluded(self, path: str) -> bool:
        """Check if a path should be excluded from rate limiting.

        Args:
            path: Request path to check

        Returns:
            bool: True if path should be excluded
        """
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True
        return False

    def _add_rate_limit_headers(self, response: Response, result) -> None:
        """Add rate limiting headers to response.

        Args:
            response: HTTP response to modify
            result: RateLimitResult with rate limiting information
        """
        try:
            headers = result.to_headers()
            for key, value in headers.items():
                response.headers[key] = value
        except Exception:
            # Don't fail the request if headers can't be added
            pass

    def update_strategies(self, strategies: List[RateLimitStrategy]) -> None:
        """Update available rate limiting strategies.

        Args:
            strategies: New list of strategies
        """
        self.rate_limit_use_case.update_strategies(strategies)

    def set_default_strategy(self, strategy_name: RateLimitStrategyName) -> None:
        """Update default rate limiting strategy.

        Args:
            strategy_name: New default strategy name
        """
        self.default_strategy_name = strategy_name

    def disable(self) -> None:
        """Disable rate limiting middleware."""
        self.enabled = False

    def enable(self) -> None:
        """Enable rate limiting middleware."""
        self.enabled = True
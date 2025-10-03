import hashlib
import logging
from typing import Optional

from fastapi import Request

from ..entities import KeyExtractionStrategy, KeyExtractionType


class RateLimitException(Exception):
    """Custom exception for rate limiting errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class KeyExtractionUseCase:
    """Use case for extracting rate limiting keys from requests.

    This use case handles the business logic for determining the appropriate
    identifier to use for rate limiting based on the extraction strategy.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def extract_key(self, request: Request, strategy: KeyExtractionStrategy) -> str:
        """Extract rate limiting key from request based on strategy.

        Args:
            request: FastAPI request object
            strategy: Key extraction strategy to use

        Returns:
            str: Extracted key for rate limiting

        Raises:
            RateLimitException: If key extraction fails
        """
        try:
            if strategy.type == KeyExtractionType.IP:
                return self._extract_ip_key(request)
            elif strategy.type == KeyExtractionType.HEADER:
                return self._extract_header_key(request, strategy)
            elif strategy.type == KeyExtractionType.QUERY_PARAM:
                return self._extract_query_param_key(request, strategy)
            elif strategy.type == KeyExtractionType.FORM_FIELD:
                return self._extract_form_field_key(request, strategy)
            elif strategy.type == KeyExtractionType.CUSTOM:
                return self._extract_custom_key(request, strategy)
            elif strategy.type == KeyExtractionType.COMBINED:
                return self._extract_combined_key(request, strategy)
            elif strategy.type == KeyExtractionType.FALLBACK:
                return self._extract_fallback_key(request, strategy)
            else:
                raise RateLimitException(
                    message=f"Invalid key extraction type: {strategy.type}",
                    status_code=400,
                )
        except Exception as e:
            self.logger.error(f"Key extraction failed: {str(e)}")
            # If extraction fails, fall back to IP-based key
            return self._extract_ip_key(request)

    def _extract_ip_key(self, request: Request) -> str:
        """Extract IP address as rate limiting key."""
        # Check for forwarded IP headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client IP
        client_ip = getattr(request.client, "host", "unknown")
        return client_ip

    def _extract_header_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract header value as rate limiting key."""
        header_value = request.headers.get(strategy.field_name)
        if not header_value:
            if strategy.default_value:
                return strategy.default_value
            # Fall back to IP if header not found
            return self._extract_ip_key(request)
        return header_value

    def _extract_query_param_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract query parameter as rate limiting key."""
        param_value = request.query_params.get(strategy.field_name)
        if not param_value:
            if strategy.default_value:
                return strategy.default_value
            # Fall back to IP if param not found
            return self._extract_ip_key(request)
        return param_value

    def _extract_form_field_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract form field as rate limiting key."""
        # This would require accessing form data, which is async
        # For now, fall back to default or IP
        if strategy.default_value:
            return strategy.default_value
        return self._extract_ip_key(request)

    def _extract_custom_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract key using custom function."""
        if not strategy.extractor_function:
            raise RateLimitException(
                message="Custom extractor function not provided", status_code=500
            )

        try:
            return strategy.extractor_function(request)
        except Exception as e:
            self.logger.error(f"Custom key extraction failed: {str(e)}")
            # Fall back to IP
            return self._extract_ip_key(request)

    def _extract_combined_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract combined key from multiple sources."""
        if not strategy.combination_keys:
            raise RateLimitException(
                message="Combination keys not provided", status_code=500
            )

        key_parts = []
        for key_type in strategy.combination_keys:
            if key_type == "ip":
                key_parts.append(self._extract_ip_key(request))
            elif key_type.startswith("header:"):
                header_name = key_type.split(":", 1)[1]
                header_value = request.headers.get(header_name, "unknown")
                key_parts.append(header_value)
            elif key_type.startswith("query:"):
                param_name = key_type.split(":", 1)[1]
                param_value = request.query_params.get(param_name, "unknown")
                key_parts.append(param_value)
            else:
                key_parts.append(key_type)  # Use as literal value

        # Create a hash of the combined keys for consistent length
        combined_key = "|".join(key_parts)
        return hashlib.sha256(combined_key.encode()).hexdigest()[:32]

    def _extract_fallback_key(
        self, request: Request, strategy: KeyExtractionStrategy
    ) -> str:
        """Extract key using fallback strategies in sequence.

        Tries each strategy in the fallback list until one succeeds.
        If all fail, falls back to IP extraction.
        """
        if not strategy.fallback_strategies:
            raise RateLimitException(
                message="Fallback strategies not provided", status_code=500
            )

        for fallback_strategy in strategy.fallback_strategies:
            try:
                # Recursively extract using each fallback strategy
                result = self.extract_key(request, fallback_strategy)
                # If we get a valid result (not just IP fallback), use it
                if (
                    result != self._extract_ip_key(request)
                    or fallback_strategy.type == KeyExtractionType.IP
                ):
                    return result
            except Exception as e:
                self.logger.debug(
                    f"Fallback strategy {fallback_strategy.type} failed: {str(e)}"
                )
                continue

        # If all fallback strategies fail, use IP as final fallback
        self.logger.warning("All fallback strategies failed, using IP address")
        return self._extract_ip_key(request)

    def validate_strategy(self, strategy: KeyExtractionStrategy) -> bool:
        """Validate that a key extraction strategy is properly configured.

        Args:
            strategy: Strategy to validate

        Returns:
            bool: True if valid, False otherwise
        """
        try:
            if strategy.type == KeyExtractionType.IP:
                return True
            elif strategy.type in [
                KeyExtractionType.HEADER,
                KeyExtractionType.QUERY_PARAM,
                KeyExtractionType.FORM_FIELD,
            ]:
                return bool(strategy.field_name)
            elif strategy.type == KeyExtractionType.CUSTOM:
                return callable(strategy.extractor_function)
            elif strategy.type == KeyExtractionType.COMBINED:
                return bool(
                    strategy.combination_keys and len(strategy.combination_keys) >= 2
                )
            elif strategy.type == KeyExtractionType.FALLBACK:
                return bool(
                    strategy.fallback_strategies
                    and len(strategy.fallback_strategies) >= 2
                )
            return False
        except Exception as e:
            self.logger.error(f"Strategy validation failed: {str(e)}")
            return False

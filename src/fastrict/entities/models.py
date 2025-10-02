from datetime import datetime
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import KeyExtractionType, RateLimitMode, RateLimitStrategyName


class RateLimitStrategy(BaseModel):
    """Defines a rate limiting strategy with time window and request limits.

    This entity represents a complete rate limiting configuration including
    the request limit, time window, and strategy identification.
    """

    name: RateLimitStrategyName = Field(
        description="Name identifier for the rate limit strategy"
    )
    limit: int = Field(
        gt=0, description="Maximum number of requests allowed within the time window"
    )
    ttl: int = Field(gt=0, description="Time window in seconds for the rate limit")

    model_config = ConfigDict(frozen=True)  # Immutable as per project guidelines

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Rate limit must be greater than 0")
        return v

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("TTL must be greater than 0")
        return v


class KeyExtractionStrategy(BaseModel):
    """Defines how to extract the rate limiting key from a request.

    This entity encapsulates the logic for determining what identifier
    to use for rate limiting (IP, header value, query parameter, etc.).
    """

    type: KeyExtractionType = Field(description="Type of key extraction strategy")
    field_name: Optional[str] = Field(
        default=None,
        description="Name of header/query param/form field when applicable",
    )
    default_value: Optional[str] = Field(
        default=None, description="Default value to use if extraction fails"
    )
    extractor_function: Optional[Callable] = Field(
        default=None, description="Custom function for CUSTOM type extraction"
    )
    combination_keys: Optional[List[str]] = Field(
        default=None, description="List of keys to combine for COMBINED type"
    )

    model_config = ConfigDict(
        frozen=True, arbitrary_types_allowed=True
    )  # Allow Callable type

    @model_validator(mode="after")
    def validate_extraction_strategy(self) -> "KeyExtractionStrategy":
        """Validate that required fields are present based on extraction type."""
        extraction_type = self.type

        # Validate field_name requirement
        if (
            extraction_type
            in [
                KeyExtractionType.HEADER,
                KeyExtractionType.QUERY_PARAM,
                KeyExtractionType.FORM_FIELD,
            ]
            and not self.field_name
        ):
            raise ValueError(
                f"field_name is required for {extraction_type.value} extraction"
            )

        # Validate extractor_function requirement
        if extraction_type == KeyExtractionType.CUSTOM and not self.extractor_function:
            raise ValueError("extractor_function is required for CUSTOM extraction")

        # Validate combination_keys requirement
        if extraction_type == KeyExtractionType.COMBINED and (
            not self.combination_keys or len(self.combination_keys) < 2
        ):
            raise ValueError(
                "combination_keys must contain at least 2 keys for COMBINED extraction"
            )

        return self


class RateLimitConfig(BaseModel):
    """Configuration for route-specific rate limiting via decorator.

    This entity represents the complete configuration that can be
    specified in the @throttle decorator.
    """

    strategy: Optional[RateLimitStrategy] = Field(
        default=None, description="Custom rate limit strategy for this route"
    )
    strategy_name: Optional[RateLimitStrategyName] = Field(
        default=None, description="Name of predefined strategy to use"
    )
    key_extraction: Optional[KeyExtractionStrategy] = Field(
        default=None, description="Custom key extraction strategy"
    )
    enabled: bool = Field(
        default=True, description="Whether rate limiting is enabled for this route"
    )
    bypass: bool = Field(
        default=False,
        description="Whether to completely bypass rate limiting for this route",
    )
    bypass_function: Optional[Callable] = Field(
        default=None,
        description="Optional function to bypass rate limiting based on request",
    )
    custom_error_message: Optional[str] = Field(
        default=None, description="Custom error message for rate limit violations"
    )
    rate_limit_mode: Optional[RateLimitMode] = Field(
        default=None,
        description="Override rate limiting mode for this route (GLOBAL or PER_ROUTE)",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def validate_strategy_options(self) -> "RateLimitConfig":
        """Validate that exactly one strategy option is specified."""
        if self.strategy and self.strategy_name:
            raise ValueError("Cannot specify both 'strategy' and 'strategy_name'")
        if not self.strategy and not self.strategy_name:
            raise ValueError("Must specify either 'strategy' or 'strategy_name'")
        return self


class RateLimitResult(BaseModel):
    """Result of a rate limit check operation.

    This entity encapsulates the outcome of checking whether a request
    should be allowed or blocked based on rate limiting rules.
    """

    allowed: bool = Field(description="Whether the request is allowed")
    key: str = Field(description="The rate limiting key that was used")
    current_count: int = Field(
        ge=0, description="Current number of requests in the time window"
    )
    limit: int = Field(gt=0, description="Maximum allowed requests in the time window")
    ttl: int = Field(gt=0, description="Time window in seconds")
    retry_after: Optional[int] = Field(
        default=None, description="Seconds to wait before retrying (when blocked)"
    )
    strategy_name: RateLimitStrategyName = Field(
        description="Name of the strategy that was applied"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the check was performed",
    )

    model_config = ConfigDict(frozen=True)

    @property
    def remaining_requests(self) -> int:
        """Calculate remaining requests in current window."""
        return max(0, self.limit - self.current_count)

    @property
    def usage_percentage(self) -> float:
        """Calculate usage percentage of the rate limit."""
        return (self.current_count / self.limit) * 100.0

    def to_headers(self) -> Dict[str, str]:
        """Convert result to HTTP headers following standard conventions."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining_requests),
            "X-RateLimit-Used": str(self.current_count),
            "X-RateLimit-Window": str(self.ttl),
        }

        if not self.allowed and self.retry_after:
            headers["Retry-After"] = str(self.retry_after)

        return headers

"""Basic tests for fastrict."""

import pytest

from fastrict import (
    KeyExtractionStrategy,
    KeyExtractionType,
    RateLimitStrategy,
    RateLimitStrategyName,
)


class TestRateLimitStrategy:
    """Test RateLimitStrategy entity."""

    def test_create_valid_strategy(self):
        """Test creating a valid rate limit strategy."""
        strategy = RateLimitStrategy(name=RateLimitStrategyName.SHORT, limit=5, ttl=60)

        assert strategy.name == RateLimitStrategyName.SHORT
        assert strategy.limit == 5
        assert strategy.ttl == 60

    def test_invalid_limit_raises_error(self):
        """Test that invalid limit raises validation error."""
        with pytest.raises(ValueError):
            RateLimitStrategy(
                name=RateLimitStrategyName.MEDIUM,
                limit=0,  # Invalid
                ttl=60,
            )


class TestKeyExtractionStrategy:
    """Test KeyExtractionStrategy entity."""

    def test_ip_strategy(self):
        """Test IP-based key extraction strategy."""
        strategy = KeyExtractionStrategy(type=KeyExtractionType.IP)

        assert strategy.type == KeyExtractionType.IP
        assert strategy.field_name is None

    def test_header_strategy(self):
        """Test header-based key extraction strategy."""
        strategy = KeyExtractionStrategy(
            type=KeyExtractionType.HEADER, field_name="X-API-Key"
        )

        assert strategy.type == KeyExtractionType.HEADER
        assert strategy.field_name == "X-API-Key"

    def test_header_strategy_requires_field_name(self):
        """Test that header strategy requires field_name."""
        with pytest.raises(ValueError):
            KeyExtractionStrategy(
                type=KeyExtractionType.HEADER
                # Missing field_name
            )


class TestImports:
    """Test that all public components can be imported."""

    def test_import_entities(self):
        """Test importing entity classes."""
        from fastrict import (
            KeyExtractionStrategy,
            KeyExtractionType,
            RateLimitConfig,
            RateLimitResult,
            RateLimitStrategy,
            RateLimitStrategyName,
        )

        # Test that classes exist and can be instantiated
        assert RateLimitStrategy is not None
        assert RateLimitStrategyName is not None
        assert KeyExtractionStrategy is not None
        assert KeyExtractionType is not None
        assert RateLimitConfig is not None
        assert RateLimitResult is not None

    def test_import_framework_components(self):
        """Test importing framework components."""
        from fastrict import (
            RateLimitMiddleware,
            throttle,
        )

        assert RateLimitMiddleware is not None
        assert throttle is not None

    def test_import_use_cases(self):
        """Test importing use cases."""
        from fastrict import (
            KeyExtractionUseCase,
            RateLimitUseCase,
        )

        assert RateLimitUseCase is not None
        assert KeyExtractionUseCase is not None

    def test_import_adapters(self):
        """Test importing adapters."""
        from fastrict import (
            RedisRateLimitRepository,
        )

        assert RedisRateLimitRepository is not None

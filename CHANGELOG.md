# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-10-03

### Fixed
- **Type Validation Improvements**: Resolved TypeAdapter compatibility issues when using the `@throttle` decorator with complex Query Parameter extraction scenarios
- **Query Parameter Handling**: Enhanced robustness for nested and multi-type query parameter processing in rate limiting contexts
- **Decorator Stability**: Improved error handling and type coercion for edge cases in parameter-based key extraction strategies


## [0.1.0] - 2025-10-03

### Added
- **Middleware Default Key Extraction**: New `default_key_extraction` parameter for RateLimitMiddleware
- **Fallback Key Extraction**: New `KeyExtractionType.FALLBACK` for sequential extraction strategies
- **Helper Functions**: Pre-built fallback strategies via `create_auth_header_fallback()`, `create_api_key_fallback()`, `create_user_id_fallback()`
- **Enhanced Decorator**: New `key_extraction_strategy` parameter for `@throttle` decorator
- **Flexible Priority System**: Route-specific > Middleware default > IP fallback

### Enhanced
- Key extraction logic now supports complex fallback scenarios
- Middleware can set default extraction strategy for all routes
- Decorator supports complete KeyExtractionStrategy objects
- Improved documentation with comprehensive fallback examples

### Features
- Try multiple extraction methods in sequence (e.g., API key → Auth header → IP)
- Middleware-level defaults that apply to all routes unless overridden
- Route-specific strategies override middleware defaults
- Automatic fallback to IP address if all strategies fail
- Production-ready fallback patterns for authentication scenarios

### Use Cases
- Multi-tenant SaaS applications with API key fallbacks
- Authentication-based rate limiting with IP fallbacks
- Complex user identification scenarios
- Graceful degradation for missing headers

## [0.0.3] - 2024-10-02

### Added
- Initial release of fastrict
- Rate limiting middleware for FastAPI applications
- Decorator-based route-specific rate limiting
- Redis backend with sliding window implementation
- Multiple key extraction strategies (IP, headers, query params, custom, combined)
- Built-in rate limiting strategies (short, medium, long-term)
- Bypass functions for conditional rate limiting
- Comprehensive error handling and logging
- Standard HTTP rate limiting headers
- Production-ready performance optimizations
- Clean Architecture implementation
- Comprehensive test suite
- Documentation and examples

### Features
- Support for 1K-30K concurrent connections
- Flexible key extraction strategies
- Custom error messages
- Monitoring and metrics support
- Graceful degradation and fallbacks
- Redis cluster support
- Automatic cleanup of expired keys
- Thread-safe operations

[0.0.3]: https://github.com/msameim181/fastrict/releases/tag/v0.0.3

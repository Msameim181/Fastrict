# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/0.0.3/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

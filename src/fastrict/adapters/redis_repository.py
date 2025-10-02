import logging
from datetime import datetime, timezone
from typing import Optional

import redis

from ..use_cases.interface.repository import IRateLimitRepository
from ..use_cases.key_extraction import RateLimitException


class RedisRateLimitRepository(IRateLimitRepository):
    """Redis-based implementation of rate limiting repository.

    This repository uses Redis sorted sets to implement sliding window
    rate limiting with precise time-based counting.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        logger: Optional[logging.Logger] = None,
        key_prefix: str = "rate_limit",
    ):
        """Initialize Redis rate limit repository."""
        self.redis_client = redis_client
        try:
            self.redis_client.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {str(e)}")
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.key_prefix = key_prefix

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        logger: Optional[logging.Logger] = None,
        key_prefix: str = "rate_limit",
        **redis_kwargs,
    ):
        """Create repository from Redis URL.

        Args:
            redis_url: Redis connection URL
            logger: Optional logger instance
            key_prefix: Prefix for Redis keys
            **redis_kwargs: Additional Redis connection parameters
        """
        redis_client = redis.from_url(redis_url, decode_responses=True, **redis_kwargs)
        return cls(redis_client=redis_client, logger=logger, key_prefix=key_prefix)

    def _get_redis_key(self, key: str) -> str:
        """Generate Redis key with prefix."""
        return f"{self.key_prefix}:{key}"

    def _get_current_timestamp(self) -> float:
        """Get current timestamp in UTC."""
        return datetime.now(tz=timezone.utc).timestamp()

    def increment_counter(self, key: str, ttl: int) -> int:
        """Increment rate limit counter using sliding window.

        Uses Redis sorted sets where:
        - Key: rate_limit:{identifier}
        - Score: timestamp
        - Member: unique timestamp string

        Args:
            key: Rate limiting identifier
            ttl: Time window in seconds

        Returns:
            int: Current count after increment

        Raises:
            RateLimitException: If Redis operations fail
        """
        try:
            redis_key = self._get_redis_key(key)
            now = self._get_current_timestamp()
            window_start = now - ttl

            # Use Redis pipeline for atomic operations
            pipeline = self.redis_client.pipeline()

            # Remove expired entries
            pipeline.zremrangebyscore(redis_key, 0, window_start)

            # Add current timestamp
            pipeline.zadd(redis_key, {str(now): now})

            # Set expiry for the key
            pipeline.expire(
                redis_key, ttl + 1
            )  # Add buffer to prevent premature expiry

            # Get current count
            pipeline.zcard(redis_key)

            # Execute all operations atomically
            results = pipeline.execute()

            # The last result is the count
            current_count = results[-1]

            self.logger.debug(
                f"Rate limit increment - Key: {key}, Count: {current_count}, TTL: {ttl}"
            )

            return current_count

        except Exception as e:
            self.logger.error(
                f"Failed to increment rate limit counter for key {key}: {str(e)}"
            )
            raise RateLimitException(
                message="Rate limit counter increment failed", status_code=500
            )

    def get_current_count(self, key: str) -> int:
        """Get current count without incrementing.

        Args:
            key: Rate limiting identifier

        Returns:
            int: Current count in the window
        """
        try:
            redis_key = self._get_redis_key(key)
            count = self.redis_client.zcard(redis_key)

            self.logger.debug(f"Rate limit current count - Key: {key}, Count: {count}")

            return count

        except Exception as e:
            self.logger.error(f"Failed to get current count for key {key}: {str(e)}")
            # Return 0 on error to be safe
            return 0

    def reset_counter(self, key: str) -> bool:
        """Reset counter for a key.

        Args:
            key: Rate limiting identifier

        Returns:
            bool: True if reset successful
        """
        try:
            redis_key = self._get_redis_key(key)
            deleted_count = self.redis_client.delete(redis_key)

            self.logger.debug(
                f"Rate limit reset - Key: {key}, Deleted: {deleted_count > 0}"
            )

            return deleted_count > 0

        except Exception as e:
            self.logger.error(f"Failed to reset counter for key {key}: {str(e)}")
            return False

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Rate limiting identifier

        Returns:
            int: Remaining seconds (-1 if no TTL, -2 if key doesn't exist)
        """
        try:
            redis_key = self._get_redis_key(key)
            ttl = self.redis_client.ttl(redis_key)

            self.logger.debug(f"Rate limit TTL - Key: {key}, TTL: {ttl}")

            return ttl

        except Exception as e:
            self.logger.error(f"Failed to get TTL for key {key}: {str(e)}")
            return -2  # Indicate error

    def cleanup_expired_keys(self, pattern: Optional[str] = None) -> int:
        """Clean up expired rate limiting keys.

        This is a maintenance operation to clean up any keys that
        might not have been automatically expired.

        Args:
            pattern: Optional pattern to match keys (default: all rate limit keys)

        Returns:
            int: Number of keys cleaned up
        """
        try:
            if pattern is None:
                pattern = f"{self.key_prefix}:*"

            keys = self.redis_client.keys(pattern)
            cleaned_count = 0

            for key in keys:
                try:
                    # Check if key has any members
                    count = self.redis_client.zcard(key)
                    if count == 0:
                        self.redis_client.delete(key)
                        cleaned_count += 1
                except Exception:
                    # If we can't check the key, skip it
                    continue

            self.logger.info(f"Cleaned up {cleaned_count} expired rate limit keys")

            return cleaned_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup expired keys: {str(e)}")
            return 0

    def get_rate_limit_info(self, key: str, ttl: int) -> dict:
        """Get comprehensive rate limit information for a key.

        Args:
            key: Rate limiting identifier
            ttl: Time window in seconds

        Returns:
            dict: Rate limit information including count, timestamps, etc.
        """
        try:
            redis_key = self._get_redis_key(key)
            now = self._get_current_timestamp()
            window_start = now - ttl

            # Get all entries in the current window
            entries = self.redis_client.zrangebyscore(
                redis_key, window_start, now, withscores=True
            )

            # Get key TTL
            key_ttl = self.get_ttl(key)

            return {
                "key": key,
                "redis_key": redis_key,
                "current_count": len(entries),
                "window_start": window_start,
                "window_end": now,
                "window_size": ttl,
                "key_ttl": key_ttl,
                "entries": [float(score) for _, score in entries],
                "oldest_entry": min([float(score) for _, score in entries])
                if entries
                else None,
                "newest_entry": max([float(score) for _, score in entries])
                if entries
                else None,
            }

        except Exception as e:
            self.logger.error(f"Failed to get rate limit info for key {key}: {str(e)}")
            return {"key": key, "error": str(e), "current_count": 0}

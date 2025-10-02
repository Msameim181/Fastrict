import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..use_cases.interface.repository import IRateLimitRepository
from ..use_cases.key_extraction import RateLimitException


@dataclass
class RateLimitEntry:
    """Represents a single rate limit entry with timestamp."""

    timestamp: float
    unique_id: str = field(default_factory=lambda: str(time.time()))


@dataclass
class RateLimitData:
    """Rate limit data for a specific key."""

    entries: List[RateLimitEntry] = field(default_factory=list)
    expiry_time: Optional[float] = None

    def is_expired(self) -> bool:
        """Check if the data has expired."""
        if self.expiry_time is None:
            return False
        return time.time() > self.expiry_time


class MemoryRateLimitRepository(IRateLimitRepository):
    """In-memory implementation of rate limiting repository.

    This repository uses in-memory data structures to implement sliding window
    rate limiting with precise time-based counting, similar to Redis implementation.

    Features:
    - Thread-safe operations using locks
    - Sliding window rate limiting
    - Automatic cleanup of expired entries
    - TTL support for keys
    - Comprehensive rate limit information
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        key_prefix: str = "rate_limit",
        cleanup_interval: int = 60,
        auto_cleanup: bool = True,
    ):
        """Initialize memory rate limit repository.

        Args:
            logger: Optional logger instance
            key_prefix: Prefix for keys (for consistency with Redis)
            cleanup_interval: Interval in seconds for automatic cleanup
            auto_cleanup: Whether to enable automatic cleanup of expired entries
        """
        self._data: Dict[str, RateLimitData] = {}
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._global_lock = threading.Lock()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.key_prefix = key_prefix
        self.cleanup_interval = cleanup_interval
        self.auto_cleanup = auto_cleanup
        self._last_cleanup = time.time()

    def _get_key(self, key: str) -> str:
        """Generate key with prefix (for consistency with Redis)."""
        return f"{self.key_prefix}:{key}"

    def _get_current_timestamp(self) -> float:
        """Get current timestamp in UTC."""
        return datetime.now(tz=timezone.utc).timestamp()

    def _cleanup_expired_entries(
        self, key: str, current_time: float, window_start: float
    ) -> None:
        """Remove expired entries from a key's data."""
        prefixed_key = self._get_key(key)

        if prefixed_key in self._data:
            rate_data = self._data[prefixed_key]

            # Remove entries outside the time window
            rate_data.entries = [
                entry for entry in rate_data.entries if entry.timestamp >= window_start
            ]

            # Check if the key itself has expired
            if rate_data.is_expired():
                del self._data[prefixed_key]
                self.logger.debug(f"Removed expired key: {key}")

    def _maybe_run_cleanup(self) -> None:
        """Run cleanup if enough time has passed and auto_cleanup is enabled."""
        if not self.auto_cleanup:
            return

        current_time = time.time()
        if current_time - self._last_cleanup >= self.cleanup_interval:
            self._run_global_cleanup()
            self._last_cleanup = current_time

    def _run_global_cleanup(self) -> None:
        """Run cleanup on all keys."""
        with self._global_lock:
            expired_keys = []

            for prefixed_key, rate_data in self._data.items():
                if rate_data.is_expired():
                    expired_keys.append(prefixed_key)

            for prefixed_key in expired_keys:
                del self._data[prefixed_key]

            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired keys")

    def increment_counter(self, key: str, ttl: int) -> int:
        """Increment rate limit counter using sliding window.

        Args:
            key: Rate limiting identifier
            ttl: Time window in seconds

        Returns:
            int: Current count after increment

        Raises:
            RateLimitException: If operations fail
        """
        try:
            prefixed_key = self._get_key(key)
            current_time = self._get_current_timestamp()
            window_start = current_time - ttl

            # Run cleanup if needed
            self._maybe_run_cleanup()

            with self._locks[prefixed_key]:
                # Initialize data if not exists
                if prefixed_key not in self._data:
                    self._data[prefixed_key] = RateLimitData()

                rate_data = self._data[prefixed_key]

                # Clean up expired entries
                self._cleanup_expired_entries(key, current_time, window_start)

                # Add new entry
                new_entry = RateLimitEntry(timestamp=current_time)
                rate_data.entries.append(new_entry)

                # Set expiry time for the key
                rate_data.expiry_time = current_time + ttl + 1  # Add buffer

                # Get current count
                current_count = len(rate_data.entries)

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
            prefixed_key = self._get_key(key)

            with self._locks[prefixed_key]:
                if prefixed_key not in self._data:
                    return 0

                rate_data = self._data[prefixed_key]

                # Check if expired
                if rate_data.is_expired():
                    del self._data[prefixed_key]
                    return 0

                # Note: This only returns the stored count, not filtered by window
                # For window-filtered count, use get_current_count_with_window
                count = len(rate_data.entries)

                self.logger.debug(
                    f"Rate limit current count - Key: {key}, Count: {count}"
                )

                return count

        except Exception as e:
            self.logger.error(f"Failed to get current count for key {key}: {str(e)}")
            # Return 0 on error to be safe
            return 0

    def get_current_count_with_window(self, key: str, ttl: int) -> int:
        """Get current count within a specific time window.

        Args:
            key: Rate limiting identifier
            ttl: Time window in seconds

        Returns:
            int: Current count in the specified window
        """
        try:
            prefixed_key = self._get_key(key)
            current_time = self._get_current_timestamp()
            window_start = current_time - ttl

            with self._locks[prefixed_key]:
                if prefixed_key not in self._data:
                    return 0

                rate_data = self._data[prefixed_key]

                # Check if expired
                if rate_data.is_expired():
                    del self._data[prefixed_key]
                    return 0

                # Clean up expired entries and count valid ones
                valid_entries = [
                    entry
                    for entry in rate_data.entries
                    if entry.timestamp >= window_start
                ]

                # Update the stored entries to remove expired ones
                rate_data.entries = valid_entries

                count = len(valid_entries)

                self.logger.debug(
                    f"Rate limit current count with window - Key: {key}, Count: {count}, TTL: {ttl}"
                )

                return count

        except Exception as e:
            self.logger.error(
                f"Failed to get current count with window for key {key}: {str(e)}"
            )
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
            prefixed_key = self._get_key(key)

            with self._locks[prefixed_key]:
                if prefixed_key in self._data:
                    del self._data[prefixed_key]
                    self.logger.debug(f"Rate limit reset - Key: {key}")
                    return True
                else:
                    self.logger.debug(f"Rate limit reset - Key: {key}, Key not found")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to reset counter for key {key}: {str(e)}")
            return False

    def _get_ttl_internal(self, prefixed_key: str, rate_data: RateLimitData) -> int:
        """Internal method to get TTL without acquiring locks.

        Args:
            prefixed_key: The prefixed key
            rate_data: The rate limit data

        Returns:
            int: Remaining seconds (-1 if no TTL, -2 if key doesn't exist)
        """
        if rate_data.expiry_time is None:
            return -1  # No TTL set

        current_time = time.time()
        if rate_data.is_expired():
            return -2  # Key expired

        remaining = int(rate_data.expiry_time - current_time)
        remaining = max(0, remaining)  # Ensure non-negative

        return remaining

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Rate limiting identifier

        Returns:
            int: Remaining seconds (-1 if no TTL, -2 if key doesn't exist)
        """
        try:
            prefixed_key = self._get_key(key)

            with self._locks[prefixed_key]:
                if prefixed_key not in self._data:
                    return -2  # Key doesn't exist

                rate_data = self._data[prefixed_key]

                if rate_data.is_expired():
                    del self._data[prefixed_key]
                    return -2  # Key expired

                remaining = self._get_ttl_internal(prefixed_key, rate_data)

                self.logger.debug(f"Rate limit TTL - Key: {key}, TTL: {remaining}")

                return remaining

        except Exception as e:
            self.logger.error(f"Failed to get TTL for key {key}: {str(e)}")
            return -2  # Indicate error

    def cleanup_expired_keys(self, pattern: Optional[str] = None) -> int:
        """Clean up expired rate limiting keys.

        This is a maintenance operation to clean up any keys that
        might not have been automatically expired.

        Args:
            pattern: Optional pattern to match keys (for consistency with Redis)
                    Note: In memory implementation, this is simplified to prefix matching

        Returns:
            int: Number of keys cleaned up
        """
        try:
            cleaned_count = 0

            with self._global_lock:
                expired_keys = []

                for prefixed_key, rate_data in self._data.items():
                    # Simple pattern matching (starts with pattern)
                    if pattern and not prefixed_key.startswith(
                        pattern.replace("*", "")
                    ):
                        continue

                    if rate_data.is_expired() or len(rate_data.entries) == 0:
                        expired_keys.append(prefixed_key)

                for prefixed_key in expired_keys:
                    del self._data[prefixed_key]
                    cleaned_count += 1

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
            prefixed_key = self._get_key(key)
            current_time = self._get_current_timestamp()
            window_start = current_time - ttl

            with self._locks[prefixed_key]:
                if prefixed_key not in self._data:
                    return {
                        "key": key,
                        "prefixed_key": prefixed_key,
                        "current_count": 0,
                        "window_start": window_start,
                        "window_end": current_time,
                        "window_size": ttl,
                        "key_ttl": -2,  # Key doesn't exist
                        "entries": [],
                        "oldest_entry": None,
                        "newest_entry": None,
                    }

                rate_data = self._data[prefixed_key]

                # Filter entries within the window
                valid_entries = [
                    entry
                    for entry in rate_data.entries
                    if entry.timestamp >= window_start
                ]

                # Get key TTL using internal method to avoid deadlock
                key_ttl = self._get_ttl_internal(prefixed_key, rate_data)

                entry_timestamps = [entry.timestamp for entry in valid_entries]

                return {
                    "key": key,
                    "prefixed_key": prefixed_key,
                    "current_count": len(valid_entries),
                    "window_start": window_start,
                    "window_end": current_time,
                    "window_size": ttl,
                    "key_ttl": key_ttl,
                    "entries": entry_timestamps,
                    "oldest_entry": min(entry_timestamps) if entry_timestamps else None,
                    "newest_entry": max(entry_timestamps) if entry_timestamps else None,
                    "total_stored_entries": len(rate_data.entries),
                    "expiry_time": rate_data.expiry_time,
                }

        except Exception as e:
            self.logger.error(f"Failed to get rate limit info for key {key}: {str(e)}")
            return {"key": key, "error": str(e), "current_count": 0}

    def get_all_keys(self, cleanup_first: bool = False) -> List[str]:
        """Get all active rate limit keys.

        Args:
            cleanup_first: Whether to run cleanup before getting keys

        Returns:
            List[str]: List of all active keys (without prefix)
        """
        try:
            with self._global_lock:
                # Optionally clean up expired keys first
                if cleanup_first:
                    expired_keys = []
                    for prefixed_key, rate_data in self._data.items():
                        if rate_data.is_expired():
                            expired_keys.append(prefixed_key)

                    for prefixed_key in expired_keys:
                        del self._data[prefixed_key]

                # Return keys without prefix
                keys = [
                    prefixed_key.replace(f"{self.key_prefix}:", "", 1)
                    for prefixed_key in self._data.keys()
                ]

                return keys

        except Exception as e:
            self.logger.error(f"Failed to get all keys: {str(e)}")
            return []

    def get_memory_stats(self) -> dict:
        """Get memory usage statistics.

        Returns:
            dict: Memory usage statistics
        """
        try:
            with self._global_lock:
                total_keys = len(self._data)
                total_entries = sum(len(data.entries) for data in self._data.values())
                expired_keys = sum(
                    1 for data in self._data.values() if data.is_expired()
                )

                return {
                    "total_keys": total_keys,
                    "total_entries": total_entries,
                    "expired_keys": expired_keys,
                    "active_keys": total_keys - expired_keys,
                    "average_entries_per_key": total_entries / total_keys
                    if total_keys > 0
                    else 0,
                    "last_cleanup": self._last_cleanup,
                    "cleanup_interval": self.cleanup_interval,
                    "auto_cleanup_enabled": self.auto_cleanup,
                }

        except Exception as e:
            self.logger.error(f"Failed to get memory stats: {str(e)}")
            return {"error": str(e)}

    def clear_all(self) -> bool:
        """Clear all rate limit data.

        Returns:
            bool: True if successful
        """
        try:
            with self._global_lock:
                self._data.clear()
                self.logger.info("Cleared all rate limit data")
                return True

        except Exception as e:
            self.logger.error(f"Failed to clear all data: {str(e)}")
            return False

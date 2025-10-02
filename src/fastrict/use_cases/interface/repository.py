from abc import ABC, abstractmethod


class IRateLimitRepository(ABC):
    """Abstract interface for rate limiting data storage.

    This interface defines the contract that rate limiting repositories
    must implement for storing and retrieving rate limit data.
    """

    @abstractmethod
    def increment_counter(self, key: str, ttl: int) -> int:
        """Increment rate limit counter for a key.

        Args:
            key: Rate limiting identifier
            ttl: Time window in seconds

        Returns:
            int: Current count after increment
        """
        pass

    @abstractmethod
    def get_current_count(self, key: str) -> int:
        """Get current count for a key without incrementing.

        Args:
            key: Rate limiting identifier

        Returns:
            int: Current count
        """
        pass

    @abstractmethod
    def reset_counter(self, key: str) -> bool:
        """Reset counter for a key.

        Args:
            key: Rate limiting identifier

        Returns:
            bool: True if reset successful
        """
        pass

    @abstractmethod
    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Rate limiting identifier

        Returns:
            int: Remaining seconds (-1 if no TTL, -2 if key doesn't exist)
        """
        pass

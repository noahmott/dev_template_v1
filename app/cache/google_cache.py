"""Caching layer for Google Reviews data."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any


class GoogleReviewsCache:
    """Cache for Google Reviews scraping results."""

    def __init__(self, ttl_hours: int = 24):
        """Initialize cache with TTL.

        Args:
            ttl_hours: Time to live in hours (default 24)
        """
        self.ttl = timedelta(hours=ttl_hours)
        self.cache: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get cached data.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # Check if expired
        if datetime.now() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            return None

        return entry["data"]

    async def set(self, key: str, value: dict[str, Any]) -> None:
        """Set cache data.

        Args:
            key: Cache key
            value: Data to cache
        """
        self.cache[key] = {"data": value, "timestamp": datetime.now()}

    async def invalidate(self, key: str) -> None:
        """Invalidate cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self.cache:
            del self.cache[key]

    def generate_key(self, url: str, **kwargs) -> str:
        """Generate cache key from URL and parameters.

        Args:
            url: Base URL
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        # Create a deterministic key from URL and parameters
        key_data = {"url": url, **kwargs}
        key_str = json.dumps(key_data, sort_keys=True)

        # Hash for shorter key
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    async def clear_expired(self) -> int:
        """Clear all expired cache entries.

        Returns:
            Number of entries cleared
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items() if now - entry["timestamp"] > self.ttl
        ]

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)

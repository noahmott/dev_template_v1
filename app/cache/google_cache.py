"""Caching layer for Google Reviews data."""

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.telemetry.logger import get_logger


class GoogleReviewsCache:
    """Cache for Google Reviews scraping results."""

    def __init__(self, ttl_hours: int = 24):
        """Initialize cache with TTL.

        Args:
            ttl_hours: Time to live in hours (default 24)
        """
        self.ttl = timedelta(hours=ttl_hours)
        self.cache: dict[str, dict[str, Any]] = {}
        self.logger = get_logger("google_reviews_cache")

        self.logger.info(
            "Google Reviews cache initialized",
            extra={
                "ttl_hours": ttl_hours,
                "operation": "cache_init",
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get cached data.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        self.logger.info(
            "Cache get operation started",
            extra={
                "correlation_id": correlation_id,
                "cache_key": key,
                "operation": "cache_get_start",
            },
        )

        if key not in self.cache:
            end_time = time.time()
            self.logger.info(
                "Cache miss - key not found",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": key,
                    "duration_seconds": end_time - start_time,
                    "operation": "cache_miss_not_found",
                },
            )
            return None

        entry = self.cache[key]

        # Check if expired
        if datetime.now() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            end_time = time.time()
            self.logger.info(
                "Cache miss - entry expired and removed",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": key,
                    "entry_age_hours": (datetime.now() - entry["timestamp"]).total_seconds() / 3600,
                    "ttl_hours": self.ttl.total_seconds() / 3600,
                    "duration_seconds": end_time - start_time,
                    "operation": "cache_miss_expired",
                },
            )
            return None

        end_time = time.time()
        self.logger.info(
            "Cache hit - returning cached data",
            extra={
                "correlation_id": correlation_id,
                "cache_key": key,
                "entry_age_hours": (datetime.now() - entry["timestamp"]).total_seconds() / 3600,
                "duration_seconds": end_time - start_time,
                "operation": "cache_hit",
            },
        )

        return entry["data"]

    async def set(self, key: str, value: dict[str, Any]) -> None:
        """Set cache data.

        Args:
            key: Cache key
            value: Data to cache
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        # Calculate data size for metrics
        try:
            data_size_bytes = len(json.dumps(value))
        except Exception:
            data_size_bytes = 0

        self.logger.info(
            "Cache set operation started",
            extra={
                "correlation_id": correlation_id,
                "cache_key": key,
                "data_size_bytes": data_size_bytes,
                "operation": "cache_set_start",
            },
        )

        # Check if we're overwriting existing entry
        is_update = key in self.cache

        self.cache[key] = {"data": value, "timestamp": datetime.now()}

        end_time = time.time()
        self.logger.info(
            "Cache set operation completed",
            extra={
                "correlation_id": correlation_id,
                "cache_key": key,
                "data_size_bytes": data_size_bytes,
                "is_update": is_update,
                "cache_size_after": len(self.cache),
                "duration_seconds": end_time - start_time,
                "operation": "cache_set_complete",
            },
        )

    async def invalidate(self, key: str) -> None:
        """Invalidate cache entry.

        Args:
            key: Cache key to invalidate
        """
        correlation_id = str(uuid.uuid4())

        self.logger.info(
            "Cache invalidation operation started",
            extra={
                "correlation_id": correlation_id,
                "cache_key": key,
                "operation": "cache_invalidate_start",
            },
        )

        if key in self.cache:
            del self.cache[key]
            self.logger.info(
                "Cache entry invalidated successfully",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": key,
                    "cache_size_after": len(self.cache),
                    "operation": "cache_invalidate_success",
                },
            )
        else:
            self.logger.warning(
                "Cache invalidation attempted on non-existent key",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": key,
                    "operation": "cache_invalidate_key_not_found",
                },
            )

    def generate_key(self, url: str, **kwargs) -> str:
        """Generate cache key from URL and parameters.

        Args:
            url: Base URL
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        correlation_id = str(uuid.uuid4())

        # Create a deterministic key from URL and parameters
        key_data = {"url": url, **kwargs}
        key_str = json.dumps(key_data, sort_keys=True)

        # Hash for shorter key
        cache_key = hashlib.sha256(key_str.encode()).hexdigest()[:16]

        self.logger.info(
            "Cache key generated",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "url": url,
                "parameters_count": len(kwargs),
                "operation": "cache_key_generate",
            },
        )

        return cache_key

    async def clear_expired(self) -> int:
        """Clear all expired cache entries.

        Returns:
            Number of entries cleared
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        self.logger.info(
            "Cache cleanup operation started",
            extra={
                "correlation_id": correlation_id,
                "cache_size_before": len(self.cache),
                "operation": "cache_cleanup_start",
            },
        )

        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items() if now - entry["timestamp"] > self.ttl
        ]

        for key in expired_keys:
            del self.cache[key]

        end_time = time.time()
        self.logger.info(
            "Cache cleanup operation completed",
            extra={
                "correlation_id": correlation_id,
                "expired_entries_removed": len(expired_keys),
                "cache_size_before": len(self.cache) + len(expired_keys),
                "cache_size_after": len(self.cache),
                "duration_seconds": end_time - start_time,
                "operation": "cache_cleanup_complete",
            },
        )

        return len(expired_keys)

"""Telemetry and metrics for scraping operations."""

import json
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.telemetry.logger import get_logger


class ScraperMetrics:
    """Metrics collection for scraping operations."""

    def __init__(self):
        """Initialize metrics collector."""
        self.logger = get_logger(__name__)
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_reviews_scraped": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "rate_limit_hits": 0,
            "robots_txt_blocks": 0,
            "security_blocks": 0,
            "platform_stats": {
                "yelp": {"requests": 0, "reviews": 0, "failures": 0},
                "google": {"requests": 0, "reviews": 0, "failures": 0},
                "tripadvisor": {"requests": 0, "reviews": 0, "failures": 0},
            },
            "response_times": [],
            "error_types": {},
        }

    def log_scraping_request(
        self,
        url: str,
        platform: str | None = None,
        job_id: str | None = None,
        request_id: str | None = None,
    ):
        """Log a scraping request.

        Args:
            url: URL being scraped
            platform: Platform name
            job_id: Associated job ID
            request_id: Request ID for correlation
        """
        self.metrics["total_requests"] += 1

        log_data = {
            "event": "scraping_request",
            "url": url,
            "platform": platform,
            "job_id": job_id,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(
            "Scraping request initiated",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_scraping_success(
        self,
        url: str,
        platform: str | None = None,
        review_count: int = 0,
        response_time: float = 0,
        job_id: str | None = None,
        request_id: str | None = None,
    ):
        """Log successful scraping.

        Args:
            url: URL that was scraped
            platform: Platform name
            review_count: Number of reviews scraped
            response_time: Time taken in seconds
            job_id: Associated job ID
            request_id: Request ID for correlation
        """
        self.metrics["successful_scrapes"] += 1
        self.metrics["total_reviews_scraped"] += review_count
        self.metrics["response_times"].append(response_time)

        if platform and platform in self.metrics["platform_stats"]:
            self.metrics["platform_stats"][platform]["requests"] += 1
            self.metrics["platform_stats"][platform]["reviews"] += review_count

        # Keep only last 1000 response times
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"] = self.metrics["response_times"][-1000:]

        log_data = {
            "event": "scraping_success",
            "url": url,
            "platform": platform,
            "review_count": review_count,
            "response_time": response_time,
            "job_id": job_id,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(
            f"Scraping completed successfully: {review_count} reviews in {response_time:.2f}s",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_scraping_failure(
        self,
        url: str,
        error: str,
        platform: str | None = None,
        job_id: str | None = None,
        request_id: str | None = None,
        error_type: str | None = None,
    ):
        """Log scraping failure.

        Args:
            url: URL that failed
            error: Error message
            platform: Platform name
            job_id: Associated job ID
            request_id: Request ID for correlation
            error_type: Type of error
        """
        self.metrics["failed_scrapes"] += 1

        if platform and platform in self.metrics["platform_stats"]:
            self.metrics["platform_stats"][platform]["failures"] += 1

        if error_type:
            self.metrics["error_types"][error_type] = (
                self.metrics["error_types"].get(error_type, 0) + 1
            )

        log_data = {
            "event": "scraping_failure",
            "url": url,
            "error": error,
            "error_type": error_type,
            "platform": platform,
            "job_id": job_id,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.error(
            f"Scraping failed: {error}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_cache_hit(self, cache_key: str, request_id: str | None = None):
        """Log cache hit.

        Args:
            cache_key: Cache key that was hit
            request_id: Request ID for correlation
        """
        self.metrics["cache_hits"] += 1

        log_data = {
            "event": "cache_hit",
            "cache_key": cache_key,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.debug(
            f"Cache hit for key: {cache_key}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_cache_miss(self, cache_key: str, request_id: str | None = None):
        """Log cache miss.

        Args:
            cache_key: Cache key that was missed
            request_id: Request ID for correlation
        """
        self.metrics["cache_misses"] += 1

        log_data = {
            "event": "cache_miss",
            "cache_key": cache_key,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.debug(
            f"Cache miss for key: {cache_key}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_rate_limit(self, domain: str, request_id: str | None = None):
        """Log rate limit hit.

        Args:
            domain: Domain that hit rate limit
            request_id: Request ID for correlation
        """
        self.metrics["rate_limit_hits"] += 1

        log_data = {
            "event": "rate_limit_hit",
            "domain": domain,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(
            f"Rate limit hit for domain: {domain}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_robots_txt_block(self, url: str, request_id: str | None = None):
        """Log robots.txt block.

        Args:
            url: URL blocked by robots.txt
            request_id: Request ID for correlation
        """
        self.metrics["robots_txt_blocks"] += 1

        log_data = {
            "event": "robots_txt_block",
            "url": url,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(
            f"Blocked by robots.txt: {url}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_security_block(
        self, reason: str, url: str | None = None, request_id: str | None = None
    ):
        """Log security block.

        Args:
            reason: Reason for block
            url: URL that was blocked
            request_id: Request ID for correlation
        """
        self.metrics["security_blocks"] += 1

        log_data = {
            "event": "security_block",
            "reason": reason,
            "url": url,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(
            f"Security block: {reason}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_job_created(
        self, job_id: str, platform: str | None = None, request_id: str | None = None
    ):
        """Log job creation.

        Args:
            job_id: Created job ID
            platform: Platform for job
            request_id: Request ID for correlation
        """
        log_data = {
            "event": "job_created",
            "job_id": job_id,
            "platform": platform,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(
            f"Scraping job created: {job_id}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def log_job_completed(
        self,
        job_id: str,
        status: str,
        duration: float,
        review_count: int = 0,
        request_id: str | None = None,
    ):
        """Log job completion.

        Args:
            job_id: Completed job ID
            status: Final status
            duration: Job duration in seconds
            review_count: Total reviews collected
            request_id: Request ID for correlation
        """
        log_data = {
            "event": "job_completed",
            "job_id": job_id,
            "status": status,
            "duration": duration,
            "review_count": review_count,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(
            f"Job {job_id} completed with status {status} in {duration:.2f}s",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get current metrics summary.

        Returns:
            Dictionary of metrics
        """
        avg_response_time = (
            sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            if self.metrics["response_times"]
            else 0
        )

        cache_hit_rate = (
            self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"])
            if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0
            else 0
        )

        success_rate = (
            self.metrics["successful_scrapes"]
            / (self.metrics["successful_scrapes"] + self.metrics["failed_scrapes"])
            if (self.metrics["successful_scrapes"] + self.metrics["failed_scrapes"]) > 0
            else 0
        )

        return {
            "total_requests": self.metrics["total_requests"],
            "successful_scrapes": self.metrics["successful_scrapes"],
            "failed_scrapes": self.metrics["failed_scrapes"],
            "success_rate": success_rate,
            "total_reviews_scraped": self.metrics["total_reviews_scraped"],
            "avg_response_time": avg_response_time,
            "cache_hit_rate": cache_hit_rate,
            "rate_limit_hits": self.metrics["rate_limit_hits"],
            "robots_txt_blocks": self.metrics["robots_txt_blocks"],
            "security_blocks": self.metrics["security_blocks"],
            "platform_stats": self.metrics["platform_stats"],
            "error_types": self.metrics["error_types"],
        }

    @contextmanager
    def track_operation(self, operation_name: str, **kwargs):
        """Context manager to track operation timing.

        Args:
            operation_name: Name of operation
            **kwargs: Additional context

        Yields:
            Operation context
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        log_data = {
            "event": f"{operation_name}_start",
            "request_id": request_id,
            "context": kwargs,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.debug(
            f"Starting {operation_name}",
            extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
        )

        try:
            yield
            duration = time.time() - start_time

            log_data = {
                "event": f"{operation_name}_complete",
                "duration": duration,
                "request_id": request_id,
                "context": kwargs,
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.debug(
                f"Completed {operation_name} in {duration:.3f}s",
                extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
            )

        except Exception as e:
            duration = time.time() - start_time

            log_data = {
                "event": f"{operation_name}_error",
                "error": str(e),
                "duration": duration,
                "request_id": request_id,
                "context": kwargs,
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.error(
                f"Error in {operation_name} after {duration:.3f}s: {e}",
                extra={"json_fields": json.dumps(log_data, ensure_ascii=True)},
            )
            raise


# Global metrics instance
metrics = ScraperMetrics()

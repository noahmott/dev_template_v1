"""Rate limiting middleware for API endpoints."""

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent abuse."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Max requests per minute per IP
            requests_per_hour: Max requests per hour per IP
            burst_size: Max burst requests allowed
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size

        # Track requests by IP: {ip: [(timestamp, endpoint), ...]}
        self.requests: dict[str, list[tuple[float, str]]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        Args:
            request: FastAPI request

        Returns:
            Client IP address
        """
        # Check for proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _clean_old_requests(self, ip: str, current_time: float):
        """Remove old requests outside the tracking window.

        Args:
            ip: Client IP
            current_time: Current timestamp
        """
        # Keep only requests from last hour
        cutoff_time = current_time - 3600
        self.requests[ip] = [
            (ts, endpoint) for ts, endpoint in self.requests[ip] if ts > cutoff_time
        ]

    def _check_rate_limit(self, ip: str, endpoint: str, current_time: float) -> bool:
        """Check if request exceeds rate limits.

        Args:
            ip: Client IP
            endpoint: API endpoint
            current_time: Current timestamp

        Returns:
            True if within limits, False if exceeded
        """
        # Clean old requests
        self._clean_old_requests(ip, current_time)

        requests = self.requests[ip]

        # Check burst limit (last 5 seconds)
        burst_window = current_time - 5
        burst_requests = sum(1 for ts, _ in requests if ts > burst_window)
        if burst_requests >= self.burst_size:
            return False

        # Check minute limit
        minute_window = current_time - 60
        minute_requests = sum(1 for ts, _ in requests if ts > minute_window)
        if minute_requests >= self.requests_per_minute:
            return False

        # Check hour limit
        hour_window = current_time - 3600
        hour_requests = sum(1 for ts, _ in requests if ts > hour_window)
        if hour_requests >= self.requests_per_hour:
            return False

        # Special limits for scraping endpoints
        if "/scraping" in endpoint:
            # More restrictive for scraping endpoints
            scraping_minute_window = current_time - 60
            scraping_requests = sum(
                1 for ts, ep in requests if ts > scraping_minute_window and "/scraping" in ep
            )
            if scraping_requests >= 10:  # Max 10 scraping requests per minute
                return False

        return True

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response or rate limit error
        """
        # Skip rate limiting for health checks
        if request.url.path in ["/healthz", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        current_time = time.time()

        # Check rate limits
        if not self._check_rate_limit(client_ip, endpoint, current_time):
            # Calculate retry time
            requests = self.requests[client_ip]
            minute_window = current_time - 60
            minute_requests = [ts for ts, _ in requests if ts > minute_window]

            if minute_requests:
                oldest_request = min(minute_requests)
                retry_after = int(60 - (current_time - oldest_request))
            else:
                retry_after = 60

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(current_time + retry_after)),
                },
            )

        # Record request
        self.requests[client_ip].append((current_time, endpoint))

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        minute_window = current_time - 60
        minute_requests = sum(1 for ts, _ in self.requests[client_ip] if ts > minute_window)
        remaining = max(0, self.requests_per_minute - minute_requests)

        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))

        return response

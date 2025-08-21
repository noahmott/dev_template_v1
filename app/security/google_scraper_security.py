"""Security measures for Google Reviews scraping."""

import hashlib
import hmac
import os
import secrets
from urllib.parse import urlparse

from fastapi import HTTPException


class GoogleScraperSecurity:
    """Security layer for Google Reviews scraping operations."""

    def __init__(self):
        """Initialize security settings."""
        self.allowed_domains = [
            "google.com",
            "maps.google.com",
            "www.google.com",
        ]
        self.max_url_length = 2048
        self.secret_key = os.getenv("SCRAPER_SECRET_KEY", secrets.token_urlsafe(32))

    def validate_google_url(self, url: str) -> bool:
        """Validate that URL is a legitimate Google Maps URL.

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        if not url or len(url) > self.max_url_length:
            return False

        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ["https"]:
                return False

            # Check domain
            domain = parsed.netloc.lower()
            if not any(domain.endswith(allowed) for allowed in self.allowed_domains):
                return False

            # Check path contains maps indicator
            if "/maps/" not in parsed.path and "/place/" not in parsed.path:
                return False

            return True

        except Exception:
            return False

    def sanitize_input(self, text: str, max_length: int = 500) -> str:
        """Sanitize user input to prevent injection attacks.

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate to max length
        text = text[:max_length]

        # Remove potential script tags and SQL keywords
        dangerous_patterns = [
            "<script",
            "</script>",
            "javascript:",
            "onclick",
            "onerror",
            "DROP TABLE",
            "DELETE FROM",
            "INSERT INTO",
            "--",
            "/*",
            "*/",
            "xp_",
            "sp_",
        ]

        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in text_lower:
                raise HTTPException(status_code=400, detail="Invalid input detected")

        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char == "\n")

        return text.strip()

    def generate_job_token(self, job_id: str) -> str:
        """Generate secure token for job access.

        Args:
            job_id: Job ID

        Returns:
            Secure token
        """
        message = f"job:{job_id}".encode()
        return hmac.new(self.secret_key.encode(), message, hashlib.sha256).hexdigest()

    def verify_job_token(self, job_id: str, token: str) -> bool:
        """Verify job access token.

        Args:
            job_id: Job ID
            token: Token to verify

        Returns:
            True if valid, False otherwise
        """
        expected = self.generate_job_token(job_id)
        return hmac.compare_digest(expected, token)

    def check_rate_limit_headers(self, headers: dict) -> int | None:
        """Check for rate limit headers from Google.

        Args:
            headers: Response headers

        Returns:
            Retry-after seconds if rate limited, None otherwise
        """
        # Check for 429 status
        if headers.get("status") == "429":
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    return 60  # Default to 1 minute
            return 60

        return None

    def validate_review_data(self, review: dict) -> bool:
        """Validate scraped review data for safety.

        Args:
            review: Review data dictionary

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        required = ["text", "rating", "author", "platform"]
        if not all(field in review for field in required):
            return False

        # Validate rating range
        try:
            rating = float(review["rating"])
            if rating < 0 or rating > 5:
                return False
        except (ValueError, TypeError):
            return False

        # Check platform
        if review["platform"] != "google":
            return False

        # Validate text length
        if len(review.get("text", "")) > 10000:
            return False

        return True

    def anonymize_pii(self, text: str) -> str:
        """Remove or mask potential PII from text.

        Args:
            text: Text that may contain PII

        Returns:
            Text with PII removed/masked
        """
        import re

        # Remove email addresses
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)

        # Remove phone numbers (US format)
        text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", text)

        # Remove SSN-like patterns
        text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)

        # Remove credit card-like patterns
        text = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CARD]", text)

        return text

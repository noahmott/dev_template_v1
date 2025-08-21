"""Security utilities for web scraping operations."""

import hashlib
import hmac
import re
import secrets
from urllib.parse import urlparse

from fastapi import HTTPException


class ScraperSecurity:
    """Security utilities for scraping operations."""

    # Allowed domains for scraping
    ALLOWED_DOMAINS = {
        "yelp.com",
        "www.yelp.com",
        "google.com",
        "www.google.com",
        "maps.google.com",
        "tripadvisor.com",
        "www.tripadvisor.com",
    }

    # Blocked URL patterns (regex)
    BLOCKED_PATTERNS = [
        r".*\.(exe|dll|bat|cmd|sh|ps1)$",  # Executable files
        r".*\/(admin|login|auth|api-key|token).*",  # Admin/auth pages
        r".*\.(zip|tar|gz|rar|7z)$",  # Archive files
        r"file:\/\/.*",  # Local file URLs
        r".*localhost.*",  # Localhost URLs
        r".*127\.0\.0\.1.*",  # Loopback addresses
        r".*::1.*",  # IPv6 loopback
        r".*\.(onion|i2p)$",  # Dark web domains
    ]

    # Maximum URL length
    MAX_URL_LENGTH = 2048

    # Rate limiting settings
    MAX_REQUESTS_PER_MINUTE = 10
    MAX_REQUESTS_PER_HOUR = 300
    MAX_REQUESTS_PER_DAY = 5000

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate URL for security issues.

        Args:
            url: URL to validate

        Returns:
            True if URL is safe, False otherwise

        Raises:
            HTTPException: If URL is invalid or unsafe
        """
        if not url or len(url) > cls.MAX_URL_LENGTH:
            raise HTTPException(status_code=400, detail="Invalid URL length")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid URL format") from e

        # Check scheme
        if parsed.scheme not in ["http", "https"]:
            raise HTTPException(status_code=400, detail="Only HTTP/HTTPS URLs are allowed")

        # Check domain allowlist
        domain = parsed.netloc.lower()
        if domain not in cls.ALLOWED_DOMAINS:
            # Check if it's a subdomain of allowed domains
            allowed = False
            for allowed_domain in cls.ALLOWED_DOMAINS:
                if domain.endswith(f".{allowed_domain}"):
                    allowed = True
                    break
            if not allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Domain {domain} is not in the allowed list",
                )

        # Check blocked patterns
        url_lower = url.lower()
        for pattern in cls.BLOCKED_PATTERNS:
            if re.match(pattern, url_lower):
                raise HTTPException(status_code=403, detail="URL matches blocked pattern")

        # Check for SQL injection attempts
        sql_keywords = [
            "select",
            "insert",
            "update",
            "delete",
            "drop",
            "union",
            "exec",
            "script",
        ]
        for keyword in sql_keywords:
            if f" {keyword} " in url_lower or f"%20{keyword}%20" in url_lower:
                raise HTTPException(status_code=403, detail="Potential SQL injection detected")

        # Check for XSS attempts
        xss_patterns = ["<script", "javascript:", "onerror=", "onclick=", "alert("]
        for pattern in xss_patterns:
            if pattern in url_lower:
                raise HTTPException(status_code=403, detail="Potential XSS attack detected")

        return True

    @classmethod
    def sanitize_input(cls, text: str, max_length: int = 1000) -> str:
        """Sanitize user input text.

        Args:
            text: Text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate to max length
        text = text[:max_length]

        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char == "\n")

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove script tags specifically
        text = re.sub(r"<script.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Escape special characters
        text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

        return text.strip()

    @classmethod
    def generate_job_token(cls, job_id: str, secret_key: str) -> str:
        """Generate secure token for job access.

        Args:
            job_id: Job ID
            secret_key: Secret key for HMAC

        Returns:
            Secure token
        """
        message = f"job:{job_id}:{secrets.token_hex(8)}"
        signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
        return f"{message}:{signature}"

    @classmethod
    def verify_job_token(cls, token: str, job_id: str, secret_key: str) -> bool:
        """Verify job access token.

        Args:
            token: Token to verify
            job_id: Expected job ID
            secret_key: Secret key for HMAC

        Returns:
            True if valid, False otherwise
        """
        try:
            parts = token.split(":")
            if len(parts) != 4:
                return False

            token_type, token_job_id, nonce, signature = parts

            if token_type != "job" or token_job_id != job_id:
                return False

            message = f"{token_type}:{token_job_id}:{nonce}"
            expected_signature = hmac.new(
                secret_key.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except Exception:
            return False

    @classmethod
    def mask_sensitive_data(cls, data: dict) -> dict:
        """Mask sensitive data in response.

        Args:
            data: Data dictionary

        Returns:
            Data with sensitive fields masked
        """
        sensitive_fields = [
            "password",
            "token",
            "api_key",
            "secret",
            "auth",
            "cookie",
            "session",
        ]

        masked_data = data.copy()

        for key, value in masked_data.items():
            # Check if key contains sensitive field name
            key_lower = key.lower()
            for field in sensitive_fields:
                if field in key_lower:
                    if isinstance(value, str):
                        # Mask all but first and last 2 characters
                        if len(value) > 4:
                            masked_data[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                        else:
                            masked_data[key] = "*" * len(value)
                    break

            # Recursively mask nested dictionaries
            if isinstance(value, dict):
                masked_data[key] = cls.mask_sensitive_data(value)
            elif isinstance(value, list):
                masked_data[key] = [
                    cls.mask_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]

        return masked_data

    @classmethod
    def validate_platform(cls, platform: str) -> bool:
        """Validate platform name.

        Args:
            platform: Platform name

        Returns:
            True if valid

        Raises:
            HTTPException: If invalid
        """
        allowed_platforms = ["yelp", "google", "tripadvisor"]
        if platform.lower() not in allowed_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform. Must be one of: {', '.join(allowed_platforms)}",
            )
        return True

    @classmethod
    def get_safe_user_agent(cls) -> str:
        """Get safe user agent string.

        Returns:
            User agent string
        """
        return "Mozilla/5.0 (compatible; RestaurantScraperBot/1.0; +https://example.com/bot)"

    @classmethod
    def check_content_type(cls, content_type: str | None) -> bool:
        """Check if content type is safe to parse.

        Args:
            content_type: Content-Type header value

        Returns:
            True if safe

        Raises:
            HTTPException: If unsafe
        """
        if not content_type:
            return True

        # Allow HTML and JSON
        safe_types = ["text/html", "application/json", "text/plain"]

        content_type_lower = content_type.lower()
        for safe_type in safe_types:
            if safe_type in content_type_lower:
                return True

        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type}")

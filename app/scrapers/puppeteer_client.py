"""Puppeteer client for JavaScript-rendered content scraping."""

import asyncio
import hashlib
import logging
import os
import re
from urllib.parse import urlparse

from pyppeteer.browser import Browser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.scraping import BusinessInfo, Review


class PuppeteerClient:
    """Client for scraping JavaScript-rendered content using Pyppeteer."""

    def __init__(self, max_concurrent_browsers: int = 3):
        """Initialize Puppeteer client.

        Args:
            max_concurrent_browsers: Maximum number of concurrent browser instances
        """
        self.max_concurrent_browsers = max_concurrent_browsers
        self.browsers: list[Browser] = []
        self.semaphore = asyncio.Semaphore(max_concurrent_browsers)
        self.logger = logging.getLogger(__name__)
        self.timeout = int(os.getenv("SCRAPING_TIMEOUT_SECONDS", "30")) * 1000

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browsers."""
        await self.cleanup()

    async def cleanup(self):
        """Close all browser instances."""
        for browser in self.browsers:
            try:
                await browser.close()
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")
        self.browsers.clear()

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def scrape_url(self, url: str, wait_selector: str | None = None) -> str | None:
        """Scrape a URL and return HTML content.

        Args:
            url: URL to scrape
            wait_selector: CSS selector to wait for before getting content

        Returns:
            HTML content or None if failed
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    async def scrape_yelp_reviews(self, url: str, max_pages: int = 5) -> list[Review]:
        """Scrape reviews from Yelp.

        Args:
            url: Yelp business URL
            max_pages: Maximum number of pages to scrape

        Returns:
            List of scraped reviews
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    async def scrape_google_reviews(self, url: str, max_reviews: int = 100) -> list[Review]:
        """Scrape reviews from Google.

        Args:
            url: Google Maps/Business URL
            max_reviews: Maximum number of reviews to scrape

        Returns:
            List of scraped reviews
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    async def scrape_tripadvisor_reviews(self, url: str, max_pages: int = 5) -> list[Review]:
        """Scrape reviews from TripAdvisor.

        Args:
            url: TripAdvisor restaurant URL
            max_pages: Maximum number of pages to scrape

        Returns:
            List of scraped reviews
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    async def extract_business_info(self, url: str) -> BusinessInfo | None:
        """Extract business information from a URL.

        Args:
            url: Business page URL

        Returns:
            Business information or None if failed
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    async def search_business(self, business_name: str, location: str, platform: str) -> str | None:
        """Search for a business and return its URL.

        Args:
            business_name: Name of the business
            location: Location (city, state, etc.)
            platform: Platform to search on (yelp, google, tripadvisor)

        Returns:
            Business URL or None if not found
        """
        # Implementation will be added in IMPLEMENTER phase
        raise NotImplementedError("To be implemented in IMPLEMENTER phase")

    def _get_platform_from_url(self, url: str) -> str | None:
        """Determine platform from URL.

        Args:
            url: URL to analyze

        Returns:
            Platform name or None
        """
        domain = urlparse(url).netloc.lower()
        if "yelp" in domain:
            return "yelp"
        elif "google" in domain or "maps.google" in domain:
            return "google"
        elif "tripadvisor" in domain:
            return "tripadvisor"
        return None

    def _generate_review_hash(self, review_text: str, author: str) -> str:
        """Generate hash for review deduplication.

        Args:
            review_text: Review content
            author: Review author

        Returns:
            SHA256 hash of review
        """
        content = f"{author}:{review_text}".encode()
        return hashlib.sha256(content).hexdigest()

    def _sanitize_text(self, text: str | None) -> str:
        """Sanitize text by removing extra whitespace.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        if not text:
            return ""
        # Remove extra whitespace and newlines
        text = re.sub(r"\\s+", " ", text)
        return text.strip()

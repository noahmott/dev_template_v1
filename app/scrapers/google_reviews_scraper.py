"""Google Reviews specific scraper implementation."""

from app.models.scraping import BusinessInfo, Review


class GoogleReviewsScraper:
    """Scraper specifically for Google Reviews."""

    def __init__(self):
        """Initialize Google Reviews scraper."""
        pass

    async def scrape_reviews(self, url: str, max_reviews: int = 100) -> list[Review]:
        """Scrape reviews from Google Maps business page.

        Args:
            url: Google Maps business URL
            max_reviews: Maximum number of reviews to scrape

        Returns:
            List of Review objects
        """
        pass

    async def search_business(self, business_name: str, location: str) -> str | None:
        """Search for a business on Google Maps.

        Args:
            business_name: Name of the business
            location: Location to search in

        Returns:
            Google Maps URL of the business or None
        """
        pass

    async def extract_business_info(self, url: str) -> BusinessInfo | None:
        """Extract business information from Google Maps page.

        Args:
            url: Google Maps business URL

        Returns:
            BusinessInfo object or None
        """
        pass

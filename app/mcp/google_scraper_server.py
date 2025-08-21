"""Google Reviews MCP server implementation."""

import os
from typing import Any

from fastmcp import FastMCP

from app.scrapers.google_reviews_scraper import GoogleReviewsScraper
from app.services.google_scraper_service import GoogleScraperService

# Initialize MCP server
mcp_server = FastMCP("google-reviews-scraper")

# Initialize services
scraper = GoogleReviewsScraper()
service = GoogleScraperService()


@mcp_server.tool()
async def scrape_google_reviews(url: str, max_pages: int = 5) -> list[dict[str, Any]]:
    """Scrape reviews from Google Maps/Business pages.

    Args:
        url: Google Maps business URL
        max_pages: Maximum number of pages to scrape (default 5)

    Returns:
        List of review dictionaries
    """
    # Validate URL
    if not url or not url.startswith(("https://www.google.com/maps/", "https://maps.google.com/")):
        raise ValueError(f"Invalid Google Maps URL: {url}")

    # Calculate max reviews from pages (approx 20 reviews per "page")
    max_reviews = max_pages * 20

    # Scrape reviews
    reviews = await scraper.scrape_reviews(url, max_reviews=max_reviews)

    # Convert to dictionaries
    return [review.model_dump() for review in reviews]


@mcp_server.tool()
async def search_google_business(business_name: str, location: str) -> dict[str, Any]:
    """Search for a business on Google Maps and scrape its reviews.

    Args:
        business_name: Name of the business to search
        location: Location (city, state) to search in

    Returns:
        Scraping job with results
    """
    # Validate inputs
    if not business_name or not location:
        raise ValueError("Both business_name and location are required")

    # Create and execute scraping job
    job = await service.create_scraping_job(business_name, location)

    # Return job details
    return job.model_dump()


@mcp_server.tool()
async def extract_google_business_info(url: str) -> dict[str, Any]:
    """Extract business information from a Google Maps URL.

    Args:
        url: Google Maps business URL

    Returns:
        Business information dictionary
    """
    # Validate URL
    if not url or not url.startswith(("https://www.google.com/maps/", "https://maps.google.com/")):
        raise ValueError(f"Invalid Google Maps URL: {url}")

    # Extract business info
    info = await scraper.extract_business_info(url)

    if not info:
        raise ValueError(f"Could not extract business information from {url}")

    return info.model_dump()


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    return mcp_server


if __name__ == "__main__":
    # Run the MCP server
    import asyncio

    port = int(os.getenv("MCP_SERVER_PORT", "3000"))
    asyncio.run(mcp_server.run(port=port))

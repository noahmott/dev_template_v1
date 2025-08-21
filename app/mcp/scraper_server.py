"""MCP server for web scraping tools using FastMCP."""

import asyncio
import hashlib
import json
import os
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as redis
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from app.models.scraping import JobStatus
from app.services.scraper_service import ScraperService

# Initialize FastMCP server
mcp = FastMCP("Restaurant Review Scraper")

# Global instances
_redis_client: redis.Redis | None = None
_scraper_service: ScraperService | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if not _redis_client:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = await redis.from_url(redis_url)
    return _redis_client


async def get_scraper_service() -> ScraperService:
    """Get or create scraper service."""
    global _scraper_service
    if not _scraper_service:
        _scraper_service = ScraperService()
    return _scraper_service


class ScrapeReviewsInput(BaseModel):
    """Input schema for scrape_reviews tool."""

    url: str = Field(description="URL to scrape reviews from")
    max_pages: int = Field(default=5, description="Maximum number of pages to scrape")


class SearchAndScrapeInput(BaseModel):
    """Input schema for search_and_scrape tool."""

    business_name: str = Field(description="Name of the business to search for")
    location: str = Field(description="Location/city to search in")
    platform: str = Field(description="Platform to search on (yelp, google, tripadvisor)")
    webhook_url: str | None = Field(None, description="Webhook URL for job completion")


class ExtractBusinessInfoInput(BaseModel):
    """Input schema for extract_business_info tool."""

    url: str = Field(description="URL of the business page")


@mcp.tool()
async def scrape_reviews(url: str, max_pages: int = 5) -> list[dict[str, Any]]:
    """
    Scrape reviews from a given URL.

    Args:
        url: The URL to scrape reviews from
        max_pages: Maximum number of pages to scrape (default: 5)

    Returns:
        List of review dictionaries
    """
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    # Check cache first
    redis_client = await get_redis_client()
    cache_key = f"reviews:{hashlib.md5(f'{url}:{max_pages}'.encode()).hexdigest()}"

    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Check rate limit
    domain = parsed.netloc
    rate_key = f"rate:{domain}"
    current_rate = await redis_client.get(rate_key) or 0

    if int(current_rate) >= 10:
        raise Exception(f"Rate limit exceeded for {domain}")

    await redis_client.incr(rate_key)
    await redis_client.expire(rate_key, 60)

    # Scrape with Puppeteer
    scraper_service = await get_scraper_service()

    try:
        reviews = await scraper_service.scrape_url(url, max_pages)

        # Cache results for 24 hours
        await redis_client.set(cache_key, json.dumps(reviews), ex=86400)

        return reviews
    except Exception as e:
        # Retry logic is handled by the service
        raise e


@mcp.tool()
async def search_and_scrape(
    business_name: str, location: str, platform: str, webhook_url: str | None = None
) -> dict[str, Any]:
    """
    Search for a business and scrape its reviews.

    Args:
        business_name: Name of the business
        location: Location/city
        platform: Platform to search (yelp, google, tripadvisor)
        webhook_url: Optional webhook for completion notification

    Returns:
        Job information with ID and status
    """
    # Validate platform
    supported_platforms = ["yelp", "google", "tripadvisor"]
    if platform.lower() not in supported_platforms:
        raise ValueError(f"Unsupported platform: {platform}")

    scraper_service = await get_scraper_service()

    # Create scraping job
    job = await scraper_service.create_job(
        business_name=business_name, location=location, platform=platform, webhook_url=webhook_url
    )

    # Start async scraping
    asyncio.create_task(scraper_service.execute_job(job))

    return {
        "id": job.id,
        "status": job.status.value,
        "platform": platform,
        "business_name": business_name,
        "location": location,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@mcp.tool()
async def extract_business_info(url: str) -> dict[str, Any]:
    """
    Extract business information from a URL.

    Args:
        url: URL of the business page

    Returns:
        Business information including name, address, rating, etc.
    """
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    scraper_service = await get_scraper_service()

    # Extract business info
    info = await scraper_service.extract_business_info(url)

    return info


@mcp.tool()
async def get_job_status(job_id: str) -> dict[str, Any]:
    """
    Get the status of a scraping job.

    Args:
        job_id: The job ID to check

    Returns:
        Job status information
    """
    scraper_service = await get_scraper_service()
    job = await scraper_service.get_job(job_id)

    if not job:
        raise ValueError(f"Job not found: {job_id}")

    return {
        "id": job.id,
        "status": job.status.value,
        "progress": job.progress,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@mcp.tool()
async def get_job_results(job_id: str) -> list[dict[str, Any]]:
    """
    Get the results of a completed scraping job.

    Args:
        job_id: The job ID to get results for

    Returns:
        List of scraped reviews
    """
    scraper_service = await get_scraper_service()
    results = await scraper_service.get_job_results(job_id)

    if results is None:
        job = await scraper_service.get_job(job_id)
        if job and job.status != JobStatus.COMPLETED:
            raise ValueError(f"Job {job_id} is not completed yet. Status: {job.status.value}")
        raise ValueError(f"No results found for job: {job_id}")

    return results


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with scraping tools."""
    return mcp

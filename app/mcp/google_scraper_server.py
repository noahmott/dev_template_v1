"""Google Reviews MCP server implementation."""

import os
import time
import uuid
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from app.scrapers.google_reviews_scraper import GoogleReviewsScraper
from app.services.google_scraper_service import GoogleScraperService
from app.telemetry.logger import get_logger

# Initialize MCP server
mcp_server = FastMCP("google-reviews-scraper")

# Initialize services
scraper = GoogleReviewsScraper()
service = GoogleScraperService()
logger = get_logger("google_mcp_server")


@mcp_server.tool()
async def scrape_google_reviews(url: str, max_pages: int = 5) -> list[dict[str, Any]]:
    """Scrape reviews from Google Maps/Business pages.

    Args:
        url: Google Maps business URL
        max_pages: Maximum number of pages to scrape (default 5)

    Returns:
        List of review dictionaries
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "MCP tool scrape_google_reviews called",
        extra={
            "correlation_id": correlation_id,
            "tool_name": "scrape_google_reviews",
            "url": url,
            "max_pages": max_pages,
            "operation": "mcp_tool_start",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # Validate URL
        if not url or not url.startswith(
            ("https://www.google.com/maps/", "https://maps.google.com/")
        ):
            logger.warning(
                "Invalid Google Maps URL provided to MCP tool",
                extra={
                    "correlation_id": correlation_id,
                    "tool_name": "scrape_google_reviews",
                    "invalid_url": url,
                    "operation": "mcp_tool_validation_failed",
                },
            )
            raise ValueError(f"Invalid Google Maps URL: {url}")

        # Calculate max reviews from pages (approx 20 reviews per "page")
        max_reviews = max_pages * 20

        logger.info(
            "Starting reviews scraping via MCP tool",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "scrape_google_reviews",
                "max_reviews": max_reviews,
                "operation": "mcp_tool_scraping_start",
            },
        )

        # Scrape reviews
        reviews = await scraper.scrape_reviews(url, max_reviews=max_reviews)

        # Convert to dictionaries
        result = [review.model_dump() for review in reviews]

        end_time = time.time()
        logger.info(
            "MCP tool scrape_google_reviews completed successfully",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "scrape_google_reviews",
                "reviews_count": len(result),
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_success",
            },
        )

        return result

    except Exception as e:
        end_time = time.time()
        logger.error(
            "MCP tool scrape_google_reviews failed",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "scrape_google_reviews",
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "max_pages": max_pages,
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_error",
            },
        )
        raise


@mcp_server.tool()
async def search_google_business(business_name: str, location: str) -> dict[str, Any]:
    """Search for a business on Google Maps and scrape its reviews.

    Args:
        business_name: Name of the business to search
        location: Location (city, state) to search in

    Returns:
        Scraping job with results
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "MCP tool search_google_business called",
        extra={
            "correlation_id": correlation_id,
            "tool_name": "search_google_business",
            "business_name": business_name,
            "location": location,
            "operation": "mcp_tool_start",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # Validate inputs
        if not business_name or not location:
            logger.warning(
                "Invalid inputs provided to MCP tool",
                extra={
                    "correlation_id": correlation_id,
                    "tool_name": "search_google_business",
                    "business_name_empty": not business_name,
                    "location_empty": not location,
                    "operation": "mcp_tool_validation_failed",
                },
            )
            raise ValueError("Both business_name and location are required")

        logger.info(
            "Starting business search via MCP tool",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "search_google_business",
                "operation": "mcp_tool_search_start",
            },
        )

        # Create and execute scraping job
        job = await service.create_scraping_job(business_name, location)

        # Return job details
        result = job.model_dump()

        end_time = time.time()
        logger.info(
            "MCP tool search_google_business completed",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "search_google_business",
                "job_id": job.id,
                "job_status": job.status,
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_success",
            },
        )

        return result

    except Exception as e:
        end_time = time.time()
        logger.error(
            "MCP tool search_google_business failed",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "search_google_business",
                "error": str(e),
                "error_type": type(e).__name__,
                "business_name": business_name,
                "location": location,
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_error",
            },
        )
        raise


@mcp_server.tool()
async def extract_google_business_info(url: str) -> dict[str, Any]:
    """Extract business information from a Google Maps URL.

    Args:
        url: Google Maps business URL

    Returns:
        Business information dictionary
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "MCP tool extract_google_business_info called",
        extra={
            "correlation_id": correlation_id,
            "tool_name": "extract_google_business_info",
            "url": url,
            "operation": "mcp_tool_start",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # Validate URL
        if not url or not url.startswith(
            ("https://www.google.com/maps/", "https://maps.google.com/")
        ):
            logger.warning(
                "Invalid Google Maps URL provided to MCP tool",
                extra={
                    "correlation_id": correlation_id,
                    "tool_name": "extract_google_business_info",
                    "invalid_url": url,
                    "operation": "mcp_tool_validation_failed",
                },
            )
            raise ValueError(f"Invalid Google Maps URL: {url}")

        logger.info(
            "Starting business info extraction via MCP tool",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "extract_google_business_info",
                "operation": "mcp_tool_extraction_start",
            },
        )

        # Extract business info
        info = await scraper.extract_business_info(url)

        if not info:
            logger.warning(
                "Could not extract business information",
                extra={
                    "correlation_id": correlation_id,
                    "tool_name": "extract_google_business_info",
                    "url": url,
                    "operation": "mcp_tool_no_info_found",
                },
            )
            raise ValueError(f"Could not extract business information from {url}")

        result = info.model_dump()

        end_time = time.time()
        logger.info(
            "MCP tool extract_google_business_info completed",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "extract_google_business_info",
                "business_name": info.name,
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_success",
            },
        )

        return result

    except Exception as e:
        end_time = time.time()
        logger.error(
            "MCP tool extract_google_business_info failed",
            extra={
                "correlation_id": correlation_id,
                "tool_name": "extract_google_business_info",
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "duration_seconds": end_time - start_time,
                "operation": "mcp_tool_error",
            },
        )
        raise


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    logger.info(
        "Creating MCP server instance",
        extra={
            "server_name": "google-reviews-scraper",
            "operation": "mcp_server_create",
            "timestamp": datetime.now().isoformat(),
        },
    )
    return mcp_server


if __name__ == "__main__":
    # Run the MCP server
    import asyncio

    port = int(os.getenv("MCP_SERVER_PORT", "3000"))

    logger.info(
        "Starting MCP server",
        extra={
            "server_name": "google-reviews-scraper",
            "port": port,
            "operation": "mcp_server_start",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        asyncio.run(mcp_server.run(port=port))
    except Exception as e:
        logger.error(
            "MCP server failed to start",
            extra={
                "server_name": "google-reviews-scraper",
                "port": port,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": "mcp_server_start_error",
            },
        )
        raise

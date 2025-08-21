"""FastAPI endpoints for Google Reviews scraping."""

import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.cache.google_cache import GoogleReviewsCache
from app.scrapers.google_reviews_scraper import GoogleReviewsScraper
from app.security.google_scraper_security import GoogleScraperSecurity
from app.services.google_scraper_service import GoogleScraperService
from app.telemetry.logger import get_logger

router = APIRouter(prefix="/api/v1/google", tags=["google-reviews"])

# Initialize services
scraper = GoogleReviewsScraper()
service = GoogleScraperService()
cache = GoogleReviewsCache()
security = GoogleScraperSecurity()
logger = get_logger("google_reviews_api")


class GoogleSearchRequest(BaseModel):
    """Request model for Google business search."""

    business_name: str = Field(..., description="Name of the business to search")
    location: str = Field(..., description="Location (city, state) to search in")


class GoogleScrapeRequest(BaseModel):
    """Request model for Google Reviews scraping."""

    url: str = Field(..., description="Google Maps business URL")
    max_pages: int = Field(5, description="Maximum number of pages to scrape", ge=1, le=20)


@router.post("/search", response_model=dict[str, Any])
async def search_google_business(
    request: GoogleSearchRequest, http_request: Request
) -> dict[str, Any]:
    """Search for a business on Google Maps.

    Args:
        request: Search request with business name and location
        http_request: FastAPI request object

    Returns:
        Scraping job with Google Maps URL
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "Google business search request received",
        extra={
            "correlation_id": correlation_id,
            "business_name": request.business_name,
            "location": request.location,
            "client_ip": http_request.client.host if http_request.client else "unknown",
            "user_agent": http_request.headers.get("user-agent", "unknown"),
            "operation": "search_google_business",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # Sanitize inputs
        logger.info(
            "Sanitizing input parameters",
            extra={"correlation_id": correlation_id, "operation": "input_sanitization"},
        )

        business_name = security.sanitize_input(request.business_name, max_length=200)
        location = security.sanitize_input(request.location, max_length=200)

        if business_name != request.business_name or location != request.location:
            logger.warning(
                "Input sanitization modified parameters",
                extra={
                    "correlation_id": correlation_id,
                    "original_business_name": request.business_name,
                    "sanitized_business_name": business_name,
                    "original_location": request.location,
                    "sanitized_location": location,
                    "operation": "input_sanitization_modified",
                },
            )

        # Check cache first
        cache_key = cache.generate_key(url="search", business_name=business_name, location=location)

        logger.info(
            "Checking cache for search results",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "operation": "cache_check",
            },
        )

        cached_result = await cache.get(cache_key)
        if cached_result:
            end_time = time.time()
            logger.info(
                "Cache hit - returning cached search results",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": cache_key,
                    "duration_seconds": end_time - start_time,
                    "operation": "cache_hit",
                },
            )
            return cached_result

        # Create scraping job
        logger.info(
            "Cache miss - creating new scraping job",
            extra={"correlation_id": correlation_id, "operation": "cache_miss"},
        )

        job = await service.create_scraping_job(business_name=business_name, location=location)

        result = job.model_dump()

        # Cache successful results
        if job.status == "completed":
            logger.info(
                "Caching successful search results",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": cache_key,
                    "job_id": job.id,
                    "operation": "cache_set",
                },
            )
            await cache.set(cache_key, result)

        end_time = time.time()
        logger.info(
            "Google business search completed",
            extra={
                "correlation_id": correlation_id,
                "job_id": job.id,
                "job_status": job.status,
                "duration_seconds": end_time - start_time,
                "operation": "search_google_business_complete",
            },
        )

        return result

    except Exception as e:
        end_time = time.time()
        logger.error(
            "Google business search failed",
            extra={
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "business_name": request.business_name,
                "location": request.location,
                "duration_seconds": end_time - start_time,
                "operation": "search_google_business_error",
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/scrape", response_model=list[dict[str, Any]])
async def scrape_google_reviews(
    request: GoogleScrapeRequest, http_request: Request
) -> list[dict[str, Any]]:
    """Scrape reviews from a Google Maps business page.

    Args:
        request: Scrape request with URL and max pages
        http_request: FastAPI request object

    Returns:
        List of scraped reviews
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "Google reviews scrape request received",
        extra={
            "correlation_id": correlation_id,
            "url": request.url,
            "max_pages": request.max_pages,
            "client_ip": http_request.client.host if http_request.client else "unknown",
            "user_agent": http_request.headers.get("user-agent", "unknown"),
            "operation": "scrape_google_reviews",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # Validate URL with security check
        logger.info(
            "Validating Google Maps URL",
            extra={
                "correlation_id": correlation_id,
                "url": request.url,
                "operation": "url_validation",
            },
        )

        if not security.validate_google_url(request.url):
            logger.warning(
                "Invalid or unsafe Google Maps URL rejected",
                extra={
                    "correlation_id": correlation_id,
                    "url": request.url,
                    "operation": "url_validation_failed",
                },
            )
            raise HTTPException(status_code=400, detail="Invalid or unsafe Google Maps URL")

        # Check cache
        cache_key = cache.generate_key(url=request.url, max_pages=request.max_pages)

        logger.info(
            "Checking cache for scrape results",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "operation": "cache_check",
            },
        )

        cached_result = await cache.get(cache_key)
        if cached_result:
            end_time = time.time()
            logger.info(
                "Cache hit - returning cached reviews",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": cache_key,
                    "reviews_count": len(cached_result),
                    "duration_seconds": end_time - start_time,
                    "operation": "cache_hit",
                },
            )
            return cached_result

        # Scrape reviews
        max_reviews = request.max_pages * 20

        logger.info(
            "Cache miss - starting reviews scraping",
            extra={
                "correlation_id": correlation_id,
                "max_reviews": max_reviews,
                "max_pages": request.max_pages,
                "operation": "cache_miss",
            },
        )

        reviews = await scraper.scrape_reviews(request.url, max_reviews=max_reviews)

        result = [review.model_dump() for review in reviews]

        # Cache results
        logger.info(
            "Caching scrape results",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "reviews_count": len(result),
                "operation": "cache_set",
            },
        )
        await cache.set(cache_key, result)

        end_time = time.time()
        logger.info(
            "Google reviews scraping completed",
            extra={
                "correlation_id": correlation_id,
                "reviews_count": len(result),
                "duration_seconds": end_time - start_time,
                "reviews_per_second": len(result) / (end_time - start_time)
                if end_time > start_time
                else 0,
                "operation": "scrape_google_reviews_complete",
            },
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        end_time = time.time()
        logger.error(
            "Google reviews scraping failed",
            extra={
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "url": request.url,
                "max_pages": request.max_pages,
                "duration_seconds": end_time - start_time,
                "operation": "scrape_google_reviews_error",
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/business/{business_id:path}", response_model=dict[str, Any])
async def get_google_business_info(business_id: str, http_request: Request) -> dict[str, Any]:
    """Get business information from Google Maps.

    Args:
        business_id: Google business ID or URL
        http_request: FastAPI request object

    Returns:
        Business information
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "Google business info request received",
        extra={
            "correlation_id": correlation_id,
            "business_id": business_id,
            "client_ip": http_request.client.host if http_request.client else "unknown",
            "user_agent": http_request.headers.get("user-agent", "unknown"),
            "operation": "get_google_business_info",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        # If it's not a full URL, construct one
        if not business_id.startswith("http"):
            url = f"https://www.google.com/maps/place/{business_id}"
            logger.info(
                "Constructed Google Maps URL from business ID",
                extra={
                    "correlation_id": correlation_id,
                    "business_id": business_id,
                    "constructed_url": url,
                    "operation": "url_construction",
                },
            )
        else:
            url = business_id
            logger.info(
                "Using provided URL for business info",
                extra={"correlation_id": correlation_id, "url": url, "operation": "url_direct"},
            )

        # Check cache
        cache_key = cache.generate_key(url=url, action="info")

        logger.info(
            "Checking cache for business info",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "operation": "cache_check",
            },
        )

        cached_result = await cache.get(cache_key)
        if cached_result:
            end_time = time.time()
            logger.info(
                "Cache hit - returning cached business info",
                extra={
                    "correlation_id": correlation_id,
                    "cache_key": cache_key,
                    "duration_seconds": end_time - start_time,
                    "operation": "cache_hit",
                },
            )
            return cached_result

        # Extract business info
        logger.info(
            "Cache miss - extracting business info",
            extra={"correlation_id": correlation_id, "url": url, "operation": "cache_miss"},
        )

        info = await scraper.extract_business_info(url)

        if not info:
            logger.warning(
                "Business information not found",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "operation": "business_info_not_found",
                },
            )
            raise HTTPException(status_code=404, detail="Business information not found")

        result = info.model_dump()

        # Cache results
        logger.info(
            "Caching business info results",
            extra={
                "correlation_id": correlation_id,
                "cache_key": cache_key,
                "business_name": info.name,
                "operation": "cache_set",
            },
        )
        await cache.set(cache_key, result)

        end_time = time.time()
        logger.info(
            "Business info extraction completed",
            extra={
                "correlation_id": correlation_id,
                "business_name": info.name,
                "duration_seconds": end_time - start_time,
                "operation": "get_google_business_info_complete",
            },
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        end_time = time.time()
        logger.error(
            "Business info extraction failed",
            extra={
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "business_id": business_id,
                "duration_seconds": end_time - start_time,
                "operation": "get_google_business_info_error",
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_job_status(job_id: str, http_request: Request) -> dict[str, Any]:
    """Get the status of a scraping job.

    Args:
        job_id: ID of the job
        http_request: FastAPI request object

    Returns:
        Job details including status
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "Job status request received",
        extra={
            "correlation_id": correlation_id,
            "job_id": job_id,
            "client_ip": http_request.client.host if http_request.client else "unknown",
            "operation": "get_job_status_request",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        job = await service.get_job(job_id)
        result = job.model_dump()

        end_time = time.time()
        logger.info(
            "Job status retrieved successfully",
            extra={
                "correlation_id": correlation_id,
                "job_id": job_id,
                "job_status": job.status,
                "duration_seconds": end_time - start_time,
                "operation": "get_job_status_success",
            },
        )

        return result
    except ValueError as e:
        end_time = time.time()
        logger.warning(
            "Job not found for status request",
            extra={
                "correlation_id": correlation_id,
                "job_id": job_id,
                "error": str(e),
                "duration_seconds": end_time - start_time,
                "operation": "get_job_status_not_found",
            },
        )
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        end_time = time.time()
        logger.error(
            "Job status request failed",
            extra={
                "correlation_id": correlation_id,
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_seconds": end_time - start_time,
                "operation": "get_job_status_error",
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, http_request: Request) -> dict[str, bool]:
    """Cancel a scraping job.

    Args:
        job_id: ID of the job to cancel
        http_request: FastAPI request object

    Returns:
        Success status
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "Job cancellation request received",
        extra={
            "correlation_id": correlation_id,
            "job_id": job_id,
            "client_ip": http_request.client.host if http_request.client else "unknown",
            "operation": "cancel_job_request",
            "timestamp": datetime.now().isoformat(),
        },
    )

    try:
        cancelled = await service.cancel_job(job_id)

        if not cancelled:
            end_time = time.time()
            logger.warning(
                "Job could not be cancelled",
                extra={
                    "correlation_id": correlation_id,
                    "job_id": job_id,
                    "duration_seconds": end_time - start_time,
                    "operation": "cancel_job_failed",
                },
            )
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")

        end_time = time.time()
        logger.info(
            "Job cancelled successfully",
            extra={
                "correlation_id": correlation_id,
                "job_id": job_id,
                "duration_seconds": end_time - start_time,
                "operation": "cancel_job_success",
            },
        )

        return {"cancelled": True}
    except HTTPException:
        raise
    except Exception as e:
        end_time = time.time()
        logger.error(
            "Job cancellation failed",
            extra={
                "correlation_id": correlation_id,
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_seconds": end_time - start_time,
                "operation": "cancel_job_error",
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

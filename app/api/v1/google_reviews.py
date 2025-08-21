"""FastAPI endpoints for Google Reviews scraping."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.cache.google_cache import GoogleReviewsCache
from app.scrapers.google_reviews_scraper import GoogleReviewsScraper
from app.security.google_scraper_security import GoogleScraperSecurity
from app.services.google_scraper_service import GoogleScraperService

router = APIRouter(prefix="/api/v1/google", tags=["google-reviews"])

# Initialize services
scraper = GoogleReviewsScraper()
service = GoogleScraperService()
cache = GoogleReviewsCache()
security = GoogleScraperSecurity()


class GoogleSearchRequest(BaseModel):
    """Request model for Google business search."""

    business_name: str = Field(..., description="Name of the business to search")
    location: str = Field(..., description="Location (city, state) to search in")


class GoogleScrapeRequest(BaseModel):
    """Request model for Google Reviews scraping."""

    url: str = Field(..., description="Google Maps business URL")
    max_pages: int = Field(5, description="Maximum number of pages to scrape", ge=1, le=20)


@router.post("/search", response_model=dict[str, Any])
async def search_google_business(request: GoogleSearchRequest) -> dict[str, Any]:
    """Search for a business on Google Maps.

    Args:
        request: Search request with business name and location

    Returns:
        Scraping job with Google Maps URL
    """
    try:
        # Sanitize inputs
        business_name = security.sanitize_input(request.business_name, max_length=200)
        location = security.sanitize_input(request.location, max_length=200)

        # Check cache first
        cache_key = cache.generate_key(url="search", business_name=business_name, location=location)
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        # Create scraping job
        job = await service.create_scraping_job(business_name=business_name, location=location)

        result = job.model_dump()

        # Cache successful results
        if job.status == "completed":
            await cache.set(cache_key, result)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/scrape", response_model=list[dict[str, Any]])
async def scrape_google_reviews(request: GoogleScrapeRequest) -> list[dict[str, Any]]:
    """Scrape reviews from a Google Maps business page.

    Args:
        request: Scrape request with URL and max pages

    Returns:
        List of scraped reviews
    """
    try:
        # Validate URL with security check
        if not security.validate_google_url(request.url):
            raise HTTPException(status_code=400, detail="Invalid or unsafe Google Maps URL")

        # Check cache
        cache_key = cache.generate_key(url=request.url, max_pages=request.max_pages)
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        # Scrape reviews
        max_reviews = request.max_pages * 20
        reviews = await scraper.scrape_reviews(request.url, max_reviews=max_reviews)

        result = [review.model_dump() for review in reviews]

        # Cache results
        await cache.set(cache_key, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/business/{business_id:path}", response_model=dict[str, Any])
async def get_google_business_info(business_id: str) -> dict[str, Any]:
    """Get business information from Google Maps.

    Args:
        business_id: Google business ID or URL

    Returns:
        Business information
    """
    try:
        # If it's not a full URL, construct one
        if not business_id.startswith("http"):
            url = f"https://www.google.com/maps/place/{business_id}"
        else:
            url = business_id

        # Check cache
        cache_key = cache.generate_key(url=url, action="info")
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        # Extract business info
        info = await scraper.extract_business_info(url)

        if not info:
            raise HTTPException(status_code=404, detail="Business information not found")

        result = info.model_dump()

        # Cache results
        await cache.set(cache_key, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get the status of a scraping job.

    Args:
        job_id: ID of the job

    Returns:
        Job details including status
    """
    try:
        job = await service.get_job(job_id)
        return job.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, bool]:
    """Cancel a scraping job.

    Args:
        job_id: ID of the job to cancel

    Returns:
        Success status
    """
    try:
        cancelled = await service.cancel_job(job_id)
        if not cancelled:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        return {"cancelled": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

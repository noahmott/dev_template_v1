"""API endpoints for scraping operations."""

import logging
import os
from datetime import datetime

try:
    import aioredis
except ImportError:
    aioredis = None  # type: ignore
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.scraping import BusinessInfo, JobStatus, Review, ScrapingJob
from app.security.scraper_security import ScraperSecurity
from app.services.scraper_service import ScraperService

router = APIRouter(prefix="/api/v1/scraping", tags=["scraping"])
logger = logging.getLogger(__name__)

# Initialize service on module load
_scraper_service: ScraperService | None = None


async def get_scraper_service() -> ScraperService:
    """Get or create scraper service instance."""
    global _scraper_service
    if not _scraper_service:
        # Initialize Redis client if configured
        redis_client = None
        redis_url = os.getenv("REDIS_URL")
        if redis_url and aioredis:
            try:
                redis_client = await aioredis.from_url(redis_url)  # type: ignore
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")

        _scraper_service = ScraperService(redis_client=redis_client)

    return _scraper_service


class CreateJobRequest(BaseModel):
    """Request model for creating a scraping job."""

    url: str | None = Field(None, description="Direct URL to scrape")
    business_name: str | None = Field(None, description="Business name for search")
    location: str | None = Field(None, description="Location for search")
    platform: str | None = Field(
        None, description="Platform to search on (yelp, google, tripadvisor)"
    )
    max_pages: int = Field(5, description="Maximum pages to scrape", ge=1, le=20)


class JobResponse(BaseModel):
    """Response model for job creation."""

    job_id: str
    status: JobStatus
    message: str


@router.post("/jobs", response_model=JobResponse)
async def create_scraping_job(
    request: CreateJobRequest, background_tasks: BackgroundTasks
) -> JobResponse:
    """Create a new scraping job.

    Args:
        request: Job creation request
        background_tasks: FastAPI background tasks

    Returns:
        Job response with ID and status
    """
    scraper_service = await get_scraper_service()

    # Security validation
    if request.url:
        ScraperSecurity.validate_url(request.url)
    if request.platform:
        ScraperSecurity.validate_platform(request.platform)
    if request.business_name:
        request.business_name = ScraperSecurity.sanitize_input(request.business_name)
    if request.location:
        request.location = ScraperSecurity.sanitize_input(request.location)

    # Validate request
    if not request.url and not (request.business_name and request.location and request.platform):
        raise HTTPException(
            status_code=400,
            detail="Either provide a URL or business_name, location, and platform",
        )

    # Create job
    job = await scraper_service.create_scraping_job(
        url=request.url,
        business_name=request.business_name,
        location=request.location,
        platform=request.platform,
        max_pages=request.max_pages,
    )

    # Start scraping in background
    async def run_scraping() -> None:
        try:
            if request.url:
                # Direct URL scraping
                reviews = await scraper_service.scrape_reviews(request.url, request.max_pages)
                job.results = reviews
                job.status = JobStatus.COMPLETED
            else:
                # Search and scrape
                result_job = await scraper_service.search_and_scrape(
                    request.business_name or "",
                    request.location or "",
                    request.platform or "",
                )
                job.results = result_job.results
                job.status = result_job.status

            job.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Error in scraping job {job.id}: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()

    background_tasks.add_task(run_scraping)

    return JobResponse(
        job_id=job.id,
        status=job.status,
        message="Scraping job created successfully",
    )


@router.get("/jobs/{job_id}", response_model=ScrapingJob)
async def get_job_status(job_id: str) -> ScrapingJob:
    """Get status of a scraping job.

    Args:
        job_id: Job ID

    Returns:
        Scraping job details

    Raises:
        HTTPException: If job not found
    """
    scraper_service = await get_scraper_service()

    job = await scraper_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    return job


@router.get("/jobs/{job_id}/results", response_model=list[Review])
async def get_job_results(job_id: str) -> list[Review]:
    """Get results of a completed scraping job.

    Args:
        job_id: Job ID

    Returns:
        List of scraped reviews

    Raises:
        HTTPException: If job not found or not completed
    """
    scraper_service = await get_scraper_service()

    job = await scraper_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not completed yet. Status: {job.status}",
        )

    return job.results or []


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a scraping job.

    Args:
        job_id: Job ID to cancel

    Returns:
        Cancellation status

    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    scraper_service = await get_scraper_service()

    success = await scraper_service.cancel_job(job_id)
    if not success:
        job = await scraper_service.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} cannot be cancelled. Current status: {job.status}",
            )

    return {"message": f"Job {job_id} cancelled successfully"}


@router.post("/scrape", response_model=list[Review])
async def scrape_url_direct(
    url: str = Query(..., description="URL to scrape"),
    max_pages: int = Query(5, description="Maximum pages to scrape", ge=1, le=20),
) -> list[Review]:
    """Directly scrape a URL without creating a job.

    Args:
        url: URL to scrape
        max_pages: Maximum pages to scrape

    Returns:
        List of scraped reviews
    """
    scraper_service = await get_scraper_service()

    try:
        reviews = await scraper_service.scrape_reviews(url, max_pages)
        return reviews
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error scraping URL {url}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape URL: {str(e)}",
        ) from e


@router.post("/extract", response_model=BusinessInfo)
async def extract_business_info(
    url: str = Query(..., description="Business page URL"),
) -> BusinessInfo:
    """Extract business information from a URL.

    Args:
        url: Business page URL

    Returns:
        Business information

    Raises:
        HTTPException: If extraction fails
    """
    scraper_service = await get_scraper_service()

    try:
        business_info = await scraper_service.extract_business_info(url)
        if not business_info:
            raise HTTPException(
                status_code=404,
                detail="Could not extract business information from the provided URL",
            )
        return business_info
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error extracting business info from {url}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract business information: {str(e)}",
        ) from e


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Check health of scraping service.

    Returns:
        Health status
    """
    # Implementation will be added in IMPLEMENTER phase
    return {"status": "healthy", "service": "scraping"}

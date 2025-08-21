"""Service layer for Google Reviews scraping."""

import time
import uuid
from datetime import datetime

from app.models.scraping import JobStatus, ScrapingJob
from app.scrapers.google_reviews_scraper import GoogleReviewsScraper
from app.telemetry.logger import get_logger


class GoogleScraperService:
    """Service for managing Google Reviews scraping operations."""

    def __init__(self):
        """Initialize Google scraper service."""
        self.scraper = GoogleReviewsScraper()
        self.jobs: dict[str, ScrapingJob] = {}
        self.logger = get_logger("google_scraper_service")

    async def create_scraping_job(self, business_name: str, location: str) -> ScrapingJob:
        """Create a new scraping job for Google Reviews.

        Args:
            business_name: Name of the business
            location: Location to search in

        Returns:
            ScrapingJob object
        """
        start_time = time.time()

        # Create job
        job_id = str(uuid.uuid4())
        job = ScrapingJob(id=job_id, status=JobStatus.PENDING, created_at=datetime.now())

        self.logger.info(
            "Creating new scraping job",
            extra={
                "job_id": job_id,
                "business_name": business_name,
                "location": location,
                "operation": "create_scraping_job",
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Store job
        self.jobs[job_id] = job

        try:
            # Update status
            job.status = JobStatus.RUNNING

            self.logger.info(
                "Job status updated to RUNNING",
                extra={
                    "job_id": job_id,
                    "status": job.status.value,
                    "operation": "job_status_update",
                },
            )

            # Search for business
            self.logger.info(
                "Starting business search",
                extra={
                    "job_id": job_id,
                    "business_name": business_name,
                    "location": location,
                    "operation": "business_search_start",
                },
            )

            business_url = await self.scraper.search_business(business_name, location)

            if not business_url:
                job.status = JobStatus.FAILED
                job.error = f"Could not find business: {business_name} in {location}"
                job.completed_at = datetime.now()

                self.logger.warning(
                    "Business search failed - no results found",
                    extra={
                        "job_id": job_id,
                        "business_name": business_name,
                        "location": location,
                        "error": job.error,
                        "operation": "business_search_failed",
                    },
                )
                return job

            job.url = business_url

            self.logger.info(
                "Business found, starting reviews scraping",
                extra={
                    "job_id": job_id,
                    "business_url": business_url,
                    "operation": "reviews_scraping_start",
                },
            )

            # Scrape reviews
            reviews = await self.scraper.scrape_reviews(business_url, max_reviews=100)

            job.results = reviews
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()

            end_time = time.time()
            self.logger.info(
                "Scraping job completed successfully",
                extra={
                    "job_id": job_id,
                    "reviews_count": len(reviews),
                    "duration_seconds": end_time - start_time,
                    "business_url": business_url,
                    "operation": "create_scraping_job_success",
                },
            )

        except Exception as e:
            end_time = time.time()
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()

            self.logger.error(
                "Scraping job failed with exception",
                extra={
                    "job_id": job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "business_name": business_name,
                    "location": location,
                    "duration_seconds": end_time - start_time,
                    "operation": "create_scraping_job_error",
                },
            )

        return job

    async def execute_job(self, job_id: str) -> ScrapingJob:
        """Execute a scraping job.

        Args:
            job_id: ID of the job to execute

        Returns:
            Updated ScrapingJob object
        """
        start_time = time.time()

        self.logger.info(
            "Starting job execution",
            extra={
                "job_id": job_id,
                "operation": "execute_job_start",
                "timestamp": datetime.now().isoformat(),
            },
        )

        job = self.jobs.get(job_id)
        if not job:
            self.logger.error(
                "Job not found for execution",
                extra={"job_id": job_id, "operation": "execute_job_not_found"},
            )
            raise ValueError(f"Job {job_id} not found")

        if job.status != JobStatus.PENDING:
            self.logger.warning(
                "Job execution skipped - not in PENDING status",
                extra={
                    "job_id": job_id,
                    "current_status": job.status.value,
                    "operation": "execute_job_skip",
                },
            )
            return job

        try:
            job.status = JobStatus.RUNNING

            self.logger.info(
                "Job status updated to RUNNING for execution",
                extra={
                    "job_id": job_id,
                    "status": job.status.value,
                    "operation": "execute_job_running",
                },
            )

            if job.url:
                self.logger.info(
                    "Starting reviews scraping for existing URL",
                    extra={"job_id": job_id, "url": job.url, "operation": "execute_job_scraping"},
                )

                # Scrape the URL
                reviews = await self.scraper.scrape_reviews(job.url, max_reviews=100)
                job.results = reviews
                job.status = JobStatus.COMPLETED

                end_time = time.time()
                self.logger.info(
                    "Job execution completed successfully",
                    extra={
                        "job_id": job_id,
                        "reviews_count": len(reviews),
                        "duration_seconds": end_time - start_time,
                        "operation": "execute_job_success",
                    },
                )
            else:
                job.status = JobStatus.FAILED
                job.error = "No URL provided for job"

                self.logger.error(
                    "Job execution failed - no URL provided",
                    extra={"job_id": job_id, "error": job.error, "operation": "execute_job_no_url"},
                )

            job.completed_at = datetime.now()

        except Exception as e:
            end_time = time.time()
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()

            self.logger.error(
                "Job execution failed with exception",
                extra={
                    "job_id": job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_seconds": end_time - start_time,
                    "operation": "execute_job_error",
                },
            )

        return job

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get the status of a scraping job.

        Args:
            job_id: ID of the job

        Returns:
            JobStatus enum value
        """
        self.logger.info(
            "Retrieving job status", extra={"job_id": job_id, "operation": "get_job_status"}
        )

        job = self.jobs.get(job_id)
        if not job:
            self.logger.error(
                "Job not found for status check",
                extra={"job_id": job_id, "operation": "get_job_status_not_found"},
            )
            raise ValueError(f"Job {job_id} not found")

        self.logger.info(
            "Job status retrieved",
            extra={
                "job_id": job_id,
                "status": job.status.value,
                "operation": "get_job_status_success",
            },
        )

        return job.status

    async def get_job(self, job_id: str) -> ScrapingJob:
        """Get a scraping job by ID.

        Args:
            job_id: ID of the job

        Returns:
            ScrapingJob object
        """
        self.logger.info("Retrieving job details", extra={"job_id": job_id, "operation": "get_job"})

        job = self.jobs.get(job_id)
        if not job:
            self.logger.error(
                "Job not found for retrieval",
                extra={"job_id": job_id, "operation": "get_job_not_found"},
            )
            raise ValueError(f"Job {job_id} not found")

        self.logger.info(
            "Job details retrieved",
            extra={
                "job_id": job_id,
                "status": job.status.value,
                "has_results": job.results is not None,
                "results_count": len(job.results) if job.results else 0,
                "operation": "get_job_success",
            },
        )

        return job

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scraping job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            True if cancelled, False otherwise
        """
        self.logger.info(
            "Attempting to cancel job", extra={"job_id": job_id, "operation": "cancel_job_attempt"}
        )

        job = self.jobs.get(job_id)
        if not job:
            self.logger.warning(
                "Cannot cancel job - not found",
                extra={"job_id": job_id, "operation": "cancel_job_not_found"},
            )
            return False

        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            old_status = job.status
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()

            self.logger.info(
                "Job cancelled successfully",
                extra={
                    "job_id": job_id,
                    "previous_status": old_status.value,
                    "new_status": job.status.value,
                    "operation": "cancel_job_success",
                },
            )
            return True

        self.logger.warning(
            "Cannot cancel job - not in cancellable status",
            extra={
                "job_id": job_id,
                "current_status": job.status.value,
                "operation": "cancel_job_invalid_status",
            },
        )
        return False

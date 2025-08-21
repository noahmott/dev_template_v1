"""Service layer for Google Reviews scraping."""

import uuid
from datetime import datetime

from app.models.scraping import JobStatus, ScrapingJob
from app.scrapers.google_reviews_scraper import GoogleReviewsScraper


class GoogleScraperService:
    """Service for managing Google Reviews scraping operations."""

    def __init__(self):
        """Initialize Google scraper service."""
        self.scraper = GoogleReviewsScraper()
        self.jobs: dict[str, ScrapingJob] = {}

    async def create_scraping_job(self, business_name: str, location: str) -> ScrapingJob:
        """Create a new scraping job for Google Reviews.

        Args:
            business_name: Name of the business
            location: Location to search in

        Returns:
            ScrapingJob object
        """
        # Create job
        job_id = str(uuid.uuid4())
        job = ScrapingJob(id=job_id, status=JobStatus.PENDING, created_at=datetime.now())

        # Store job
        self.jobs[job_id] = job

        try:
            # Update status
            job.status = JobStatus.RUNNING

            # Search for business
            business_url = await self.scraper.search_business(business_name, location)

            if not business_url:
                job.status = JobStatus.FAILED
                job.error = f"Could not find business: {business_name} in {location}"
                job.completed_at = datetime.now()
                return job

            job.url = business_url

            # Scrape reviews
            reviews = await self.scraper.scrape_reviews(business_url, max_reviews=100)

            job.results = reviews
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()

        return job

    async def execute_job(self, job_id: str) -> ScrapingJob:
        """Execute a scraping job.

        Args:
            job_id: ID of the job to execute

        Returns:
            Updated ScrapingJob object
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != JobStatus.PENDING:
            return job

        try:
            job.status = JobStatus.RUNNING

            if job.url:
                # Scrape the URL
                reviews = await self.scraper.scrape_reviews(job.url, max_reviews=100)
                job.results = reviews
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.FAILED
                job.error = "No URL provided for job"

            job.completed_at = datetime.now()

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()

        return job

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get the status of a scraping job.

        Args:
            job_id: ID of the job

        Returns:
            JobStatus enum value
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        return job.status

    async def get_job(self, job_id: str) -> ScrapingJob:
        """Get a scraping job by ID.

        Args:
            job_id: ID of the job

        Returns:
            ScrapingJob object
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        return job

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scraping job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            True if cancelled, False otherwise
        """
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            return True

        return False

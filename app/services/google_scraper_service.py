"""Service layer for Google Reviews scraping."""

from app.models.scraping import JobStatus, ScrapingJob


class GoogleScraperService:
    """Service for managing Google Reviews scraping operations."""

    def __init__(self):
        """Initialize Google scraper service."""
        pass

    async def create_scraping_job(self, business_name: str, location: str) -> ScrapingJob:
        """Create a new scraping job for Google Reviews.

        Args:
            business_name: Name of the business
            location: Location to search in

        Returns:
            ScrapingJob object
        """
        pass

    async def execute_job(self, job_id: str) -> ScrapingJob:
        """Execute a scraping job.

        Args:
            job_id: ID of the job to execute

        Returns:
            Updated ScrapingJob object
        """
        pass

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get the status of a scraping job.

        Args:
            job_id: ID of the job

        Returns:
            JobStatus enum value
        """
        pass

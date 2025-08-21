"""Scraping service for managing scraping operations."""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import redis.asyncio as redis

from app.models.scraping import BusinessInfo, JobStatus, Review, ScrapingJob
from app.scrapers.puppeteer_client import PuppeteerClient


class ScraperService:
    """Service for managing web scraping operations."""

    def __init__(self, redis_client: redis.Redis | None = None):
        """Initialize scraper service.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.puppeteer_client = PuppeteerClient()
        self.jobs: dict[str, ScrapingJob] = {}
        self.rate_limits: dict[str, list[float]] = {}
        self.max_requests_per_minute = 10
        self.cache_ttl = 86400  # 24 hours

    async def create_scraping_job(
        self,
        url: str | None = None,
        business_name: str | None = None,
        location: str | None = None,
        platform: str | None = None,
        max_pages: int = 5,
    ) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            url: Direct URL to scrape
            business_name: Business name for search
            location: Location for search
            platform: Platform to search on
            max_pages: Maximum pages to scrape

        Returns:
            Created scraping job
        """
        job_id = str(uuid.uuid4())

        job = ScrapingJob(
            id=job_id,
            status=JobStatus.PENDING,
            url=url,
            business_name=business_name,
            location=location,
            platform=platform,
            max_pages=max_pages,
            created_at=datetime.now(),
            results=[],
        )

        self.jobs[job_id] = job

        # Store in Redis if available
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"job:{job_id}",
                    json.dumps(job.model_dump(mode="json")),
                    ex=86400,  # 24 hours
                )
            except Exception as e:
                self.logger.error(f"Error storing job in Redis: {e}")

        return job

    async def get_job_status(self, job_id: str) -> ScrapingJob | None:
        """Get status of a scraping job.

        Args:
            job_id: Job ID

        Returns:
            Scraping job or None if not found
        """
        # Check in-memory first
        if job_id in self.jobs:
            return self.jobs[job_id]

        # Check Redis if available
        if self.redis_client:
            try:
                job_data = await self.redis_client.get(f"job:{job_id}")
                if job_data:
                    if isinstance(job_data, bytes):
                        job_data = job_data.decode()
                    job_dict = json.loads(job_data)
                    job = ScrapingJob(**job_dict)
                    # Cache in memory
                    self.jobs[job_id] = job
                    return job
            except Exception as e:
                self.logger.error(f"Error retrieving job from Redis: {e}")

        return None

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scraping job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        job = await self.get_job_status(job_id)
        if not job:
            return False

        # Can only cancel pending or running jobs
        if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False

        # Update job status
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now()

        # Update in memory
        self.jobs[job_id] = job

        # Update in Redis if available
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"job:{job_id}",
                    json.dumps(job.model_dump(mode="json")),
                    ex=86400,  # 24 hours
                )
            except Exception as e:
                self.logger.error(f"Error updating cancelled job in Redis: {e}")

        return True

    async def scrape_reviews(self, url: str, max_pages: int = 5) -> list[Review]:
        """Scrape reviews from a URL.

        Args:
            url: URL to scrape
            max_pages: Maximum pages to scrape

        Returns:
            List of scraped reviews
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        domain = parsed.netloc

        # Check cache first
        cache_key = self._generate_cache_key(url=url, max_pages=max_pages)
        cached_result = await self._get_cached_result(cache_key)
        if cached_result:
            return [Review(**review) for review in cached_result.get("reviews", [])]

        # Check rate limit
        if not await self._check_rate_limit(domain):
            raise Exception(f"Rate limit exceeded for {domain}")

        # Check robots.txt
        if not await self._check_robots_txt(url):
            raise Exception(f"Scraping not allowed by robots.txt for {url}")

        # Update rate limit
        await self._update_rate_limit(domain)

        # Determine platform and scrape
        platform = self.puppeteer_client._get_platform_from_url(url)
        reviews = []

        try:
            if platform == "yelp":
                # Yelp is not supported
                raise Exception("Yelp scraping is not supported")
            elif platform == "google":
                reviews = await self.puppeteer_client.scrape_google_reviews(url, max_pages * 20)
            elif platform == "tripadvisor":
                reviews = await self.puppeteer_client.scrape_tripadvisor_reviews(url, max_pages)
            else:
                # Generic scraping fallback
                content = await self.puppeteer_client.scrape_url(url)
                if content:
                    # Parse generic reviews (simplified)
                    reviews = []

            # Deduplicate reviews
            reviews = self._deduplicate_reviews(reviews)

            # Cache results
            await self._set_cached_result(cache_key, {"reviews": [r.model_dump() for r in reviews]})

            return reviews

        except Exception as e:
            self.logger.error(f"Error scraping reviews from {url}: {e}")
            raise

    async def search_and_scrape(
        self, business_name: str, location: str, platform: str
    ) -> ScrapingJob:
        """Search for a business and scrape its reviews.

        Args:
            business_name: Business name
            location: Location
            platform: Platform to search on

        Returns:
            Scraping job with results
        """
        # Create job
        job_id = str(uuid.uuid4())
        job = ScrapingJob(id=job_id, status=JobStatus.PENDING, created_at=datetime.now())

        try:
            # Update status to running
            job.status = JobStatus.RUNNING

            # Search for business URL
            business_url = await self.puppeteer_client.search_business(
                business_name, location, platform
            )

            if not business_url:
                job.status = JobStatus.FAILED
                job.error = f"Could not find business: {business_name} in {location}"
                job.completed_at = datetime.now()
                return job

            job.url = business_url

            # Scrape reviews
            reviews = await self.scrape_reviews(business_url, 5)

            job.results = reviews
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            self.logger.error(f"Error in search_and_scrape: {e}")

        # Update job in storage
        self.jobs[job.id] = job
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"job:{job.id}",
                    json.dumps(job.model_dump(mode="json")),
                    ex=86400,
                )
            except Exception as e:
                self.logger.error(f"Error updating job in Redis: {e}")

        return job

    async def extract_business_info(self, url: str) -> BusinessInfo | None:
        """Extract business information from a URL.

        Args:
            url: Business page URL

        Returns:
            Business information or None
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        domain = parsed.netloc

        # Check cache first
        cache_key = self._generate_cache_key(url=url, action="business_info")
        cached_result = await self._get_cached_result(cache_key)
        if cached_result and "business_info" in cached_result:
            return BusinessInfo(**cached_result["business_info"])

        # Check rate limit
        if not await self._check_rate_limit(domain):
            raise Exception(f"Rate limit exceeded for {domain}")

        # Check robots.txt
        if not await self._check_robots_txt(url):
            raise Exception(f"Scraping not allowed by robots.txt for {url}")

        # Update rate limit
        await self._update_rate_limit(domain)

        try:
            # Extract business info using Puppeteer client
            business_info = await self.puppeteer_client.extract_business_info(url)

            if business_info:
                # Cache result
                await self._set_cached_result(
                    cache_key, {"business_info": business_info.model_dump()}
                )

            return business_info

        except Exception as e:
            self.logger.error(f"Error extracting business info from {url}: {e}")
            return None

    async def _check_rate_limit(self, domain: str) -> bool:
        """Check if rate limit allows request.

        Args:
            domain: Domain to check

        Returns:
            True if request allowed, False otherwise
        """
        # Check in-memory rate limits first
        current_time = time.time()

        if domain in self.rate_limits:
            # Remove old timestamps (older than 60 seconds)
            self.rate_limits[domain] = [
                timestamp for timestamp in self.rate_limits[domain] if current_time - timestamp < 60
            ]

            if len(self.rate_limits[domain]) >= self.max_requests_per_minute:
                return False

        # Also check Redis if available for distributed rate limiting
        if self.redis_client:
            try:
                rate_key = f"rate:{domain}"
                current_count = await self.redis_client.get(rate_key)
                if current_count and int(current_count) >= self.max_requests_per_minute:
                    return False
            except Exception as e:
                self.logger.error(f"Error checking rate limit in Redis: {e}")

        return True

    async def _update_rate_limit(self, domain: str):
        """Update rate limit tracking for domain.

        Args:
            domain: Domain to update
        """
        current_time = time.time()

        # Update in-memory tracking
        if domain not in self.rate_limits:
            self.rate_limits[domain] = []
        self.rate_limits[domain].append(current_time)

        # Update Redis tracking if available
        if self.redis_client:
            try:
                rate_key = f"rate:{domain}"
                # Use Redis pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                pipe.incr(rate_key)
                pipe.expire(rate_key, 60)  # 60 seconds
                await pipe.execute()
            except Exception as e:
                self.logger.error(f"Error updating rate limit in Redis: {e}")

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed, False otherwise
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Check cache first
            cache_key = f"robots:{parsed.netloc}"
            if self.redis_client:
                cached_result = await self.redis_client.get(cache_key)
                if cached_result:
                    if isinstance(cached_result, bytes):
                        cached_result = cached_result.decode()
                    return cached_result == "allowed"

            # Create robots parser
            rp = RobotFileParser()
            rp.set_url(robots_url)

            try:
                # Read robots.txt in a separate thread since it's blocking
                import asyncio

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, rp.read)

                # Check if our user agent can fetch the URL
                user_agent = "RestaurantScraperBot/1.0"
                can_fetch = rp.can_fetch(user_agent, url)

                # Cache result for 1 hour
                if self.redis_client:
                    result_str = "allowed" if can_fetch else "disallowed"
                    await self.redis_client.set(cache_key, result_str, ex=3600)

                return can_fetch

            except Exception:
                # If we can't read robots.txt, assume it's allowed
                # but cache as allowed for shorter time
                if self.redis_client:
                    await self.redis_client.set(cache_key, "allowed", ex=300)
                return True

        except Exception as e:
            self.logger.warning(f"Error checking robots.txt for {url}: {e}")
            # Default to allowed if there's an error
            return True

    async def _get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        """Get cached result from Redis.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None
        """
        if not self.redis_client:
            return None

        try:
            cached_data = await self.redis_client.get(f"cache:{cache_key}")
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode()
                return json.loads(cached_data)
        except Exception as e:
            self.logger.error(f"Error getting cached result for {cache_key}: {e}")

        return None

    async def _set_cached_result(self, cache_key: str, result: dict[str, Any]):
        """Set cached result in Redis.

        Args:
            cache_key: Cache key
            result: Result to cache
        """
        if not self.redis_client:
            return

        try:
            await self.redis_client.set(
                f"cache:{cache_key}", json.dumps(result, default=str), ex=self.cache_ttl
            )
        except Exception as e:
            self.logger.error(f"Error caching result for {cache_key}: {e}")

    def _generate_cache_key(self, **kwargs) -> str:
        """Generate cache key from parameters.

        Args:
            **kwargs: Parameters to hash

        Returns:
            Cache key
        """
        # Sort kwargs for consistent hashing
        sorted_params = sorted(kwargs.items())
        param_string = "&".join([f"{k}={v}" for k, v in sorted_params])

        # Create hash
        hash_obj = hashlib.sha256(param_string.encode())
        return hash_obj.hexdigest()[:16]  # Use first 16 characters

    def _deduplicate_reviews(self, reviews: list[Review]) -> list[Review]:
        """Remove duplicate reviews.

        Args:
            reviews: List of reviews

        Returns:
            Deduplicated list of reviews
        """
        if not reviews:
            return reviews

        seen_hashes = set()
        unique_reviews = []

        for review in reviews:
            # Generate hash based on text and author
            review_hash = self.puppeteer_client._generate_review_hash(review.text, review.author)

            if review_hash not in seen_hashes:
                seen_hashes.add(review_hash)
                unique_reviews.append(review)

        self.logger.info(f"Deduplicated reviews: {len(reviews)} -> {len(unique_reviews)}")

        return unique_reviews

    async def create_job(
        self,
        business_name: str | None = None,
        location: str | None = None,
        platform: str | None = None,
        webhook_url: str | None = None,
        url: str | None = None,
        max_pages: int = 5,
    ) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            business_name: Business name for search
            location: Location for search
            platform: Platform to search on
            webhook_url: Optional webhook URL
            url: Direct URL to scrape
            max_pages: Maximum pages to scrape

        Returns:
            Created scraping job
        """
        return await self.create_scraping_job(
            url=url,
            business_name=business_name,
            location=location,
            platform=platform,
            max_pages=max_pages,
        )

    async def get_job(self, job_id: str) -> ScrapingJob | None:
        """Get a scraping job by ID.

        Args:
            job_id: Job ID

        Returns:
            Scraping job or None if not found
        """
        return await self.get_job_status(job_id)

    async def execute_job(self, job: ScrapingJob) -> None:
        """Execute a scraping job asynchronously.

        Args:
            job: Job to execute
        """
        try:
            job.status = JobStatus.RUNNING

            if job.url:
                # Direct URL scraping
                reviews = await self.scrape_reviews(job.url, job.max_pages)
                job.results = reviews
            elif job.business_name and job.location and job.platform:
                # Search and scrape
                updated_job = await self.search_and_scrape(
                    job.business_name, job.location, job.platform
                )
                job.results = updated_job.results
                job.url = updated_job.url
                job.error = updated_job.error
            else:
                raise ValueError("Job must have either URL or business search parameters")

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            self.logger.error(f"Error executing job {job.id}: {e}")

        # Update job in storage
        self.jobs[job.id] = job
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"job:{job.id}",
                    json.dumps(job.model_dump(mode="json")),
                    ex=86400,
                )
            except Exception as e:
                self.logger.error(f"Error updating job in Redis: {e}")

    async def get_job_results(self, job_id: str) -> list[dict[str, Any]] | None:
        """Get results from a completed job.

        Args:
            job_id: Job ID

        Returns:
            List of review results or None if not found/completed
        """
        job = await self.get_job_status(job_id)
        if not job or job.status != JobStatus.COMPLETED:
            return None

        if job.results:
            return [review.model_dump() for review in job.results]
        return []

    async def cleanup(self):
        """Cleanup resources."""
        await self.puppeteer_client.cleanup()

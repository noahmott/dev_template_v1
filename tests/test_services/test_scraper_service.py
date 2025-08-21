"""Tests for scraper service layer."""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.scraping import JobStatus, ScrapingJob
from app.services.scraper_service import ScraperService


@pytest.fixture
async def scraper_service():
    """Create test scraper service."""
    service = ScraperService()
    yield service
    await service.cleanup()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("app.services.scraper_service.redis") as mock:
        client = MagicMock()
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock()
        client.delete = AsyncMock()
        client.expire = AsyncMock()
        mock.from_url.return_value = client
        yield client


@pytest.fixture
def mock_puppeteer():
    """Mock Puppeteer client."""
    with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock:
        client = mock.return_value
        client.initialize = AsyncMock()
        client.scrape_page = AsyncMock()
        client.close = AsyncMock()
        yield client


class TestJobManagement:
    """Test job creation and management."""

    @pytest.mark.asyncio
    async def test_create_job(self, scraper_service, mock_redis):
        """Test creating a new scraping job."""
        url = "https://yelp.com/biz/test"
        job = await scraper_service.create_job(url, max_pages=3)

        assert job.id
        assert job.status == JobStatus.PENDING
        assert job.url == url
        assert job.max_pages == 3

        # Check Redis storage
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_get_job(self, scraper_service, mock_redis):
        """Test retrieving a job."""
        job_id = str(uuid.uuid4())
        job_data = {
            "id": job_id,
            "status": "running",
            "url": "https://yelp.com/biz/test",
            "created_at": datetime.now().isoformat(),
        }

        mock_redis.get.return_value = job_data
        job = await scraper_service.get_job(job_id)

        assert job.id == job_id
        assert job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_job_status(self, scraper_service, mock_redis):
        """Test updating job status."""
        job_id = str(uuid.uuid4())
        await scraper_service.update_job_status(job_id, JobStatus.COMPLETED)

        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_job(self, scraper_service, mock_redis):
        """Test canceling a job."""
        job_id = str(uuid.uuid4())
        mock_redis.get.return_value = {"id": job_id, "status": "running"}

        result = await scraper_service.cancel_job(job_id)

        assert result is True
        mock_redis.set.assert_called()


class TestScrapingExecution:
    """Test scraping execution logic."""

    @pytest.mark.asyncio
    async def test_execute_scraping(self, scraper_service, mock_puppeteer):
        """Test executing a scraping job."""
        job = ScrapingJob(
            id=str(uuid.uuid4()),
            url="https://yelp.com/biz/test",
            max_pages=2,
            status=JobStatus.PENDING,
        )

        mock_puppeteer.scrape_page.return_value = [
            {"text": "Review 1", "rating": 5.0},
            {"text": "Review 2", "rating": 4.0},
        ]

        results = await scraper_service.execute_scraping(job)

        assert len(results) == 2
        assert results[0]["text"] == "Review 1"
        mock_puppeteer.initialize.assert_called_once()
        mock_puppeteer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry(self, scraper_service, mock_puppeteer):
        """Test scraping with retry logic."""
        job = ScrapingJob(
            id=str(uuid.uuid4()),
            url="https://yelp.com/biz/test",
            max_pages=1,
            status=JobStatus.PENDING,
        )

        # First attempt fails, second succeeds
        mock_puppeteer.scrape_page.side_effect = [
            Exception("Connection failed"),
            [{"text": "Success", "rating": 5.0}],
        ]

        results = await scraper_service.execute_scraping(job)

        assert len(results) == 1
        assert results[0]["text"] == "Success"
        assert mock_puppeteer.scrape_page.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_timeout(self, scraper_service, mock_puppeteer):
        """Test scraping timeout handling."""
        job = ScrapingJob(
            id=str(uuid.uuid4()),
            url="https://yelp.com/biz/test",
            max_pages=1,
            status=JobStatus.PENDING,
        )

        # Simulate timeout
        async def slow_scrape(*args):
            await asyncio.sleep(35)  # Longer than 30s timeout
            return []

        mock_puppeteer.scrape_page = slow_scrape

        with pytest.raises(asyncio.TimeoutError):
            await scraper_service.execute_scraping(job, timeout=1)


class TestCaching:
    """Test caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_results(self, scraper_service, mock_redis):
        """Test caching scraping results."""
        job_id = str(uuid.uuid4())
        results = [{"text": "Cached review", "rating": 4.5}]

        await scraper_service.cache_results(job_id, results)

        mock_redis.set.assert_called()
        mock_redis.expire.assert_called_with(f"results:{job_id}", 86400)  # 24 hours

    @pytest.mark.asyncio
    async def test_get_cached_results(self, scraper_service, mock_redis):
        """Test retrieving cached results."""
        job_id = str(uuid.uuid4())
        cached_data = [{"text": "Cached review", "rating": 4.5}]

        mock_redis.get.return_value = cached_data
        results = await scraper_service.get_cached_results(job_id)

        assert results == cached_data

    @pytest.mark.asyncio
    async def test_cache_expiration(self, scraper_service, mock_redis):
        """Test cache expiration."""
        job_id = str(uuid.uuid4())

        # No cached data
        mock_redis.get.return_value = None
        results = await scraper_service.get_cached_results(job_id)

        assert results is None


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, scraper_service, mock_redis):
        """Test rate limit checking."""
        domain = "yelp.com"

        # Under limit
        mock_redis.get.return_value = 5
        can_proceed = await scraper_service.check_rate_limit(domain)
        assert can_proceed is True

        # At limit
        mock_redis.get.return_value = 10
        can_proceed = await scraper_service.check_rate_limit(domain)
        assert can_proceed is False

    @pytest.mark.asyncio
    async def test_rate_limit_increment(self, scraper_service, mock_redis):
        """Test incrementing rate limit counter."""
        domain = "yelp.com"

        await scraper_service.increment_rate_limit(domain)

        mock_redis.set.assert_called()
        mock_redis.expire.assert_called_with(f"rate:{domain}", 60)  # 1 minute


class TestConcurrency:
    """Test concurrent scraping limits."""

    @pytest.mark.asyncio
    async def test_concurrent_browser_limit(self, scraper_service):
        """Test enforcing concurrent browser limit."""
        [
            ScrapingJob(
                id=str(uuid.uuid4()),
                url=f"https://yelp.com/biz/test{i}",
                max_pages=1,
                status=JobStatus.PENDING,
            )
            for i in range(5)
        ]

        # Should only run 3 concurrently
        active_count = await scraper_service.get_active_browser_count()
        assert active_count <= 3

    @pytest.mark.asyncio
    async def test_queue_management(self, scraper_service, mock_redis):
        """Test job queue management."""
        # Add jobs to queue
        for _i in range(10):
            job_id = str(uuid.uuid4())
            await scraper_service.add_to_queue(job_id)

        # Process queue
        processed = await scraper_service.process_queue(max_jobs=5)
        assert processed == 5


class TestWebhooks:
    """Test webhook functionality."""

    @pytest.mark.asyncio
    async def test_webhook_on_completion(self, scraper_service):
        """Test webhook called on job completion."""
        with patch("aiohttp.ClientSession") as mock_session:
            session = mock_session.return_value.__aenter__.return_value
            session.post = AsyncMock()

            job = ScrapingJob(
                id=str(uuid.uuid4()),
                url="https://yelp.com/biz/test",
                webhook_url="https://example.com/webhook",
                status=JobStatus.COMPLETED,
            )

            await scraper_service.send_webhook(job)

            session.post.assert_called_once_with(
                "https://example.com/webhook",
                json={"job_id": job.id, "status": "completed"},
            )

    @pytest.mark.asyncio
    async def test_webhook_retry(self, scraper_service):
        """Test webhook retry on failure."""
        with patch("aiohttp.ClientSession") as mock_session:
            session = mock_session.return_value.__aenter__.return_value
            session.post = AsyncMock(side_effect=[Exception("Network error"), None])

            job = ScrapingJob(
                id=str(uuid.uuid4()),
                url="https://yelp.com/biz/test",
                webhook_url="https://example.com/webhook",
                status=JobStatus.COMPLETED,
            )

            await scraper_service.send_webhook(job)

            assert session.post.call_count == 2  # Initial + retry


class TestDataValidation:
    """Test data validation and deduplication."""

    def test_validate_review_schema(self, scraper_service):
        """Test review data validation."""
        valid_review = {
            "text": "Great food!",
            "rating": 5.0,
            "date": "2024-01-01",
            "author": "John Doe",
            "platform": "yelp",
        }

        assert scraper_service.validate_review(valid_review) is True

        invalid_review = {"text": "Missing fields"}
        assert scraper_service.validate_review(invalid_review) is False

    def test_deduplicate_reviews(self, scraper_service):
        """Test review deduplication."""
        reviews = [
            {"text": "Great food!", "rating": 5.0},
            {"text": "Great food!", "rating": 5.0},  # Duplicate
            {"text": "Good service", "rating": 4.0},
        ]

        unique = scraper_service.deduplicate_reviews(reviews)
        assert len(unique) == 2

    def test_content_hash(self, scraper_service):
        """Test content hashing for deduplication."""
        review1 = {"text": "Great food!", "rating": 5.0}
        review2 = {"text": "Great food!", "rating": 5.0}
        review3 = {"text": "Different review", "rating": 5.0}

        hash1 = scraper_service.get_content_hash(review1)
        hash2 = scraper_service.get_content_hash(review2)
        hash3 = scraper_service.get_content_hash(review3)

        assert hash1 == hash2
        assert hash1 != hash3


class TestComplianceChecks:
    """Test compliance and ethics checks."""

    @pytest.mark.asyncio
    async def test_robots_txt_check(self, scraper_service):
        """Test robots.txt compliance."""
        with patch("app.services.scraper_service.check_robots_txt") as mock_check:
            mock_check.return_value = True
            can_scrape = await scraper_service.check_robots_compliance("https://yelp.com/biz/test")
            assert can_scrape is True

            mock_check.return_value = False
            can_scrape = await scraper_service.check_robots_compliance("https://blocked.com/page")
            assert can_scrape is False

    @pytest.mark.asyncio
    async def test_user_agent_bot_identification(self, scraper_service):
        """Test bot identification in User-Agent."""
        user_agent = scraper_service.get_user_agent()
        assert "bot" in user_agent.lower() or "scraper" in user_agent.lower()

    @pytest.mark.asyncio
    async def test_handle_429_response(self, scraper_service):
        """Test handling 429 Too Many Requests."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_client:
            client = mock_client.return_value
            client.get_response_status = AsyncMock(return_value=429)

            should_retry = await scraper_service.handle_http_error(429)
            assert should_retry is True

            # Should implement exponential backoff
            wait_time = scraper_service.get_backoff_time(attempt=3)
            assert wait_time >= 4  # 2^3 = 8 seconds minimum

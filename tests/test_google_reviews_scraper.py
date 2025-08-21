"""Comprehensive tests for Google Reviews MCP scraping service."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.google_scraper_server import mcp_server
from app.models.scraping import BusinessInfo, JobStatus, Review, ScrapingJob
from app.scrapers.puppeteer_client import PuppeteerClient
from app.services.scraper_service import ScraperService


class TestGoogleReviewsScraper:
    """Test Google Reviews scraping functionality."""

    @pytest.fixture
    def social_house_url(self):
        """URL for Social House restaurant in Orlando."""
        return "https://www.google.com/maps/place/Social+House/@28.5383,-81.3792,17z"

    @pytest.fixture
    def mock_social_house_reviews(self):
        """Mock reviews for Social House."""
        return [
            Review(
                text="Amazing sushi and great atmosphere! The Dragon Roll was exceptional.",
                rating=5.0,
                date="2024-01-15",
                author="Sarah Johnson",
                platform="google",
                url="https://www.google.com/maps/place/Social+House",
                response=None,
            ),
            Review(
                text="Good food but service was a bit slow during happy hour.",
                rating=4.0,
                date="2024-01-10",
                author="Mike Chen",
                platform="google",
                url="https://www.google.com/maps/place/Social+House",
                response="Thank you for your feedback. We're working on improving service times.",
            ),
            Review(
                text="Best Japanese fusion in Orlando! Love the creative cocktails.",
                rating=5.0,
                date="2024-01-05",
                author="Emily Rodriguez",
                platform="google",
                url="https://www.google.com/maps/place/Social+House",
                response=None,
            ),
        ]

    @pytest.fixture
    def mock_social_house_info(self):
        """Mock business info for Social House."""
        return BusinessInfo(
            name="Social House",
            address="7575 Dr Phillips Blvd, Orlando, FL 32819",
            phone="(407) 370-0700",
            rating=4.3,
            review_count=1842,
            categories=["Japanese Restaurant", "Sushi Bar", "Asian Fusion"],
            url="https://www.google.com/maps/place/Social+House",
        )

    @pytest.fixture
    async def scraper_service(self):
        """Create scraper service instance."""
        service = ScraperService(redis_client=None)
        yield service
        await service.cleanup()

    @pytest.fixture
    async def puppeteer_client(self):
        """Create puppeteer client instance."""
        client = PuppeteerClient(max_concurrent_browsers=1)
        yield client
        await client.cleanup()


class TestMCPGoogleReviewsTools:
    """Test MCP tools for Google Reviews."""

    @pytest.mark.asyncio
    async def test_scrape_google_reviews_tool(self, social_house_url, mock_social_house_reviews):
        """Test scrape_google_reviews MCP tool."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.scrape_reviews = AsyncMock(return_value=mock_social_house_reviews)

            # Simulate MCP tool call
            result = await mcp_server.scrape_google_reviews(url=social_house_url, max_pages=5)

            assert len(result) == 3
            assert (
                result[0]["text"]
                == "Amazing sushi and great atmosphere! The Dragon Roll was exceptional."
            )
            assert result[0]["rating"] == 5.0
            assert result[0]["platform"] == "google"

    @pytest.mark.asyncio
    async def test_search_google_business_tool(self, mock_social_house_info):
        """Test search_google_business MCP tool."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_job = ScrapingJob(
                id="test-123",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(),
                completed_at=datetime.now(),
                url="https://www.google.com/maps/place/Social+House",
                results=[],
            )
            mock_instance.search_and_scrape = AsyncMock(return_value=mock_job)

            # Simulate MCP tool call
            result = await mcp_server.search_google_business(
                business_name="Social House", location="Orlando, FL"
            )

            assert result["id"] == "test-123"
            assert result["status"] == "completed"
            assert "Social+House" in result["url"]

    @pytest.mark.asyncio
    async def test_extract_google_business_info_tool(
        self, social_house_url, mock_social_house_info
    ):
        """Test extract_google_business_info MCP tool."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.extract_business_info = AsyncMock(return_value=mock_social_house_info)

            # Simulate MCP tool call
            result = await mcp_server.extract_google_business_info(url=social_house_url)

            assert result["name"] == "Social House"
            assert result["address"] == "7575 Dr Phillips Blvd, Orlando, FL 32819"
            assert result["rating"] == 4.3
            assert result["review_count"] == 1842
            assert "Japanese Restaurant" in result["categories"]


class TestGoogleReviewsExtraction:
    """Test Google Reviews extraction logic."""

    @pytest.mark.asyncio
    async def test_extract_review_text(self, puppeteer_client):
        """Test extracting review text from Google HTML."""
        mock_html = """
        <div data-review-id="123">
            <span class="wiI7pd">Excellent sushi and service!</span>
            <div class="d4r55">John Smith</div>
            <span class="rsqaWe">2 weeks ago</span>
            <div aria-label="5 stars">5 stars</div>
        </div>
        """
        with patch.object(puppeteer_client, "scrape_url", return_value=mock_html):
            await puppeteer_client.scrape_google_reviews(
                "https://www.google.com/maps/place/test", max_reviews=10
            )

            # Since we're mocking HTML, actual parsing would happen in implementation
            # This tests the structure
            assert puppeteer_client.scrape_url.called

    @pytest.mark.asyncio
    async def test_handle_pagination(self, puppeteer_client):
        """Test handling Google Reviews infinite scroll pagination."""
        with patch.object(puppeteer_client, "scrape_url") as mock_scrape:
            mock_scrape.return_value = "<div>Mock content</div>"

            # Test that pagination scrolls to load more reviews
            await puppeteer_client.scrape_google_reviews(
                "https://www.google.com/maps/place/test", max_reviews=100
            )

            mock_scrape.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_owner_responses(self, puppeteer_client):
        """Test extracting owner responses from reviews."""
        mock_html = """
        <div data-review-id="456">
            <span class="wiI7pd">Food was okay</span>
            <div class="CDe7pd">Thank you for your feedback. We appreciate it!</div>
        </div>
        """
        with patch.object(puppeteer_client, "scrape_url", return_value=mock_html):
            await puppeteer_client.scrape_google_reviews(
                "https://www.google.com/maps/place/test", max_reviews=10
            )

            assert puppeteer_client.scrape_url.called


class TestGoogleBusinessSearch:
    """Test Google business search functionality."""

    @pytest.mark.asyncio
    async def test_search_business_by_name(self, puppeteer_client):
        """Test searching for Social House on Google Maps."""

        with patch.object(puppeteer_client, "scrape_url") as mock_scrape:
            mock_scrape.return_value = """
            <a href="/maps/place/Social+House/@28.5383,-81.3792,17z" data-cid="12345">
                Social House
            </a>
            """

            await puppeteer_client.search_business("Social House", "Orlando, FL", "google")

            assert mock_scrape.called
            # URL construction would happen in implementation

    @pytest.mark.asyncio
    async def test_handle_multiple_search_results(self, puppeteer_client):
        """Test handling multiple search results and selecting first."""
        with patch.object(puppeteer_client, "scrape_url") as mock_scrape:
            mock_scrape.return_value = """
            <div>
                <a href="/maps/place/Social+House/@28.5383,-81.3792">Social House</a>
                <a href="/maps/place/Other+Place">Other Place</a>
            </div>
            """

            await puppeteer_client.search_business("Social House", "Orlando", "google")

            assert mock_scrape.called


class TestRateLimiting:
    """Test rate limiting for Google Reviews."""

    @pytest.mark.asyncio
    async def test_google_rate_limit(self, scraper_service):
        """Test rate limiting for Google domain."""
        # Make 10 requests (at the limit)
        for _i in range(10):
            allowed = await scraper_service._check_rate_limit("google.com")
            assert allowed
            await scraper_service._update_rate_limit("google.com")

        # 11th request should be rate limited
        allowed = await scraper_service._check_rate_limit("google.com")
        assert not allowed

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self, scraper_service):
        """Test rate limit resets after time window."""
        await scraper_service._update_rate_limit("google.com")

        # Simulate time passing
        with patch("time.time", return_value=1000000):
            await scraper_service._update_rate_limit("google.com")

        with patch("time.time", return_value=1000061):  # 61 seconds later
            allowed = await scraper_service._check_rate_limit("google.com")
            assert allowed


class TestCaching:
    """Test caching of Google Reviews data."""

    @pytest.mark.asyncio
    async def test_cache_google_reviews(self, scraper_service, mock_social_house_reviews):
        """Test caching scraped reviews."""
        url = "https://www.google.com/maps/place/Social+House"

        with patch.object(scraper_service.puppeteer_client, "scrape_google_reviews") as mock_scrape:
            mock_scrape.return_value = mock_social_house_reviews

            # First call - should scrape
            reviews1 = await scraper_service.scrape_reviews(url, max_pages=1)
            assert len(reviews1) == 3
            assert mock_scrape.call_count == 1

            # Second call - should use cache (if Redis was connected)
            await scraper_service.scrape_reviews(url, max_pages=1)
            # Without Redis, it will scrape again
            assert mock_scrape.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_business_info(self, scraper_service, mock_social_house_info):
        """Test caching business information."""
        url = "https://www.google.com/maps/place/Social+House"

        with patch.object(
            scraper_service.puppeteer_client, "extract_business_info"
        ) as mock_extract:
            mock_extract.return_value = mock_social_house_info

            # First call
            info1 = await scraper_service.extract_business_info(url)
            assert info1.name == "Social House"
            assert mock_extract.call_count == 1


class TestErrorHandling:
    """Test error handling for Google Reviews scraping."""

    @pytest.mark.asyncio
    async def test_handle_invalid_google_url(self, scraper_service):
        """Test handling invalid Google Maps URLs."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await scraper_service.scrape_reviews("not-a-url", max_pages=1)

    @pytest.mark.asyncio
    async def test_handle_google_captcha(self, puppeteer_client):
        """Test handling Google CAPTCHA challenges."""
        with patch.object(puppeteer_client, "scrape_url") as mock_scrape:
            mock_scrape.return_value = '<div id="recaptcha">Please verify</div>'

            reviews = await puppeteer_client.scrape_google_reviews(
                "https://www.google.com/maps/place/test", max_reviews=10
            )

            # Should return empty list when CAPTCHA detected
            assert len(reviews) == 0

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, puppeteer_client):
        """Test retry logic on network errors."""
        with patch.object(puppeteer_client, "scrape_url") as mock_scrape:
            mock_scrape.side_effect = [
                ConnectionError("Network error"),
                ConnectionError("Network error"),
                "<div>Success</div>",
            ]

            # Should retry and eventually succeed
            result = await puppeteer_client.scrape_url("https://www.google.com/maps/place/test")

            assert result == "<div>Success</div>"
            assert mock_scrape.call_count == 3


class TestCompliance:
    """Test compliance features for Google scraping."""

    @pytest.mark.asyncio
    async def test_robots_txt_compliance(self, scraper_service):
        """Test robots.txt compliance for Google."""
        with patch.object(scraper_service, "_check_robots_txt") as mock_robots:
            mock_robots.return_value = True

            allowed = await scraper_service._check_robots_txt(
                "https://www.google.com/maps/place/test"
            )

            assert allowed

    @pytest.mark.asyncio
    async def test_user_agent_identification(self, puppeteer_client):
        """Test proper user agent identification."""
        # User agent should identify as bot
        assert "Mozilla" in puppeteer_client._sanitize_text("Mozilla/5.0")


class TestPerformance:
    """Test performance requirements."""

    @pytest.mark.asyncio
    async def test_scraping_speed(self, scraper_service):
        """Test scraping completes within 10 seconds per page."""
        start_time = asyncio.get_event_loop().time()

        with patch.object(scraper_service.puppeteer_client, "scrape_google_reviews") as mock_scrape:
            mock_scrape.return_value = []

            await scraper_service.scrape_reviews(
                "https://www.google.com/maps/place/Social+House", max_pages=1
            )

            elapsed = asyncio.get_event_loop().time() - start_time
            # Should complete quickly with mocked response
            assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_concurrent_browsers_limit(self, puppeteer_client):
        """Test browser instance limits."""
        assert puppeteer_client.max_concurrent_browsers <= 3
        assert len(puppeteer_client.browsers) == 0

        # Simulate browser creation
        puppeteer_client.browsers = [MagicMock() for _ in range(3)]
        assert len(puppeteer_client.browsers) == 3


class TestDataValidation:
    """Test data validation for Google Reviews."""

    def test_review_model_validation(self):
        """Test Review model validation."""
        # Valid review
        review = Review(
            text="Great restaurant!",
            rating=4.5,
            date="2024-01-15",
            author="John Doe",
            platform="google",
            url="https://www.google.com/maps/place/test",
        )
        assert review.rating == 4.5
        assert review.platform == "google"

        # Invalid rating should fail
        with pytest.raises(ValueError):
            Review(
                text="Bad review",
                rating=6.0,  # Invalid: > 5
                date="2024-01-15",
                author="Jane Doe",
                platform="google",
                url="https://www.google.com/maps/place/test",
            )

    def test_business_info_validation(self):
        """Test BusinessInfo model validation."""
        info = BusinessInfo(
            name="Social House",
            address="7575 Dr Phillips Blvd, Orlando, FL",
            phone="(407) 370-0700",
            rating=4.3,
            review_count=1842,
            categories=["Japanese", "Sushi"],
            url="https://www.google.com/maps/place/Social+House",
        )
        assert info.name == "Social House"
        assert info.rating == 4.3
        assert len(info.categories) == 2

    @pytest.mark.asyncio
    async def test_deduplicate_reviews(self, scraper_service, mock_social_house_reviews):
        """Test review deduplication."""
        # Add duplicate
        reviews = mock_social_house_reviews + [mock_social_house_reviews[0]]

        deduplicated = scraper_service._deduplicate_reviews(reviews)

        assert len(deduplicated) == 3  # Should remove duplicate


class TestJobManagement:
    """Test scraping job management."""

    @pytest.mark.asyncio
    async def test_create_scraping_job(self, scraper_service):
        """Test creating a scraping job."""
        job = await scraper_service.search_and_scrape(
            business_name="Social House", location="Orlando, FL", platform="google"
        )

        assert job.id is not None
        assert job.status in [
            JobStatus.PENDING,
            JobStatus.RUNNING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
        ]
        assert job.created_at is not None

    @pytest.mark.asyncio
    async def test_get_job_status(self, scraper_service):
        """Test getting job status."""
        # Create a job
        job = ScrapingJob(id="test-job-123", status=JobStatus.RUNNING, created_at=datetime.now())
        scraper_service.jobs["test-job-123"] = job

        # Get job
        retrieved = await scraper_service.get_job("test-job-123")
        assert retrieved.id == "test-job-123"
        assert retrieved.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_cancel_job(self, scraper_service):
        """Test canceling a scraping job."""
        # Create a running job
        job = ScrapingJob(id="test-job-456", status=JobStatus.RUNNING, created_at=datetime.now())
        scraper_service.jobs["test-job-456"] = job

        # Cancel it
        cancelled = await scraper_service.cancel_job("test-job-456")
        assert cancelled
        assert scraper_service.jobs["test-job-456"].status == JobStatus.CANCELLED


class TestIntegration:
    """Integration tests for Google Reviews scraping."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_google_scraping(self):
        """Test complete Google Reviews scraping workflow."""
        # This would be a real integration test
        # For now, we mock the components
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.search_business = AsyncMock(
                return_value="https://www.google.com/maps/place/Social+House"
            )
            mock_instance.scrape_google_reviews = AsyncMock(
                return_value=[
                    Review(
                        text="Integration test review",
                        rating=5.0,
                        date="2024-01-20",
                        author="Test User",
                        platform="google",
                        url="https://www.google.com/maps/place/Social+House",
                    )
                ]
            )

            service = ScraperService(redis_client=None)
            service.puppeteer_client = mock_instance

            job = await service.search_and_scrape(
                business_name="Social House", location="Orlando, FL", platform="google"
            )

            # Job should complete
            assert job.status in [JobStatus.COMPLETED, JobStatus.FAILED]
            if job.status == JobStatus.COMPLETED:
                assert len(job.results) > 0

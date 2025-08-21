"""Tests for Puppeteer scraper."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.puppeteer_client import PuppeteerClient


@pytest.fixture
async def puppeteer_client():
    """Create test Puppeteer client."""
    client = PuppeteerClient()
    yield client
    await client.close()


@pytest.fixture
def mock_browser():
    """Mock browser instance."""
    with patch("pyppeteer.launch") as mock_launch:
        browser = AsyncMock()
        page = AsyncMock()

        browser.newPage.return_value = page
        browser.close = AsyncMock()
        mock_launch.return_value = browser

        yield {"browser": browser, "page": page, "launch": mock_launch}


class TestPuppeteerClient:
    """Test Puppeteer client functionality."""

    @pytest.mark.asyncio
    async def test_browser_launch(self, mock_browser):
        """Test browser launches with correct options."""
        client = PuppeteerClient()
        await client.initialize()

        mock_browser["launch"].assert_called_once()
        call_args = mock_browser["launch"].call_args[1]

        assert call_args["headless"] is True
        assert "--no-sandbox" in call_args["args"]
        assert "--disable-setuid-sandbox" in call_args["args"]

    @pytest.mark.asyncio
    async def test_page_navigation(self, puppeteer_client, mock_browser):
        """Test navigating to a URL."""
        await puppeteer_client.initialize()
        await puppeteer_client.navigate("https://example.com")

        mock_browser["page"].goto.assert_called_with(
            "https://example.com", {"waitUntil": "networkidle0", "timeout": 30000}
        )

    @pytest.mark.asyncio
    async def test_extract_reviews_yelp(self, puppeteer_client, mock_browser):
        """Test extracting reviews from Yelp."""
        mock_browser["page"].evaluate.return_value = [
            {"text": "Amazing food!", "rating": 5, "date": "2024-01-01", "author": "Jane Doe"}
        ]

        await puppeteer_client.initialize()
        reviews = await puppeteer_client.scrape_yelp_reviews("https://yelp.com/biz/test")

        assert len(reviews) == 1
        assert reviews[0]["text"] == "Amazing food!"
        assert reviews[0]["rating"] == 5
        assert reviews[0]["platform"] == "yelp"

    @pytest.mark.asyncio
    async def test_extract_reviews_google(self, puppeteer_client, mock_browser):
        """Test extracting reviews from Google."""
        mock_browser["page"].evaluate.return_value = [
            {"text": "Great service", "rating": 4, "date": "2 months ago", "author": "John Smith"}
        ]

        await puppeteer_client.initialize()
        reviews = await puppeteer_client.scrape_google_reviews("https://google.com/maps/place/test")

        assert len(reviews) == 1
        assert reviews[0]["text"] == "Great service"
        assert reviews[0]["rating"] == 4
        assert reviews[0]["platform"] == "google"

    @pytest.mark.asyncio
    async def test_pagination_handling(self, puppeteer_client, mock_browser):
        """Test handling pagination."""
        # First page
        mock_browser["page"].evaluate.side_effect = [
            [{"text": f"Review {i}", "rating": 4} for i in range(10)],
            True,  # Has next page
            [{"text": f"Review {i+10}", "rating": 4} for i in range(10)],
            False,  # No more pages
        ]

        await puppeteer_client.initialize()
        reviews = await puppeteer_client.scrape_with_pagination(
            "https://yelp.com/biz/test", max_pages=2
        )

        assert len(reviews) == 20
        assert reviews[0]["text"] == "Review 0"
        assert reviews[19]["text"] == "Review 19"

    @pytest.mark.asyncio
    async def test_error_recovery(self, puppeteer_client, mock_browser):
        """Test error recovery during scraping."""
        mock_browser["page"].evaluate.side_effect = [
            Exception("Page crashed"),
            [{"text": "Success", "rating": 5}],
        ]

        await puppeteer_client.initialize()

        # Should retry and succeed
        reviews = await puppeteer_client.scrape_yelp_reviews("https://yelp.com/biz/test")
        assert len(reviews) == 1
        assert reviews[0]["text"] == "Success"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, puppeteer_client, mock_browser):
        """Test timeout during page load."""
        mock_browser["page"].goto.side_effect = TimeoutError("Navigation timeout")

        await puppeteer_client.initialize()

        with pytest.raises(TimeoutError):
            await puppeteer_client.navigate("https://slow-site.com")

    @pytest.mark.asyncio
    async def test_browser_cleanup(self, puppeteer_client, mock_browser):
        """Test browser is properly closed."""
        await puppeteer_client.initialize()
        await puppeteer_client.close()

        mock_browser["browser"].close.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, puppeteer_client, mock_browser):
        """Test user agent is rotated."""
        await puppeteer_client.initialize()

        ua1 = await puppeteer_client.get_user_agent()
        ua2 = await puppeteer_client.get_user_agent()

        # User agents should be different (rotation)
        assert ua1 != ua2

    @pytest.mark.asyncio
    async def test_javascript_execution(self, puppeteer_client, mock_browser):
        """Test executing JavaScript on page."""
        mock_browser["page"].evaluate.return_value = "Hello World"

        await puppeteer_client.initialize()
        result = await puppeteer_client.execute_js("return 'Hello World';")

        assert result == "Hello World"
        mock_browser["page"].evaluate.assert_called()

    @pytest.mark.asyncio
    async def test_screenshot_capability(self, puppeteer_client, mock_browser):
        """Test taking screenshots for debugging."""
        mock_browser["page"].screenshot.return_value = b"image_data"

        await puppeteer_client.initialize()
        screenshot = await puppeteer_client.take_screenshot()

        assert screenshot == b"image_data"
        mock_browser["page"].screenshot.assert_called()

    @pytest.mark.asyncio
    async def test_wait_for_selector(self, puppeteer_client, mock_browser):
        """Test waiting for specific selectors."""
        await puppeteer_client.initialize()
        await puppeteer_client.wait_for_selector(".review-container")

        mock_browser["page"].waitForSelector.assert_called_with(
            ".review-container", {"timeout": 10000}
        )

    @pytest.mark.asyncio
    async def test_memory_management(self, puppeteer_client, mock_browser):
        """Test browser recycling after N pages."""
        await puppeteer_client.initialize()

        # Scrape 10 pages (should trigger browser recycle)
        for i in range(10):
            await puppeteer_client.navigate(f"https://example.com/{i}")

        # Browser should be recycled
        assert mock_browser["browser"].close.call_count >= 1

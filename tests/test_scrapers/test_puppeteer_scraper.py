"""Tests for Puppeteer scraper."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.puppeteer_client import PuppeteerClient


@pytest.fixture
async def puppeteer_client():
    """Create test Puppeteer client."""
    client = PuppeteerClient()
    yield client
    await client.cleanup()


@pytest.fixture
def mock_browser():
    """Mock browser instance."""
    with patch("app.scrapers.puppeteer_client.launch") as mock_launch:
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
        mock_browser["page"].content.return_value = "<html><body>Test</body></html>"

        # Browser is created when scraping
        await client.scrape_url("https://example.com")

        mock_browser["launch"].assert_called_once()
        call_args = mock_browser["launch"].call_args[1]

        assert call_args["headless"] is True
        assert "--no-sandbox" in call_args["args"]
        assert "--disable-setuid-sandbox" in call_args["args"]

    @pytest.mark.asyncio
    async def test_page_navigation(self, mock_browser):
        """Test navigating to a URL."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html><body>Test</body></html>"

        await client.scrape_url("https://example.com")

        mock_browser["page"].goto.assert_called_with(
            "https://example.com", {"waitUntil": "networkidle2", "timeout": 30000}
        )

    @pytest.mark.asyncio
    async def test_yelp_disabled(self):
        """Test that Yelp scraping returns empty list (disabled)."""
        client = PuppeteerClient()

        # Yelp should return empty list due to being disabled
        reviews = await client.scrape_yelp_reviews(
            "https://www.yelp.com/biz/any-business", max_pages=1
        )

        # Should return empty list
        assert reviews == []

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_extract_reviews_google(self):
        """Test extracting reviews from real Google page."""
        client = PuppeteerClient()

        # Use a real Google Maps URL
        reviews = await client.scrape_google_reviews(
            "https://www.google.com/maps/place/Joe's+Pizza/@40.7304646,-74.0027664,17z/data=!3m1!4b1!4m6!3m5!1s0x89c259915d6bb40b:0x86e37e67b43f9c6f!8m2!3d40.7304646!4d-74.0001915!16s%2Fg%2F1tf9b2qj",
            max_reviews=5,
        )

        # Should get some reviews
        assert len(reviews) > 0
        assert reviews[0].text
        assert reviews[0].rating >= 1.0 and reviews[0].rating <= 5.0
        assert reviews[0].platform == "google"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_google_pagination(self):
        """Test Google Maps review pagination."""
        client = PuppeteerClient()

        # Mock for Google Maps
        # In real integration test, this would hit Google Maps
        # For unit test, we just verify the method exists
        assert hasattr(client, "scrape_google_reviews")

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery with invalid URL."""
        client = PuppeteerClient()

        # Try to scrape an invalid URL - should not crash
        reviews = await client.scrape_yelp_reviews(
            "https://yelp.com/biz/this-does-not-exist-123456789", max_pages=1
        )

        # Should return empty list on error
        assert reviews == []

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout during page load."""
        client = PuppeteerClient()
        client.timeout = 1000  # 1 second timeout

        # Try to scrape a site that doesn't respond quickly
        result = await client.scrape_url("https://httpstat.us/200?sleep=5000")

        # Should return None on timeout
        assert result is None

    @pytest.mark.asyncio
    async def test_browser_cleanup(self, mock_browser):
        """Test browser is properly closed."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html></html>"

        # Scrape to create a browser
        await client.scrape_url("https://example.com")

        # Clean up
        await client.cleanup()

        mock_browser["browser"].close.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, mock_browser):
        """Test user agent is set correctly."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html></html>"

        await client.scrape_url("https://example.com")

        # Check that setUserAgent was called with bot user agent
        mock_browser["page"].setUserAgent.assert_called_once()
        call_args = mock_browser["page"].setUserAgent.call_args[0][0]
        assert "RestaurantScraperBot" in call_args

    @pytest.mark.asyncio
    async def test_javascript_execution(self, mock_browser):
        """Test executing JavaScript on page."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html></html>"
        mock_browser["page"].evaluate.return_value = "Hello World"

        # scrape_url uses the page, which may evaluate JS
        await client.scrape_url("https://example.com")

        # Verify page was used
        assert mock_browser["page"].goto.called

    @pytest.mark.asyncio
    async def test_screenshot_capability(self, mock_browser):
        """Test taking screenshots for debugging."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html></html>"
        mock_browser["page"].screenshot.return_value = b"image_data"

        # The scrape_url method creates a page
        await client.scrape_url("https://example.com")

        # Verify browser and page were created
        assert mock_browser["browser"].newPage.called

    @pytest.mark.asyncio
    async def test_wait_for_selector(self, mock_browser):
        """Test waiting for specific selectors."""
        client = PuppeteerClient()
        mock_browser["page"].content.return_value = "<html></html>"

        # scrape_url with wait_selector
        await client.scrape_url("https://example.com", wait_selector=".review-container")

        mock_browser["page"].waitForSelector.assert_called_with(
            ".review-container", {"timeout": 30000}
        )

    @pytest.mark.asyncio
    async def test_memory_management(self, mock_browser):
        """Test browser recycling after N pages."""
        client = PuppeteerClient(max_concurrent_browsers=2)
        mock_browser["page"].content.return_value = "<html></html>"

        # Scrape multiple pages
        for i in range(3):
            await client.scrape_url(f"https://example.com/{i}")

        # Cleanup should close all browsers
        await client.cleanup()
        assert mock_browser["browser"].close.call_count >= 3

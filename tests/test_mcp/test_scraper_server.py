"""Tests for MCP scraper server."""

from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.scraper_server import create_mcp_server


@pytest.fixture
def mcp_server():
    """Create test MCP server instance."""
    return create_mcp_server()


@pytest.fixture
def mock_puppeteer():
    """Mock puppeteer client."""
    with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock:
        client = mock.return_value
        client.scrape_page = AsyncMock()
        yield client


class TestMCPServerInitialization:
    """Test MCP server setup and configuration."""

    def test_server_creation(self, mcp_server):
        """Test MCP server is created with correct name."""
        assert mcp_server.name == "Restaurant Review Scraper"

    def test_tools_registered(self, mcp_server):
        """Test all required tools are registered."""
        tools = mcp_server.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "scrape_reviews" in tool_names
        assert "search_and_scrape" in tool_names
        assert "extract_business_info" in tool_names

    def test_tool_descriptions(self, mcp_server):
        """Test tools have proper descriptions."""
        tools = mcp_server.list_tools()
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


class TestScrapeReviewsTool:
    """Test the scrape_reviews MCP tool."""

    @pytest.mark.asyncio
    async def test_scrape_valid_url(self, mcp_server, mock_puppeteer):
        """Test scraping a valid URL."""
        mock_puppeteer.scrape_page.return_value = [
            {
                "text": "Great food!",
                "rating": 5.0,
                "date": "2024-01-01",
                "author": "John Doe",
                "platform": "yelp",
                "url": "https://yelp.com/biz/test",
            }
        ]

        result = await mcp_server.call_tool(
            "scrape_reviews", {"url": "https://yelp.com/biz/test", "max_pages": 1}
        )

        assert len(result) == 1
        assert result[0]["text"] == "Great food!"
        assert result[0]["rating"] == 5.0

    @pytest.mark.asyncio
    async def test_scrape_invalid_url(self, mcp_server):
        """Test scraping with invalid URL."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await mcp_server.call_tool("scrape_reviews", {"url": "not-a-url", "max_pages": 1})

    @pytest.mark.asyncio
    async def test_scrape_pagination(self, mcp_server, mock_puppeteer):
        """Test scraping multiple pages."""
        mock_puppeteer.scrape_page.side_effect = [
            [{"text": f"Review {i}", "rating": 4.0} for i in range(10)] for _ in range(3)
        ]

        result = await mcp_server.call_tool(
            "scrape_reviews", {"url": "https://yelp.com/biz/test", "max_pages": 3}
        )

        assert len(result) == 30
        assert mock_puppeteer.scrape_page.call_count == 3


class TestSearchAndScrapeTool:
    """Test the search_and_scrape MCP tool."""

    @pytest.mark.asyncio
    async def test_search_and_scrape_yelp(self, mcp_server, mock_puppeteer):
        """Test searching and scraping from Yelp."""
        mock_puppeteer.search_business.return_value = "https://yelp.com/biz/test"
        mock_puppeteer.scrape_page.return_value = [{"text": "Found via search", "rating": 4.5}]

        result = await mcp_server.call_tool(
            "search_and_scrape",
            {"business_name": "Test Restaurant", "location": "New York", "platform": "yelp"},
        )

        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["results"][0]["text"] == "Found via search"

    @pytest.mark.asyncio
    async def test_search_unsupported_platform(self, mcp_server):
        """Test searching on unsupported platform."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            await mcp_server.call_tool(
                "search_and_scrape",
                {"business_name": "Test", "location": "NYC", "platform": "unknown"},
            )


class TestExtractBusinessInfoTool:
    """Test the extract_business_info MCP tool."""

    @pytest.mark.asyncio
    async def test_extract_business_info(self, mcp_server, mock_puppeteer):
        """Test extracting business information."""
        mock_puppeteer.extract_business_info.return_value = {
            "name": "Test Restaurant",
            "address": "123 Main St",
            "phone": "555-1234",
            "rating": 4.5,
            "review_count": 100,
            "categories": ["Italian", "Pizza"],
        }

        result = await mcp_server.call_tool(
            "extract_business_info", {"url": "https://yelp.com/biz/test"}
        )

        assert result["name"] == "Test Restaurant"
        assert result["rating"] == 4.5
        assert "Italian" in result["categories"]


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, mcp_server, mock_puppeteer):
        """Test that rate limits are enforced."""
        # Make 10 rapid requests (limit is 10/minute)
        for i in range(10):
            await mcp_server.call_tool(
                "scrape_reviews", {"url": f"https://yelp.com/biz/test{i}", "max_pages": 1}
            )

        # 11th request should be rate limited
        with pytest.raises(Exception, match="Rate limit"):
            await mcp_server.call_tool(
                "scrape_reviews", {"url": "https://yelp.com/biz/test11", "max_pages": 1}
            )


class TestCaching:
    """Test result caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mcp_server, mock_puppeteer):
        """Test that cached results are returned."""
        url = "https://yelp.com/biz/test"

        # First call - should hit puppeteer
        result1 = await mcp_server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})

        # Second call - should return cached
        result2 = await mcp_server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})

        assert result1 == result2
        mock_puppeteer.scrape_page.assert_called_once()


class TestErrorHandling:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_browser_crash_recovery(self, mcp_server, mock_puppeteer):
        """Test recovery from browser crash."""
        mock_puppeteer.scrape_page.side_effect = [
            Exception("Browser crashed"),
            [{"text": "Success after retry", "rating": 4.0}],
        ]

        result = await mcp_server.call_tool(
            "scrape_reviews", {"url": "https://yelp.com/biz/test", "max_pages": 1}
        )

        assert len(result) == 1
        assert result[0]["text"] == "Success after retry"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mcp_server, mock_puppeteer):
        """Test timeout handling."""
        mock_puppeteer.scrape_page.side_effect = TimeoutError("Page load timeout")

        with pytest.raises(TimeoutError):
            await mcp_server.call_tool(
                "scrape_reviews", {"url": "https://yelp.com/biz/test", "max_pages": 1}
            )

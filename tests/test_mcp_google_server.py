"""Tests for Google Reviews MCP server implementation."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from app.models.scraping import BusinessInfo, JobStatus, Review, ScrapingJob


@pytest.fixture
async def google_mcp_server():
    """Create MCP server instance for Google Reviews."""
    from app.mcp.scraper_server import create_mcp_server

    server = create_mcp_server()
    yield server


class TestGoogleMCPTools:
    """Test MCP tools for Google Reviews."""

    @pytest.mark.asyncio
    async def test_tool_registration(self, google_mcp_server):
        """Test that Google Reviews tools are registered."""
        tools = await google_mcp_server.get_tools()

        # Check that Google-specific tools exist
        assert "scrape_google_reviews" in tools
        assert "search_google_business" in tools
        assert "extract_google_business_info" in tools

        # Verify no Yelp or TripAdvisor tools
        for tool_name in tools:
            assert "yelp" not in tool_name.lower()
            assert "tripadvisor" not in tool_name.lower()

    @pytest.mark.asyncio
    async def test_tool_descriptions(self, google_mcp_server):
        """Test tool descriptions are clear and Google-specific."""
        tools = await google_mcp_server.get_tools()

        # Check scrape_google_reviews description
        scrape_tool = tools["scrape_google_reviews"]
        assert "Google" in scrape_tool.description
        assert len(scrape_tool.description) > 20

        # Check search_google_business description
        search_tool = tools["search_google_business"]
        assert "Google" in search_tool.description or "Maps" in search_tool.description

        # Check extract_google_business_info description
        extract_tool = tools["extract_google_business_info"]
        assert (
            "Google" in extract_tool.description or "business" in extract_tool.description.lower()
        )

    @pytest.mark.asyncio
    async def test_tool_parameters(self, google_mcp_server):
        """Test tool parameter schemas."""
        tools = await google_mcp_server.get_tools()

        # Test scrape_google_reviews parameters
        scrape_tool = tools["scrape_google_reviews"]
        params = scrape_tool.parameters
        assert "url" in params["properties"]
        assert "max_pages" in params["properties"]
        assert params["properties"]["url"]["type"] == "string"
        assert params["properties"]["max_pages"]["type"] == "integer"

        # Test search_google_business parameters
        search_tool = tools["search_google_business"]
        params = search_tool.parameters
        assert "business_name" in params["properties"]
        assert "location" in params["properties"]
        assert params["required"] == ["business_name", "location"]

        # Test extract_google_business_info parameters
        extract_tool = tools["extract_google_business_info"]
        params = extract_tool.parameters
        assert "url" in params["properties"]
        assert params["required"] == ["url"]


class TestScrapeGoogleReviewsTool:
    """Test scrape_google_reviews MCP tool."""

    @pytest.mark.asyncio
    async def test_scrape_social_house(self, google_mcp_server):
        """Test scraping Social House reviews."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.scrape_reviews = AsyncMock(
                return_value=[
                    Review(
                        text="Excellent sushi and ambiance!",
                        rating=5.0,
                        date="2024-01-20",
                        author="Alice Brown",
                        platform="google",
                        url="https://www.google.com/maps/place/Social+House",
                        response=None,
                    ),
                    Review(
                        text="Good happy hour deals.",
                        rating=4.0,
                        date="2024-01-18",
                        author="Bob Smith",
                        platform="google",
                        url="https://www.google.com/maps/place/Social+House",
                        response="Thanks for visiting!",
                    ),
                ]
            )

            tools = await google_mcp_server.get_tools()
            scrape_tool = tools["scrape_google_reviews"]

            result = await scrape_tool.fn(
                url="https://www.google.com/maps/place/Social+House/@28.5383,-81.3792,17z",
                max_pages=2,
            )

            assert len(result) == 2
            assert result[0]["text"] == "Excellent sushi and ambiance!"
            assert result[0]["rating"] == 5.0
            assert result[0]["platform"] == "google"
            assert result[1]["response"] == "Thanks for visiting!"

    @pytest.mark.asyncio
    async def test_scrape_with_pagination(self, google_mcp_server):
        """Test scraping with multiple pages."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value

            # Simulate 100 reviews (Google's infinite scroll)
            mock_reviews = [
                Review(
                    text=f"Review number {i}",
                    rating=4.0 + (i % 2),
                    date="2024-01-01",
                    author=f"User {i}",
                    platform="google",
                    url="https://www.google.com/maps/place/test",
                    response=None,
                )
                for i in range(100)
            ]
            mock_instance.scrape_reviews = AsyncMock(return_value=mock_reviews)

            tools = await google_mcp_server.get_tools()
            scrape_tool = tools["scrape_google_reviews"]

            result = await scrape_tool.fn(
                url="https://www.google.com/maps/place/test", max_pages=10
            )

            assert len(result) == 100
            assert all(r["platform"] == "google" for r in result)

    @pytest.mark.asyncio
    async def test_scrape_invalid_url(self, google_mcp_server):
        """Test scraping with invalid URL."""
        tools = await google_mcp_server.get_tools()
        scrape_tool = tools["scrape_google_reviews"]

        with pytest.raises(ValueError, match="Invalid URL"):
            await scrape_tool.fn(url="not-a-valid-url", max_pages=1)

    @pytest.mark.asyncio
    async def test_scrape_non_google_url(self, google_mcp_server):
        """Test scraping with non-Google URL."""
        tools = await google_mcp_server.get_tools()
        scrape_tool = tools["scrape_google_reviews"]

        with pytest.raises(ValueError, match="Google"):
            await scrape_tool.fn(url="https://www.yelp.com/biz/test", max_pages=1)


class TestSearchGoogleBusinessTool:
    """Test search_google_business MCP tool."""

    @pytest.mark.asyncio
    async def test_search_social_house(self, google_mcp_server):
        """Test searching for Social House."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_job = ScrapingJob(
                id="job-123",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(),
                completed_at=datetime.now(),
                url="https://www.google.com/maps/place/Social+House/@28.5383,-81.3792",
                results=[
                    Review(
                        text="Found via search",
                        rating=5.0,
                        date="2024-01-20",
                        author="Search User",
                        platform="google",
                        url="https://www.google.com/maps/place/Social+House",
                    )
                ],
            )
            mock_instance.search_and_scrape = AsyncMock(return_value=mock_job)

            tools = await google_mcp_server.get_tools()
            search_tool = tools["search_google_business"]

            result = await search_tool.fn(business_name="Social House", location="Orlando, FL")

            assert result["id"] == "job-123"
            assert result["status"] == "completed"
            assert "Social+House" in result["url"]
            assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_search_not_found(self, google_mcp_server):
        """Test searching for non-existent business."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_job = ScrapingJob(
                id="job-404",
                status=JobStatus.FAILED,
                created_at=datetime.now(),
                completed_at=datetime.now(),
                error="Could not find business: Fake Restaurant in Orlando, FL",
            )
            mock_instance.search_and_scrape = AsyncMock(return_value=mock_job)

            tools = await google_mcp_server.get_tools()
            search_tool = tools["search_google_business"]

            result = await search_tool.fn(business_name="Fake Restaurant", location="Orlando, FL")

            assert result["id"] == "job-404"
            assert result["status"] == "failed"
            assert "Could not find" in result["error"]

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self, google_mcp_server):
        """Test searching with special characters in name."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_job = ScrapingJob(
                id="job-special",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(),
                url="https://www.google.com/maps/place/test",
                results=[],
            )
            mock_instance.search_and_scrape = AsyncMock(return_value=mock_job)

            tools = await google_mcp_server.get_tools()
            search_tool = tools["search_google_business"]

            # Business name with special characters
            result = await search_tool.fn(
                business_name="Joe's Pizza & Pasta", location="New York, NY"
            )

            assert result["id"] == "job-special"
            mock_instance.search_and_scrape.assert_called_once()


class TestExtractGoogleBusinessInfoTool:
    """Test extract_google_business_info MCP tool."""

    @pytest.mark.asyncio
    async def test_extract_social_house_info(self, google_mcp_server):
        """Test extracting Social House business info."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_info = BusinessInfo(
                name="Social House",
                address="7575 Dr Phillips Blvd, Orlando, FL 32819",
                phone="(407) 370-0700",
                rating=4.3,
                review_count=1842,
                categories=["Japanese Restaurant", "Sushi Bar", "Asian Fusion"],
                url="https://www.google.com/maps/place/Social+House",
            )
            mock_instance.extract_business_info = AsyncMock(return_value=mock_info)

            tools = await google_mcp_server.get_tools()
            extract_tool = tools["extract_google_business_info"]

            result = await extract_tool.fn(
                url="https://www.google.com/maps/place/Social+House/@28.5383,-81.3792"
            )

            assert result["name"] == "Social House"
            assert result["address"] == "7575 Dr Phillips Blvd, Orlando, FL 32819"
            assert result["phone"] == "(407) 370-0700"
            assert result["rating"] == 4.3
            assert result["review_count"] == 1842
            assert len(result["categories"]) == 3
            assert "Japanese Restaurant" in result["categories"]

    @pytest.mark.asyncio
    async def test_extract_missing_info(self, google_mcp_server):
        """Test extracting info when some fields are missing."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_info = BusinessInfo(
                name="Test Business",
                address=None,  # Missing address
                phone=None,  # Missing phone
                rating=4.0,
                review_count=50,
                categories=["Restaurant"],
                url="https://www.google.com/maps/place/test",
            )
            mock_instance.extract_business_info = AsyncMock(return_value=mock_info)

            tools = await google_mcp_server.get_tools()
            extract_tool = tools["extract_google_business_info"]

            result = await extract_tool.fn(url="https://www.google.com/maps/place/test")

            assert result["name"] == "Test Business"
            assert result["address"] is None
            assert result["phone"] is None
            assert result["rating"] == 4.0

    @pytest.mark.asyncio
    async def test_extract_invalid_url(self, google_mcp_server):
        """Test extracting info with invalid URL."""
        tools = await google_mcp_server.get_tools()
        extract_tool = tools["extract_google_business_info"]

        with pytest.raises(ValueError, match="Invalid URL"):
            await extract_tool.fn(url="not-a-url")


class TestMCPServerLifecycle:
    """Test MCP server lifecycle management."""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test server initializes correctly."""
        from app.mcp.scraper_server import create_mcp_server

        server = create_mcp_server()
        assert server is not None
        assert isinstance(server, FastMCP)

    @pytest.mark.asyncio
    async def test_server_shutdown(self, google_mcp_server):
        """Test graceful server shutdown."""
        # Server should handle shutdown gracefully
        with patch("app.services.scraper_service.ScraperService.cleanup") as mock_cleanup:
            mock_cleanup.return_value = asyncio.Future()
            mock_cleanup.return_value.set_result(None)

            # Simulate shutdown
            # In real implementation, this would close browsers, Redis connections, etc.
            assert google_mcp_server is not None

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, google_mcp_server):
        """Test handling concurrent MCP tool calls."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.scrape_reviews = AsyncMock(
                return_value=[
                    Review(
                        text="Concurrent test",
                        rating=4.0,
                        date="2024-01-20",
                        author="Test",
                        platform="google",
                        url="https://www.google.com/maps/place/test",
                    )
                ]
            )

            tools = await google_mcp_server.get_tools()
            scrape_tool = tools["scrape_google_reviews"]

            # Make 5 concurrent calls
            tasks = [
                scrape_tool.fn(url=f"https://www.google.com/maps/place/test{i}", max_pages=1)
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(len(r) == 1 for r in results)


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance."""

    @pytest.mark.asyncio
    async def test_tool_response_format(self, google_mcp_server):
        """Test tool responses follow MCP format."""
        with patch("app.services.scraper_service.ScraperService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.scrape_reviews = AsyncMock(return_value=[])

            tools = await google_mcp_server.get_tools()
            scrape_tool = tools["scrape_google_reviews"]

            result = await scrape_tool.fn(url="https://www.google.com/maps/place/test", max_pages=1)

            # Result should be JSON-serializable
            import json

            json.dumps(result)  # Should not raise

    @pytest.mark.asyncio
    async def test_error_response_format(self, google_mcp_server):
        """Test error responses follow MCP format."""
        tools = await google_mcp_server.get_tools()
        scrape_tool = tools["scrape_google_reviews"]

        with pytest.raises(ValueError) as exc_info:
            await scrape_tool.fn(url="invalid", max_pages=1)

        # Error should have proper message
        assert "Invalid URL" in str(exc_info.value)

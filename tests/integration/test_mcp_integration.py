"""Integration tests for MCP server with scraping functionality."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.scraper_server import create_mcp_server


@pytest.fixture
async def mcp_integration():
    """Create integrated MCP server with mocked external dependencies."""
    with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
        with patch("redis.from_url") as mock_redis:
            # Setup mock Puppeteer
            client = mock_puppeteer.return_value
            client.initialize = AsyncMock()
            client.scrape_page = AsyncMock(
                return_value=[{"text": "Integration test review", "rating": 4.5}]
            )
            client.close = AsyncMock()

            # Setup mock Redis
            redis_client = AsyncMock()
            redis_client.get = AsyncMock(return_value=None)
            redis_client.set = AsyncMock()
            redis_client.expire = AsyncMock()
            mock_redis.return_value = redis_client

            server = create_mcp_server()
            yield {"server": server, "puppeteer": client, "redis": redis_client}


class TestEndToEndScraping:
    """Test complete scraping workflow through MCP."""

    @pytest.mark.asyncio
    async def test_full_scraping_workflow(self, mcp_integration):
        """Test complete workflow from MCP request to results."""
        server = mcp_integration["server"]

        # 1. Create scraping job
        job_result = await server.call_tool(
            "search_and_scrape",
            {"business_name": "Test Restaurant", "location": "New York", "platform": "yelp"},
        )

        assert job_result["status"] in ["pending", "running"]
        assert job_result["id"]

        # 2. Check job status
        job_id = job_result["id"]
        status = await server.call_tool("get_job_status", {"job_id": job_id})

        assert status["id"] == job_id

        # 3. Get results
        await asyncio.sleep(0.1)  # Simulate processing time
        results = await server.call_tool("get_job_results", {"job_id": job_id})

        assert len(results) > 0
        assert results[0]["text"] == "Integration test review"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mcp_integration):
        """Test handling multiple concurrent MCP requests."""
        server = mcp_integration["server"]

        # Create 5 concurrent scraping jobs
        tasks = []
        for i in range(5):
            task = server.call_tool(
                "scrape_reviews", {"url": f"https://yelp.com/biz/test{i}", "max_pages": 1}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_platform_specific_scraping(self, mcp_integration):
        """Test scraping from different platforms."""
        server = mcp_integration["server"]
        puppeteer = mcp_integration["puppeteer"]

        platforms = ["yelp", "google", "tripadvisor"]

        for platform in platforms:
            # Configure mock for platform-specific response
            puppeteer.scrape_page.return_value = [
                {"text": f"Review from {platform}", "rating": 4.0, "platform": platform}
            ]

            result = await server.call_tool(
                "search_and_scrape",
                {"business_name": "Test", "location": "NYC", "platform": platform},
            )

            assert result["platform"] == platform


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance."""

    @pytest.mark.asyncio
    async def test_tool_discovery(self, mcp_integration):
        """Test MCP tool discovery."""
        server = mcp_integration["server"]
        tools = server.list_tools()

        required_tools = ["scrape_reviews", "search_and_scrape", "extract_business_info"]
        tool_names = [tool.name for tool in tools]

        for required in required_tools:
            assert required in tool_names

    @pytest.mark.asyncio
    async def test_tool_schemas(self, mcp_integration):
        """Test tool parameter schemas."""
        server = mcp_integration["server"]
        tools = server.list_tools()

        for tool in tools:
            assert tool.input_schema
            assert "properties" in tool.input_schema
            assert "required" in tool.input_schema

    @pytest.mark.asyncio
    async def test_error_responses(self, mcp_integration):
        """Test MCP error response format."""
        server = mcp_integration["server"]

        # Invalid parameters
        with pytest.raises(ValueError) as exc_info:
            await server.call_tool("scrape_reviews", {"invalid_param": "test"})

        error = str(exc_info.value)
        assert "url" in error.lower() or "required" in error.lower()


class TestCachingIntegration:
    """Test caching integration with MCP."""

    @pytest.mark.asyncio
    async def test_cache_hit_workflow(self, mcp_integration):
        """Test that cached results are returned correctly."""
        server = mcp_integration["server"]
        redis_client = mcp_integration["redis"]

        url = "https://yelp.com/biz/cached"

        # First request - cache miss
        result1 = await server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})

        # Configure Redis to return cached data
        redis_client.get.return_value = json.dumps(result1)

        # Second request - cache hit
        result2 = await server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mcp_integration):
        """Test cache invalidation after expiry."""
        server = mcp_integration["server"]
        redis_client = mcp_integration["redis"]

        # Simulate expired cache
        redis_client.get.return_value = None

        result = await server.call_tool(
            "scrape_reviews", {"url": "https://yelp.com/biz/expired", "max_pages": 1}
        )

        # Should fetch fresh data
        assert len(result) > 0
        redis_client.set.assert_called()


class TestRateLimitingIntegration:
    """Test rate limiting integration."""

    @pytest.mark.asyncio
    async def test_rate_limit_across_tools(self, mcp_integration):
        """Test rate limiting applies across different tools."""
        server = mcp_integration["server"]
        redis_client = mcp_integration["redis"]

        # Simulate rate limit counter
        call_count = 0

        async def mock_get(key):
            nonlocal call_count
            if key.startswith("rate:"):
                return call_count
            return None

        async def mock_incr(key):
            nonlocal call_count
            if key.startswith("rate:"):
                call_count += 1
            return call_count

        redis_client.get = mock_get
        redis_client.incr = mock_incr

        # Make requests up to limit
        for i in range(10):
            await server.call_tool(
                "scrape_reviews", {"url": f"https://yelp.com/biz/test{i}", "max_pages": 1}
            )

        # 11th request should be rate limited
        with pytest.raises(Exception, match="rate limit"):
            await server.call_tool(
                "scrape_reviews", {"url": "https://yelp.com/biz/test11", "max_pages": 1}
            )


class TestMemoryManagement:
    """Test memory management in integration."""

    @pytest.mark.asyncio
    async def test_browser_recycling(self, mcp_integration):
        """Test browser instances are recycled."""
        server = mcp_integration["server"]
        puppeteer = mcp_integration["puppeteer"]

        # Track browser lifecycle
        close_count = 0

        async def mock_close():
            nonlocal close_count
            close_count += 1

        puppeteer.close = mock_close

        # Process many pages to trigger recycling
        for i in range(20):
            await server.call_tool(
                "scrape_reviews", {"url": f"https://yelp.com/biz/test{i}", "max_pages": 1}
            )

        # Browser should have been recycled at least once
        assert close_count >= 2

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self, mcp_integration):
        """Test memory usage stays within limits."""
        server = mcp_integration["server"]

        # Monitor memory usage during scraping
        import psutil

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run multiple scraping operations
        for i in range(10):
            await server.call_tool(
                "scrape_reviews", {"url": f"https://yelp.com/biz/test{i}", "max_pages": 2}
            )

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Should stay under 512MB increase per spec
        assert memory_increase < 512


class TestAsyncJobProcessing:
    """Test async job processing integration."""

    @pytest.mark.asyncio
    async def test_webhook_integration(self, mcp_integration):
        """Test webhook notifications work correctly."""
        server = mcp_integration["server"]

        with patch("aiohttp.ClientSession") as mock_session:
            session = mock_session.return_value.__aenter__.return_value
            session.post = AsyncMock()

            # Create job with webhook
            await server.call_tool(
                "search_and_scrape",
                {
                    "business_name": "Test",
                    "location": "NYC",
                    "platform": "yelp",
                    "webhook_url": "https://example.com/webhook",
                },
            )

            # Wait for job completion
            await asyncio.sleep(0.1)

            # Webhook should be called
            session.post.assert_called()
            call_args = session.post.call_args
            assert "example.com/webhook" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_job_status_tracking(self, mcp_integration):
        """Test job status transitions."""
        server = mcp_integration["server"]
        redis_client = mcp_integration["redis"]

        # Track status updates
        status_updates = []

        async def mock_set(key, value):
            if key.startswith("job:"):
                data = json.loads(value) if isinstance(value, str) else value
                status_updates.append(data.get("status"))

        redis_client.set = mock_set

        # Create and process job
        await server.call_tool(
            "search_and_scrape", {"business_name": "Test", "location": "NYC", "platform": "yelp"}
        )

        await asyncio.sleep(0.1)

        # Should have transitioned through states
        assert "pending" in status_updates
        assert "running" in status_updates or "completed" in status_updates


class TestErrorRecovery:
    """Test error recovery in integration."""

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, mcp_integration):
        """Test handling partial failures in batch operations."""
        server = mcp_integration["server"]
        puppeteer = mcp_integration["puppeteer"]

        # Some pages fail, some succeed
        puppeteer.scrape_page.side_effect = [
            [{"text": "Success 1", "rating": 5}],
            Exception("Page 2 failed"),
            [{"text": "Success 3", "rating": 4}],
        ]

        urls = [
            "https://yelp.com/biz/test1",
            "https://yelp.com/biz/test2",
            "https://yelp.com/biz/test3",
        ]

        results = []
        errors = []

        for url in urls:
            try:
                result = await server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Should have 2 successes and 1 failure
        assert len(results) == 2
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mcp_integration):
        """Test graceful shutdown of MCP server."""
        server = mcp_integration["server"]
        puppeteer = mcp_integration["puppeteer"]

        # Start a long-running job
        task = asyncio.create_task(
            server.call_tool(
                "scrape_reviews", {"url": "https://yelp.com/biz/long", "max_pages": 10}
            )
        )

        # Simulate shutdown after short delay
        await asyncio.sleep(0.1)
        task.cancel()

        # Cleanup should be called
        puppeteer.close.assert_called()

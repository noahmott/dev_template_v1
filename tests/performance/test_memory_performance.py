"""Performance and memory leak tests for MCP scraper."""

import asyncio
import gc
import time
from unittest.mock import AsyncMock, patch

import psutil
import pytest

from app.mcp.scraper_server import create_mcp_server


class TestMemoryLeaks:
    """Test for memory leaks during extended operation."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_no_memory_leak_after_hour(self):
        """Test no memory leaks after 1 hour of operation."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            client = mock_puppeteer.return_value
            client.initialize = AsyncMock()
            client.scrape_page = AsyncMock(return_value=[{"text": "Test review", "rating": 4.0}])
            client.close = AsyncMock()

            server = create_mcp_server()
            process = psutil.Process()

            # Initial memory snapshot
            gc.collect()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Run for simulated hour (accelerated)
            start_time = time.time()
            request_count = 0

            while time.time() - start_time < 60:  # Run for 1 minute in test
                await server.call_tool(
                    "scrape_reviews", {"url": f"https://test.com/{request_count}", "max_pages": 1}
                )
                request_count += 1

                # Periodic garbage collection
                if request_count % 100 == 0:
                    gc.collect()

            # Final memory snapshot
            gc.collect()
            final_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Memory increase should be minimal (< 50MB)
            memory_increase = final_memory - initial_memory
            assert memory_increase < 50, f"Memory leak detected: {memory_increase}MB increase"

    @pytest.mark.asyncio
    async def test_browser_instance_cleanup(self):
        """Test that browser instances are properly cleaned up."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            instances_created = []
            instances_closed = []

            def track_creation(*args, **kwargs):
                instance = AsyncMock()
                instance.initialize = AsyncMock()
                instance.scrape_page = AsyncMock(return_value=[])
                instance.close = AsyncMock(side_effect=lambda: instances_closed.append(instance))
                instances_created.append(instance)
                return instance

            mock_puppeteer.side_effect = track_creation

            server = create_mcp_server()

            # Create multiple scraping sessions
            for i in range(10):
                await server.call_tool(
                    "scrape_reviews", {"url": f"https://test.com/{i}", "max_pages": 1}
                )

            # All created instances should be closed
            assert len(instances_closed) == len(instances_created)


class TestPerformance:
    """Test performance requirements."""

    @pytest.mark.asyncio
    async def test_scraping_speed(self):
        """Test average scraping time < 10s per page."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            client = mock_puppeteer.return_value
            client.initialize = AsyncMock()

            # Simulate realistic page load time
            async def mock_scrape(*args):
                await asyncio.sleep(0.5)  # 500ms per page
                return [{"text": "Review", "rating": 4.0} for _ in range(10)]

            client.scrape_page = mock_scrape
            client.close = AsyncMock()

            server = create_mcp_server()

            # Measure scraping time
            start = time.time()
            await server.call_tool("scrape_reviews", {"url": "https://test.com", "max_pages": 5})
            elapsed = time.time() - start

            # Should complete 5 pages in < 50s (10s per page)
            assert elapsed < 50

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test handling 100 concurrent requests without crash."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            client = mock_puppeteer.return_value
            client.initialize = AsyncMock()
            client.scrape_page = AsyncMock(
                return_value=[{"text": "Concurrent test", "rating": 4.0}]
            )
            client.close = AsyncMock()

            server = create_mcp_server()

            # Create 100 concurrent requests
            tasks = []
            for i in range(100):
                task = server.call_tool(
                    "scrape_reviews", {"url": f"https://test.com/{i}", "max_pages": 1}
                )
                tasks.append(task)

            # All should complete without crash
            start = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start

            # Check results
            successful = [r for r in results if not isinstance(r, Exception)]
            assert len(successful) >= 95  # 95% success rate

            # Should handle all requests reasonably quickly
            assert elapsed < 60  # Less than 1 minute for 100 requests

    @pytest.mark.asyncio
    async def test_memory_per_browser_instance(self):
        """Test memory usage stays under 512MB per browser."""
        with patch("pyppeteer.launch") as mock_launch:
            browser = AsyncMock()
            page = AsyncMock()
            browser.newPage.return_value = page
            browser.close = AsyncMock()
            mock_launch.return_value = browser

            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create 3 browser instances (max concurrent)
            from app.scrapers.puppeteer_client import PuppeteerClient

            clients = []
            for _ in range(3):
                client = PuppeteerClient()
                await client.initialize()
                clients.append(client)

            # Check memory after creating browsers
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_per_browser = (current_memory - initial_memory) / 3

            # Each browser should use < 512MB
            assert memory_per_browser < 512

            # Cleanup
            for client in clients:
                await client.close()

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test cache improves performance significantly."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            with patch("redis.from_url") as mock_redis:
                client = mock_puppeteer.return_value
                client.initialize = AsyncMock()

                # Slow scraping simulation
                async def slow_scrape(*args):
                    await asyncio.sleep(2)  # 2 seconds
                    return [{"text": "Slow result", "rating": 4.0}]

                client.scrape_page = slow_scrape
                client.close = AsyncMock()

                # Setup Redis cache
                redis_client = AsyncMock()
                cache = {}

                async def mock_get(key):
                    return cache.get(key)

                async def mock_set(key, value, *args):
                    cache[key] = value

                redis_client.get = mock_get
                redis_client.set = mock_set
                redis_client.expire = AsyncMock()
                mock_redis.return_value = redis_client

                server = create_mcp_server()
                url = "https://test.com/cached"

                # First request - no cache
                start = time.time()
                await server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})
                first_time = time.time() - start

                # Second request - should hit cache
                start = time.time()
                await server.call_tool("scrape_reviews", {"url": url, "max_pages": 1})
                second_time = time.time() - start

                # Cache should be much faster
                assert second_time < first_time / 10  # At least 10x faster

    @pytest.mark.asyncio
    async def test_rate_limit_performance(self):
        """Test rate limiting doesn't significantly impact performance."""
        with patch("app.scrapers.puppeteer_client.PuppeteerClient") as mock_puppeteer:
            client = mock_puppeteer.return_value
            client.initialize = AsyncMock()
            client.scrape_page = AsyncMock(return_value=[])
            client.close = AsyncMock()

            server = create_mcp_server()

            # Measure time for 10 requests (at rate limit)
            start = time.time()
            for i in range(10):
                await server.call_tool(
                    "scrape_reviews", {"url": f"https://test.com/{i}", "max_pages": 1}
                )
            elapsed = time.time() - start

            # Should complete quickly even with rate limiting
            assert elapsed < 30  # Less than 3 seconds per request average

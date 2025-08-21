# SCRAPER-001: Google Reviews MCP Scraping Service

## Overview
Design document for MCP-enabled Google Reviews scraping service using Puppeteer.

## Architecture

### Components

1. **MCP Server** (`app/mcp/google_scraper_server.py`)
   - FastMCP-based server exposing Google Reviews scraping tools
   - Runs on configurable port (default 3000)
   - Handles MCP protocol communication

2. **Google Reviews Scraper** (`app/scrapers/google_reviews.py`)
   - Puppeteer-based scraper for Google Reviews
   - Handles JavaScript rendering
   - Pagination support
   - Data extraction and validation

3. **FastAPI Integration** (`app/api/v1/scraping.py`)
   - REST endpoints for non-MCP access
   - Async job management
   - Webhook support

4. **Data Models** (`app/models/scraping.py`)
   - Review: Pydantic model for review data
   - BusinessInfo: Google business metadata
   - ScrapingJob: Job tracking and status

5. **Caching Layer** (`app/cache/redis_cache.py`)
   - Redis-based result caching
   - 24-hour TTL for scraped data
   - Job status tracking

## Data Flow

1. MCP client sends scraping request
2. Server validates request parameters
3. Puppeteer browser instance launched (headless)
4. Navigate to Google Reviews page
5. Extract review data with validation
6. Handle pagination if needed
7. Cache results in Redis
8. Return structured data to client

## Google Reviews Specifics

### URL Patterns
- Direct business URL: `https://www.google.com/maps/place/...`
- Search URL: `https://www.google.com/maps/search/...`

### Data Extraction
- Review text (class: "wiI7pd")
- Rating (aria-label attribute)
- Date (class: "rsqaWe")
- Author name (class: "d4r55")
- Owner response (if present)

### Challenges
- Dynamic content loading
- Infinite scroll pagination
- Rate limiting by Google
- CAPTCHA detection

## Security Considerations

1. **Rate Limiting**
   - Max 10 requests/minute to Google
   - Exponential backoff on 429 responses
   - Random delays between requests

2. **Browser Fingerprinting**
   - Rotate user agents
   - Use stealth plugins
   - Randomize viewport sizes

3. **Compliance**
   - Identify as bot in User-Agent
   - Respect robots.txt
   - No PII storage beyond public names

## Error Handling

1. **Network Failures**
   - Retry with exponential backoff
   - Max 3 retry attempts
   - Correlation IDs for tracking

2. **Parsing Failures**
   - Graceful degradation
   - Log unparseable content
   - Return partial results

3. **Browser Crashes**
   - Auto-restart browser pool
   - Queue redistribution
   - Memory monitoring

## Testing Strategy

1. **Unit Tests**
   - Scraper class methods
   - Data validation
   - URL pattern matching

2. **Integration Tests**
   - Mock Google Reviews HTML
   - MCP protocol compliance
   - Redis caching behavior

3. **Performance Tests**
   - Concurrent request handling
   - Memory usage monitoring
   - Browser pool management

## Deployment

1. **Environment Variables**
   ```
   MCP_SERVER_PORT=3000
   REDIS_URL=redis://localhost:6379
   MAX_CONCURRENT_BROWSERS=3
   SCRAPING_TIMEOUT_SECONDS=30
   GOOGLE_RATE_LIMIT=10
   ```

2. **Dependencies**
   - fastmcp (latest from main)
   - pyppeteer (latest from dev fork)
   - redis-py (latest)
   - tenacity (for retries)
   - pydantic v2

3. **Monitoring**
   - OpenTelemetry traces
   - Structured JSON logging
   - Prometheus metrics

## Rollback Plan

1. Feature flag: `ENABLE_MCP_SCRAPER`
2. Graceful shutdown of MCP server
3. Fallback to manual Excel upload
4. Preserve cached data

## Success Criteria

- 95% success rate on valid Google URLs
- < 10s average scraping time
- Zero memory leaks
- 100 concurrent requests without crash

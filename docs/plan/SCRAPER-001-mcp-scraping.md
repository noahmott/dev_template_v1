# SCRAPER-001: MCP-Enabled Web Scraping Service

## Overview
Build an MCP server that exposes modern scraping capabilities using Puppeteer for restaurant review collection from multiple platforms (Yelp, Google Reviews, TripAdvisor).

## Problem Statement
- Current system relies on manual Excel-based review data
- No real-time scraping capabilities
- Need to handle JavaScript-heavy review sites
- Require standardized API for AI assistants to access scraping tools

## Solution Design

### Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ MCP Client  │────▶│  MCP Server │────▶│  Puppeteer  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   FastAPI   │     │  Websites   │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    └─────────────┘
```

### Components

1. **MCP Server (app/mcp/scraper_server.py)**
   - FastMCP-based server exposing scraping tools
   - Handles MCP protocol communication
   - Tool registration and parameter validation

2. **Puppeteer Client (app/scrapers/puppeteer_client.py)**
   - Headless browser management
   - JavaScript execution capabilities
   - Page navigation and content extraction

3. **FastAPI Integration (app/api/v1/scraping.py)**
   - REST endpoints for non-MCP access
   - Async job management
   - Result caching

4. **Rate Limiting (Redis)**
   - Per-domain rate limiting
   - Request queuing
   - Cache management

## Data Flow

1. Client sends scraping request via MCP protocol
2. MCP server validates parameters and checks rate limits
3. Puppeteer launches headless browser
4. Navigate to target URL and wait for content
5. Extract review data using selectors
6. Clean and validate data
7. Cache results in Redis (24hr TTL)
8. Return structured data to client

## Data Schema

### Review Model
```python
{
    "text": str,
    "rating": float,
    "date": datetime,
    "author": str,
    "platform": str,
    "url": str,
    "response": Optional[str]
}
```

### ScrapingJob Model
```python
{
    "id": str,
    "status": Enum["pending", "running", "completed", "failed"],
    "created_at": datetime,
    "completed_at": Optional[datetime],
    "results": List[Review],
    "error": Optional[str]
}
```

## Security Considerations
- User-agent rotation to avoid detection
- Respect robots.txt
- No credential harvesting
- Input sanitization for URLs
- Rate limiting to prevent abuse

## Performance Targets
- < 10s per page scraping time
- Max 3 concurrent browsers
- Memory usage < 512MB per browser
- 95% success rate on valid URLs

## Testing Strategy
- Unit tests for each scraper method
- Integration tests with mock HTML
- MCP protocol compliance tests
- Rate limiting behavior tests
- Memory leak detection

## Rollback Plan
- Feature flag: ENABLE_MCP_SCRAPER
- Graceful degradation to manual upload
- Preserve existing Excel import functionality

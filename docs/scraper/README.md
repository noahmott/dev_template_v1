# MCP Web Scraping Service

## Overview

The MCP Web Scraping Service provides automated web scraping capabilities for restaurant reviews from multiple platforms (Yelp, Google Reviews, TripAdvisor). It's built using FastMCP for MCP protocol support and Puppeteer for JavaScript-rendered content scraping.

## Features

- **Multi-Platform Support**: Scrape reviews from Yelp, Google Reviews, and TripAdvisor
- **MCP Protocol**: Expose scraping tools via MCP for AI assistant integration
- **REST API**: FastAPI endpoints for direct HTTP access
- **Caching**: Redis-based caching to reduce redundant scraping
- **Rate Limiting**: Configurable rate limits to respect website resources
- **Security**: Comprehensive security measures including URL validation and input sanitization
- **Observability**: Detailed metrics and logging for monitoring

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   MCP Client    │     │   REST Client   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│           FastAPI Application           │
├─────────────────────────────────────────┤
│         MCP Server (FastMCP)            │
├─────────────────────────────────────────┤
│        ScraperService (Core)            │
├─────────────────────────────────────────┤
│      PuppeteerClient (Browser)          │
├─────────────────────────────────────────┤
│    Redis Cache    │    Rate Limiter     │
└─────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Redis (optional, for caching)
- Chrome/Chromium browser

### Dependencies

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install key dependencies manually
pip install fastmcp@git+https://github.com/jlowin/fastmcp.git@main
pip install pyppeteer@git+https://github.com/pyppeteer/pyppeteer.git@dev
pip install aioredis tenacity beautifulsoup4
```

### Environment Variables

```bash
# MCP Server Configuration
MCP_SERVER_PORT=3000

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379

# Scraping Configuration
MAX_CONCURRENT_BROWSERS=3
SCRAPING_TIMEOUT_SECONDS=30

# Rate Limiting
MAX_REQUESTS_PER_MINUTE=10
MAX_REQUESTS_PER_HOUR=300
```

## Usage

### Starting the Service

```bash
# Run the FastAPI application
uvicorn app.main:app --reload --port 8000

# Run the MCP server (if separate)
python -m app.mcp.scraper_server
```

### API Endpoints

#### Create Scraping Job

```bash
POST /api/v1/scraping/jobs
Content-Type: application/json

{
  "url": "https://www.yelp.com/biz/restaurant-name",
  "max_pages": 5
}

# Or search and scrape
{
  "business_name": "Joe's Pizza",
  "location": "New York, NY",
  "platform": "yelp"
}
```

#### Get Job Status

```bash
GET /api/v1/scraping/jobs/{job_id}
```

#### Get Job Results

```bash
GET /api/v1/scraping/jobs/{job_id}/results
```

#### Direct Scraping (Synchronous)

```bash
POST /api/v1/scraping/scrape?url=https://www.yelp.com/biz/restaurant&max_pages=3
```

#### Extract Business Info

```bash
POST /api/v1/scraping/extract?url=https://www.yelp.com/biz/restaurant
```

#### Get Metrics

```bash
GET /api/v1/scraping/metrics
```

### MCP Tools

The service exposes the following MCP tools:

1. **scrape_reviews**
   - Scrape reviews from a given URL
   - Parameters: `url`, `max_pages`

2. **search_and_scrape**
   - Search for a business and scrape its reviews
   - Parameters: `business_name`, `location`, `platform`

3. **extract_business_info**
   - Extract business information from a URL
   - Parameters: `url`

4. **get_job_status**
   - Get the status of a scraping job
   - Parameters: `job_id`

5. **get_job_results**
   - Get the results of a completed job
   - Parameters: `job_id`

## Security

### URL Validation

- Only allowed domains (Yelp, Google, TripAdvisor)
- Blocked patterns for executable files and admin pages
- SQL injection and XSS protection

### Rate Limiting

- Per-IP rate limiting
- Burst protection
- Special limits for scraping endpoints

### Input Sanitization

- HTML tag removal
- Control character filtering
- Length limits

## Monitoring

### Metrics

The service tracks:
- Total requests and success/failure rates
- Response times
- Cache hit rates
- Rate limit hits
- Platform-specific statistics
- Error types and frequencies

### Logging

- JSON-formatted logs
- Correlation IDs for request tracing
- Different log levels for debugging
- No sensitive data in logs

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=app --cov-report=term-missing --cov-fail-under=85

# Run specific test suites
pytest tests/test_scrapers/
pytest tests/test_mcp/
pytest tests/test_api/
```

## Troubleshooting

### Common Issues

1. **Pyppeteer Browser Download**
   ```bash
   # Manually download browser
   python -m pyppeteer.install
   ```

2. **Redis Connection**
   - Ensure Redis is running
   - Check REDIS_URL environment variable
   - Service works without Redis (no caching)

3. **Rate Limiting**
   - Check X-RateLimit headers in responses
   - Wait for Retry-After duration
   - Adjust limits in configuration

4. **Robots.txt Compliance**
   - Some URLs may be blocked
   - Check logs for robots.txt blocks
   - Ensure User-Agent is set correctly

## Performance

### Optimization Tips

1. **Caching**: Enable Redis for 24-hour result caching
2. **Concurrent Browsers**: Adjust MAX_CONCURRENT_BROWSERS
3. **Timeouts**: Configure SCRAPING_TIMEOUT_SECONDS
4. **Rate Limits**: Balance between speed and compliance

### Benchmarks

- Average response time: < 10s per page
- Memory usage: < 512MB per browser instance
- Cache hit rate: > 60% after warm-up
- Success rate: > 95% for valid URLs

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

## License

[License information]

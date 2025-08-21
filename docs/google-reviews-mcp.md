# Google Reviews MCP Scraping Service

## Overview

MCP-enabled Google Reviews scraping service built with FastMCP and Puppeteer for automated restaurant review collection.

## Features

- **MCP Protocol Support**: Exposes scraping tools via Model Context Protocol
- **Google Reviews Scraping**: Extract reviews, ratings, dates, and owner responses
- **Business Search**: Find businesses on Google Maps by name and location
- **Business Info Extraction**: Get business details including rating, address, phone
- **Caching**: 24-hour Redis-based caching for reduced API calls
- **Security**: Input sanitization, URL validation, rate limiting
- **Comprehensive Logging**: JSON-structured logging with correlation IDs

## Architecture

```
┌─────────────────┐
│   MCP Client    │
└────────┬────────┘
         │
    MCP Protocol
         │
┌────────▼────────┐
│  MCP Server     │
│ (FastMCP)       │
└────────┬────────┘
         │
┌────────▼────────┐
│ Google Scraper  │
│  (Puppeteer)    │
└────────┬────────┘
         │
┌────────▼────────┐
│  Google Maps    │
└─────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Redis (optional, for caching)
- Chrome/Chromium browser

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export MCP_SERVER_PORT=3000
export REDIS_URL=redis://localhost:6379
export SCRAPING_TIMEOUT_SECONDS=30
export MAX_CONCURRENT_BROWSERS=3
```

## Usage

### Starting the MCP Server

```bash
python -m app.mcp.google_scraper_server
```

The server will start on port 3000 (or configured port).

### Available MCP Tools

#### 1. scrape_google_reviews

Scrape reviews from a Google Maps business page.

```python
{
    "tool": "scrape_google_reviews",
    "parameters": {
        "url": "https://www.google.com/maps/place/Social+House/@28.5383,-81.3792",
        "max_pages": 5  # Approx 20 reviews per page
    }
}
```

**Response:**
```json
[
    {
        "text": "Amazing sushi and great atmosphere!",
        "rating": 5.0,
        "date": "2024-01-15",
        "author": "Sarah Johnson",
        "platform": "google",
        "url": "https://www.google.com/maps/place/Social+House",
        "response": null
    }
]
```

#### 2. search_google_business

Search for a business and scrape its reviews.

```python
{
    "tool": "search_google_business",
    "parameters": {
        "business_name": "Social House",
        "location": "Orlando, FL"
    }
}
```

**Response:**
```json
{
    "id": "job-123",
    "status": "completed",
    "url": "https://www.google.com/maps/place/Social+House",
    "results": [...]
}
```

#### 3. extract_google_business_info

Extract business information from a Google Maps URL.

```python
{
    "tool": "extract_google_business_info",
    "parameters": {
        "url": "https://www.google.com/maps/place/Social+House"
    }
}
```

**Response:**
```json
{
    "name": "Social House",
    "address": "7575 Dr Phillips Blvd, Orlando, FL 32819",
    "phone": "(407) 370-0700",
    "rating": 4.3,
    "review_count": 1842,
    "categories": ["Japanese Restaurant", "Sushi Bar"],
    "url": "https://www.google.com/maps/place/Social+House"
}
```

### REST API Endpoints

The service also exposes REST endpoints for non-MCP access:

#### Search Business
```bash
POST /api/v1/google/search
{
    "business_name": "Social House",
    "location": "Orlando, FL"
}
```

#### Scrape Reviews
```bash
POST /api/v1/google/scrape
{
    "url": "https://www.google.com/maps/place/Social+House",
    "max_pages": 5
}
```

#### Get Business Info
```bash
GET /api/v1/google/business/{business_id}
```

#### Get Job Status
```bash
GET /api/v1/google/jobs/{job_id}
```

#### Cancel Job
```bash
DELETE /api/v1/google/jobs/{job_id}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| MCP_SERVER_PORT | 3000 | MCP server port |
| REDIS_URL | redis://localhost:6379 | Redis connection URL |
| MAX_CONCURRENT_BROWSERS | 3 | Maximum concurrent Puppeteer instances |
| SCRAPING_TIMEOUT_SECONDS | 30 | Page load timeout |
| GOOGLE_RATE_LIMIT | 10 | Requests per minute to Google |
| ENABLE_MCP_SCRAPER | false | Feature flag |

### Rate Limiting

- Maximum 10 requests per minute per domain
- Exponential backoff on 429 responses
- Random delays between requests

## Security

### Input Validation
- URL validation for Google Maps domains only
- Input sanitization to prevent injection
- Maximum input length restrictions

### Compliance
- Respects robots.txt
- Identifies as bot in User-Agent
- No PII storage beyond public review data

### Authentication
- Optional job token verification
- HMAC-based token generation

## Monitoring

### Logging
- JSON-structured logs
- Correlation IDs for request tracking
- Performance metrics included
- ASCII-only (no emojis)

### Metrics
- Scraping duration
- Reviews per second
- Cache hit rates
- Error rates

### Health Checks
```bash
GET /healthz
```

## Testing

### Run Tests
```bash
# All tests
python -m pytest tests/

# Google-specific tests
python -m pytest tests/test_google_reviews_scraper.py

# With coverage
python -m pytest --cov=app --cov-report=term-missing
```

### Test Coverage
- Unit tests for scraper components
- Integration tests with mock HTML
- MCP protocol compliance tests
- Performance and memory tests

## Troubleshooting

### Common Issues

#### Browser Launch Fails
```
Error: Failed to launch browser
Solution: Install Chrome/Chromium or set executablePath
```

#### Rate Limiting
```
Error: 429 Too Many Requests
Solution: Reduce request frequency or increase delays
```

#### No Reviews Found
```
Error: No review elements found
Solution: Check if page structure changed, update selectors
```

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance

### Optimization Tips

1. **Browser Pooling**: Reuse browser instances
2. **Caching**: Use Redis for 24-hour cache
3. **Concurrent Limits**: Adjust MAX_CONCURRENT_BROWSERS
4. **Scroll Optimization**: Limit scroll attempts

### Benchmarks

- Average scraping time: <10s per page
- Memory usage: <512MB per browser
- Success rate: 95% on valid URLs
- Concurrent capacity: 100 requests

## Development

### Project Structure
```
app/
├── mcp/
│   └── google_scraper_server.py    # MCP server
├── scrapers/
│   └── google_reviews_scraper.py   # Puppeteer scraper
├── services/
│   └── google_scraper_service.py   # Business logic
├── api/v1/
│   └── google_reviews.py           # REST endpoints
├── cache/
│   └── google_cache.py             # Caching layer
├── security/
│   └── google_scraper_security.py  # Security measures
└── models/
    └── scraping.py                 # Data models
```

### Adding Features

1. Create feature branch
2. Follow TDD approach
3. Implement with security in mind
4. Add comprehensive logging
5. Update documentation
6. Submit PR

## License

Proprietary - See LICENSE file

## Support

For issues or questions:
- Create GitHub issue
- Check logs for correlation IDs
- Review this documentation

## Changelog

### v1.0.0 (2024-01-21)
- Initial Google Reviews MCP implementation
- Removed Yelp and TripAdvisor support
- Added comprehensive logging
- Security hardening
- Performance optimizations

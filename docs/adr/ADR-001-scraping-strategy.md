# ADR-001: Web Scraping Architecture

## Status
Accepted

## Context
Need to collect restaurant reviews from multiple platforms (Yelp, Google Reviews, TripAdvisor) in real-time. These platforms heavily use JavaScript for content rendering, making traditional HTTP requests insufficient.

## Decision
Use Puppeteer (via pyppeteer) for browser automation with MCP protocol for tool exposure.

## Rationale

### Why Puppeteer over alternatives:
- **Puppeteer vs Selenium**: Better performance, smaller footprint, easier API
- **Puppeteer vs Playwright**: More mature Python port (pyppeteer), lighter weight
- **Puppeteer vs BeautifulSoup alone**: Can handle JavaScript-rendered content

### Why MCP for tool exposure:
- Standardized protocol for AI assistants
- Built-in parameter validation
- Supports async operations
- FastMCP provides clean Python API

### Why Redis for rate limiting:
- Distributed rate limiting across workers
- Built-in TTL for cache expiration
- Fast in-memory operations
- Wide Python ecosystem support

## Consequences

### Positive
- Handle modern JavaScript-heavy sites
- Standardized AI assistant integration
- Scalable rate limiting
- Real-time data collection

### Negative
- Higher resource usage than simple HTTP
- Browser instances require memory management
- Additional Redis dependency
- Potential detection by anti-bot measures

### Mitigation
- Limit concurrent browsers to 3
- Implement browser recycling after N pages
- Use user-agent rotation
- Respect robots.txt and rate limits

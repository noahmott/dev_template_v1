# Scraping Service API Documentation

## Base URL

```
http://localhost:8000/api/v1/scraping
```

## Authentication

Currently, no authentication is required. In production, implement API keys or OAuth.

## Rate Limiting

- **General**: 60 requests/minute, 1000 requests/hour
- **Scraping endpoints**: 10 requests/minute
- **Burst limit**: 10 requests in 5 seconds

Rate limit headers:
- `X-RateLimit-Limit`: Maximum requests per minute
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp for limit reset
- `Retry-After`: Seconds to wait when rate limited (429 response)

## Endpoints

### 1. Create Scraping Job

Create an asynchronous scraping job.

**Endpoint:** `POST /jobs`

**Request Body:**

```json
{
  "url": "string",           // Direct URL to scrape (optional)
  "business_name": "string", // Business name for search (optional)
  "location": "string",      // Location for search (optional)
  "platform": "string",      // Platform: yelp, google, tripadvisor (optional)
  "max_pages": 5            // Maximum pages to scrape (1-20, default: 5)
}
```

Either `url` OR (`business_name`, `location`, `platform`) must be provided.

**Response:** `200 OK`

```json
{
  "job_id": "uuid",
  "status": "PENDING",
  "message": "Scraping job created successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid input
- `403 Forbidden`: URL not allowed
- `429 Too Many Requests`: Rate limit exceeded

### 2. Get Job Status

Retrieve the status of a scraping job.

**Endpoint:** `GET /jobs/{job_id}`

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "status": "COMPLETED",  // PENDING, IN_PROGRESS, COMPLETED, FAILED
  "url": "string",
  "business_name": "string",
  "location": "string",
  "platform": "string",
  "created_at": "2024-01-01T12:00:00",
  "completed_at": "2024-01-01T12:05:00",
  "progress": 100,
  "error": null,
  "results": []  // Empty array, use /results endpoint for data
}
```

**Error Responses:**

- `404 Not Found`: Job not found

### 3. Get Job Results

Retrieve the scraped reviews from a completed job.

**Endpoint:** `GET /jobs/{job_id}/results`

**Response:** `200 OK`

```json
[
  {
    "text": "Great food and service!",
    "rating": 5.0,
    "date": "2024-01-01",
    "author": "John Doe",
    "platform": "yelp",
    "url": "https://www.yelp.com/biz/...",
    "response": "Thank you for your review!"  // Business response if available
  }
]
```

**Error Responses:**

- `404 Not Found`: Job not found
- `400 Bad Request`: Job not completed

### 4. Cancel Job

Cancel a pending or in-progress job.

**Endpoint:** `DELETE /jobs/{job_id}`

**Response:** `200 OK`

```json
{
  "message": "Job cancelled successfully"
}
```

**Error Responses:**

- `404 Not Found`: Job not found
- `400 Bad Request`: Job cannot be cancelled (already completed/failed)

### 5. Direct Scraping

Scrape a URL synchronously without creating a job.

**Endpoint:** `POST /scrape`

**Query Parameters:**

- `url` (required): URL to scrape
- `max_pages` (optional): Maximum pages (1-20, default: 5)

**Response:** `200 OK`

```json
[
  {
    "text": "Review content...",
    "rating": 4.5,
    "date": "2024-01-01",
    "author": "Jane Smith",
    "platform": "google",
    "url": "https://maps.google.com/...",
    "response": null
  }
]
```

**Error Responses:**

- `400 Bad Request`: Invalid URL
- `403 Forbidden`: URL not allowed
- `500 Internal Server Error`: Scraping failed

### 6. Extract Business Info

Extract business information from a URL.

**Endpoint:** `POST /extract`

**Query Parameters:**

- `url` (required): Business page URL

**Response:** `200 OK`

```json
{
  "name": "Joe's Pizza",
  "address": "123 Main St, New York, NY 10001",
  "phone": "+1-212-555-0123",
  "rating": 4.5,
  "review_count": 1234,
  "categories": ["Pizza", "Italian"],
  "url": "https://www.yelp.com/biz/joes-pizza"
}
```

**Error Responses:**

- `400 Bad Request`: Invalid URL
- `403 Forbidden`: URL not allowed
- `404 Not Found`: No business info found
- `500 Internal Server Error`: Extraction failed

### 7. Health Check

Check service health.

**Endpoint:** `GET /health`

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "service": "scraping"
}
```

### 8. Get Metrics

Retrieve service metrics.

**Endpoint:** `GET /metrics`

**Response:** `200 OK`

```json
{
  "total_requests": 1000,
  "successful_scrapes": 950,
  "failed_scrapes": 50,
  "success_rate": 0.95,
  "total_reviews_scraped": 15000,
  "avg_response_time": 8.5,
  "cache_hit_rate": 0.65,
  "rate_limit_hits": 10,
  "robots_txt_blocks": 5,
  "security_blocks": 2,
  "platform_stats": {
    "yelp": {
      "requests": 400,
      "reviews": 6000,
      "failures": 20
    },
    "google": {
      "requests": 350,
      "reviews": 5000,
      "failures": 15
    },
    "tripadvisor": {
      "requests": 250,
      "reviews": 4000,
      "failures": 15
    }
  },
  "error_types": {
    "timeout": 25,
    "connection": 15,
    "parsing": 10
  }
}
```

## Data Models

### Review

```typescript
interface Review {
  text: string;           // Review content
  rating: number;         // Rating (0-5)
  date: string;          // Date (YYYY-MM-DD format)
  author: string;        // Reviewer name
  platform: string;      // Platform name
  url: string;          // Source URL
  response?: string;    // Business response (optional)
}
```

### BusinessInfo

```typescript
interface BusinessInfo {
  name: string;           // Business name
  address?: string;       // Physical address
  phone?: string;         // Phone number
  rating?: number;        // Average rating
  review_count?: number;  // Total reviews
  categories: string[];   // Business categories
  url: string;           // Business page URL
}
```

### ScrapingJob

```typescript
interface ScrapingJob {
  id: string;                    // Job UUID
  status: JobStatus;             // Job status
  url?: string;                  // Target URL
  business_name?: string;        // Business name
  location?: string;             // Location
  platform?: string;             // Platform
  max_pages: number;             // Max pages to scrape
  created_at: string;            // Creation timestamp
  completed_at?: string;         // Completion timestamp
  progress: number;              // Progress percentage
  error?: string;                // Error message if failed
  results: Review[];             // Scraped reviews
}
```

### JobStatus

```typescript
enum JobStatus {
  PENDING = "PENDING",
  IN_PROGRESS = "IN_PROGRESS",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED"
}
```

## Error Handling

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Codes

- `400`: Bad Request - Invalid input parameters
- `403`: Forbidden - Security violation or blocked resource
- `404`: Not Found - Resource doesn't exist
- `415`: Unsupported Media Type - Invalid content type
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error - Server-side error

## Examples

### Example 1: Scrape Yelp Reviews

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.yelp.com/biz/joes-pizza-new-york",
    "max_pages": 3
  }'
```

### Example 2: Search and Scrape

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Joe'\''s Pizza",
    "location": "New York, NY",
    "platform": "yelp"
  }'
```

### Example 3: Check Job Status

```bash
curl "http://localhost:8000/api/v1/scraping/jobs/123e4567-e89b-12d3-a456-426614174000"
```

### Example 4: Get Results

```bash
curl "http://localhost:8000/api/v1/scraping/jobs/123e4567-e89b-12d3-a456-426614174000/results"
```

## WebSocket Support (Future)

Future versions will support WebSocket connections for real-time job status updates.

## Pagination (Future)

Future versions will support pagination for large result sets using:
- `limit`: Number of results per page
- `offset`: Starting position
- `cursor`: Cursor-based pagination

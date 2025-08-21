from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.scraping import router as scraping_router
from app.middleware.rate_limiter import RateLimiterMiddleware

app = FastAPI(
    title="Restaurant Review Sentiment Analysis API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Configure for production
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(
    RateLimiterMiddleware,
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_size=10,
)

# Include routers
app.include_router(scraping_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

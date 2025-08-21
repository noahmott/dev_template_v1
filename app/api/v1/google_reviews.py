"""FastAPI endpoints for Google Reviews scraping."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/google", tags=["google-reviews"])


class GoogleSearchRequest(BaseModel):
    """Request model for Google business search."""

    business_name: str
    location: str


class GoogleScrapeRequest(BaseModel):
    """Request model for Google Reviews scraping."""

    url: str
    max_pages: int = 5


@router.post("/search")
async def search_google_business(request: GoogleSearchRequest):
    """Search for a business on Google Maps.

    Args:
        request: Search request with business name and location

    Returns:
        Scraping job with Google Maps URL
    """
    pass


@router.post("/scrape")
async def scrape_google_reviews(request: GoogleScrapeRequest):
    """Scrape reviews from a Google Maps business page.

    Args:
        request: Scrape request with URL and max pages

    Returns:
        List of scraped reviews
    """
    pass


@router.get("/business/{business_id}")
async def get_google_business_info(business_id: str):
    """Get business information from Google Maps.

    Args:
        business_id: Google business ID or URL

    Returns:
        Business information
    """
    pass

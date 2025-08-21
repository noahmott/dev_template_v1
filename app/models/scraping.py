"""Data models for scraping operations."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Scraping job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Review(BaseModel):
    """Review data model."""

    text: str
    rating: float
    date: str
    author: str
    platform: str
    url: str
    response: str | None = None


class BusinessInfo(BaseModel):
    """Business information model."""

    name: str
    address: str | None = None
    phone: str | None = None
    rating: float | None = None
    review_count: int | None = None
    categories: list[str] = Field(default_factory=list)
    url: str


class ScrapingJob(BaseModel):
    """Scraping job model."""

    id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    results: list[Review] | None = None
    error: str | None = None
    url: str | None = None
    webhook_url: str | None = None

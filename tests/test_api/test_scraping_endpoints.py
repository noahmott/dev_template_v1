"""Tests for scraping API endpoints."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_scraper():
    """Mock scraper service."""
    with patch("app.services.scraper_service.ScraperService") as mock:
        service = mock.return_value
        service.create_job = AsyncMock()
        service.get_job = AsyncMock()
        service.get_job_results = AsyncMock()
        service.cancel_job = AsyncMock()
        yield service


class TestScrapingEndpoints:
    """Test scraping API endpoints."""

    def test_create_scraping_job(self, client, mock_scraper):
        """Test creating a new scraping job."""
        job_id = str(uuid.uuid4())
        mock_scraper.create_job.return_value = {
            "id": job_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        response = client.post(
            "/api/v1/scraping/jobs", json={"url": "https://yelp.com/biz/test", "max_pages": 3}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "pending"

    def test_create_job_invalid_url(self, client):
        """Test creating job with invalid URL."""
        response = client.post("/api/v1/scraping/jobs", json={"url": "not-a-url", "max_pages": 1})

        assert response.status_code == 422
        assert "Invalid URL" in response.json()["detail"]

    def test_get_job_status(self, client, mock_scraper):
        """Test getting job status."""
        job_id = str(uuid.uuid4())
        mock_scraper.get_job.return_value = {
            "id": job_id,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "progress": 50,
        }

        response = client.get(f"/api/v1/scraping/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "running"
        assert data["progress"] == 50

    def test_get_nonexistent_job(self, client, mock_scraper):
        """Test getting non-existent job."""
        mock_scraper.get_job.return_value = None

        response = client.get(f"/api/v1/scraping/jobs/{uuid.uuid4()}")

        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    def test_get_job_results(self, client, mock_scraper):
        """Test getting job results."""
        job_id = str(uuid.uuid4())
        mock_scraper.get_job_results.return_value = {
            "id": job_id,
            "status": "completed",
            "results": [
                {"text": "Great food!", "rating": 5.0, "date": "2024-01-01", "author": "John Doe"}
            ],
        }

        response = client.get(f"/api/v1/scraping/jobs/{job_id}/results")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["text"] == "Great food!"

    def test_get_results_job_not_complete(self, client, mock_scraper):
        """Test getting results for incomplete job."""
        mock_scraper.get_job_results.return_value = {
            "id": str(uuid.uuid4()),
            "status": "running",
            "results": None,
        }

        response = client.get(f"/api/v1/scraping/jobs/{uuid.uuid4()}/results")

        assert response.status_code == 202
        assert "Job still running" in response.json()["detail"]

    def test_cancel_job(self, client, mock_scraper):
        """Test canceling a job."""
        job_id = str(uuid.uuid4())
        mock_scraper.cancel_job.return_value = True

        response = client.delete(f"/api/v1/scraping/jobs/{job_id}")

        assert response.status_code == 204
        mock_scraper.cancel_job.assert_called_once_with(job_id)

    def test_cancel_nonexistent_job(self, client, mock_scraper):
        """Test canceling non-existent job."""
        mock_scraper.cancel_job.return_value = False

        response = client.delete(f"/api/v1/scraping/jobs/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_rate_limiting(self, client, mock_scraper):
        """Test rate limiting on endpoints."""
        # Make 11 rapid requests (limit is 10)
        for i in range(11):
            response = client.post(
                "/api/v1/scraping/jobs",
                json={"url": f"https://yelp.com/biz/test{i}", "max_pages": 1},
            )

            if i < 10:
                assert response.status_code in [201, 200]
            else:
                assert response.status_code == 429
                assert "Rate limit exceeded" in response.json()["detail"]

    def test_webhook_callback(self, client, mock_scraper):
        """Test webhook callback on job completion."""
        job_id = str(uuid.uuid4())
        webhook_url = "https://example.com/webhook"

        mock_scraper.create_job.return_value = {
            "id": job_id,
            "status": "pending",
            "webhook_url": webhook_url,
        }

        response = client.post(
            "/api/v1/scraping/jobs",
            json={"url": "https://yelp.com/biz/test", "max_pages": 1, "webhook_url": webhook_url},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["webhook_url"] == webhook_url

    def test_batch_scraping(self, client, mock_scraper):
        """Test batch scraping multiple URLs."""
        mock_scraper.create_batch_job.return_value = {
            "batch_id": str(uuid.uuid4()),
            "jobs": [
                {"id": str(uuid.uuid4()), "url": "https://yelp.com/biz/1"},
                {"id": str(uuid.uuid4()), "url": "https://yelp.com/biz/2"},
            ],
        }

        response = client.post(
            "/api/v1/scraping/batch",
            json={"urls": ["https://yelp.com/biz/1", "https://yelp.com/biz/2"], "max_pages": 1},
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["jobs"]) == 2

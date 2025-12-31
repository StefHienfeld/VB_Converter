"""
Integration tests for VB_Converter API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_returns_200(self, client: TestClient):
        """Health endpoint should return 200 with status info."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert "timestamp" in data

    def test_liveness_returns_alive(self, client: TestClient):
        """Liveness probe should return alive status."""
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_returns_status(self, client: TestClient):
        """Readiness probe should return ready status with checks."""
        response = client.get("/api/health/ready")
        # May be 200 or 503 depending on SpaCy model availability
        assert response.status_code in [200, 503]

        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_security_headers_present(self, client: TestClient):
        """Security headers should be present in responses."""
        response = client.get("/api/health")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-XSS-Protection" in response.headers

    def test_request_id_header(self, client: TestClient):
        """Response should include X-Request-ID header."""
        response = client.get("/api/health")
        assert "X-Request-ID" in response.headers


class TestCacheEndpoints:
    """Tests for cache management endpoints."""

    def test_cache_stats(self, client: TestClient):
        """Cache stats endpoint should return statistics."""
        response = client.get("/api/cache/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_entries" in data or "status" in data


class TestAnalysisEndpoints:
    """Tests for analysis workflow endpoints."""

    def test_status_invalid_job_id(self, client: TestClient):
        """Status endpoint should return 404 for invalid job ID."""
        response = client.get("/api/status/invalid-job-id-12345")
        assert response.status_code == 404

    def test_results_invalid_job_id(self, client: TestClient):
        """Results endpoint should return 404 for invalid job ID."""
        response = client.get("/api/results/invalid-job-id-12345")
        assert response.status_code == 404

    def test_report_invalid_job_id(self, client: TestClient):
        """Report endpoint should return 404 for invalid job ID."""
        response = client.get("/api/report/invalid-job-id-12345")
        assert response.status_code == 404

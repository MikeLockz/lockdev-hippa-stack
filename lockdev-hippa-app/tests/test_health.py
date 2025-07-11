"""
Tests for health endpoints.
"""
import pytest


def test_health_check(client):
    """Test basic health check."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_liveness_check(client):
    """Test liveness check."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_startup_check(client):
    """Test startup check."""
    response = client.get("/health/startup")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "timestamp" in data


def test_security_headers(client):
    """Test security headers are present."""
    response = client.get("/health/")
    assert response.status_code == 200
    
    # Check security headers
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "X-XSS-Protection" in response.headers
    assert "Strict-Transport-Security" in response.headers
    assert "Content-Security-Policy" in response.headers
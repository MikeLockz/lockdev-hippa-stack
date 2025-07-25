"""
Health check endpoints for HIPAA-compliant application.
"""

import os
from datetime import datetime, UTC
from typing import Dict, Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel


logger = structlog.get_logger()
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime
    version: str
    environment: str


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""

    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, Any]


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development"),
    )


@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check() -> DetailedHealthResponse:
    """Readiness check including database connectivity."""
    services = {}
    overall_status = "healthy"

    # Check database connection (optional)
    try:
        from ..utils.database import get_db_session

        db_gen = get_db_session()
        db = await db_gen.__anext__()

        # Simple query to check database connectivity
        from sqlalchemy import text

        result = await db.execute(text("SELECT 1"))
        if result:
            services["database"] = {
                "status": "healthy",
                "response_time_ms": 0,  # Measure actual response time
            }
        else:
            services["database"] = {
                "status": "unhealthy",
                "error": "Query failed",
            }

        await db_gen.aclose()
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        services["database"] = {
            "status": "unavailable",
            "error": "Database not connected",
        }

    # Check external services (add as needed)
    services["external_apis"] = {"status": "healthy"}

    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.now(UTC),
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development"),
        services=services,
    )


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    """Liveness check for Kubernetes/ECS."""
    return {"status": "alive", "timestamp": datetime.now(UTC)}


@router.get("/startup")
async def startup_check() -> dict[str, Any]:
    """Startup check for container orchestration."""
    # Add any startup-specific checks here
    return {"status": "ready", "timestamp": datetime.now(UTC)}

"""
Health check endpoints for HIPAA-compliant application.
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.database import get_db_session


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
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development")
    )


@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check():
    """Readiness check including database connectivity."""
    services = {}
    overall_status = "healthy"
    
    # Check database connection (optional)
    try:
        from ..utils.database import get_db_session
        db_gen = get_db_session()
        db = await db_gen.__anext__()
        
        # Simple query to check database connectivity
        result = await db.execute("SELECT 1")
        if result:
            services["database"] = {
                "status": "healthy",
                "response_time_ms": 0  # You could measure actual response time
            }
        else:
            services["database"] = {"status": "unhealthy", "error": "Query failed"}
        
        await db_gen.aclose()
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        services["database"] = {"status": "unavailable", "error": "Database not connected"}
    
    # Check external services (add as needed)
    services["external_apis"] = {"status": "healthy"}
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development"),
        services=services
    )


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes/ECS."""
    return {"status": "alive", "timestamp": datetime.utcnow()}


@router.get("/startup")
async def startup_check():
    """Startup check for container orchestration."""
    # Add any startup-specific checks here
    return {"status": "ready", "timestamp": datetime.utcnow()}
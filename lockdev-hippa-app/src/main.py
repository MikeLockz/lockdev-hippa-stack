"""
HIPAA-compliant FastAPI application main module.
"""
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

from .routes.health import router as health_router
from .routes.api import router as api_router
from .utils.security import setup_security_headers
from .utils.logging import setup_logging
from .utils.database import init_database


# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint"]
)
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    setup_logging()
    logger = structlog.get_logger()

    logger.info("Starting HIPAA-compliant application", version="0.1.0")

    # Initialize database (optional - application can run without database)
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(
            "Database initialization failed - " "application will run without database",
            error=str(e),
        )

    yield

    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="HIPAA-Compliant Healthcare API",
        description="A secure, HIPAA-compliant healthcare data API",
        version="0.1.0",
        docs_url=("/docs" if os.getenv("ENVIRONMENT") == "development" else None),
        redoc_url=("/redoc" if os.getenv("ENVIRONMENT") == "development" else None),
        lifespan=lifespan,
    )

    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure based on your domain
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://yourdomain.com"],  # Configure for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        return setup_security_headers(response)

    # Request/response logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger = structlog.get_logger()

        # Log request (be careful not to log sensitive data)
        logger.info(
            "Request received",
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent", ""),
        )

        # Metrics
        REQUEST_COUNT.labels(
            method=request.method, endpoint=str(request.url.path)
        ).inc()

        with REQUEST_DURATION.time():
            response = await call_next(request)

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
        )

        return response

    # Include routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(api_router, prefix="/api/v1", tags=["api"])

    # Metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = structlog.get_logger()
        logger.error(
            "Unhandled exception",
            method=request.method,
            url=str(request.url),
            error=str(exc),
        )

        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # nosec B104 - Required for containerized deployment
        port=8000,
        log_level="info",
        access_log=True,
    )

"""
HIPAA-compliant FastAPI application main module.
"""

import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Awaitable

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
from .routes.auth import router as auth_router
from .utils.security import setup_security_headers
from .utils.logging import setup_logging
from .utils.database import init_database
from .auth import AuthConfig, create_auth_provider, AuthenticationProvider


# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint"]
)
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration")

# Global authentication provider instance
auth_provider: AuthenticationProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management."""
    global auth_provider
    
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

    # Initialize authentication provider
    try:
        config = AuthConfig()
        auth_provider = await create_auth_provider(config.provider_type)
        
        # Validate provider health
        health = await auth_provider.health_check()
        if not health.get("is_healthy", False):
            logger.error(
                "Authentication provider health check failed", 
                health=health,
                provider_type=config.provider_type.value
            )
            raise RuntimeError("Authentication provider unavailable")
        
        logger.info(
            "Authentication provider initialized", 
            provider_type=config.provider_type.value,
            version=health.get("version", "unknown"),
            health=health
        )
        
    except Exception as e:
        logger.error(
            "Failed to initialize authentication provider",
            error=str(e)
        )
        # Don't fail startup - allow app to run with degraded functionality
        auth_provider = None

    yield

    # Shutdown
    if auth_provider:
        try:
            await auth_provider.cleanup()
            logger.info("Authentication provider cleanup completed")
        except Exception as e:
            logger.warning(
                "Authentication provider cleanup failed",
                error=str(e)
            )
    
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
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        return setup_security_headers(response)

    # Enhanced authentication middleware
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Enhanced authentication middleware with user context injection."""
        start_time = time.time()
        
        # Initialize request state
        request.state.user = None
        
        # Extract and validate token if present and auth provider is available
        if auth_provider and "authorization" in request.headers:
            auth_header = request.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    auth_user = await auth_provider.validate_token(token)
                    request.state.user = auth_user
                except Exception:
                    # Token validation failed - let endpoints handle it
                    pass
        
        response = await call_next(request)
        
        # Log request completion with timing
        duration = time.time() - start_time
        logger = structlog.get_logger()
        
        # Enhanced logging with user context
        log_data = {
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": getattr(request.state, "user", {}).id if getattr(request.state, "user", None) else None
        }
        
        # Log to auth provider if available
        if auth_provider:
            try:
                await auth_provider.log_authentication_event(
                    user_id=log_data["user_id"],
                    event_type="api_request",
                    ip_address=request.client.host if request.client else "unknown",
                    details=log_data
                )
            except Exception as e:
                logger.warning("Failed to log to auth provider", error=str(e))
        
        return response

    # Request/response logging middleware
    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
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
    app.include_router(auth_router, prefix="/auth", tags=["authentication"])

    # Metrics endpoint
    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
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

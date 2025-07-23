"""
Main API routes for HIPAA-compliant application.
"""

from datetime import datetime
from typing import Optional, Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..utils.database import get_db_session
from ..utils.security import get_current_user
from ..models.user import User


logger = structlog.get_logger()
router = APIRouter()


class HelloResponse(BaseModel):
    """Hello world response model."""

    message: str
    timestamp: datetime
    user_id: Optional[str] = None


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    created_at: datetime
    is_active: bool


@router.get("/hello", response_model=HelloResponse)
async def hello_world(
    current_user: Optional[User] = Depends(get_current_user),
) -> HelloResponse:
    """Hello world endpoint with optional authentication."""
    logger.info(
        "Hello world endpoint accessed",
        user_id=current_user.id if current_user else None,
    )

    return HelloResponse(
        message="Hello from HIPAA-compliant healthcare API!",
        timestamp=datetime.utcnow(),
        user_id=str(current_user.id) if current_user else None,
    )


@router.get("/secure", response_model=HelloResponse)
async def secure_endpoint(
    current_user: User = Depends(get_current_user),
) -> HelloResponse:
    """Secure endpoint requiring authentication."""
    logger.info("Secure endpoint accessed", user_id=current_user.id)

    return HelloResponse(
        message="This is a secure endpoint - you are authenticated!",
        timestamp=datetime.utcnow(),
        user_id=str(current_user.id),
    )


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Get current user information."""
    logger.info("User info requested", user_id=current_user.id)

    return UserResponse(
        id=str(current_user.id),
        email=str(current_user.email),
        created_at=current_user.created_at,  # type: ignore[arg-type]
        is_active=bool(current_user.is_active),
    )


@router.get("/audit-log")
async def get_audit_log(
    current_user: User = Depends(get_current_user), limit: int = 10
) -> dict[str, Any]:
    """Get audit log entries (HIPAA compliance requirement)."""
    logger.info("Audit log requested", user_id=current_user.id, limit=limit)

    # In a real application, you would fetch from an audit log table
    # This is a placeholder implementation
    return {
        "message": "Audit log functionality - placeholder",
        "note": "In production, this would return actual audit trail data",
        "user_id": current_user.id,
        "timestamp": datetime.utcnow(),
    }

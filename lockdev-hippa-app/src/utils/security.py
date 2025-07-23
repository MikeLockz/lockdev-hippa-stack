"""
Security utilities for HIPAA compliance.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..utils.database import get_db_session


logger = structlog.get_logger()

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def setup_security_headers(response: Response) -> Response:
    """Add security headers to response for HIPAA compliance."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "media-src 'self'; "
        "frame-src 'none';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), "
        "payment=(), usb=(), screen-wake-lock=(), "
        "web-share=(), cross-origin-isolated=()"
    )

    return response


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """Get current user from JWT token."""
    if not credentials:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # In a real application, you would fetch the user from the database
    # For now, we'll create a mock user
    user = User(
        id=user_id,
        email=f"user{user_id}@example.com",
        created_at=datetime.utcnow(),
        is_active=True,
    )

    if user is None:
        raise credentials_exception

    logger.info("User authenticated", user_id=user.id)
    return user


def require_auth(current_user: User = Depends(get_current_user)) -> User:
    """Require authentication - raises exception if not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

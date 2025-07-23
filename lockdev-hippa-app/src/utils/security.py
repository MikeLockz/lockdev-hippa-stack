"""
Security utilities for HIPAA compliance.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import uuid

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..models.user import User
from ..models.audit_log import AuditLog
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
    """Get current user from JWT token with real database lookup."""
    if not credentials:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Log authentication attempt for HIPAA audit
    client_ip = "unknown"  # In production, extract from request headers
    
    try:
        # Decode and validate JWT token
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id_str = payload.get("sub")
        if not isinstance(user_id_str, str) or user_id_str is None:
            await _log_auth_failure(db, None, "Invalid token format", client_ip)
            raise credentials_exception
            
        # Convert string UUID to UUID object
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            await _log_auth_failure(db, user_id_str, "Invalid UUID format", client_ip)
            raise credentials_exception
            
    except JWTError as e:
        await _log_auth_failure(db, None, f"JWT decode error: {str(e)}", client_ip)
        raise credentials_exception

    # Fetch user from database
    try:
        stmt = select(User).where(
            User.id == user_id,
            User.is_active == True  # Only active users
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            await _log_auth_failure(db, str(user_id), "User not found or inactive", client_ip)
            raise credentials_exception
            
        # Check if account is locked
        if user.account_locked_until and user.account_locked_until > datetime.utcnow():
            await _log_auth_failure(db, str(user_id), "Account locked", client_ip)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Update last login and log successful authentication
        user.last_login = datetime.utcnow()
        await db.commit()
        
        await _log_auth_success(db, str(user_id), client_ip)
        logger.info("User authenticated successfully", 
                   user_id=str(user.id), 
                   email=user.email)
        
        return user
        
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Database error during authentication", 
                    user_id=str(user_id), 
                    error=str(e))
        await _log_auth_failure(db, str(user_id), f"Database error: {str(e)}", client_ip)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        await db.rollback()
        logger.error("Unexpected error during authentication", 
                    user_id=str(user_id), 
                    error=str(e))
        await _log_auth_failure(db, str(user_id), f"Unexpected error: {str(e)}", client_ip)
        raise credentials_exception


async def _log_auth_success(db: AsyncSession, user_id: str, client_ip: str) -> None:
    """Log successful authentication for HIPAA audit trail."""
    try:
        audit_log = AuditLog(
            action="authentication_success",
            resource_type="user",
            resource_id=user_id,
            user_id=uuid.UUID(user_id),
            ip_address=client_ip,
            outcome="success",
            details={
                "authentication_method": "JWT",
                "timestamp": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        await db.commit()
    except Exception as e:
        logger.error("Failed to log authentication success", 
                    user_id=user_id, error=str(e))
        # Don't raise - we don't want audit logging failures to break auth


async def _log_auth_failure(db: AsyncSession, user_id: Optional[str], 
                           reason: str, client_ip: str) -> None:
    """Log failed authentication for HIPAA audit trail."""
    try:
        audit_log = AuditLog(
            action="authentication_failure",
            resource_type="user",
            resource_id=user_id,
            user_id=uuid.UUID(user_id) if user_id else None,
            ip_address=client_ip,
            outcome="failure",
            details={
                "reason": reason,
                "authentication_method": "JWT",
                "timestamp": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        await db.commit()
    except Exception as e:
        logger.error("Failed to log authentication failure", 
                    user_id=user_id, error=str(e))
        # Don't raise - we don't want audit logging failures to break auth


def require_auth(current_user: User = Depends(get_current_user)) -> User:
    """Require authentication - raises exception if not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    client_ip = "unknown"  # In production, extract from request headers
    
    try:
        # Find user by email
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            await _log_auth_failure(db, None, f"User not found: {email}", client_ip)
            return None
            
        # Check if account is locked
        if user.account_locked_until and user.account_locked_until > datetime.utcnow():
            await _log_auth_failure(db, str(user.id), "Account locked", client_ip)
            return None
            
        # Verify password
        if not verify_password(password, user.hashed_password):
            # Increment failed login attempts
            try:
                attempts = int(user.login_attempts) + 1
                user.login_attempts = str(attempts)
                
                # Lock account after 5 failed attempts for 30 minutes
                if attempts >= 5:
                    user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
                    await _log_auth_failure(db, str(user.id), 
                                          f"Account locked after {attempts} failed attempts", 
                                          client_ip)
                else:
                    await _log_auth_failure(db, str(user.id), 
                                          f"Invalid password (attempt {attempts})", 
                                          client_ip)
                
                await db.commit()
            except ValueError:
                # Handle case where login_attempts is not a valid integer
                user.login_attempts = "1"
                await db.commit()
                await _log_auth_failure(db, str(user.id), "Invalid password (attempt 1)", client_ip)
            
            return None
        
        # Check if user is active
        if not user.is_active:
            await _log_auth_failure(db, str(user.id), "User account inactive", client_ip)
            return None
            
        # Reset failed login attempts on successful authentication
        user.login_attempts = "0"
        user.last_login = datetime.utcnow()
        await db.commit()
        
        await _log_auth_success(db, str(user.id), client_ip)
        return user
        
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Database error during user authentication", 
                    email=email, error=str(e))
        return None
    except Exception as e:
        await db.rollback()
        logger.error("Unexpected error during user authentication", 
                    email=email, error=str(e))
        return None

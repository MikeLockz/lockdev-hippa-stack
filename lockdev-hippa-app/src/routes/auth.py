"""
Authentication routes for vendor-agnostic authentication system.

This module provides authentication endpoints including login, logout, token refresh,
password management, and MFA operations with full HIPAA compliance.
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    AuthUser, 
    AuthToken, 
    AuthResult,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    UserNotFoundError,
    MFARequiredError,
    AuthorizationError
)

logger = structlog.get_logger()
router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool = False


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""
    token: str = Field(..., min_length=1, max_length=512)
    new_password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str = Field(..., min_length=1, max_length=512)


class MFASetupResponse(BaseModel):
    """MFA setup response model."""
    qr_code_url: str
    backup_codes: list[str]
    secret: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request model."""
    code: str = Field(..., min_length=6, max_length=8)
    backup_code: Optional[str] = Field(None, min_length=8, max_length=12)


class AuthResponse(BaseModel):
    """Standard authentication response."""
    message: str
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


async def get_auth_provider():
    """Get the current authentication provider from main app."""
    # Import here to avoid circular imports
    from ..main import auth_provider
    if not auth_provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication provider not initialized"
        )
    return auth_provider


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request."""
    return request.headers.get("user-agent", "unknown")


@router.post("/login", response_model=AuthToken, tags=["authentication"])
async def login(
    request: LoginRequest,
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthToken:
    """
    Authenticate user with email and password.
    
    Returns JWT access and refresh tokens on successful authentication.
    Includes comprehensive audit logging for HIPAA compliance.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Authenticate with vendor-agnostic provider
        auth_result = await provider.authenticate(
            email=request.email,
            password=request.password,
            remember_me=request.remember_me
        )
        
        # Log successful authentication
        await provider.log_authentication_event(
            user_id=auth_result.user.id,
            event_type="login_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "method": "password",
                "remember_me": request.remember_me,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "User login successful",
            user_id=auth_result.user.id,
            email=request.email,
            ip_address=client_ip
        )
        
        return auth_result.token
        
    except InvalidCredentialsError as e:
        # Log failed authentication
        await provider.log_authentication_event(
            user_id=None,
            event_type="login_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "reason": "invalid_credentials",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Login failed - invalid credentials",
            email=request.email,
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    except UserNotFoundError as e:
        # Log failed authentication (but don't reveal user doesn't exist)
        await provider.log_authentication_event(
            user_id=None,
            event_type="login_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "reason": "user_not_found",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Login failed - user not found",
            email=request.email,
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    except MFARequiredError as e:
        # Log MFA requirement
        await provider.log_authentication_event(
            user_id=e.user_id,
            event_type="mfa_required",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "mfa_methods": e.available_methods,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Login requires MFA",
            email=request.email,
            user_id=e.user_id,
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                "message": "Multi-factor authentication required",
                "mfa_token": e.mfa_token,
                "available_methods": e.available_methods
            }
        )
        
    except AuthenticationError as e:
        # Log general authentication error
        await provider.log_authentication_event(
            user_id=None,
            event_type="login_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.error(
            "Login failed - authentication error",
            email=request.email,
            error=str(e),
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )


@router.post("/refresh", response_model=AuthToken, tags=["authentication"])
async def refresh_token(
    request: RefreshTokenRequest,
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthToken:
    """
    Refresh access token using refresh token.
    
    Returns new JWT access and refresh tokens.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Refresh token with vendor-agnostic provider
        new_token = await provider.refresh_token(request.refresh_token)
        
        # Extract user ID from token for logging
        user_id = new_token.user_id if hasattr(new_token, 'user_id') else None
        
        # Log successful token refresh
        await provider.log_authentication_event(
            user_id=user_id,
            event_type="token_refresh_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Token refresh successful",
            user_id=user_id,
            ip_address=client_ip
        )
        
        return new_token
        
    except TokenExpiredError as e:
        # Log expired token
        await provider.log_authentication_event(
            user_id=None,
            event_type="token_refresh_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "token_expired",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Token refresh failed - token expired",
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
        
    except AuthenticationError as e:
        # Log refresh error
        await provider.log_authentication_event(
            user_id=None,
            event_type="token_refresh_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "invalid_token",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Token refresh failed - invalid token",
            error=str(e),
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout", response_model=AuthResponse, tags=["authentication"])
async def logout(
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthResponse:
    """
    Logout user and invalidate tokens.
    
    Note: This endpoint will work even if the user dependency fails,
    allowing logout even with invalid/expired tokens.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Try to get current user for logging, but don't fail if not available
    current_user = None
    auth_header = http_request.headers.get("authorization", "")
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            current_user = await provider.validate_token(token)
        except Exception:
            # Token validation failed, but we still want to allow logout
            pass
    
    try:
        # Logout with vendor-agnostic provider
        await provider.logout(token if auth_header.startswith("Bearer ") else None)
        
        # Log successful logout
        await provider.log_authentication_event(
            user_id=current_user.id if current_user else None,
            event_type="logout_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "User logout successful",
            user_id=current_user.id if current_user else None,
            ip_address=client_ip
        )
        
        return AuthResponse(
            message="Successfully logged out",
            success=True
        )
        
    except Exception as e:
        # Log logout error but still return success (logout should always work)
        await provider.log_authentication_event(
            user_id=current_user.id if current_user else None,
            event_type="logout_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Logout error (but returning success)",
            user_id=current_user.id if current_user else None,
            error=str(e),
            ip_address=client_ip
        )
        
        # Still return success - logout should always appear to work
        return AuthResponse(
            message="Successfully logged out",
            success=True
        )


@router.get("/me", response_model=AuthUser, tags=["user"])
async def get_current_user_info(
    request: Request,
    provider=Depends(get_auth_provider)
) -> AuthUser:
    """
    Get current authenticated user information.
    
    Requires valid authentication token.
    """
    # Import here to avoid circular imports
    from ..utils.auth_dependencies import require_auth
    current_user = await require_auth(request, provider)
    
    logger.info(
        "User info requested",
        user_id=current_user.id
    )
    
    return current_user


@router.post("/change-password", response_model=AuthResponse, tags=["user"])
async def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthResponse:
    """
    Change user password.
    
    Requires valid authentication and current password verification.
    """
    from ..utils.auth_dependencies import require_auth
    current_user = await require_auth(http_request, provider)
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Change password with vendor-agnostic provider
        await provider.change_password(
            user_id=current_user.id,
            current_password=request.current_password,
            new_password=request.new_password
        )
        
        # Log successful password change
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="password_change_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Password change successful",
            user_id=current_user.id,
            ip_address=client_ip
        )
        
        return AuthResponse(
            message="Password changed successfully",
            success=True
        )
        
    except InvalidCredentialsError as e:
        # Log failed password change
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="password_change_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "invalid_current_password",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Password change failed - invalid current password",
            user_id=current_user.id,
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
        
    except AuthenticationError as e:
        # Log password change error
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="password_change_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.error(
            "Password change failed - authentication error",
            user_id=current_user.id,
            error=str(e),
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change service temporarily unavailable"
        )


@router.post("/forgot-password", response_model=AuthResponse, tags=["password-reset"])
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthResponse:
    """
    Initiate password reset process.
    
    Sends password reset email if user exists.
    Always returns success to prevent user enumeration.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Initiate password reset with vendor-agnostic provider
        await provider.initiate_password_reset(request.email)
        
        # Log password reset request
        await provider.log_authentication_event(
            user_id=None,  # Don't log user ID to prevent enumeration
            event_type="password_reset_requested",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Password reset requested",
            email=request.email,
            ip_address=client_ip
        )
        
    except Exception as e:
        # Log error but still return success to prevent enumeration
        await provider.log_authentication_event(
            user_id=None,
            event_type="password_reset_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "email": request.email,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Password reset error",
            email=request.email,
            error=str(e),
            ip_address=client_ip
        )
    
    # Always return success to prevent user enumeration
    return AuthResponse(
        message="If an account with that email exists, a password reset link has been sent",
        success=True
    )


@router.post("/reset-password", response_model=AuthResponse, tags=["password-reset"])
async def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    provider=Depends(get_auth_provider)
) -> AuthResponse:
    """
    Complete password reset process using reset token.
    
    Sets new password if reset token is valid.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Reset password with vendor-agnostic provider
        result = await provider.reset_password(
            reset_token=request.token,
            new_password=request.new_password
        )
        
        # Log successful password reset
        await provider.log_authentication_event(
            user_id=result.user_id if hasattr(result, 'user_id') else None,
            event_type="password_reset_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Password reset successful",
            ip_address=client_ip
        )
        
        return AuthResponse(
            message="Password has been reset successfully",
            success=True
        )
        
    except TokenExpiredError as e:
        # Log expired reset token
        await provider.log_authentication_event(
            user_id=None,
            event_type="password_reset_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "token_expired",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Password reset failed - token expired",
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired"
        )
        
    except AuthenticationError as e:
        # Log invalid reset token
        await provider.log_authentication_event(
            user_id=None,
            event_type="password_reset_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "invalid_token",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Password reset failed - invalid token",
            error=str(e),
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )


@router.get("/mfa/setup", response_model=MFASetupResponse, tags=["mfa"])
async def setup_mfa(
    request: Request,
    provider=Depends(get_auth_provider)
) -> MFASetupResponse:
    """
    Set up multi-factor authentication for current user.
    
    Returns QR code URL and backup codes for MFA setup.
    """
    from ..utils.auth_dependencies import require_auth
    current_user = await require_auth(request, provider)
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Setup MFA with vendor-agnostic provider
        mfa_setup = await provider.setup_mfa(current_user.id)
        
        # Log MFA setup
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="mfa_setup_initiated",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "MFA setup initiated",
            user_id=current_user.id,
            ip_address=client_ip
        )
        
        return MFASetupResponse(
            qr_code_url=mfa_setup.qr_code_url,
            backup_codes=mfa_setup.backup_codes,
            secret=mfa_setup.secret
        )
        
    except AuthenticationError as e:
        # Log MFA setup error
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="mfa_setup_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.error(
            "MFA setup failed",
            user_id=current_user.id,
            error=str(e),
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA setup service temporarily unavailable"
        )


@router.post("/mfa/verify", response_model=AuthResponse, tags=["mfa"])
async def verify_mfa(
    verify_request: MFAVerifyRequest,
    request: Request,
    provider=Depends(get_auth_provider)
) -> AuthResponse:
    """
    Verify multi-factor authentication code.
    
    Completes MFA verification process with TOTP code or backup code.
    """
    from ..utils.auth_dependencies import require_auth
    current_user = await require_auth(request, provider)
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    try:
        # Verify MFA with vendor-agnostic provider
        await provider.verify_mfa(
            user_id=current_user.id,
            code=verify_request.code,
            backup_code=verify_request.backup_code
        )
        
        # Log successful MFA verification
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="mfa_verification_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "method": "backup_code" if verify_request.backup_code else "totp",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "MFA verification successful",
            user_id=current_user.id,
            method="backup_code" if verify_request.backup_code else "totp",
            ip_address=client_ip
        )
        
        return AuthResponse(
            message="MFA verification successful",
            success=True
        )
        
    except InvalidCredentialsError as e:
        # Log failed MFA verification
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="mfa_verification_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "invalid_code",
                "method": "backup_code" if verify_request.backup_code else "totp",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "MFA verification failed - invalid code",
            user_id=current_user.id,
            method="backup_code" if verify_request.backup_code else "totp",
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code"
        )
        
    except AuthenticationError as e:
        # Log MFA verification error
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="mfa_verification_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "error": str(e),
                "method": "backup_code" if verify_request.backup_code else "totp",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.error(
            "MFA verification failed",
            user_id=current_user.id,
            error=str(e),
            method="backup_code" if verify_request.backup_code else "totp",
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA verification service temporarily unavailable"
        )
"""
Vendor-agnostic authentication dependencies for FastAPI.

This module provides authentication and authorization dependencies that work
with any authentication provider through the vendor-agnostic interface.
"""

import time
from typing import Optional, List, Callable
from datetime import datetime

import structlog
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..auth import (
    AuthUser,
    AuthenticationError,
    AuthorizationError,
    TokenExpiredError,
    UserNotFoundError
)

logger = structlog.get_logger()

# HTTP Bearer token extractor (optional - doesn't auto-error)
security = HTTPBearer(auto_error=False)


async def get_auth_provider():
    """
    Get the current authentication provider from main app.
    
    Returns:
        AuthenticationProvider: Current provider instance
        
    Raises:
        HTTPException: If provider is not initialized
    """
    # Import here to avoid circular imports
    from ..main import auth_provider
    if not auth_provider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication provider not initialized"
        )
    return auth_provider


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Client IP address or 'unknown'
    """
    # Check for forwarded headers first (load balancer/proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """
    Extract user agent from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: User agent string or 'unknown'
    """
    return request.headers.get("user-agent", "unknown")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    provider=Depends(get_auth_provider)
) -> Optional[AuthUser]:
    """
    Get current user from any authentication provider (optional authentication).
    
    This dependency attempts to authenticate the user but doesn't fail if
    no credentials are provided or if authentication fails. It's designed
    for endpoints that work with both authenticated and anonymous users.
    
    Args:
        request: FastAPI request object
        credentials: Optional HTTP Bearer credentials
        provider: Authentication provider instance
        
    Returns:
        Optional[AuthUser]: Authenticated user or None
    """
    if not credentials:
        return None
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    start_time = time.time()
    
    try:
        # Use vendor-agnostic token validation
        auth_user = await provider.validate_token(credentials.credentials)
        
        # Store user in request state for middleware access
        request.state.user = auth_user
        
        # Calculate validation time
        validation_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log successful authentication for audit
        await provider.log_authentication_event(
            user_id=auth_user.id,
            event_type="token_validation_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "validation_time_ms": validation_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Token validation successful",
            user_id=auth_user.id,
            ip_address=client_ip,
            validation_time_ms=validation_time_ms
        )
        
        return auth_user
        
    except TokenExpiredError as e:
        # Log expired token (but don't raise exception in optional auth)
        await provider.log_authentication_event(
            user_id=None,
            event_type="token_validation_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "token_expired",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Token validation failed - token expired",
            ip_address=client_ip,
            error=str(e)
        )
        
        return None
        
    except AuthenticationError as e:
        # Log failed authentication (but don't raise exception in optional auth)
        await provider.log_authentication_event(
            user_id=None,
            event_type="token_validation_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "authentication_error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Token validation failed - authentication error",
            ip_address=client_ip,
            error=str(e)
        )
        
        return None
        
    except Exception as e:
        # Log unexpected error (but don't raise exception in optional auth)
        await provider.log_authentication_event(
            user_id=None,
            event_type="token_validation_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "unexpected_error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Token validation failed - unexpected error",
            ip_address=client_ip,
            error=str(e)
        )
        
        return None


async def require_auth(
    request: Request,
    provider=Depends(get_auth_provider)
) -> AuthUser:
    """
    Require authentication - raises 401 if not authenticated.
    
    This dependency enforces authentication and will raise an HTTP 401
    exception if the user is not authenticated or if authentication fails.
    
    Args:
        request: FastAPI request object
        provider: Authentication provider instance
        
    Returns:
        AuthUser: Authenticated user
        
    Raises:
        HTTPException: 401 if authentication fails or not provided
    """
    credentials = None
    auth_header = request.headers.get("authorization", "")
    
    if auth_header.startswith("Bearer "):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=auth_header[7:]
        )
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    start_time = time.time()
    
    try:
        # Use vendor-agnostic token validation
        auth_user = await provider.validate_token(credentials.credentials)
        
        # Store user in request state for middleware access
        request.state.user = auth_user
        
        # Calculate validation time
        validation_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log successful authentication for audit
        await provider.log_authentication_event(
            user_id=auth_user.id,
            event_type="required_auth_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "validation_time_ms": validation_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Required authentication successful",
            user_id=auth_user.id,
            ip_address=client_ip,
            validation_time_ms=validation_time_ms
        )
        
        return auth_user
        
    except TokenExpiredError as e:
        # Log expired token
        await provider.log_authentication_event(
            user_id=None,
            event_type="required_auth_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "token_expired",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Required authentication failed - token expired",
            ip_address=client_ip,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    except UserNotFoundError as e:
        # Log user not found
        await provider.log_authentication_event(
            user_id=None,
            event_type="required_auth_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "user_not_found",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Required authentication failed - user not found",
            ip_address=client_ip,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token - user not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    except AuthenticationError as e:
        # Log failed authentication
        await provider.log_authentication_event(
            user_id=None,
            event_type="required_auth_failure",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "authentication_error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "Required authentication failed - authentication error",
            ip_address=client_ip,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    except Exception as e:
        # Log unexpected error
        await provider.log_authentication_event(
            user_id=None,
            event_type="required_auth_error",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "unexpected_error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.error(
            "Required authentication failed - unexpected error",
            ip_address=client_ip,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable",
            headers={"WWW-Authenticate": "Bearer"}
        )


def require_role(required_roles: List[str]) -> Callable:
    """
    Dependency factory for role-based access control.
    
    Creates a dependency that requires the user to have at least one of
    the specified roles.
    
    Args:
        required_roles: List of roles that are allowed access
        
    Returns:
        Callable: FastAPI dependency function
        
    Example:
        @router.get("/admin")
        async def admin_endpoint(
            user: AuthUser = Depends(require_role(["ADMIN", "SUPER_USER"]))
        ):
            # Only users with ADMIN or SUPER_USER role can access
            pass
    """
    async def role_checker(
        request: Request,
        current_user: AuthUser = Depends(require_auth)
    ) -> AuthUser:
        """
        Check if user has required role.
        
        Args:
            request: FastAPI request object
            current_user: Authenticated user
            
        Returns:
            AuthUser: User with verified role access
            
        Raises:
            HTTPException: 403 if user doesn't have required role
        """
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Check if user has any of the required roles
        user_roles = current_user.roles if current_user.roles else []
        has_required_role = any(role in user_roles for role in required_roles)
        
        if not has_required_role:
            # Log authorization failure
            provider = await get_auth_provider()
            await provider.log_authentication_event(
                user_id=current_user.id,
                event_type="authorization_failure",
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    "reason": "insufficient_role",
                    "required_roles": required_roles,
                    "user_roles": user_roles,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.warning(
                "Authorization failed - insufficient role",
                user_id=current_user.id,
                required_roles=required_roles,
                user_roles=user_roles,
                ip_address=client_ip
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}"
            )
        
        # Log successful authorization
        provider = await get_auth_provider()
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="authorization_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "required_roles": required_roles,
                "user_roles": user_roles,
                "matched_roles": [role for role in user_roles if role in required_roles],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Authorization successful - role check passed",
            user_id=current_user.id,
            required_roles=required_roles,
            user_roles=user_roles,
            ip_address=client_ip
        )
        
        return current_user
    
    return role_checker


async def require_phi_access(
    request: Request,
    current_user: AuthUser = Depends(require_auth)
) -> AuthUser:
    """
    Require PHI (Protected Health Information) access authorization.
    
    This dependency enforces additional authorization checks for endpoints
    that handle PHI data, ensuring HIPAA compliance.
    
    Args:
        request: FastAPI request object
        current_user: Authenticated user
        
    Returns:
        AuthUser: User with verified PHI access
        
    Raises:
        HTTPException: 403 if user doesn't have PHI access
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Check if user has PHI access authorization
    if not getattr(current_user, 'phi_access_granted', False):
        # Log PHI access denial
        provider = await get_auth_provider()
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="phi_access_denied",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "reason": "phi_access_not_granted",
                "user_roles": current_user.roles if current_user.roles else [],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(
            "PHI access denied - user not authorized",
            user_id=current_user.id,
            ip_address=client_ip
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. PHI access authorization required."
        )
    
    # Log successful PHI access
    provider = await get_auth_provider()
    await provider.log_authentication_event(
        user_id=current_user.id,
        event_type="phi_access_granted",
        ip_address=client_ip,
        user_agent=user_agent,
        details={
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.debug(
        "PHI access granted",
        user_id=current_user.id,
        ip_address=client_ip
    )
    
    return current_user


def require_permissions(required_permissions: List[str]) -> Callable:
    """
    Dependency factory for permission-based access control.
    
    Creates a dependency that requires the user to have all of the
    specified permissions.
    
    Args:
        required_permissions: List of permissions that are required
        
    Returns:
        Callable: FastAPI dependency function
        
    Example:
        @router.post("/patients")
        async def create_patient(
            user: AuthUser = Depends(require_permissions(["patient:create", "phi:access"]))
        ):
            # Only users with both permissions can access
            pass
    """
    async def permission_checker(
        request: Request,
        current_user: AuthUser = Depends(require_auth)
    ) -> AuthUser:
        """
        Check if user has required permissions.
        
        Args:
            request: FastAPI request object
            current_user: Authenticated user
            
        Returns:
            AuthUser: User with verified permissions
            
        Raises:
            HTTPException: 403 if user doesn't have required permissions
        """
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Check if user has all required permissions
        user_permissions = getattr(current_user, 'permissions', []) or []
        missing_permissions = [perm for perm in required_permissions if perm not in user_permissions]
        
        if missing_permissions:
            # Log authorization failure
            provider = await get_auth_provider()
            await provider.log_authentication_event(
                user_id=current_user.id,
                event_type="authorization_failure",
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    "reason": "insufficient_permissions",
                    "required_permissions": required_permissions,
                    "user_permissions": user_permissions,
                    "missing_permissions": missing_permissions,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.warning(
                "Authorization failed - insufficient permissions",
                user_id=current_user.id,
                required_permissions=required_permissions,
                missing_permissions=missing_permissions,
                ip_address=client_ip
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permissions: {missing_permissions}"
            )
        
        # Log successful authorization
        provider = await get_auth_provider()
        await provider.log_authentication_event(
            user_id=current_user.id,
            event_type="authorization_success",
            ip_address=client_ip,
            user_agent=user_agent,
            details={
                "required_permissions": required_permissions,
                "user_permissions": user_permissions,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(
            "Authorization successful - permission check passed",
            user_id=current_user.id,
            required_permissions=required_permissions,
            ip_address=client_ip
        )
        
        return current_user
    
    return permission_checker
"""
Custom exceptions for authentication operations.

This module defines HIPAA-compliant authentication exceptions that provide
structured error handling while avoiding exposure of sensitive information.
"""

from typing import Optional, Dict, Any


class ConfigurationError(Exception):
    """Exception raised for authentication configuration errors."""
    
    def __init__(
        self,
        message: str = "Authentication configuration error",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize configuration error.
        
        Args:
            message: Human-readable error message
            config_key: Configuration key that caused the error
            details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.config_key = config_key
        self.details = details or {}


class AuthenticationError(Exception):
    """Base exception for authentication-related errors."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize authentication error.
        
        Args:
            message: Human-readable error message (sanitized for logs)
            error_code: Machine-readable error code for API responses
            details: Additional error context (non-sensitive data only)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "AUTH_ERROR"
        self.details = details or {}


class AuthorizationError(AuthenticationError):
    """Exception raised when user lacks required permissions."""
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permissions: Optional[list[str]] = None,
        user_permissions: Optional[list[str]] = None
    ) -> None:
        """
        Initialize authorization error.
        
        Args:
            message: Human-readable error message
            required_permissions: List of required permissions
            user_permissions: List of user's current permissions (for audit)
        """
        details = {}
        if required_permissions:
            details["required_permissions"] = required_permissions
        if user_permissions:
            details["user_permissions"] = user_permissions
            
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=details
        )


class InvalidCredentialsError(AuthenticationError):
    """Exception raised when credentials are invalid."""
    
    def __init__(
        self,
        message: str = "Invalid credentials",
        credential_type: Optional[str] = None
    ) -> None:
        """
        Initialize invalid credentials error.
        
        Args:
            message: Human-readable error message
            credential_type: Type of credential that failed (for audit)
        """
        details = {}
        if credential_type:
            details["credential_type"] = credential_type
            
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
            details=details
        )


class TokenExpiredError(AuthenticationError):
    """Exception raised when authentication token has expired."""
    
    def __init__(
        self,
        message: str = "Authentication token has expired",
        token_type: Optional[str] = None,
        expired_at: Optional[str] = None
    ) -> None:
        """
        Initialize token expired error.
        
        Args:
            message: Human-readable error message
            token_type: Type of token that expired
            expired_at: ISO timestamp when token expired
        """
        details = {}
        if token_type:
            details["token_type"] = token_type
        if expired_at:
            details["expired_at"] = expired_at
            
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
            details=details
        )


class UserNotFoundError(AuthenticationError):
    """Exception raised when user cannot be found."""
    
    def __init__(
        self,
        message: str = "User not found",
        user_identifier: Optional[str] = None
    ) -> None:
        """
        Initialize user not found error.
        
        Args:
            message: Human-readable error message
            user_identifier: Non-sensitive user identifier for audit
        """
        details = {}
        if user_identifier:
            # Only include non-sensitive identifier (e.g., user ID, not email)
            details["user_identifier"] = user_identifier
            
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
            details=details
        )


class MFARequiredError(AuthenticationError):
    """Exception raised when multi-factor authentication is required."""
    
    def __init__(
        self,
        message: str = "Multi-factor authentication required",
        available_methods: Optional[list[str]] = None,
        challenge_id: Optional[str] = None
    ) -> None:
        """
        Initialize MFA required error.
        
        Args:
            message: Human-readable error message
            available_methods: List of available MFA methods
            challenge_id: ID for the MFA challenge session
        """
        details = {}
        if available_methods:
            details["available_methods"] = available_methods
        if challenge_id:
            details["challenge_id"] = challenge_id
            
        super().__init__(
            message=message,
            error_code="MFA_REQUIRED",
            details=details
        )
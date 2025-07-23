"""
Authentication module for HIPAA-compliant application.

This module provides vendor-agnostic authentication interfaces and implementations
for the HIPAA-compliant FastAPI application. It includes abstract base classes,
data models, and exception handling for authentication operations.
"""

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    TokenExpiredError,
    UserNotFoundError,
    MFARequiredError,
)
from .interfaces import AuthenticationProvider
from .models import AuthUser, AuthToken, AuthResult

__all__ = [
    "AuthenticationProvider",
    "AuthUser",
    "AuthToken", 
    "AuthResult",
    "AuthenticationError",
    "AuthorizationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "UserNotFoundError",
    "MFARequiredError",
]
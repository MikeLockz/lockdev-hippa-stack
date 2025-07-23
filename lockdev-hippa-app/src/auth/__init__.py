"""
Authentication module for HIPAA-compliant application.

This module provides vendor-agnostic authentication interfaces and implementations
for the HIPAA-compliant FastAPI application. It includes abstract base classes,
data models, factory patterns, configuration management, and exception handling
for authentication operations.
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
from .models import AuthUser, AuthToken, AuthResult, UserRole, MFAMethod, TokenType
from .config import AuthConfig, AuthProviderType, ProviderHealthConfig
from .factory import (
    AuthProviderFactory,
    ProviderRegistry,
    ProviderRegistration,
    ProviderHealth,
    get_auth_factory,
    create_auth_provider
)

__all__ = [
    # Core interfaces and models
    "AuthenticationProvider",
    "AuthUser",
    "AuthToken", 
    "AuthResult",
    "UserRole",
    "MFAMethod",
    "TokenType",
    
    # Configuration
    "AuthConfig",
    "AuthProviderType",
    "ProviderHealthConfig",
    
    # Factory pattern
    "AuthProviderFactory",
    "ProviderRegistry",
    "ProviderRegistration",
    "ProviderHealth",
    "get_auth_factory",
    "create_auth_provider",
    
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "UserNotFoundError",
    "MFARequiredError",
]
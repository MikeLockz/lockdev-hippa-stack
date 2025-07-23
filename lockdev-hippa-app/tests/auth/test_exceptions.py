"""
Tests for authentication exceptions.

This module tests all custom authentication exceptions to ensure
proper error handling and message sanitization for HIPAA compliance.
"""

import pytest
from datetime import datetime

from src.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    TokenExpiredError,
    UserNotFoundError,
    MFARequiredError,
)


class TestAuthenticationError:
    """Test cases for the base AuthenticationError class."""
    
    def test_default_initialization(self):
        """Test default initialization of AuthenticationError."""
        error = AuthenticationError()
        
        assert str(error) == "Authentication failed"
        assert error.message == "Authentication failed"
        assert error.error_code == "AUTH_ERROR"
        assert error.details == {}
    
    def test_custom_initialization(self):
        """Test custom initialization with all parameters."""
        details = {"key": "value"}
        error = AuthenticationError(
            message="Custom error",
            error_code="CUSTOM_ERROR",
            details=details
        )
        
        assert str(error) == "Custom error"
        assert error.message == "Custom error"
        assert error.error_code == "CUSTOM_ERROR"
        assert error.details == details
    
    def test_inheritance(self):
        """Test that AuthenticationError inherits from Exception."""
        error = AuthenticationError()
        assert isinstance(error, Exception)


class TestAuthorizationError:
    """Test cases for AuthorizationError."""
    
    def test_default_initialization(self):
        """Test default initialization of AuthorizationError."""
        error = AuthorizationError()
        
        assert str(error) == "Access denied"
        assert error.message == "Access denied"
        assert error.error_code == "AUTHORIZATION_ERROR"
        assert error.details == {}
    
    def test_with_permissions(self):
        """Test initialization with permission information."""
        required = ["read:patients", "write:diagnoses"]
        user_perms = ["read:patients"]
        
        error = AuthorizationError(
            message="Insufficient permissions",
            required_permissions=required,
            user_permissions=user_perms
        )
        
        assert error.message == "Insufficient permissions"
        assert error.error_code == "AUTHORIZATION_ERROR"
        assert error.details["required_permissions"] == required
        assert error.details["user_permissions"] == user_perms
    
    def test_inheritance(self):
        """Test that AuthorizationError inherits from AuthenticationError."""
        error = AuthorizationError()
        assert isinstance(error, AuthenticationError)


class TestInvalidCredentialsError:
    """Test cases for InvalidCredentialsError."""
    
    def test_default_initialization(self):
        """Test default initialization of InvalidCredentialsError."""
        error = InvalidCredentialsError()
        
        assert str(error) == "Invalid credentials"
        assert error.message == "Invalid credentials"
        assert error.error_code == "INVALID_CREDENTIALS"
        assert error.details == {}
    
    def test_with_credential_type(self):
        """Test initialization with credential type."""
        error = InvalidCredentialsError(
            message="Invalid password",
            credential_type="password"
        )
        
        assert error.message == "Invalid password"
        assert error.error_code == "INVALID_CREDENTIALS"
        assert error.details["credential_type"] == "password"
    
    def test_inheritance(self):
        """Test that InvalidCredentialsError inherits from AuthenticationError."""
        error = InvalidCredentialsError()
        assert isinstance(error, AuthenticationError)


class TestTokenExpiredError:
    """Test cases for TokenExpiredError."""
    
    def test_default_initialization(self):
        """Test default initialization of TokenExpiredError."""
        error = TokenExpiredError()
        
        assert str(error) == "Authentication token has expired"
        assert error.message == "Authentication token has expired"
        assert error.error_code == "TOKEN_EXPIRED"
        assert error.details == {}
    
    def test_with_token_info(self):
        """Test initialization with token information."""
        expired_at = datetime.utcnow().isoformat()
        
        error = TokenExpiredError(
            message="Access token expired",
            token_type="access",
            expired_at=expired_at
        )
        
        assert error.message == "Access token expired"
        assert error.error_code == "TOKEN_EXPIRED"
        assert error.details["token_type"] == "access"
        assert error.details["expired_at"] == expired_at
    
    def test_inheritance(self):
        """Test that TokenExpiredError inherits from AuthenticationError."""
        error = TokenExpiredError()
        assert isinstance(error, AuthenticationError)


class TestUserNotFoundError:
    """Test cases for UserNotFoundError."""
    
    def test_default_initialization(self):
        """Test default initialization of UserNotFoundError."""
        error = UserNotFoundError()
        
        assert str(error) == "User not found"
        assert error.message == "User not found"
        assert error.error_code == "USER_NOT_FOUND"
        assert error.details == {}
    
    def test_with_user_identifier(self):
        """Test initialization with user identifier."""
        error = UserNotFoundError(
            message="User account not found",
            user_identifier="user123"
        )
        
        assert error.message == "User account not found"
        assert error.error_code == "USER_NOT_FOUND"
        assert error.details["user_identifier"] == "user123"
    
    def test_inheritance(self):
        """Test that UserNotFoundError inherits from AuthenticationError."""
        error = UserNotFoundError()
        assert isinstance(error, AuthenticationError)


class TestMFARequiredError:
    """Test cases for MFARequiredError."""
    
    def test_default_initialization(self):
        """Test default initialization of MFARequiredError."""
        error = MFARequiredError()
        
        assert str(error) == "Multi-factor authentication required"
        assert error.message == "Multi-factor authentication required"
        assert error.error_code == "MFA_REQUIRED"
        assert error.details == {}
    
    def test_with_mfa_info(self):
        """Test initialization with MFA information."""
        methods = ["sms", "totp"]
        challenge_id = "challenge123"
        
        error = MFARequiredError(
            message="Complete MFA to continue",
            available_methods=methods,
            challenge_id=challenge_id
        )
        
        assert error.message == "Complete MFA to continue"
        assert error.error_code == "MFA_REQUIRED"
        assert error.details["available_methods"] == methods
        assert error.details["challenge_id"] == challenge_id
    
    def test_inheritance(self):
        """Test that MFARequiredError inherits from AuthenticationError."""
        error = MFARequiredError()
        assert isinstance(error, AuthenticationError)


class TestExceptionChaining:
    """Test exception chaining and context preservation."""
    
    def test_exception_chaining(self):
        """Test that exceptions properly chain with underlying causes."""
        try:
            # Simulate an underlying error
            raise ValueError("Database connection failed")
        except ValueError as e:
            # Chain with authentication error
            auth_error = AuthenticationError("Authentication service unavailable")
            auth_error.__cause__ = e
            
            assert auth_error.__cause__ is e
            assert str(auth_error.__cause__) == "Database connection failed"
    
    def test_error_details_isolation(self):
        """Test that error details don't leak sensitive information."""
        # Test that sensitive data is not accidentally included
        error = InvalidCredentialsError(
            message="Login failed",
            credential_type="password"
        )
        
        # Ensure only non-sensitive data is in details
        assert "credential_type" in error.details
        assert "password" not in error.details
        assert "secret" not in error.details
        assert "token" not in error.details
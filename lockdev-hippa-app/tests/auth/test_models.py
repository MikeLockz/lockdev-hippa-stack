"""
Tests for authentication models.

This module tests all Pydantic authentication models to ensure
proper validation, serialization, and HIPAA compliance.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from pydantic import ValidationError

from src.auth.models import (
    UserRole,
    MFAMethod,
    TokenType,
    AuthUser,
    AuthToken,
    AuthResult,
)


class TestUserRole:
    """Test cases for UserRole enum."""
    
    def test_all_roles_defined(self):
        """Test that all expected user roles are defined."""
        expected_roles = {
            "admin", "clinician", "nurse", "technician", 
            "patient", "audit_user", "system"
        }
        actual_roles = {role.value for role in UserRole}
        assert actual_roles == expected_roles
    
    def test_role_string_values(self):
        """Test that role values are proper strings."""
        for role in UserRole:
            assert isinstance(role.value, str)
            assert len(role.value) > 0


class TestMFAMethod:
    """Test cases for MFAMethod enum."""
    
    def test_all_methods_defined(self):
        """Test that all expected MFA methods are defined."""
        expected_methods = {
            "sms", "email", "totp", "hardware_token", "biometric"
        }
        actual_methods = {method.value for method in MFAMethod}
        assert actual_methods == expected_methods


class TestTokenType:
    """Test cases for TokenType enum."""
    
    def test_all_types_defined(self):
        """Test that all expected token types are defined."""
        expected_types = {
            "access", "refresh", "mfa_challenge", "password_reset"
        }
        actual_types = {token_type.value for token_type in TokenType}
        assert actual_types == expected_types


class TestAuthUser:
    """Test cases for AuthUser model."""
    
    def test_minimal_valid_user(self):
        """Test creation of user with minimal required fields."""
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "created_at": datetime.utcnow()
        }
        
        user = AuthUser(**user_data)
        
        assert user.id == "user123"
        assert user.email == "test@example.com"
        assert user.username is None
        assert user.roles == [UserRole.PATIENT]  # Default role
        assert user.permissions == []
        assert user.is_active is True
        assert user.is_verified is False
        assert user.mfa_enabled is False
        assert user.mfa_methods == []
        assert user.failed_login_attempts == 0
        assert user.metadata == {}
    
    def test_complete_user(self):
        """Test creation of user with all fields."""
        created_at = datetime.utcnow()
        last_login = created_at + timedelta(hours=1)
        
        user_data = {
            "id": "user123",
            "email": "doctor@hospital.com",
            "username": "dr_smith",
            "roles": [UserRole.CLINICIAN, UserRole.ADMIN],
            "permissions": ["read:patients", "write:diagnoses"],
            "is_active": True,
            "is_verified": True,
            "mfa_enabled": True,
            "mfa_methods": [MFAMethod.TOTP, MFAMethod.SMS],
            "created_at": created_at,
            "last_login": last_login,
            "last_password_change": created_at,
            "password_expires_at": created_at + timedelta(days=90),
            "failed_login_attempts": 0,
            "department": "Cardiology",
            "license_number": "MD123456",
            "supervisor_id": "supervisor789",
            "metadata": {"shift": "day", "location": "wing_a"}
        }
        
        user = AuthUser(**user_data)
        
        assert user.id == "user123"
        assert user.email == "doctor@hospital.com"
        assert user.username == "dr_smith"
        assert user.roles == [UserRole.CLINICIAN, UserRole.ADMIN]
        assert user.permissions == ["read:patients", "write:diagnoses"]
        assert user.mfa_enabled is True
        assert user.mfa_methods == [MFAMethod.TOTP, MFAMethod.SMS]
        assert user.department == "Cardiology"
        assert user.license_number == "MD123456"
        assert user.supervisor_id == "supervisor789"
        assert user.metadata == {"shift": "day", "location": "wing_a"}
    
    def test_email_validation(self):
        """Test email validation and normalization."""
        # Valid email should work
        user_data = {
            "id": "user123",
            "email": "Test@EXAMPLE.COM",
            "created_at": datetime.utcnow()
        }
        user = AuthUser(**user_data)
        assert user.email == "test@example.com"  # Should be lowercase
        
        # Invalid emails should raise ValidationError
        invalid_emails = ["invalid", "@example.com", "test@", ""]
        
        for invalid_email in invalid_emails:
            with pytest.raises(ValidationError):
                AuthUser(
                    id="user123",
                    email=invalid_email,
                    created_at=datetime.utcnow()
                )
    
    def test_failed_attempts_validation(self):
        """Test failed login attempts validation."""
        # Valid attempt count
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "created_at": datetime.utcnow(),
            "failed_login_attempts": 3
        }
        user = AuthUser(**user_data)
        assert user.failed_login_attempts == 3
        
        # Negative attempts should raise ValidationError
        with pytest.raises(ValidationError):
            AuthUser(
                id="user123",
                email="test@example.com",
                created_at=datetime.utcnow(),
                failed_login_attempts=-1
            )
    
    def test_default_role_assignment(self):
        """Test that empty roles list gets default patient role."""
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "created_at": datetime.utcnow(),
            "roles": []
        }
        user = AuthUser(**user_data)
        assert user.roles == [UserRole.PATIENT]
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "created_at": datetime.utcnow(),
            "extra_field": "not_allowed"
        }
        
        with pytest.raises(ValidationError):
            AuthUser(**user_data)


class TestAuthToken:
    """Test cases for AuthToken model."""
    
    def test_minimal_valid_token(self):
        """Test creation of token with minimal required fields."""
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(hours=1)
        
        token_data = {
            "token_id": "token123",
            "token_type": TokenType.ACCESS,
            "token_value": "a" * 32,  # Minimum 32 characters
            "issued_at": issued_at,
            "expires_at": expires_at,
            "user_id": "user123",
            "issued_by": "auth_service"
        }
        
        token = AuthToken(**token_data)
        
        assert token.token_id == "token123"
        assert token.token_type == TokenType.ACCESS
        assert token.token_value == "a" * 32
        assert token.user_id == "user123"
        assert token.issued_by == "auth_service"
        assert token.audience == []
        assert token.scopes == []
        assert token.is_revoked is False
        assert token.revoked_at is None
    
    def test_complete_token(self):
        """Test creation of token with all fields."""
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(hours=1)
        revoked_at = issued_at + timedelta(minutes=30)
        
        token_data = {
            "token_id": "token123",
            "token_type": TokenType.REFRESH,
            "token_value": "secure_token_value_with_sufficient_length",
            "issued_at": issued_at,
            "expires_at": expires_at,
            "not_before": issued_at,
            "user_id": "user123",
            "session_id": "session456",
            "issued_by": "auth_service",
            "audience": ["api_server", "mobile_app"],
            "scopes": ["read:profile", "write:data"],
            "client_id": "mobile_client",
            "ip_address": "192.168.1.100",
            "user_agent": "Mobile App 1.0",
            "is_revoked": True,
            "revoked_at": revoked_at,
            "revoked_by": "admin123"
        }
        
        token = AuthToken(**token_data)
        
        assert token.session_id == "session456"
        assert token.audience == ["api_server", "mobile_app"]
        assert token.scopes == ["read:profile", "write:data"]
        assert token.client_id == "mobile_client"
        assert token.ip_address == "192.168.1.100"
        assert token.user_agent == "Mobile App 1.0"
        assert token.is_revoked is True
        assert token.revoked_at == revoked_at
        assert token.revoked_by == "admin123"
    
    def test_token_value_validation(self):
        """Test token value length validation."""
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(hours=1)
        
        # Token too short should raise ValidationError
        with pytest.raises(ValidationError):
            AuthToken(
                token_id="token123",
                token_type=TokenType.ACCESS,
                token_value="short",  # Less than 32 characters
                issued_at=issued_at,
                expires_at=expires_at,
                user_id="user123",
                issued_by="auth_service"
            )
    
    def test_expiration_validation(self):
        """Test that expiration time is after issuance."""
        issued_at = datetime.utcnow()
        expires_at = issued_at - timedelta(hours=1)  # Before issuance
        
        with pytest.raises(ValidationError):
            AuthToken(
                token_id="token123",
                token_type=TokenType.ACCESS,
                token_value="a" * 32,
                issued_at=issued_at,
                expires_at=expires_at,
                user_id="user123",
                issued_by="auth_service"
            )


class TestAuthResult:
    """Test cases for AuthResult model."""
    
    def test_successful_authentication(self):
        """Test successful authentication result."""
        user = AuthUser(
            id="user123",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
        
        access_token = AuthToken(
            token_id="token123",
            token_type=TokenType.ACCESS,
            token_value="a" * 32,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id="user123",
            issued_by="auth_service"
        )
        
        result_data = {
            "success": True,
            "user": user,
            "access_token": access_token,
            "authentication_method": "password",
            "provider": "local"
        }
        
        result = AuthResult(**result_data)
        
        assert result.success is True
        assert result.user == user
        assert result.access_token == access_token
        assert result.mfa_required is False
        assert result.authentication_method == "password"
        assert result.provider == "local"
        assert result.error_code is None
    
    def test_failed_authentication(self):
        """Test failed authentication result."""
        result_data = {
            "success": False,
            "authentication_method": "password",
            "provider": "local",
            "error_code": "INVALID_CREDENTIALS",
            "error_message": "Invalid username or password"
        }
        
        result = AuthResult(**result_data)
        
        assert result.success is False
        assert result.user is None
        assert result.access_token is None
        assert result.error_code == "INVALID_CREDENTIALS"
        assert result.error_message == "Invalid username or password"
    
    def test_mfa_required_authentication(self):
        """Test authentication result requiring MFA."""
        mfa_token = AuthToken(
            token_id="mfa123",
            token_type=TokenType.MFA_CHALLENGE,
            token_value="b" * 32,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            user_id="user123",
            issued_by="auth_service"
        )
        
        result_data = {
            "success": True,
            "mfa_required": True,
            "mfa_challenge_token": mfa_token,
            "mfa_methods": [MFAMethod.SMS, MFAMethod.TOTP],
            "authentication_method": "password",
            "provider": "local"
        }
        
        result = AuthResult(**result_data)
        
        assert result.success is True
        assert result.mfa_required is True
        assert result.mfa_challenge_token == mfa_token
        assert result.mfa_methods == [MFAMethod.SMS, MFAMethod.TOTP]
        assert result.access_token is None  # No access token yet
    
    def test_user_success_consistency_validation(self):
        """Test that user is required when authentication is successful."""
        # Success=True but no user should raise ValidationError
        with pytest.raises(ValidationError):
            AuthResult(
                success=True,
                authentication_method="password",
                provider="local"
            )
        
        # Success=False but user provided should raise ValidationError
        user = AuthUser(
            id="user123",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
        
        with pytest.raises(ValidationError):
            AuthResult(
                success=False,
                user=user,
                authentication_method="password",
                provider="local"
            )
    
    def test_token_success_consistency_validation(self):
        """Test that access token is required for successful auth without MFA."""
        user = AuthUser(
            id="user123",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
        
        # Success=True, MFA not required, but no access token
        with pytest.raises(ValidationError):
            AuthResult(
                success=True,
                user=user,
                mfa_required=False,
                authentication_method="password",
                provider="local"
            )
    
    def test_timestamp_default(self):
        """Test that timestamp is set to current time by default."""
        before = datetime.utcnow()
        
        result = AuthResult(
            success=False,
            authentication_method="password",
            provider="local"
        )
        
        after = datetime.utcnow()
        
        assert before <= result.timestamp <= after


class TestModelSerialization:
    """Test model serialization and deserialization."""
    
    def test_user_json_serialization(self):
        """Test AuthUser JSON serialization."""
        user = AuthUser(
            id="user123",
            email="test@example.com",
            roles=[UserRole.CLINICIAN],
            mfa_methods=[MFAMethod.TOTP],
            created_at=datetime.utcnow()
        )
        
        # Test model_dump (Pydantic v2)
        user_dict = user.model_dump()
        assert isinstance(user_dict, dict)
        assert user_dict["id"] == "user123"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["roles"] == ["clinician"]
        assert user_dict["mfa_methods"] == ["totp"]
        
        # Test round-trip serialization
        user_json = user.model_dump_json()
        assert isinstance(user_json, str)
        
        # Deserialize back
        user_recreated = AuthUser.model_validate_json(user_json)
        assert user_recreated.id == user.id
        assert user_recreated.email == user.email
    
    def test_token_json_serialization(self):
        """Test AuthToken JSON serialization."""
        token = AuthToken(
            token_id="token123",
            token_type=TokenType.ACCESS,
            token_value="a" * 32,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id="user123",
            issued_by="auth_service"
        )
        
        token_dict = token.model_dump()
        assert token_dict["token_type"] == "access"
        
        # Test round-trip
        token_json = token.model_dump_json()
        token_recreated = AuthToken.model_validate_json(token_json)
        assert token_recreated.token_id == token.token_id
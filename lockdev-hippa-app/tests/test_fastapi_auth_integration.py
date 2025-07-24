"""
Integration tests for FastAPI vendor-agnostic authentication system.

This module tests the integration of the vendor-agnostic authentication
system with FastAPI, including all new routes, dependencies, and middleware.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import create_app
from src.auth import (
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


# Test fixtures
@pytest.fixture
def test_app():
    """Create test FastAPI app."""
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
async def async_test_client(test_app):
    """Create async test client."""
    async with AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def mock_auth_provider():
    """Create mock authentication provider."""
    provider = AsyncMock()
    
    # Mock health check
    provider.health_check.return_value = {
        "is_healthy": True,
        "version": "1.0.0",
        "provider_type": "custom"
    }
    
    # Mock cleanup
    provider.cleanup.return_value = None
    
    return provider


@pytest.fixture
def sample_auth_user():
    """Create sample authenticated user."""
    return AuthUser(
        id="user-123",
        email="test@example.com",
        roles=["USER"],
        is_active=True,
        phi_access_granted=False,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )


@pytest.fixture
def sample_auth_token():
    """Create sample auth token."""
    return AuthToken(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        token_type="Bearer",
        expires_in=3600,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )


@pytest.fixture
def admin_auth_user():
    """Create sample admin user."""
    return AuthUser(
        id="admin-123",
        email="admin@example.com",
        roles=["ADMIN", "USER"],
        is_active=True,
        phi_access_granted=True,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )


class TestAuthenticationRoutes:
    """Test authentication routes."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, async_test_client, mock_auth_provider, sample_auth_user, sample_auth_token):
        """Test successful login."""
        # Mock authentication
        auth_result = AuthResult(user=sample_auth_user, token=sample_auth_token)
        mock_auth_provider.authenticate.return_value = auth_result
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "password123",
                "remember_me": False
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test-access-token"
        assert data["token_type"] == "Bearer"
        
        # Verify provider methods were called
        mock_auth_provider.authenticate.assert_called_once_with(
            email="test@example.com",
            password="password123",
            remember_me=False
        )
        mock_auth_provider.log_authentication_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, async_test_client, mock_auth_provider):
        """Test login with invalid credentials."""
        # Mock authentication failure
        mock_auth_provider.authenticate.side_effect = InvalidCredentialsError("Invalid credentials")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
        
        # Verify logging was called
        mock_auth_provider.log_authentication_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self, async_test_client, mock_auth_provider):
        """Test login with non-existent user."""
        # Mock user not found
        mock_auth_provider.authenticate.side_effect = UserNotFoundError("User not found")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/login", json={
                "email": "notfound@example.com",
                "password": "password123"
            })
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_mfa_required(self, async_test_client, mock_auth_provider):
        """Test login requiring MFA."""
        # Mock MFA requirement
        mfa_error = MFARequiredError(
            "MFA required",
            user_id="user-123",
            mfa_token="mfa-token-123",
            available_methods=["totp", "sms"]
        )
        mock_auth_provider.authenticate.side_effect = mfa_error
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "password123"
            })
        
        assert response.status_code == 202
        data = response.json()["detail"]
        assert data["message"] == "Multi-factor authentication required"
        assert data["mfa_token"] == "mfa-token-123"
        assert data["available_methods"] == ["totp", "sms"]
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, async_test_client, mock_auth_provider, sample_auth_token):
        """Test successful token refresh."""
        # Mock token refresh
        mock_auth_provider.refresh_token.return_value = sample_auth_token
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/refresh", json={
                "refresh_token": "old-refresh-token"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test-access-token"
        
        mock_auth_provider.refresh_token.assert_called_once_with("old-refresh-token")
    
    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, async_test_client, mock_auth_provider):
        """Test refresh with expired token."""
        # Mock token expired
        mock_auth_provider.refresh_token.side_effect = TokenExpiredError("Token expired")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/refresh", json={
                "refresh_token": "expired-token"
            })
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_logout_success(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test successful logout."""
        # Mock token validation and logout
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.logout.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/logout",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "logged out" in data["message"].lower()
        
        mock_auth_provider.logout.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_logout_without_token(self, async_test_client, mock_auth_provider):
        """Test logout without token (should still succeed)."""
        mock_auth_provider.logout.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_current_user_info(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test getting current user info."""
        # Mock token validation
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/auth/me",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "user-123"
        assert data["email"] == "test@example.com"
        assert data["roles"] == ["USER"]
    
    @pytest.mark.asyncio
    async def test_change_password_success(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test successful password change."""
        # Mock token validation and password change
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.change_password.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/change-password",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "current_password": "oldpassword123",
                    "new_password": "newpassword123"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "changed successfully" in data["message"].lower()
        
        mock_auth_provider.change_password.assert_called_once_with(
            user_id="user-123",
            current_password="oldpassword123",
            new_password="newpassword123"
        )
    
    @pytest.mark.asyncio
    async def test_change_password_invalid_current(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test password change with invalid current password."""
        # Mock token validation and invalid password
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.change_password.side_effect = InvalidCredentialsError("Invalid password")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/change-password",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "current_password": "wrongpassword",
                    "new_password": "newpassword123"
                }
            )
        
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_forgot_password(self, async_test_client, mock_auth_provider):
        """Test forgot password functionality."""
        mock_auth_provider.initiate_password_reset.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/forgot-password", json={
                "email": "test@example.com"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reset link" in data["message"].lower()
        
        mock_auth_provider.initiate_password_reset.assert_called_once_with("test@example.com")
    
    @pytest.mark.asyncio
    async def test_reset_password_success(self, async_test_client, mock_auth_provider):
        """Test successful password reset."""
        # Mock reset result
        reset_result = MagicMock()
        reset_result.user_id = "user-123"
        mock_auth_provider.reset_password.return_value = reset_result
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/reset-password", json={
                "token": "reset-token-123",
                "new_password": "newpassword123"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reset successfully" in data["message"].lower()
        
        mock_auth_provider.reset_password.assert_called_once_with(
            reset_token="reset-token-123",
            new_password="newpassword123"
        )
    
    @pytest.mark.asyncio
    async def test_reset_password_expired_token(self, async_test_client, mock_auth_provider):
        """Test password reset with expired token."""
        mock_auth_provider.reset_password.side_effect = TokenExpiredError("Token expired")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post("/auth/reset-password", json={
                "token": "expired-token",
                "new_password": "newpassword123"
            })
        
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


class TestMFARoutes:
    """Test MFA-related routes."""
    
    @pytest.mark.asyncio
    async def test_setup_mfa(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test MFA setup."""
        # Mock token validation and MFA setup
        mock_auth_provider.validate_token.return_value = sample_auth_user
        
        mfa_setup = MagicMock()
        mfa_setup.qr_code_url = "https://example.com/qr"
        mfa_setup.backup_codes = ["code1", "code2", "code3"]
        mfa_setup.secret = "secret123"
        mock_auth_provider.setup_mfa.return_value = mfa_setup
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/auth/mfa/setup",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["qr_code_url"] == "https://example.com/qr"
        assert len(data["backup_codes"]) == 3
        assert data["secret"] == "secret123"
        
        mock_auth_provider.setup_mfa.assert_called_once_with("user-123")
    
    @pytest.mark.asyncio
    async def test_verify_mfa_totp(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test MFA verification with TOTP code."""
        # Mock token validation and MFA verification
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.verify_mfa.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/mfa/verify",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "code": "123456"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "verification successful" in data["message"].lower()
        
        mock_auth_provider.verify_mfa.assert_called_once_with(
            user_id="user-123",
            code="123456",
            backup_code=None
        )
    
    @pytest.mark.asyncio
    async def test_verify_mfa_backup_code(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test MFA verification with backup code."""
        # Mock token validation and MFA verification
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.verify_mfa.return_value = None
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/mfa/verify",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "code": "123456",
                    "backup_code": "backup123"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        mock_auth_provider.verify_mfa.assert_called_once_with(
            user_id="user-123",
            code="123456",
            backup_code="backup123"
        )
    
    @pytest.mark.asyncio
    async def test_verify_mfa_invalid_code(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test MFA verification with invalid code."""
        # Mock token validation and invalid MFA code
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.verify_mfa.side_effect = InvalidCredentialsError("Invalid code")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.post(
                "/auth/mfa/verify",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "code": "wrong123"
                }
            )
        
        assert response.status_code == 400
        assert "Invalid MFA code" in response.json()["detail"]


class TestAPIRoutesDependencies:
    """Test API routes with new authentication dependencies."""
    
    @pytest.mark.asyncio
    async def test_hello_optional_auth_no_token(self, async_test_client, mock_auth_provider):
        """Test hello endpoint without authentication token."""
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get("/api/v1/hello")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello from HIPAA-compliant healthcare API!"
        assert data["user_id"] is None
    
    @pytest.mark.asyncio
    async def test_hello_optional_auth_with_token(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test hello endpoint with authentication token."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/hello",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-123"
    
    @pytest.mark.asyncio
    async def test_secure_endpoint_no_token(self, async_test_client, mock_auth_provider):
        """Test secure endpoint without token."""
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get("/api/v1/secure")
        
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_secure_endpoint_with_token(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test secure endpoint with valid token."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/secure",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-123"
        assert "authenticated" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_admin_endpoint_no_role(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test admin endpoint with user without admin role."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/admin/users",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
        assert "ADMIN" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_admin_endpoint_with_role(self, async_test_client, mock_auth_provider, admin_auth_user):
        """Test admin endpoint with admin user."""
        mock_auth_provider.validate_token.return_value = admin_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/admin/users",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["requested_by"] == "admin-123"
        assert "ADMIN" in data["user_roles"]
    
    @pytest.mark.asyncio
    async def test_phi_endpoint_no_access(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test PHI endpoint with user without PHI access."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/patients/patient-123",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 403
        assert "PHI access" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_phi_endpoint_with_access(self, async_test_client, mock_auth_provider, admin_auth_user):
        """Test PHI endpoint with user having PHI access."""
        mock_auth_provider.validate_token.return_value = admin_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/patients/patient-123",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == "patient-123"
        assert data["accessed_by"] == "admin-123"
        assert data["phi_access_granted"] is True


class TestAuthenticationMiddleware:
    """Test authentication middleware functionality."""
    
    @pytest.mark.asyncio
    async def test_middleware_sets_user_context(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test that middleware sets user context correctly."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            response = await async_test_client.get(
                "/api/v1/hello",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        # Verify logging was called (middleware should log the request)
        mock_auth_provider.log_authentication_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_middleware_handles_invalid_token(self, async_test_client, mock_auth_provider):
        """Test middleware handling of invalid tokens."""
        mock_auth_provider.validate_token.side_effect = AuthenticationError("Invalid token")
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            # Should not fail - middleware should handle gracefully
            response = await async_test_client.get(
                "/api/v1/hello",
                headers={"Authorization": "Bearer invalid-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] is None  # No user context set


class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality."""
    
    @pytest.mark.asyncio
    async def test_existing_endpoints_still_work(self, async_test_client, mock_auth_provider):
        """Test that existing endpoints continue to work."""
        with patch('src.main.auth_provider', mock_auth_provider):
            # Health endpoint should still work
            response = await async_test_client.get("/health/")
            assert response.status_code == 200
            
            # Metrics endpoint should still work
            response = await async_test_client.get("/metrics")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_existing_api_routes_updated(self, async_test_client, mock_auth_provider, sample_auth_user):
        """Test that existing API routes work with new auth system."""
        mock_auth_provider.validate_token.return_value = sample_auth_user
        mock_auth_provider.log_authentication_event.return_value = None
        
        with patch('src.main.auth_provider', mock_auth_provider):
            # Test users/me endpoint
            response = await async_test_client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "user-123"
            assert data["email"] == "test@example.com"
            
            # Test audit log endpoint
            response = await async_test_client.get(
                "/api/v1/audit-log",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user-123"


@pytest.mark.asyncio
async def test_application_startup_with_auth_provider(mock_auth_provider):
    """Test application startup with auth provider initialization."""
    with patch('src.auth.create_auth_provider', return_value=mock_auth_provider):
        with patch('src.auth.AuthConfig') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.provider_type.value = "custom"
            mock_config.return_value = mock_config_instance
            
            app = create_app()
            
            # Test that app can be created without errors
            assert app is not None
            assert app.title == "HIPAA-Compliant Healthcare API"


@pytest.mark.asyncio
async def test_application_startup_auth_provider_failure():
    """Test application startup when auth provider fails to initialize."""
    with patch('src.auth.create_auth_provider', side_effect=Exception("Provider failed")):
        with patch('src.auth.AuthConfig') as mock_config:
            mock_config_instance = MagicMock()
            mock_config.return_value = mock_config_instance
            
            # App should still start even if auth provider fails
            app = create_app()
            assert app is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
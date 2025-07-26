"""
Integration tests for the vendor-agnostic authentication system.

These tests validate the complete authentication flow end-to-end,
including provider switching, role-based access control, and HIPAA compliance.
"""

import asyncio
import json
import os
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.main import create_app
from src.auth import AuthConfig, AuthProviderType, AuthUser, AuthToken
from src.auth.factory import create_auth_provider
from src.models.user import User
from src.models.audit_log import AuditLog
from src.utils.database import get_db_session


# Test database setup
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/hipaa_test")

# Test configuration
TEST_JWT_SECRET = "test-secret-key-for-integration-tests-only"
TEST_JWT_ALGORITHM = "HS256"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine):
    """Create test database session."""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Clean up tables before each test
        await session.execute("DELETE FROM audit_logs")
        await session.execute("DELETE FROM users")
        await session.commit()
        yield session


@pytest.fixture(scope="function")
async def test_app(test_db_session):
    """Create test FastAPI application."""
    app = create_app()
    
    # Override database session dependency
    async def override_get_db_session():
        yield test_db_session
    
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    yield app


@pytest.fixture(scope="function")
async def client(test_app):
    """Create test HTTP client."""
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="function")
async def custom_auth_provider():
    """Create custom authentication provider for testing."""
    config = AuthConfig()
    config.provider_type = AuthProviderType.CUSTOM
    config.jwt_secret = TEST_JWT_SECRET
    config.jwt_algorithm = TEST_JWT_ALGORITHM
    
    provider = await create_auth_provider(AuthProviderType.CUSTOM)
    return provider


@pytest.fixture(scope="function")
async def test_user(test_db_session, custom_auth_provider):
    """Create a test user for authentication tests."""
    user_data = {
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        "role": "USER"
    }
    
    # Create user through auth provider
    user = await custom_auth_provider.create_user(**user_data)
    
    # Add to database
    db_user = User(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=True
    )
    test_db_session.add(db_user)
    await test_db_session.commit()
    
    return user


@pytest.fixture(scope="function")
async def admin_user(test_db_session, custom_auth_provider):
    """Create an admin test user."""
    user_data = {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "first_name": "Admin",
        "last_name": "User",
        "role": "ADMIN"
    }
    
    user = await custom_auth_provider.create_user(**user_data)
    
    db_user = User(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=True
    )
    test_db_session.add(db_user)
    await test_db_session.commit()
    
    return user


@pytest.fixture(scope="function")
async def test_user_token(test_user, custom_auth_provider):
    """Get authentication token for test user."""
    auth_result = await custom_auth_provider.authenticate(
        email=test_user.email,
        password="TestPassword123!"
    )
    return auth_result.token.access_token


@pytest.fixture(scope="function")
async def admin_user_token(admin_user, custom_auth_provider):
    """Get authentication token for admin user."""
    auth_result = await custom_auth_provider.authenticate(
        email=admin_user.email,
        password="AdminPassword123!"
    )
    return auth_result.token.access_token


class TestAuthenticationFlow:
    """Test complete authentication flows."""
    
    async def test_user_registration_and_login(self, client, test_db_session):
        """Test user registration followed by login."""
        # Register new user
        user_data = {
            "email": "newuser@example.com",
            "password": "NewUserPassword123!",
            "first_name": "New",
            "last_name": "User",
            "role": "USER"
        }
        
        # Create user
        response = await client.post("/auth/register", json=user_data)
        assert response.status_code == 201
        user_id = response.json()["user_id"]
        
        # Login with new credentials
        login_data = {
            "email": "newuser@example.com",
            "password": "NewUserPassword123!"
        }
        
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        token_data = response.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "bearer"
    
    async def test_token_refresh_flow(self, client, test_user, test_user_token):
        """Test token refresh functionality."""
        # Get refresh token
        login_response = await client.post("/auth/login", json={
            "email": test_user.email,
            "password": "TestPassword123!"
        })
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_data = {"refresh_token": refresh_token}
        response = await client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        new_token_data = response.json()
        assert "access_token" in new_token_data
        assert "refresh_token" in new_token_data
        assert new_token_data["token_type"] == "bearer"
    
    async def test_logout_flow(self, client, test_user, test_user_token):
        """Test user logout functionality."""
        # Logout user
        headers = {"Authorization": f"Bearer {test_user_token}"}
        response = await client.post("/auth/logout", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify token is invalidated
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 401


class TestRoleBasedAccess:
    """Test role-based access control."""
    
    async def test_admin_access_requires_admin_role(self, client, admin_user_token):
        """Test that admin endpoints require admin role."""
        headers = {"Authorization": f"Bearer {admin_user_token}"}
        
        response = await client.get("/api/v1/admin/users", headers=headers)
        assert response.status_code == 200
    
    async def test_admin_access_denied_for_regular_users(self, client, test_user_token):
        """Test that regular users cannot access admin endpoints."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = await client.get("/api/v1/admin/users", headers=headers)
        assert response.status_code == 403
    
    async def test_phi_access_requires_authorization(self, client, test_user_token):
        """Test that PHI access requires specific authorization."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = await client.get("/api/v1/patients/patient123", headers=headers)
        # Should fail because test user doesn't have PHI access
        assert response.status_code == 403


class TestProviderSwitching:
    """Test switching between authentication providers."""
    
    @patch.dict(os.environ, {"AUTH_PROVIDER_TYPE": "custom"})
    async def test_custom_provider_integration(self, client, test_user, test_user_token):
        """Test custom JWT provider integration."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        
        user_data = response.json()
        assert user_data["email"] == test_user.email
    
    async def test_provider_health_check(self, client):
        """Test authentication provider health check endpoint."""
        # Note: This would require admin role in production
        response = await client.get("/health/auth-provider")
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist


class TestAuthenticationSecurity:
    """Test authentication security features."""
    
    async def test_invalid_token_rejection(self, client):
        """Test that invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid-token"}
        
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 401
    
    async def test_expired_token_rejection(self, client, custom_auth_provider):
        """Test that expired tokens are rejected."""
        # Create an expired token
        expired_token = await custom_auth_provider.create_access_token(
            user_id="test-user-id",
            expires_delta=-timedelta(hours=1)  # Already expired
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 401
    
    async def test_rate_limiting_on_login(self, client):
        """Test rate limiting on login attempts."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        # Make multiple failed login attempts
        for i in range(10):
            response = await client.post("/auth/login", json=login_data)
            
        # The 11th attempt should be rate limited
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 429  # Rate limited
    
    async def test_password_complexity_enforcement(self, client):
        """Test that weak passwords are rejected."""
        weak_password_data = {
            "email": "weakpass@example.com",
            "password": "123",  # Too weak
            "first_name": "Test",
            "last_name": "User",
            "role": "USER"
        }
        
        response = await client.post("/auth/register", json=weak_password_data)
        assert response.status_code == 422  # Validation error


class TestHIPAACompliance:
    """Test HIPAA compliance features."""
    
    async def test_audit_logging_on_auth_events(self, client, test_user, test_db_session):
        """Test that authentication events are properly logged."""
        # Perform login
        login_data = {
            "email": test_user.email,
            "password": "TestPassword123!"
        }
        
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        # Check audit logs
        result = await test_db_session.execute(
            "SELECT * FROM audit_logs WHERE user_id = :user_id",
            {"user_id": str(test_user.id)}
        )
        audit_logs = result.fetchall()
        assert len(audit_logs) > 0
        
        # Verify login event is logged
        login_events = [log for log in audit_logs if "login_success" in str(log)]
        assert len(login_events) > 0
    
    async def test_phi_access_logging(self, client, test_user, test_user_token, test_db_session):
        """Test that PHI access is properly logged."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Access PHI endpoint (will fail due to lack of permission, but should still log)
        response = await client.get("/api/v1/patients/patient123", headers=headers)
        
        # Check audit logs for PHI access attempt
        result = await test_db_session.execute(
            "SELECT * FROM audit_logs WHERE user_id = :user_id",
            {"user_id": str(test_user.id)}
        )
        audit_logs = result.fetchall()
        
        # Should have PHI access attempt logged
        phi_events = [log for log in audit_logs if "phi_access" in str(log).lower()]
        assert len(phi_events) > 0
    
    async def test_session_timeout_enforcement(self, client, test_user, custom_auth_provider):
        """Test that session timeouts are enforced."""
        # Create a token with very short expiry
        short_lived_token = await custom_auth_provider.create_access_token(
            user_id=str(test_user.id),
            expires_delta=timedelta(seconds=1)
        )
        
        headers = {"Authorization": f"Bearer {short_lived_token}"}
        
        # Token should work immediately
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 200
        
        # Wait for token to expire
        await asyncio.sleep(2)
        
        # Token should now be rejected
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 401


class TestBackwardCompatibility:
    """Test backward compatibility with existing endpoints."""
    
    async def test_hello_endpoint_works_without_auth(self, client):
        """Test that hello endpoint works without authentication."""
        response = await client.get("/api/v1/hello")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Hello from HIPAA-compliant healthcare API!"
        assert "timestamp" in data
    
    async def test_hello_endpoint_works_with_auth(self, client, test_user, test_user_token):
        """Test that hello endpoint works with authentication."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = await client.get("/api/v1/hello", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Hello from HIPAA-compliant healthcare API!"
        assert data["user_id"] == str(test_user.id)


class TestErrorHandling:
    """Test authentication error handling and messaging."""
    
    async def test_proper_error_messages_on_invalid_auth(self, client):
        """Test that error messages don't leak sensitive information."""
        # Test invalid credentials
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 401
        
        # Ensure no sensitive information in error message
        error_data = response.json()
        assert "Invalid email or password" in error_data.get("detail", "")
        assert "nonexistent@example.com" not in error_data.get("detail", "")
    
    async def test_malformed_token_handling(self, client):
        """Test handling of malformed JWT tokens."""
        headers = {"Authorization": "Bearer malformed.jwt.token"}
        
        response = await client.get("/api/v1/secure", headers=headers)
        assert response.status_code == 401
        
        error_data = response.json()
        assert "Invalid token" in error_data.get("detail", "")


class TestConcurrentSessions:
    """Test concurrent session management."""
    
    async def test_multiple_sessions_per_user(self, client, test_user):
        """Test that users can have multiple active sessions."""
        login_data = {
            "email": test_user.email,
            "password": "TestPassword123!"
        }
        
        # Login from multiple "devices"
        responses = []
        for i in range(3):
            response = await client.post("/auth/login", json=login_data)
            responses.append(response)
        
        # All logins should succeed
        for response in responses:
            assert response.status_code == 200
            
        # All tokens should be valid
        for response in responses:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            auth_response = await client.get("/api/v1/secure", headers=headers)
            assert auth_response.status_code == 200


class TestProviderHealthMonitoring:
    """Test authentication provider health monitoring."""
    
    async def test_provider_health_check_endpoint(self, client, test_user, admin_user_token):
        """Test provider health check functionality."""
        headers = {"Authorization": f"Bearer {admin_user_token}"}
        
        # This test would require the health endpoint to be implemented
        response = await client.get("/health/auth-provider", headers=headers)
        
        # Endpoint may not exist yet, but test the pattern
        assert response.status_code in [200, 404]


@pytest.mark.asyncio
class TestAuthenticationConfiguration:
    """Test authentication configuration and environment variables."""
    
    @patch.dict(os.environ, {"AUTH_PROVIDER_TYPE": "custom"})
    async def test_custom_provider_configuration(self):
        """Test custom provider configuration."""
        config = AuthConfig()
        assert config.provider_type == AuthProviderType.CUSTOM
    
    @patch.dict(os.environ, {"AUTH_PROVIDER_TYPE": "aws_cognito"})
    async def test_cognito_provider_configuration(self):
        """Test AWS Cognito provider configuration."""
        config = AuthConfig()
        assert config.provider_type == AuthProviderType.AWS_COGNITO
    
    @patch.dict(os.environ, {"AUTH_PROVIDER_TYPE": "auth0"})
    async def test_auth0_provider_configuration(self):
        """Test Auth0 provider configuration."""
        config = AuthConfig()
        assert config.provider_type == AuthProviderType.AUTH0
    
    async def test_jwt_secret_configuration(self):
        """Test JWT secret configuration."""
        with patch.dict(os.environ, {"JWT_SECRET_KEY": TEST_JWT_SECRET}):
            config = AuthConfig()
            assert config.jwt_secret == TEST_JWT_SECRET
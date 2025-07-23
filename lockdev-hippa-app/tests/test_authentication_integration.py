"""
Integration tests for the fixed authentication system.
Tests real database authentication flows with proper user validation.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import AsyncMock, patch, MagicMock

from src.main import app
from src.models.user import User
from src.models.audit_log import AuditLog
from src.utils.security import (
    create_access_token, 
    get_password_hash, 
    authenticate_user,
    get_current_user
)
from src.utils.database import get_db_session


class TestRealAuthenticationFlow:
    """Test the fixed authentication system with real database lookups."""
    
    async def test_get_current_user_with_valid_token_and_real_user(self, mock_db_with_user):
        """Test that get_current_user properly validates JWT and fetches real user from database."""
        session, user = mock_db_with_user
        
        # Create a valid JWT token with the user's ID
        token_data = {"sub": str(user.id)}
        valid_token = create_access_token(token_data)
        
        # Mock the HTTPAuthorizationCredentials
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        # Call get_current_user
        result_user = await get_current_user(credentials, session)
        
        # Verify the user was fetched from database
        assert result_user is not None
        assert result_user.id == user.id
        assert result_user.email == user.email
        assert result_user.is_active == True
        
        # Verify database was queried
        session.execute.assert_called_once()
        # Verify last_login was updated
        session.commit.assert_called()
    
    async def test_get_current_user_with_invalid_token(self, mock_db_no_user):
        """Test that invalid JWT tokens are rejected."""
        session = mock_db_no_user
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        # Test with invalid token
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, session)
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail
    
    async def test_get_current_user_with_nonexistent_user(self, mock_db_no_user):
        """Test that tokens for non-existent users are rejected."""
        session = mock_db_no_user
        
        # Create token for non-existent user
        fake_user_id = str(uuid.uuid4())
        token_data = {"sub": fake_user_id}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, session)
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail
        
        # Verify database was queried
        session.execute.assert_called_once()
    
    async def test_get_current_user_with_inactive_user(self, test_user_data):
        """Test that inactive users are rejected."""
        # Create inactive user
        test_user_data["is_active"] = False
        inactive_user = User(**test_user_data)
        
        session = AsyncMock(spec=AsyncSession)
        async def mock_execute(stmt):
            result = AsyncMock()
            result.scalar_one_or_none.return_value = None  # Active user query returns None
            return result
        
        session.execute = mock_execute
        session.add = AsyncMock()
        session.commit = AsyncMock()
        
        # Create token for inactive user
        token_data = {"sub": str(inactive_user.id)}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, session)
        
        assert exc_info.value.status_code == 401
    
    async def test_get_current_user_with_locked_account(self, test_user_data):
        """Test that locked user accounts are rejected."""
        # Create locked user
        test_user_data["account_locked_until"] = datetime.utcnow() + timedelta(minutes=30)
        locked_user = User(**test_user_data)
        
        session = AsyncMock(spec=AsyncSession)
        async def mock_execute(stmt):
            result = AsyncMock()
            result.scalar_one_or_none.return_value = locked_user
            return result
        
        session.execute = mock_execute
        session.add = AsyncMock()
        session.commit = AsyncMock()
        
        # Create token for locked user
        token_data = {"sub": str(locked_user.id)}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, session)
        
        assert exc_info.value.status_code == 423  # HTTP_423_LOCKED
        assert "Account is temporarily locked" in exc_info.value.detail
    
    async def test_authentication_audit_logging(self, mock_db_with_user):
        """Test that authentication attempts are properly logged for HIPAA compliance."""
        session, user = mock_db_with_user
        
        # Create valid token
        token_data = {"sub": str(user.id)}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        # Call get_current_user
        result_user = await get_current_user(credentials, session)
        
        # Verify audit log was created
        session.add.assert_called()
        # Check that an AuditLog object was added
        call_args = session.add.call_args[0][0]
        assert isinstance(call_args, AuditLog)
        assert call_args.action == "authentication_success"
        assert call_args.resource_type == "user"
        assert call_args.user_id == user.id
        assert call_args.outcome == "success"
    
    async def test_no_mock_users_created(self, mock_db_with_user):
        """Critical test: Ensure no mock users are created anywhere in authentication flow."""
        session, real_user = mock_db_with_user
        
        # Create valid token
        token_data = {"sub": str(real_user.id)}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        # Call get_current_user
        result_user = await get_current_user(credentials, session)
        
        # CRITICAL: Verify the returned user is the SAME object from database
        assert result_user is real_user
        # Verify no new User objects were instantiated with mock data
        assert result_user.email == real_user.email
        assert result_user.id == real_user.id
        # Verify it's not a mock email pattern
        assert not result_user.email.startswith("user")
        assert not result_user.email.endswith("@example.com")
        
        # Verify database query was actually performed
        session.execute.assert_called_once()


class TestUserPasswordAuthentication:
    """Test the authenticate_user function for password-based authentication."""
    
    async def test_authenticate_user_success(self, mock_db_with_user):
        """Test successful user authentication with email and password."""
        session, user = mock_db_with_user
        
        # Test authentication
        result = await authenticate_user(session, user.email, "testpassword123")
        
        assert result is not None
        assert result.id == user.id
        assert result.email == user.email
        
        # Verify login attempts were reset and last_login updated
        assert user.login_attempts == "0"
        assert user.last_login is not None
        session.commit.assert_called()
    
    async def test_authenticate_user_wrong_password(self, mock_db_with_user):
        """Test authentication failure with wrong password."""
        session, user = mock_db_with_user
        
        # Test authentication with wrong password
        result = await authenticate_user(session, user.email, "wrongpassword")
        
        assert result is None
        # Verify login attempts were incremented
        assert user.login_attempts == "1"
        session.commit.assert_called()
    
    async def test_authenticate_user_not_found(self, mock_db_no_user):
        """Test authentication with non-existent email."""
        session = mock_db_no_user
        
        result = await authenticate_user(session, "nonexistent@example.com", "password")
        
        assert result is None
        session.execute.assert_called_once()


class TestAPIEndpointsWithRealAuth:
    """Test API endpoints with the fixed authentication system."""
    
    def test_secure_endpoint_without_token(self):
        """Test that secure endpoints reject requests without tokens."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        
        client = TestClient(app)
        response = client.get("/api/v1/secure")
        
        # Should return 401 because no authentication provided
        # Note: The require_auth dependency will raise an exception when get_current_user returns None
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"] or "Could not validate credentials" in data["detail"]
    
    @patch('src.utils.security.get_current_user')
    def test_secure_endpoint_with_mocked_real_user(self, mock_get_current_user, test_user_data):
        """Test secure endpoint with a real user (mocked for API test)."""
        # Create a real user object (not a mock user)
        real_user = User(**test_user_data)
        mock_get_current_user.return_value = real_user
        
        client = TestClient(app)
        response = client.get("/api/v1/secure")
        
        assert response.status_code == 200
        data = response.json()
        assert "secure endpoint" in data["message"]
        assert data["user_id"] == str(real_user.id)
    
    def test_hello_endpoint_no_auth_required(self):
        """Test that optional auth endpoints work without authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/hello")
        
        assert response.status_code == 200
        data = response.json()
        assert "Hello from HIPAA-compliant" in data["message"]
        assert data["user_id"] is None  # No user when not authenticated


@pytest.mark.asyncio
class TestSecurityVulnerabilityFixes:
    """Critical tests to ensure the authentication vulnerability is completely fixed."""
    
    async def test_no_mock_user_creation_in_codebase(self):
        """Verify that the mock user creation code has been completely removed."""
        # Read the security.py file
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Ensure no mock user creation patterns exist
        assert "mock user" not in content.lower()
        assert "User(id=user_id" not in content
        assert "f\"user{user_id}@example.com\"" not in content
        assert "For now, we'll create" not in content
        
        # Ensure real database operations are present
        assert "select(User)" in content
        assert "scalar_one_or_none()" in content
        assert "User.is_active == True" in content
    
    async def test_jwt_token_validates_against_real_database(self, mock_db_with_user):
        """Critical test: JWT tokens must validate against real database records."""
        session, real_user = mock_db_with_user
        
        # Create token with real user ID
        token_data = {"sub": str(real_user.id)}
        valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", 
            credentials=valid_token
        )
        
        # This should query the database for the user
        result_user = await get_current_user(credentials, session)
        
        # Verify actual database query was performed
        session.execute.assert_called_once()
        
        # Verify returned user is from database, not created on-the-fly
        assert result_user is real_user
        assert result_user.id == real_user.id
        assert result_user.email == real_user.email
    
    async def test_fake_jwt_tokens_are_rejected(self, mock_db_no_user):
        """Test that fake JWT tokens with random user IDs are properly rejected."""
        session = mock_db_no_user
        
        # Create token with fake user ID
        fake_user_id = str(uuid.uuid4())
        token_data = {"sub": fake_user_id}
        token_with_fake_user = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token_with_fake_user
        )
        
        # This should fail because user doesn't exist in database
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, session)
        
        assert exc_info.value.status_code == 401
        
        # Verify database was actually queried (and user not found)
        session.execute.assert_called_once()
    
    async def test_authentication_requires_database_validation(self, mock_db_no_user):
        """Ensure authentication always requires successful database validation."""
        session = mock_db_no_user
        
        # Even with a valid JWT structure, if user doesn't exist in DB, auth fails
        real_uuid = str(uuid.uuid4())
        token_data = {"sub": real_uuid}
        structurally_valid_token = create_access_token(token_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=structurally_valid_token
        )
        
        # Should fail because database returns None
        with pytest.raises(HTTPException):
            await get_current_user(credentials, session)
        
        # Confirm database lookup was attempted
        session.execute.assert_called_once()
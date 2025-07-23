"""
Tests for CustomAuthProvider.

This module tests the complete CustomAuthProvider implementation including
all 29 abstract methods from AuthenticationProvider interface.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.providers.custom import CustomAuthProvider
from src.auth.models import AuthUser, AuthToken, AuthResult, TokenType, MFAMethod, UserRole
from src.auth.exceptions import AuthenticationError
from src.models.user import User


@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_user():
    """Create a sample User object."""
    user_id = uuid.uuid4()
    return User(
        id=user_id,
        email="test@example.com",
        hashed_password="$2b$12$hashed_password",
        is_active=True,
        is_superuser=False,
        first_name="Test",
        last_name="User",
        role="user",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        password_changed_at=datetime.utcnow(),
        login_attempts="0"
    )


@pytest.fixture
def sample_auth_user():
    """Create a sample AuthUser object."""
    return AuthUser(
        id=str(uuid.uuid4()),
        email="test@example.com",
        username="test@example.com",
        roles=[UserRole.PATIENT],
        permissions=[],
        is_active=True,
        is_verified=True,
        mfa_enabled=False,
        mfa_methods=[],
        created_at=datetime.utcnow(),
        last_login=None,
        last_password_change=datetime.utcnow(),
        password_expires_at=None,
        account_locked_until=None,
        failed_login_attempts=0,
        department=None,
        license_number=None,
        supervisor_id=None,
        metadata={}
    )


@pytest.fixture
def custom_provider():
    """Create a CustomAuthProvider instance."""
    config = {
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 7,
        "mfa_challenge_expire_minutes": 5,
        "password_reset_expire_hours": 24
    }
    return CustomAuthProvider("custom", config)


@pytest.mark.asyncio
class TestCustomAuthProvider:
    """Test cases for CustomAuthProvider core authentication methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authenticate_user_success(self, mock_get_db, custom_provider, mock_db_session, sample_user, sample_auth_user):
        """Test successful user authentication."""
        # Setup mocks
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock service responses
            mock_user_service.get_user_by_email.return_value = sample_auth_user
            mock_user_service.reset_failed_login_attempts.return_value = True
            mock_user_service.update_user.return_value = sample_auth_user
            mock_session_service.create_session.return_value = "session-123"
            
            # Mock database user lookup for password verification
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_user
            mock_db_session.execute.return_value = mock_result
            
            # Mock password verification
            with patch('src.auth.providers.custom.verify_password', return_value=True):
                result = await custom_provider.authenticate_user(
                    identifier="test@example.com",
                    credential="password123",
                    client_info={"ip_address": "192.168.1.1"}
                )
            
            assert result.success is True
            assert result.user is not None
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.session_id == "session-123"
            assert result.authentication_method == "password"
            assert result.provider == "custom"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authenticate_user_invalid_credentials(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test authentication with invalid credentials."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock user not found
            mock_user_service.get_user_by_email.return_value = None
            
            result = await custom_provider.authenticate_user(
                identifier="nonexistent@example.com",
                credential="password123"
            )
            
            assert result.success is False
            assert result.error_code == "INVALID_CREDENTIALS"
            assert result.user is None
            mock_audit_service.log_login_attempt.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authenticate_user_account_locked(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test authentication with locked account."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        # Set account as locked
        sample_auth_user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_email.return_value = sample_auth_user
            
            result = await custom_provider.authenticate_user(
                identifier="test@example.com",
                credential="password123"
            )
            
            assert result.success is False
            assert result.error_code == "ACCOUNT_LOCKED"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authenticate_user_mfa_required(self, mock_get_db, custom_provider, mock_db_session, sample_user, sample_auth_user):
        """Test authentication when MFA is required."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        # Enable MFA for user
        sample_auth_user.mfa_enabled = True
        sample_auth_user.mfa_methods = [MFAMethod.TOTP]
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            mock_user_service.get_user_by_email.return_value = sample_auth_user
            mock_user_service.reset_failed_login_attempts.return_value = True
            
            # Mock database user lookup
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_user
            mock_db_session.execute.return_value = mock_result
            
            with patch('src.auth.providers.custom.verify_password', return_value=True):
                result = await custom_provider.authenticate_user(
                    identifier="test@example.com",
                    credential="password123"
                )
            
            assert result.success is True
            assert result.mfa_required is True
            assert result.mfa_challenge_token is not None
            assert result.access_token is None  # No access token until MFA complete
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authenticate_token_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful token authentication."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create a valid token first
            token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.ACCESS,
                expires_in=timedelta(minutes=30)
            )
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            mock_session_service.validate_session.return_value = sample_auth_user.id
            
            result = await custom_provider.authenticate_token(token.token_value, TokenType.ACCESS)
            
            assert result.success is True
            assert result.user.id == sample_auth_user.id
            assert result.authentication_method == "token"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_refresh_token_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful token refresh."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create a refresh token
            refresh_token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.REFRESH,
                expires_in=timedelta(days=7),
                metadata={"session_id": "session-123"}
            )
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            mock_session_service.validate_session.return_value = sample_auth_user.id
            
            result = await custom_provider.refresh_token(
                refresh_token.token_value,
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert result.success is True
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.authentication_method == "refresh_token"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_revoke_token_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful token revocation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create a token to revoke
            token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.ACCESS,
                expires_in=timedelta(minutes=30)
            )
            
            success = await custom_provider.revoke_token(
                token.token_value,
                TokenType.ACCESS,
                revoked_by="admin"
            )
            
            assert success is True
            mock_audit_service.log_token_revocation.assert_called_once()


@pytest.mark.asyncio
class TestCustomAuthProviderUserManagement:
    """Test cases for user management methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_get_user_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful user retrieval."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            user = await custom_provider.get_user(sample_auth_user.id)
            
            assert user is not None
            assert user.id == sample_auth_user.id
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_create_user_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful user creation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.create_user.return_value = sample_auth_user
            
            user_data = {
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "first_name": "New",
                "last_name": "User"
            }
            
            user = await custom_provider.create_user(user_data, "admin")
            
            assert user is not None
            mock_user_service.create_user.assert_called_once_with(user_data, "admin")
            mock_audit_service.log_authentication_event.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_update_user_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful user update."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.update_user.return_value = sample_auth_user
            
            updates = {"first_name": "Updated"}
            
            user = await custom_provider.update_user(sample_auth_user.id, updates, "admin")
            
            assert user is not None
            mock_user_service.update_user.assert_called_once_with(sample_auth_user.id, updates, "admin")
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_deactivate_user_success(self, mock_get_db, custom_provider, mock_db_session):
        """Test successful user deactivation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.deactivate_user.return_value = True
            mock_session_service.invalidate_all_user_sessions.return_value = 2
            
            user_id = str(uuid.uuid4())
            success = await custom_provider.deactivate_user(user_id, "admin", "policy violation")
            
            assert success is True
            mock_user_service.deactivate_user.assert_called_once()
            mock_session_service.invalidate_all_user_sessions.assert_called_once()


@pytest.mark.asyncio
class TestCustomAuthProviderMFA:
    """Test cases for MFA methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_initiate_mfa_challenge_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful MFA challenge initiation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        # Enable MFA for user
        sample_auth_user.mfa_enabled = True
        sample_auth_user.mfa_methods = [MFAMethod.TOTP]
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            result = await custom_provider.initiate_mfa_challenge(
                sample_auth_user.id,
                MFAMethod.TOTP,
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert result.success is True
            assert result.mfa_required is True
            assert result.mfa_challenge_token is not None
            mock_audit_service.log_mfa_event.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_verify_mfa_challenge_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful MFA challenge verification."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create MFA challenge token
            challenge_token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.MFA_CHALLENGE,
                expires_in=timedelta(minutes=5),
                metadata={"mfa_method": "totp"}
            )
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            mock_session_service.create_session.return_value = "session-123"
            
            result = await custom_provider.verify_mfa_challenge(
                challenge_token.token_value,
                "123456",  # Valid 6-digit code
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert result.success is True
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.authentication_method == "mfa"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_verify_mfa_challenge_invalid_code(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test MFA challenge verification with invalid code."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create MFA challenge token
            challenge_token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.MFA_CHALLENGE,
                expires_in=timedelta(minutes=5)
            )
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            with pytest.raises(AuthenticationError, match="Invalid verification code"):
                await custom_provider.verify_mfa_challenge(
                    challenge_token.token_value,
                    "invalid",  # Invalid code format
                )
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_setup_mfa_method_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful MFA method setup."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            success = await custom_provider.setup_mfa_method(
                sample_auth_user.id,
                MFAMethod.TOTP,
                {"secret": "JBSWY3DPEHPK3PXP"}
            )
            
            assert success is True
            mock_audit_service.log_mfa_event.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_remove_mfa_method_success(self, mock_get_db, custom_provider, mock_db_session):
        """Test successful MFA method removal."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            user_id = str(uuid.uuid4())
            success = await custom_provider.remove_mfa_method(
                user_id,
                MFAMethod.TOTP,
                removed_by="admin"
            )
            
            assert success is True
            mock_audit_service.log_mfa_event.assert_called_once()


@pytest.mark.asyncio
class TestCustomAuthProviderTokenManagement:
    """Test cases for token management methods."""
    
    async def test_create_token_access(self, custom_provider):
        """Test access token creation."""
        user_id = str(uuid.uuid4())
        
        token = await custom_provider.create_token(
            user_id,
            TokenType.ACCESS,
            expires_in=timedelta(minutes=30)
        )
        
        assert token.token_type == TokenType.ACCESS
        assert token.user_id == user_id
        assert token.issued_by == "custom"
        assert token.token_value is not None
        assert len(token.token_value) > 100  # JWT should be long
    
    async def test_create_token_refresh(self, custom_provider):
        """Test refresh token creation."""
        user_id = str(uuid.uuid4())
        
        token = await custom_provider.create_token(
            user_id,
            TokenType.REFRESH,
            expires_in=timedelta(days=7),
            scopes=["read", "write"],
            metadata={"session_id": "session-123"}
        )
        
        assert token.token_type == TokenType.REFRESH
        assert token.user_id == user_id
        assert token.scopes == ["read", "write"]
        assert token.session_id == "session-123"
    
    async def test_validate_token_success(self, custom_provider):
        """Test successful token validation."""
        user_id = str(uuid.uuid4())
        
        # Create token
        original_token = await custom_provider.create_token(
            user_id,
            TokenType.ACCESS,
            expires_in=timedelta(minutes=30)
        )
        
        # Validate token
        validated_token = await custom_provider.validate_token(
            original_token.token_value,
            TokenType.ACCESS
        )
        
        assert validated_token.token_id == original_token.token_id
        assert validated_token.user_id == user_id
        assert validated_token.token_type == TokenType.ACCESS
    
    async def test_validate_token_wrong_type(self, custom_provider):
        """Test token validation with wrong token type."""
        user_id = str(uuid.uuid4())
        
        # Create access token
        token = await custom_provider.create_token(
            user_id,
            TokenType.ACCESS,
            expires_in=timedelta(minutes=30)
        )
        
        # Try to validate as refresh token
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            await custom_provider.validate_token(
                token.token_value,
                TokenType.REFRESH
            )
    
    async def test_validate_token_expired(self, custom_provider):
        """Test validation of expired token."""
        user_id = str(uuid.uuid4())
        
        # Create token that expires immediately
        token = await custom_provider.create_token(
            user_id,
            TokenType.ACCESS,
            expires_in=timedelta(seconds=-1)  # Already expired
        )
        
        with pytest.raises(AuthenticationError, match="Token has expired"):
            await custom_provider.validate_token(
                token.token_value,
                TokenType.ACCESS
            )
    
    async def test_validate_token_invalid(self, custom_provider):
        """Test validation of invalid token."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await custom_provider.validate_token(
                "invalid.token.value",
                TokenType.ACCESS
            )
    
    async def test_get_user_tokens(self, custom_provider):
        """Test getting user tokens (placeholder implementation)."""
        user_id = str(uuid.uuid4())
        
        tokens = await custom_provider.get_user_tokens(user_id)
        
        # Current implementation returns empty list (stateless JWTs)
        assert tokens == []


@pytest.mark.asyncio
class TestCustomAuthProviderPasswordManagement:
    """Test cases for password management methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_change_password_success(self, mock_get_db, custom_provider, mock_db_session, sample_user, sample_auth_user):
        """Test successful password change."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            mock_user_service.update_user.return_value = sample_auth_user
            mock_session_service.invalidate_all_user_sessions.return_value = 2
            
            # Mock database user lookup
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_user
            mock_db_session.execute.return_value = mock_result
            
            with patch('src.auth.providers.custom.verify_password', return_value=True):
                success = await custom_provider.change_password(
                    sample_auth_user.id,
                    "current_password",
                    "new_password123!",
                    changed_by=sample_auth_user.id
                )
            
            assert success is True
            mock_user_service.update_user.assert_called_once()
            mock_session_service.invalidate_all_user_sessions.assert_called_once()
            mock_audit_service.log_password_change.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_change_password_wrong_current(self, mock_get_db, custom_provider, mock_db_session, sample_user, sample_auth_user):
        """Test password change with wrong current password."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            # Mock database user lookup
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_user
            mock_db_session.execute.return_value = mock_result
            
            with patch('src.auth.providers.custom.verify_password', return_value=False):
                with pytest.raises(AuthenticationError, match="Current password is incorrect"):
                    await custom_provider.change_password(
                        sample_auth_user.id,
                        "wrong_password",
                        "new_password123!"
                    )
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_reset_password_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful password reset."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create password reset token
            reset_token = await custom_provider.create_token(
                sample_auth_user.id,
                TokenType.PASSWORD_RESET,
                expires_in=timedelta(hours=24)
            )
            
            mock_user_service.update_user.return_value = sample_auth_user
            mock_session_service.invalidate_all_user_sessions.return_value = 1
            
            success = await custom_provider.reset_password(
                sample_auth_user.id,
                reset_token.token_value,
                "new_password123!"
            )
            
            assert success is True
            mock_user_service.update_user.assert_called_once()
            mock_session_service.invalidate_all_user_sessions.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_initiate_password_reset_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful password reset initiation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_email.return_value = sample_auth_user
            
            success = await custom_provider.initiate_password_reset(
                "test@example.com",
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert success is True
            mock_audit_service.log_authentication_event.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_initiate_password_reset_user_not_found(self, mock_get_db, custom_provider, mock_db_session):
        """Test password reset initiation for non-existent user."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_user_service.get_user_by_email.return_value = None
            
            # Should still return True to prevent email enumeration
            success = await custom_provider.initiate_password_reset("nonexistent@example.com")
            
            assert success is True
            mock_audit_service.log_authentication_event.assert_called_once()


@pytest.mark.asyncio
class TestCustomAuthProviderSessionManagement:
    """Test cases for session management methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_create_session_success(self, mock_get_db, custom_provider, mock_db_session):
        """Test successful session creation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_session_service.create_session.return_value = "session-123"
            
            user_id = str(uuid.uuid4())
            session_id = await custom_provider.create_session(
                user_id,
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert session_id == "session-123"
            mock_session_service.create_session.assert_called_once_with(
                user_id, {"ip_address": "192.168.1.1"}
            )
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_validate_session_success(self, mock_get_db, custom_provider, mock_db_session, sample_auth_user):
        """Test successful session validation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_session_service.validate_session.return_value = sample_auth_user.id
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            user = await custom_provider.validate_session("session-123")
            
            assert user is not None
            assert user.id == sample_auth_user.id
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_invalidate_session_success(self, mock_get_db, custom_provider, mock_db_session):
        """Test successful session invalidation."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            mock_session_service.invalidate_session.return_value = True
            
            success = await custom_provider.invalidate_session("session-123", "admin")
            
            assert success is True
            mock_session_service.invalidate_session.assert_called_once_with("session-123", "admin")
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_get_user_sessions(self, mock_get_db, custom_provider, mock_db_session):
        """Test getting user sessions."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            expected_sessions = [
                {"session_id": "session-1", "is_active": True},
                {"session_id": "session-2", "is_active": True}
            ]
            mock_session_service.get_user_sessions.return_value = expected_sessions
            
            user_id = str(uuid.uuid4())
            sessions = await custom_provider.get_user_sessions(user_id, active_only=True)
            
            assert sessions == expected_sessions
            mock_session_service.get_user_sessions.assert_called_once_with(user_id, True)


@pytest.mark.asyncio
class TestCustomAuthProviderAuditAndCompliance:
    """Test cases for audit and compliance methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_log_authentication_event(self, mock_get_db, custom_provider, mock_db_session):
        """Test authentication event logging."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            await custom_provider.log_authentication_event(
                event_type="test_event",
                user_id=str(uuid.uuid4()),
                success=True,
                metadata={"test": "data"}
            )
            
            mock_audit_service.log_authentication_event.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_get_user_audit_log(self, mock_get_db, custom_provider, mock_db_session):
        """Test getting user audit log."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            expected_logs = [
                {"event": "login", "timestamp": "2023-01-01T00:00:00"},
                {"event": "logout", "timestamp": "2023-01-01T01:00:00"}
            ]
            mock_audit_service.get_user_audit_log.return_value = expected_logs
            
            user_id = str(uuid.uuid4())
            logs = await custom_provider.get_user_audit_log(
                user_id,
                start_date=datetime.utcnow() - timedelta(days=7),
                end_date=datetime.utcnow(),
                event_types=["login", "logout"]
            )
            
            assert logs == expected_logs
            mock_audit_service.get_user_audit_log.assert_called_once()


@pytest.mark.asyncio
class TestCustomAuthProviderHealthAndConfig:
    """Test cases for provider health and configuration methods."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_health_check_success(self, mock_get_db, custom_provider, mock_db_session):
        """Test successful health check."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock successful database query
            mock_db_session.execute.return_value = None
            
            health = await custom_provider.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "custom"
            assert health["database"] == "connected"
            assert "timestamp" in health
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_health_check_failure(self, mock_get_db, custom_provider, mock_db_session):
        """Test health check failure."""
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        with patch.object(custom_provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock database error
            mock_db_session.execute.side_effect = Exception("Database connection failed")
            
            health = await custom_provider.health_check()
            
            assert health["status"] == "unhealthy"
            assert health["provider"] == "custom"
            assert "error" in health
    
    async def test_get_provider_config(self, custom_provider):
        """Test getting provider configuration."""
        config = await custom_provider.get_provider_config()
        
        assert config["provider_name"] == "custom"
        assert config["provider_type"] == "custom"
        assert "features" in config
        assert "token_settings" in config
        assert "security_features" in config
        
        # Check feature flags
        features = config["features"]
        assert features["mfa_support"] is True
        assert features["session_management"] is True
        assert features["password_policies"] is True
        assert features["audit_logging"] is True
        assert features["account_lockout"] is True
        
        # Check token settings
        token_settings = config["token_settings"]
        assert token_settings["access_token_expire_minutes"] == 30
        assert token_settings["refresh_token_expire_days"] == 7
        
        # Check security features
        security_features = config["security_features"]
        assert security_features["password_hashing"] == "bcrypt"
        assert security_features["token_algorithm"] == "HS256"
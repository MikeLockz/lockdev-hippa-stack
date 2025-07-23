"""
Integration tests for CustomAuthProvider with AuthProviderFactory.

This module tests the complete integration of CustomAuthProvider with the
authentication factory system and real database operations.
"""

import pytest
import uuid
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.auth.factory import AuthProviderFactory
from src.auth.config import AuthConfig, AuthProviderType
from src.auth.providers.custom import CustomAuthProvider
from src.auth.models import AuthUser, TokenType, MFAMethod, UserRole
from src.auth.exceptions import AuthenticationError


@pytest.fixture
def auth_config():
    """Create an AuthConfig instance for testing."""
    return AuthConfig(
        provider_type=AuthProviderType.CUSTOM,
        jwt_secret_key="test_secret_key_that_is_long_enough_for_validation_32_chars",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        custom_config={
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7,
            "mfa_challenge_expire_minutes": 5,
            "password_reset_expire_hours": 24
        }
    )


@pytest.fixture
async def auth_factory(auth_config):
    """Create an AuthProviderFactory instance."""
    factory = AuthProviderFactory(auth_config)
    yield factory
    await factory.shutdown()


@pytest.fixture
def sample_auth_user():
    """Create a sample AuthUser for testing."""
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


@pytest.mark.asyncio
class TestCustomProviderFactoryRegistration:
    """Test CustomAuthProvider registration with AuthProviderFactory."""
    
    async def test_custom_provider_registered(self, auth_factory):
        """Test that CustomAuthProvider is properly registered."""
        providers = auth_factory.list_providers()
        
        # Find custom provider
        custom_provider_reg = None
        for provider in providers:
            if provider.provider_type == AuthProviderType.CUSTOM:
                custom_provider_reg = provider
                break
        
        assert custom_provider_reg is not None
        assert custom_provider_reg.provider_class == CustomAuthProvider
        assert custom_provider_reg.supports_mfa is True
        assert custom_provider_reg.description == "Custom authentication provider with HIPAA compliance"
    
    async def test_create_custom_provider_via_factory(self, auth_factory):
        """Test creating CustomAuthProvider instance via factory."""
        provider = await auth_factory.create_provider(AuthProviderType.CUSTOM)
        
        assert isinstance(provider, CustomAuthProvider)
        assert provider.provider_name == "custom"
    
    async def test_get_provider_info(self, auth_factory):
        """Test getting provider information."""
        info = auth_factory.get_provider_info(AuthProviderType.CUSTOM)
        
        assert info is not None
        assert info["type"] == "custom"
        assert info["supports_mfa"] is True
        assert info["supports_sso"] is False
        assert info["version"] == "1.0.0"
    
    async def test_get_providers_by_capability(self, auth_factory):
        """Test filtering providers by capabilities."""
        mfa_providers = auth_factory.get_providers_by_capability(supports_mfa=True)
        
        assert len(mfa_providers) >= 1
        custom_provider_info = None
        for provider in mfa_providers:
            if provider["type"] == "custom":
                custom_provider_info = provider
                break
        
        assert custom_provider_info is not None
        assert custom_provider_info["supports_mfa"] is True


@pytest.mark.asyncio
class TestCustomProviderIntegration:
    """Test CustomAuthProvider integration with full authentication flow."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_full_authentication_flow(self, mock_get_db, auth_factory, sample_auth_user):
        """Test complete authentication flow through factory."""
        # Mock database session
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        # Get provider via factory
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        # Mock services
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock service responses for authentication
            mock_user_service.get_user_by_email.return_value = sample_auth_user
            mock_user_service.reset_failed_login_attempts.return_value = True
            mock_user_service.update_user.return_value = sample_auth_user
            mock_session_service.create_session.return_value = "session-123"
            
            # Mock database user lookup
            from src.models.user import User
            mock_user = User(
                id=uuid.UUID(sample_auth_user.id),
                email=sample_auth_user.email,
                hashed_password="$2b$12$hashed_password",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_db_session.execute.return_value = mock_result
            
            # Mock password verification
            with patch('src.auth.providers.custom.verify_password', return_value=True):
                # Test authentication
                result = await provider.authenticate_user(
                    identifier="test@example.com",
                    credential="password123",
                    client_info={"ip_address": "192.168.1.1"}
                )
            
            # Verify authentication result
            assert result.success is True
            assert result.user is not None
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.session_id == "session-123"
            assert result.provider == "custom"
            
            # Verify all service calls were made
            mock_user_service.get_user_by_email.assert_called_once()
            mock_session_service.create_session.assert_called_once()
            mock_audit_service.log_login_attempt.assert_called()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_token_refresh_flow(self, mock_get_db, auth_factory, sample_auth_user):
        """Test token refresh flow through factory."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create a refresh token
            refresh_token = await provider.create_token(
                sample_auth_user.id,
                TokenType.REFRESH,
                expires_in=timedelta(days=7),
                metadata={"session_id": "session-123"}
            )
            
            # Mock service responses
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            mock_session_service.validate_session.return_value = sample_auth_user.id
            
            # Test token refresh
            result = await provider.refresh_token(
                refresh_token.token_value,
                client_info={"ip_address": "192.168.1.1"}
            )
            
            # Verify refresh result
            assert result.success is True
            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.authentication_method == "refresh_token"
            
            # Verify service calls
            mock_user_service.get_user_by_id.assert_called_once()
            mock_session_service.validate_session.assert_called_once()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_mfa_flow(self, mock_get_db, auth_factory, sample_auth_user):
        """Test MFA authentication flow through factory."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        # Enable MFA for user
        sample_auth_user.mfa_enabled = True
        sample_auth_user.mfa_methods = [MFAMethod.TOTP]
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Test MFA challenge initiation
            mock_user_service.get_user_by_id.return_value = sample_auth_user
            
            challenge_result = await provider.initiate_mfa_challenge(
                sample_auth_user.id,
                MFAMethod.TOTP,
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert challenge_result.success is True
            assert challenge_result.mfa_required is True
            assert challenge_result.mfa_challenge_token is not None
            
            # Test MFA verification
            mock_session_service.create_session.return_value = "mfa-session-456"
            
            verification_result = await provider.verify_mfa_challenge(
                challenge_result.mfa_challenge_token.token_value,
                "123456",  # Valid 6-digit code
                client_info={"ip_address": "192.168.1.1"}
            )
            
            assert verification_result.success is True
            assert verification_result.access_token is not None
            assert verification_result.refresh_token is not None
            assert verification_result.authentication_method == "mfa"
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_user_management_flow(self, mock_get_db, auth_factory):
        """Test user management operations through factory."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Test user creation
            user_data = {
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "first_name": "New",
                "last_name": "User"
            }
            
            created_user = AuthUser(
                id=str(uuid.uuid4()),
                email=user_data["email"],
                username=user_data["email"],
                roles=[UserRole.PATIENT],
                permissions=[],
                is_active=True,
                is_verified=False,
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
            
            mock_user_service.create_user.return_value = created_user
            
            result_user = await provider.create_user(user_data, "admin")
            
            assert result_user.email == user_data["email"]
            mock_user_service.create_user.assert_called_once_with(user_data, "admin")
            mock_audit_service.log_authentication_event.assert_called_once()
            
            # Test user update
            mock_user_service.update_user.return_value = created_user
            
            updates = {"first_name": "Updated"}
            updated_user = await provider.update_user(created_user.id, updates, "admin")
            
            assert updated_user is not None
            mock_user_service.update_user.assert_called_once_with(created_user.id, updates, "admin")
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_health_check_integration(self, mock_get_db, auth_factory):
        """Test provider health check through factory."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        # Mock successful database query
        mock_db_session.execute.return_value = None
        
        # Test health check via factory
        health = await auth_factory.health_check_provider(AuthProviderType.CUSTOM)
        
        assert health.provider_type == AuthProviderType.CUSTOM
        assert health.is_healthy is True
        assert health.response_time_ms is not None
        assert health.response_time_ms > 0
    
    async def test_provider_configuration_integration(self, auth_factory):
        """Test provider configuration through factory."""
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        config = await provider.get_provider_config()
        
        assert config["provider_name"] == "custom"
        assert config["provider_type"] == "custom"
        assert "features" in config
        assert "token_settings" in config
        assert "security_features" in config
        
        # Verify security features
        features = config["features"]
        assert features["mfa_support"] is True
        assert features["session_management"] is True
        assert features["password_policies"] is True
        assert features["audit_logging"] is True
        assert features["account_lockout"] is True


@pytest.mark.asyncio
class TestCustomProviderErrorHandling:
    """Test error handling in CustomAuthProvider integration."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_authentication_error_handling(self, mock_get_db, auth_factory):
        """Test error handling during authentication."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            # Mock service that raises an exception
            mock_get_services.side_effect = Exception("Database connection failed")
            
            result = await provider.authenticate_user(
                identifier="test@example.com",
                credential="password123"
            )
            
            assert result.success is False
            assert result.error_code is not None
            assert "authentication_failure" in result.error_message.lower() or "authentication failed" in result.error_message.lower()
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_token_validation_error_handling(self, mock_get_db, auth_factory):
        """Test error handling during token validation."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        # Test with invalid token
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await provider.validate_token("invalid.token.value", TokenType.ACCESS)
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_user_creation_error_handling(self, mock_get_db, auth_factory):
        """Test error handling during user creation."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Mock service error
            mock_user_service.create_user.side_effect = ValueError("Email already exists")
            
            with pytest.raises(AuthenticationError, match="User creation failed"):
                await provider.create_user({
                    "email": "existing@example.com",
                    "password": "password123"
                })


@pytest.mark.asyncio
class TestCustomProviderPerformance:
    """Test performance aspects of CustomAuthProvider integration."""
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_token_creation_performance(self, mock_get_db, auth_factory):
        """Test token creation performance."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            user_id = str(uuid.uuid4())
            
            # Measure token creation time
            import time
            start_time = time.time()
            
            # Create multiple tokens
            tokens = []
            for _ in range(10):
                token = await provider.create_token(
                    user_id,
                    TokenType.ACCESS,
                    expires_in=timedelta(minutes=30)
                )
                tokens.append(token)
            
            end_time = time.time()
            creation_time = end_time - start_time
            
            # Verify all tokens were created
            assert len(tokens) == 10
            assert all(token.token_value for token in tokens)
            assert all(token.user_id == user_id for token in tokens)
            
            # Performance should be reasonable (less than 1 second for 10 tokens)
            assert creation_time < 1.0
    
    @patch('src.auth.providers.custom.get_db_session')
    async def test_concurrent_operations(self, mock_get_db, auth_factory):
        """Test concurrent authentication operations."""
        mock_db_session = AsyncMock()
        mock_get_db.return_value.__anext__ = AsyncMock(return_value=mock_db_session)
        
        provider = await auth_factory.get_provider(AuthProviderType.CUSTOM)
        
        with patch.object(provider, '_get_services') as mock_get_services:
            mock_user_service = AsyncMock()
            mock_session_service = AsyncMock()
            mock_audit_service = AsyncMock()
            
            mock_get_services.return_value = (mock_user_service, mock_session_service, mock_audit_service, mock_db_session)
            
            # Create multiple concurrent token validation operations
            import asyncio
            
            user_id = str(uuid.uuid4())
            
            # Create tokens first
            tokens = []
            for i in range(5):
                token = await provider.create_token(
                    user_id,
                    TokenType.ACCESS,
                    expires_in=timedelta(minutes=30)
                )
                tokens.append(token)
            
            # Validate tokens concurrently
            async def validate_token_async(token):
                return await provider.validate_token(token.token_value, TokenType.ACCESS)
            
            # Run concurrent validations
            validation_tasks = [validate_token_async(token) for token in tokens]
            validated_tokens = await asyncio.gather(*validation_tasks)
            
            # Verify all validations succeeded
            assert len(validated_tokens) == 5
            assert all(validated_token.user_id == user_id for validated_token in validated_tokens)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Integration tests for authentication provider factory system.

Tests cover end-to-end scenarios with multiple providers, configuration
validation, health monitoring, and real-world usage patterns.
"""

import asyncio
import pytest
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional, List

from src.auth.factory import (
    AuthProviderFactory,
    ProviderRegistry,
    get_auth_factory,
    create_auth_provider
)
from src.auth.config import AuthConfig, AuthProviderType, ProviderHealthConfig
from src.auth.interfaces import AuthenticationProvider
from src.auth.models import AuthUser, AuthToken, AuthResult, TokenType, UserRole, MFAMethod
from src.auth.exceptions import AuthenticationError


class MockCognitoProvider(AuthenticationProvider):
    """Mock AWS Cognito provider for integration testing."""
    
    def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
        super().__init__(provider_name, config)
        self.users = {}
        self.tokens = {}
        self.health_calls = 0
    
    async def authenticate_user(self, identifier: str, credential: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        if identifier == "invalid@example.com":
            return AuthResult(
                success=False,
                authentication_method="cognito",
                provider=self.provider_name,
                error_code="INVALID_CREDENTIALS",
                error_message="Invalid credentials"
            )
        
        user = AuthUser(
            id=f"cognito_{identifier}",
            email=identifier,
            roles=[UserRole.CLINICIAN],
            created_at=datetime.utcnow(),
            mfa_enabled=True,
            mfa_methods=[MFAMethod.TOTP]
        )
        
        access_token = AuthToken(
            token_id="cognito_access_token",
            token_type=TokenType.ACCESS,
            token_value="cognito_access_token_value_32_chars",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            user_id=user.id,
            issued_by=self.provider_name
        )
        
        return AuthResult(
            success=True,
            user=user,
            access_token=access_token,
            authentication_method="cognito",
            provider=self.provider_name
        )
    
    async def authenticate_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> AuthResult:
        return AuthResult(
            success=True,
            user=AuthUser(
                id="cognito_user",
                email="cognito@example.com",
                roles=[UserRole.CLINICIAN],
                created_at=datetime.utcnow()
            ),
            authentication_method="token",
            provider=self.provider_name
        )
    
    async def health_check(self) -> Dict[str, Any]:
        self.health_calls += 1
        return {
            "status": "healthy",
            "provider": "aws_cognito",
            "user_pool_id": self.config.get("user_pool_id"),
            "region": self.config.get("region"),
            "health_calls": self.health_calls
        }
    
    # Implement other required methods with basic functionality
    async def refresh_token(self, refresh_token: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, authentication_method="refresh", provider=self.provider_name)
    
    async def revoke_token(self, token: str, token_type: TokenType, revoked_by: Optional[str] = None) -> bool:
        return True
    
    async def get_user(self, user_id: str) -> Optional[AuthUser]:
        return AuthUser(id=user_id, email="cognito@example.com", roles=[UserRole.CLINICIAN], created_at=datetime.utcnow())
    
    async def create_user(self, user_data: Dict[str, Any], created_by: Optional[str] = None) -> AuthUser:
        return AuthUser(id="new_user", email=user_data.get("email"), roles=[UserRole.PATIENT], created_at=datetime.utcnow())
    
    async def update_user(self, user_id: str, updates: Dict[str, Any], updated_by: Optional[str] = None) -> AuthUser:
        return AuthUser(id=user_id, email="updated@example.com", roles=[UserRole.PATIENT], created_at=datetime.utcnow())
    
    async def deactivate_user(self, user_id: str, deactivated_by: Optional[str] = None, reason: Optional[str] = None) -> bool:
        return True
    
    async def initiate_mfa_challenge(self, user_id: str, method: MFAMethod, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, mfa_required=True, authentication_method="mfa_challenge", provider=self.provider_name)
    
    async def verify_mfa_challenge(self, challenge_token: str, verification_code: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, authentication_method="mfa_verify", provider=self.provider_name)
    
    async def setup_mfa_method(self, user_id: str, method: MFAMethod, method_data: Dict[str, Any]) -> bool:
        return True
    
    async def remove_mfa_method(self, user_id: str, method: MFAMethod, removed_by: Optional[str] = None) -> bool:
        return True
    
    async def create_token(self, user_id: str, token_type: TokenType, expires_in: Optional[timedelta] = None, scopes: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> AuthToken:
        return AuthToken(
            token_id="test_token", token_type=token_type, token_value="test_token_value_32_chars_long",
            issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id=user_id, issued_by=self.provider_name
        )
    
    async def validate_token(self, token: str, token_type: TokenType, required_scopes: Optional[List[str]] = None) -> AuthToken:
        return AuthToken(
            token_id="test_token", token_type=token_type, token_value=token,
            issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id="test_user", issued_by=self.provider_name
        )
    
    async def get_user_tokens(self, user_id: str, token_type: Optional[TokenType] = None, active_only: bool = True) -> List[AuthToken]:
        return []
    
    async def change_password(self, user_id: str, current_password: str, new_password: str, changed_by: Optional[str] = None) -> bool:
        return True
    
    async def reset_password(self, user_id: str, reset_token: str, new_password: str) -> bool:
        return True
    
    async def initiate_password_reset(self, identifier: str, client_info: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    async def create_session(self, user_id: str, client_info: Optional[Dict[str, Any]] = None) -> str:
        return "cognito_session_id"
    
    async def validate_session(self, session_id: str) -> Optional[AuthUser]:
        return AuthUser(id="test_user", email="cognito@example.com", roles=[UserRole.CLINICIAN], created_at=datetime.utcnow())
    
    async def invalidate_session(self, session_id: str, invalidated_by: Optional[str] = None) -> bool:
        return True
    
    async def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        return []
    
    async def log_authentication_event(self, event_type: str, user_id: Optional[str], success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
        pass
    
    async def get_user_audit_log(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, event_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return []
    
    async def get_provider_config(self) -> Dict[str, Any]:
        return self.config.copy()


class MockAuth0Provider(AuthenticationProvider):
    """Mock Auth0 provider for integration testing."""
    
    def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
        super().__init__(provider_name, config)
        self.is_healthy = True
    
    async def authenticate_user(self, identifier: str, credential: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        user = AuthUser(
            id=f"auth0_{identifier}",
            email=identifier,
            roles=[UserRole.ADMIN],
            created_at=datetime.utcnow(),
            mfa_enabled=False
        )
        
        return AuthResult(
            success=True,
            user=user,
            authentication_method="auth0",
            provider=self.provider_name
        )
    
    async def health_check(self) -> Dict[str, Any]:
        if not self.is_healthy:
            raise Exception("Auth0 service unavailable")
        
        return {
            "status": "healthy",
            "provider": "auth0",
            "domain": self.config.get("domain"),
            "client_id": self.config.get("client_id")
        }
    
    # Implement other required methods with basic functionality
    async def authenticate_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> AuthResult:
        return AuthResult(success=True, authentication_method="token", provider=self.provider_name)
    
    async def refresh_token(self, refresh_token: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, authentication_method="refresh", provider=self.provider_name)
    
    async def revoke_token(self, token: str, token_type: TokenType, revoked_by: Optional[str] = None) -> bool:
        return True
    
    async def get_user(self, user_id: str) -> Optional[AuthUser]:
        return AuthUser(id=user_id, email="auth0@example.com", roles=[UserRole.ADMIN], created_at=datetime.utcnow())
    
    async def create_user(self, user_data: Dict[str, Any], created_by: Optional[str] = None) -> AuthUser:
        return AuthUser(id="new_user", email=user_data.get("email"), roles=[UserRole.PATIENT], created_at=datetime.utcnow())
    
    async def update_user(self, user_id: str, updates: Dict[str, Any], updated_by: Optional[str] = None) -> AuthUser:
        return AuthUser(id=user_id, email="updated@example.com", roles=[UserRole.PATIENT], created_at=datetime.utcnow())
    
    async def deactivate_user(self, user_id: str, deactivated_by: Optional[str] = None, reason: Optional[str] = None) -> bool:
        return True
    
    async def initiate_mfa_challenge(self, user_id: str, method: MFAMethod, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, mfa_required=True, authentication_method="mfa_challenge", provider=self.provider_name)
    
    async def verify_mfa_challenge(self, challenge_token: str, verification_code: str, client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
        return AuthResult(success=True, authentication_method="mfa_verify", provider=self.provider_name)
    
    async def setup_mfa_method(self, user_id: str, method: MFAMethod, method_data: Dict[str, Any]) -> bool:
        return True
    
    async def remove_mfa_method(self, user_id: str, method: MFAMethod, removed_by: Optional[str] = None) -> bool:
        return True
    
    async def create_token(self, user_id: str, token_type: TokenType, expires_in: Optional[timedelta] = None, scopes: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> AuthToken:
        return AuthToken(
            token_id="test_token", token_type=token_type, token_value="test_token_value_32_chars_long",
            issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id=user_id, issued_by=self.provider_name
        )
    
    async def validate_token(self, token: str, token_type: TokenType, required_scopes: Optional[List[str]] = None) -> AuthToken:
        return AuthToken(
            token_id="test_token", token_type=token_type, token_value=token,
            issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(hours=1),
            user_id="test_user", issued_by=self.provider_name
        )
    
    async def get_user_tokens(self, user_id: str, token_type: Optional[TokenType] = None, active_only: bool = True) -> List[AuthToken]:
        return []
    
    async def change_password(self, user_id: str, current_password: str, new_password: str, changed_by: Optional[str] = None) -> bool:
        return True
    
    async def reset_password(self, user_id: str, reset_token: str, new_password: str) -> bool:
        return True
    
    async def initiate_password_reset(self, identifier: str, client_info: Optional[Dict[str, Any]] = None) -> bool:
        return True
    
    async def create_session(self, user_id: str, client_info: Optional[Dict[str, Any]] = None) -> str:
        return "auth0_session_id"
    
    async def validate_session(self, session_id: str) -> Optional[AuthUser]:
        return AuthUser(id="test_user", email="auth0@example.com", roles=[UserRole.ADMIN], created_at=datetime.utcnow())
    
    async def invalidate_session(self, session_id: str, invalidated_by: Optional[str] = None) -> bool:
        return True
    
    async def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        return []
    
    async def log_authentication_event(self, event_type: str, user_id: Optional[str], success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
        pass
    
    async def get_user_audit_log(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, event_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return []
    
    async def get_provider_config(self) -> Dict[str, Any]:
        return self.config.copy()


@pytest.mark.asyncio
class TestProviderFactoryIntegration:
    """Integration tests for the provider factory system."""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment variables for testing."""
        return {
            'JWT_SECRET_KEY': 'integration_test_jwt_secret_key_32_chars',
            'AUTH_PROVIDER_TYPE': 'aws_cognito',
            'AWS_COGNITO_USER_POOL_ID': 'us-east-1_test123',
            'AWS_COGNITO_CLIENT_ID': 'test_client_id',
            'AWS_COGNITO_REGION': 'us-east-1',
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_CLIENT_ID': 'test_auth0_client',
            'AUTH0_CLIENT_SECRET': 'test_auth0_secret'
        }
    
    async def test_multi_provider_registration_and_creation(self, mock_env):
        """Test registering and creating multiple providers."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            health_config = ProviderHealthConfig(health_check_enabled=False)
            factory = AuthProviderFactory(config, health_config)
            
            # Register multiple providers
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                description="Mock AWS Cognito",
                supports_mfa=True,
                supports_sso=False
            )
            
            factory.register_provider(
                provider_type=AuthProviderType.AUTH0,
                provider_class=MockAuth0Provider,
                description="Mock Auth0",
                supports_mfa=True,
                supports_sso=True
            )
            
            # Create providers
            cognito_provider = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            auth0_provider = await factory.create_provider(AuthProviderType.AUTH0)
            
            # Verify providers are different instances
            assert cognito_provider is not auth0_provider
            assert isinstance(cognito_provider, MockCognitoProvider)
            assert isinstance(auth0_provider, MockAuth0Provider)
            
            # Test authentication with different providers
            cognito_result = await cognito_provider.authenticate_user("test@example.com", "password")
            auth0_result = await auth0_provider.authenticate_user("test@example.com", "password")
            
            assert cognito_result.success is True
            assert auth0_result.success is True
            assert cognito_result.user.roles[0] == UserRole.CLINICIAN
            assert auth0_result.user.roles[0] == UserRole.ADMIN
            
            await factory.shutdown()
    
    async def test_provider_configuration_validation_integration(self, mock_env):
        """Test end-to-end configuration validation."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register provider with config validator
            def cognito_validator(config: Dict[str, Any]) -> Dict[str, Any]:
                required_fields = ['user_pool_id', 'client_id', 'region']
                for field in required_fields:
                    if not config.get(field):
                        raise ValueError(f"Missing required field: {field}")
                return config
            
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                config_validator=cognito_validator
            )
            
            # Test with valid configuration
            provider = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            assert isinstance(provider, MockCognitoProvider)
            
            # Test configuration validation
            valid_config = {
                'user_pool_id': 'us-east-1_test123',
                'client_id': 'test_client',
                'region': 'us-east-1'
            }
            
            validated_config = await factory.validate_provider_config(
                AuthProviderType.AWS_COGNITO,
                valid_config
            )
            assert validated_config == valid_config
            
            # Test invalid configuration
            invalid_config = {'user_pool_id': 'test'}  # Missing required fields
            
            with pytest.raises(AuthenticationError) as exc_info:
                await factory.validate_provider_config(
                    AuthProviderType.AWS_COGNITO,
                    invalid_config
                )
            assert "Configuration validation failed" in str(exc_info.value)
            
            await factory.shutdown()
    
    async def test_health_monitoring_integration(self, mock_env):
        """Test health monitoring across multiple providers."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            health_config = ProviderHealthConfig(
                health_check_enabled=True,
                health_check_interval_seconds=0.1  # Very short for testing
            )
            factory = AuthProviderFactory(config, health_config)
            
            # Register providers
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider
            )
            factory.register_provider(
                provider_type=AuthProviderType.AUTH0,
                provider_class=MockAuth0Provider
            )
            
            # Create providers (starts health monitoring)
            cognito_provider = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            auth0_provider = await factory.create_provider(AuthProviderType.AUTH0)
            
            # Check initial health
            cognito_health = await factory.health_check_provider(AuthProviderType.AWS_COGNITO)
            auth0_health = await factory.health_check_provider(AuthProviderType.AUTH0)
            
            assert cognito_health.is_healthy is True
            assert auth0_health.is_healthy is True
            assert cognito_health.metadata['provider'] == 'aws_cognito'
            assert auth0_health.metadata['provider'] == 'auth0'
            
            # Simulate Auth0 failure
            auth0_provider.is_healthy = False
            
            # Wait for health check to detect failure
            await asyncio.sleep(0.2)
            failed_health = await factory.health_check_provider(AuthProviderType.AUTH0)
            assert failed_health.is_healthy is False
            assert "Auth0 service unavailable" in failed_health.error_message
            
            await factory.shutdown()
    
    async def test_provider_capability_filtering_integration(self, mock_env):
        """Test filtering providers by capabilities in real scenarios."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register providers with different capabilities
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                supports_mfa=True,
                supports_sso=False
            )
            factory.register_provider(
                provider_type=AuthProviderType.AUTH0,
                provider_class=MockAuth0Provider,
                supports_mfa=True,
                supports_sso=True
            )
            
            # Test MFA-capable providers
            mfa_providers = factory.get_providers_by_capability(supports_mfa=True)
            mfa_types = [p['type'] for p in mfa_providers if p]
            assert 'aws_cognito' in mfa_types
            assert 'auth0' in mfa_types
            
            # Test SSO-capable providers
            sso_providers = factory.get_providers_by_capability(supports_sso=True)
            sso_types = [p['type'] for p in sso_providers if p]
            assert 'auth0' in sso_types
            assert 'aws_cognito' not in sso_types
            
            # Test providers with both capabilities
            both_providers = factory.get_providers_by_capability(
                supports_mfa=True,
                supports_sso=True
            )
            both_types = [p['type'] for p in both_providers if p]
            assert 'auth0' in both_types
            assert 'aws_cognito' not in both_types
            
            await factory.shutdown()
    
    async def test_provider_lifecycle_with_errors(self, mock_env):
        """Test provider lifecycle with error conditions."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register provider
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider
            )
            
            # Create provider successfully
            provider = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            assert isinstance(provider, MockCognitoProvider)
            
            # Test authentication failure handling
            failed_result = await provider.authenticate_user("invalid@example.com", "wrong_password")
            assert failed_result.success is False
            assert failed_result.error_code == "INVALID_CREDENTIALS"
            
            # Test successful authentication
            success_result = await provider.authenticate_user("valid@example.com", "password")
            assert success_result.success is True
            assert success_result.user is not None
            assert success_result.user.mfa_enabled is True
            
            # Test provider destruction
            destroyed = await factory.destroy_provider(AuthProviderType.AWS_COGNITO)
            assert destroyed is True
            
            # Try to destroy again (should return False)
            destroyed_again = await factory.destroy_provider(AuthProviderType.AWS_COGNITO)
            assert destroyed_again is False
            
            await factory.shutdown()
    
    async def test_concurrent_provider_operations(self, mock_env):
        """Test concurrent operations on multiple providers."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register multiple providers
            providers_config = [
                (AuthProviderType.AWS_COGNITO, MockCognitoProvider),
                (AuthProviderType.AUTH0, MockAuth0Provider),
            ]
            
            for provider_type, provider_class in providers_config:
                factory.register_provider(
                    provider_type=provider_type,
                    provider_class=provider_class
                )
            
            # Create providers concurrently
            creation_tasks = [
                factory.create_provider(provider_type)
                for provider_type, _ in providers_config
            ]
            
            providers = await asyncio.gather(*creation_tasks)
            assert len(providers) == 2
            
            # Perform health checks concurrently
            health_tasks = [
                factory.health_check_provider(provider_type)
                for provider_type, _ in providers_config
            ]
            
            health_results = await asyncio.gather(*health_tasks)
            assert all(health.is_healthy for health in health_results)
            
            # Perform authentication concurrently
            auth_tasks = [
                provider.authenticate_user(f"user{i}@example.com", "password")
                for i, provider in enumerate(providers)
            ]
            
            auth_results = await asyncio.gather(*auth_tasks)
            assert all(result.success for result in auth_results)
            
            await factory.shutdown()
    
    async def test_factory_reconfiguration(self, mock_env):
        """Test reconfiguring factory with new providers."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Initial configuration
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                description="Initial Cognito"
            )
            
            provider1 = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            info1 = factory.get_provider_info(AuthProviderType.AWS_COGNITO)
            assert info1['description'] == "Initial Cognito"
            
            # Reconfigure provider (unregister and re-register)
            factory.registry.unregister_provider(AuthProviderType.AWS_COGNITO)
            await factory.destroy_provider(AuthProviderType.AWS_COGNITO)
            
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                description="Updated Cognito",
                version="2.0.0"
            )
            
            provider2 = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            info2 = factory.get_provider_info(AuthProviderType.AWS_COGNITO)
            assert info2['description'] == "Updated Cognito"
            assert info2['version'] == "2.0.0"
            
            # Verify new provider is different instance
            assert provider1 is not provider2
            
            await factory.shutdown()
    
    async def test_provider_metadata_and_configuration(self, mock_env):
        """Test provider metadata handling and configuration access."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register provider with metadata
            factory.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=MockCognitoProvider,
                description="Production Cognito Provider",
                version="1.2.3",
                dependencies=["boto3", "botocore"],
                supports_mfa=True,
                supports_sso=False
            )
            
            # Create provider and verify configuration
            provider = await factory.create_provider(AuthProviderType.AWS_COGNITO)
            
            # Check provider has access to configuration
            provider_config = await provider.get_provider_config()
            assert provider_config['user_pool_id'] == 'us-east-1_test123'
            assert provider_config['client_id'] == 'test_client_id'
            assert provider_config['region'] == 'us-east-1'
            
            # Check provider metadata
            info = factory.get_provider_info(AuthProviderType.AWS_COGNITO)
            assert info['description'] == "Production Cognito Provider"
            assert info['version'] == "1.2.3"
            assert info['supports_mfa'] is True
            assert info['supports_sso'] is False
            
            # Check health status in metadata
            health = await factory.health_check_provider(AuthProviderType.AWS_COGNITO)
            assert health.metadata['user_pool_id'] == 'us-east-1_test123'
            assert health.metadata['provider'] == 'aws_cognito'
            
            await factory.shutdown()
    
    async def test_global_factory_integration(self, mock_env):
        """Test global factory functions with real providers."""
        # Clear global instance
        import src.auth.factory
        src.auth.factory._factory_instance = None
        
        try:
            with patch.dict(os.environ, mock_env):
                # Get global factory
                factory = await get_auth_factory()
                
                # Register a working provider
                factory.register_provider(
                    provider_type=AuthProviderType.AWS_COGNITO,
                    provider_class=MockCognitoProvider
                )
                
                # Create provider using convenience function
                provider = await create_auth_provider(AuthProviderType.AWS_COGNITO)
                assert isinstance(provider, MockCognitoProvider)
                
                # Test authentication
                result = await provider.authenticate_user("test@example.com", "password")
                assert result.success is True
                
                # Verify global factory is reused
                factory2 = await get_auth_factory()
                assert factory is factory2
                
                await factory.shutdown()
        
        finally:
            # Clean up global instance
            src.auth.factory._factory_instance = None
    
    async def test_error_recovery_and_resilience(self, mock_env):
        """Test error recovery and system resilience."""
        with patch.dict(os.environ, mock_env):
            config = AuthConfig()
            factory = AuthProviderFactory(config)
            
            # Register provider
            factory.register_provider(
                provider_type=AuthProviderType.AUTH0,
                provider_class=MockAuth0Provider
            )
            
            # Create provider successfully
            provider = await factory.create_provider(AuthProviderType.AUTH0)
            
            # Test normal operation
            health1 = await factory.health_check_provider(AuthProviderType.AUTH0)
            assert health1.is_healthy is True
            
            # Simulate provider failure
            provider.is_healthy = False
            
            # Health check should detect failure
            health2 = await factory.health_check_provider(AuthProviderType.AUTH0)
            assert health2.is_healthy is False
            
            # Simulate recovery
            provider.is_healthy = True
            
            # Health check should detect recovery
            health3 = await factory.health_check_provider(AuthProviderType.AUTH0)
            assert health3.is_healthy is True
            
            # Test authentication still works after recovery
            auth_result = await provider.authenticate_user("test@example.com", "password")
            assert auth_result.success is True
            
            await factory.shutdown()


@pytest.fixture(autouse=True)
def cleanup_integration():
    """Cleanup after integration tests."""
    yield
    # Reset global factory instance
    import src.auth.factory
    src.auth.factory._factory_instance = None
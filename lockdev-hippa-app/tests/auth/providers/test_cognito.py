"""
Tests for AWS Cognito authentication provider.

This module contains comprehensive tests for the CognitoAuthProvider including
unit tests, integration tests, HIPAA compliance validation, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from botocore.exceptions import ClientError

from src.auth.providers.cognito import CognitoAuthProvider
from src.auth.providers.cognito_utils import CognitoConfig, CognitoErrorHandler
from src.auth.models import AuthUser, AuthToken, AuthResult, TokenType, MFAMethod, UserRole
from src.auth.exceptions import AuthenticationError, ConfigurationError


@pytest.fixture
def cognito_config():
    """Create a test Cognito configuration."""
    return {
        'region': 'us-east-1',
        'user_pool_id': 'us-east-1_TEST123',
        'client_id': 'test-client-id',
        'client_secret': 'test-client-secret',
        'enable_advanced_security': True,
        'enable_audit_logging': True,
        'enable_mfa_enforcement': True,
        'password_policy_enabled': True,
    }


@pytest.fixture
def mock_cognito_client():
    """Create a mock Cognito client."""
    mock_client = Mock()
    mock_client.describe_user_pool.return_value = {
        'UserPool': {
            'Id': 'us-east-1_TEST123',
            'Name': 'test-pool'
        }
    }
    return mock_client


@pytest.fixture
def mock_jwt_validator():
    """Create a mock JWT validator."""
    mock_validator = Mock()
    mock_validator.validate_token.return_value = {
        'sub': 'test-user-id',
        'email': 'test@example.com',
        'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        'token_use': 'access',
        'scope': 'read write'
    }
    return mock_validator


@pytest.fixture
async def cognito_provider(cognito_config, mock_cognito_client, mock_jwt_validator):
    """Create a CognitoAuthProvider instance for testing."""
    with patch('src.auth.providers.cognito.CognitoClientManager') as mock_manager_class, \
         patch('src.auth.providers.cognito.CognitoJWTValidator') as mock_validator_class, \
         patch('src.auth.providers.cognito.CognitoAuditLogger') as mock_logger_class:
        
        # Mock the client manager
        mock_manager = Mock()
        mock_manager.cognito_client = mock_cognito_client
        mock_manager.health_check = AsyncMock(return_value={'status': 'healthy'})
        mock_manager_class.return_value = mock_manager
        
        # Mock the JWT validator
        mock_validator_class.return_value = mock_jwt_validator
        
        # Mock the audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_authentication_event = AsyncMock()
        mock_logger_class.return_value = mock_audit_logger
        
        provider = CognitoAuthProvider('test_cognito', cognito_config)
        return provider


class TestCognitoConfig:
    """Test CognitoConfig class."""
    
    def test_config_from_env(self):
        """Test configuration creation from environment variables."""
        with patch.dict('os.environ', {
            'AWS_COGNITO_REGION': 'us-west-2',
            'AWS_COGNITO_USER_POOL_ID': 'us-west-2_TEST456',
            'AWS_COGNITO_CLIENT_ID': 'test-client-456',
        }):
            config = CognitoConfig.from_env()
            assert config.region == 'us-west-2'
            assert config.user_pool_id == 'us-west-2_TEST456'
            assert config.client_id == 'test-client-456'
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = CognitoConfig(
            region='us-east-1',
            user_pool_id='us-east-1_TEST123',
            client_id='test-client-id'
        )
        config.validate()  # Should not raise
    
    def test_config_validation_missing_region(self):
        """Test configuration validation with missing region."""
        config = CognitoConfig(
            region='',
            user_pool_id='us-east-1_TEST123',
            client_id='test-client-id'
        )
        with pytest.raises(ConfigurationError, match="AWS region is required"):
            config.validate()
    
    def test_config_validation_missing_user_pool_id(self):
        """Test configuration validation with missing user pool ID."""
        config = CognitoConfig(
            region='us-east-1',
            user_pool_id='',
            client_id='test-client-id'
        )
        with pytest.raises(ConfigurationError, match="Cognito User Pool ID is required"):
            config.validate()
    
    def test_config_validation_missing_client_id(self):
        """Test configuration validation with missing client ID."""
        config = CognitoConfig(
            region='us-east-1',
            user_pool_id='us-east-1_TEST123',
            client_id=''
        )
        with pytest.raises(ConfigurationError, match="Cognito Client ID is required"):
            config.validate()


class TestCognitoErrorHandler:
    """Test CognitoErrorHandler class."""
    
    def test_handle_user_not_found_error(self):
        """Test handling of UserNotFoundException."""
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'UserNotFoundException',
                    'Message': 'User does not exist'
                }
            },
            operation_name='AdminGetUser'
        )
        
        auth_error = CognitoErrorHandler.handle_cognito_error(client_error, 'get_user')
        
        assert isinstance(auth_error, AuthenticationError)
        assert auth_error.message == 'User not found'
        assert auth_error.error_code == 'UserNotFoundException'
    
    def test_handle_not_authorized_error(self):
        """Test handling of NotAuthorizedException."""
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'NotAuthorizedException',
                    'Message': 'Incorrect username or password'
                }
            },
            operation_name='InitiateAuth'
        )
        
        auth_error = CognitoErrorHandler.handle_cognito_error(client_error, 'authenticate')
        
        assert isinstance(auth_error, AuthenticationError)
        assert auth_error.message == 'Invalid credentials'
        assert auth_error.error_code == 'NotAuthorizedException'
    
    def test_handle_unknown_error(self):
        """Test handling of unknown exceptions."""
        unknown_error = ValueError("Unknown error")
        
        auth_error = CognitoErrorHandler.handle_cognito_error(unknown_error, 'test_operation')
        
        assert isinstance(auth_error, AuthenticationError)
        assert 'Unexpected error during test_operation' in auth_error.message
        assert auth_error.error_code == 'UNKNOWN_ERROR'


class TestCognitoAuthProvider:
    """Test CognitoAuthProvider class."""
    
    @pytest.mark.asyncio
    async def test_provider_initialization(self, cognito_config):
        """Test CognitoAuthProvider initialization."""
        with patch('src.auth.providers.cognito.CognitoClientManager'), \
             patch('src.auth.providers.cognito.CognitoJWTValidator'), \
             patch('src.auth.providers.cognito.CognitoAuditLogger'):
            
            provider = CognitoAuthProvider('test_cognito', cognito_config)
            
            assert provider.provider_name == 'test_cognito'
            assert provider.cognito_config.region == 'us-east-1'
            assert provider.cognito_config.user_pool_id == 'us-east-1_TEST123'
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, cognito_provider):
        """Test successful user authentication."""
        # Mock Cognito response
        auth_response = {
            'AuthenticationResult': {
                'AccessToken': 'test-access-token',
                'RefreshToken': 'test-refresh-token',
                'ExpiresIn': 3600
            }
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = auth_response
        
        # Mock get_user to return a user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        # Mock JWT validation
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()
        })
        
        result = await cognito_provider.authenticate_user(
            'test@example.com', 
            'password123',
            {'ip_address': '127.0.0.1'}
        )
        
        assert result.success is True
        assert result.user is not None
        assert result.user.id == 'test-user-id'
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.authentication_method == 'cognito_user_password'
        assert result.provider == 'test_cognito'
    
    @pytest.mark.asyncio
    async def test_authenticate_user_mfa_required(self, cognito_provider):
        """Test user authentication with MFA challenge."""
        # Mock Cognito response with MFA challenge
        auth_response = {
            'ChallengeName': 'SMS_MFA',
            'Session': 'challenge-session-token'
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = auth_response
        
        result = await cognito_provider.authenticate_user(
            'test@example.com', 
            'password123'
        )
        
        assert result.success is False
        assert result.mfa_required is True
        assert result.mfa_challenge_token is not None
        assert MFAMethod.SMS in result.mfa_methods
        assert result.authentication_method == 'cognito_user_password'
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_credentials(self, cognito_provider):
        """Test user authentication with invalid credentials."""
        # Mock Cognito error
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'NotAuthorizedException',
                    'Message': 'Incorrect username or password'
                }
            },
            operation_name='InitiateAuth'
        )
        
        cognito_provider.client_manager.cognito_client.initiate_auth.side_effect = client_error
        
        with pytest.raises(AuthenticationError, match='Invalid credentials'):
            await cognito_provider.authenticate_user('test@example.com', 'wrong-password')
    
    @pytest.mark.asyncio
    async def test_authenticate_token_success(self, cognito_provider):
        """Test successful token authentication."""
        # Mock JWT validation
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            'scope': 'read write'
        })
        
        # Mock get_user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow()
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        result = await cognito_provider.authenticate_token('test-access-token')
        
        assert result.success is True
        assert result.user is not None
        assert result.user.id == 'test-user-id'
        assert result.access_token is not None
        assert result.authentication_method == 'cognito_token'
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, cognito_provider):
        """Test successful token refresh."""
        # Mock Cognito response
        refresh_response = {
            'AuthenticationResult': {
                'AccessToken': 'new-access-token',
                'ExpiresIn': 3600
            }
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = refresh_response
        
        # Mock JWT validation
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()
        })
        
        # Mock get_user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow()
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        result = await cognito_provider.refresh_token('test-refresh-token')
        
        assert result.success is True
        assert result.user is not None
        assert result.access_token is not None
        assert result.authentication_method == 'cognito_refresh_token'
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, cognito_provider):
        """Test retrieving user by ID."""
        # Mock Cognito response
        cognito_user_data = {
            'Users': [{
                'Username': 'test@example.com',
                'Attributes': [
                    {'Name': 'sub', 'Value': 'test-user-id'},
                    {'Name': 'email', 'Value': 'test@example.com'},
                    {'Name': 'custom:roles', 'Value': 'patient'},
                ],
                'UserStatus': 'CONFIRMED',
                'UserCreateDate': datetime.utcnow(),
                'UserLastModifiedDate': datetime.utcnow(),
                'MFAOptions': []
            }]
        }
        
        cognito_provider.client_manager.cognito_client.list_users.return_value = cognito_user_data
        
        user = await cognito_provider.get_user('test-user-id')
        
        assert user is not None
        assert user.id == 'test-user-id'
        assert user.email == 'test@example.com'
        assert UserRole.PATIENT in user.roles
        assert user.is_verified is True
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, cognito_provider):
        """Test retrieving non-existent user."""
        # Mock Cognito error
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'UserNotFoundException',
                    'Message': 'User does not exist'
                }
            },
            operation_name='ListUsers'
        )
        
        cognito_provider.client_manager.cognito_client.list_users.side_effect = client_error
        cognito_provider.client_manager.cognito_client.admin_get_user.side_effect = client_error
        
        user = await cognito_provider.get_user('non-existent-user')
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, cognito_provider):
        """Test successful user creation."""
        # Mock Cognito response
        create_response = {
            'User': {
                'Username': 'test@example.com',
                'Attributes': [
                    {'Name': 'sub', 'Value': 'new-user-id'},
                    {'Name': 'email', 'Value': 'test@example.com'},
                ],
                'UserStatus': 'FORCE_CHANGE_PASSWORD'
            }
        }
        
        cognito_provider.client_manager.cognito_client.admin_create_user.return_value = create_response
        
        # Mock get_user to return the created user
        mock_user = AuthUser(
            id='new-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow()
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        user_data = {
            'email': 'test@example.com',
            'roles': [UserRole.PATIENT],
            'department': 'cardiology'
        }
        
        created_user = await cognito_provider.create_user(user_data, 'admin-user')
        
        assert created_user is not None
        assert created_user.id == 'new-user-id'
        assert created_user.email == 'test@example.com'
    
    @pytest.mark.asyncio
    async def test_setup_mfa_sms(self, cognito_provider):
        """Test setting up SMS MFA."""
        # Mock get_user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        # Mock Cognito responses
        cognito_provider.client_manager.cognito_client.admin_update_user_attributes.return_value = {}
        cognito_provider.client_manager.cognito_client.admin_set_user_mfa_preference.return_value = {}
        
        result = await cognito_provider.setup_mfa_method(
            'test-user-id',
            MFAMethod.SMS,
            {'phone_number': '+1234567890'}
        )
        
        assert result is True
        
        # Verify that the correct Cognito methods were called
        cognito_provider.client_manager.cognito_client.admin_update_user_attributes.assert_called_once()
        cognito_provider.client_manager.cognito_client.admin_set_user_mfa_preference.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_setup_mfa_totp(self, cognito_provider):
        """Test setting up TOTP MFA."""
        # Mock get_user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        # Mock Cognito response
        totp_response = {
            'SecretCode': 'ABCDEFGHIJKLMNOP'
        }
        cognito_provider.client_manager.cognito_client.associate_software_token.return_value = totp_response
        
        method_data = {'access_token': 'test-access-token'}
        result = await cognito_provider.setup_mfa_method(
            'test-user-id',
            MFAMethod.TOTP,
            method_data
        )
        
        assert result is True
        assert method_data['secret_code'] == 'ABCDEFGHIJKLMNOP'
    
    @pytest.mark.asyncio
    async def test_change_password_success(self, cognito_provider):
        """Test successful password change."""
        # Mock get_user
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        
        # Mock Cognito response
        cognito_provider.client_manager.cognito_client.admin_set_user_password.return_value = {}
        
        result = await cognito_provider.change_password(
            'test-user-id',
            'old-password',
            'new-password',
            'admin-user'
        )
        
        assert result is True
        cognito_provider.client_manager.cognito_client.admin_set_user_password.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initiate_password_reset_success(self, cognito_provider):
        """Test successful password reset initiation."""
        # Mock Cognito response
        cognito_provider.client_manager.cognito_client.forgot_password.return_value = {}
        
        result = await cognito_provider.initiate_password_reset(
            'test@example.com',
            {'ip_address': '127.0.0.1'}
        )
        
        assert result is True
        cognito_provider.client_manager.cognito_client.forgot_password.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(self, cognito_provider):
        """Test provider health check."""
        expected_health = {
            'status': 'healthy',
            'last_check': '2024-01-01T00:00:00',
            'user_pool_id': 'us-east-1_TEST123',
            'region': 'us-east-1'
        }
        
        cognito_provider.client_manager.health_check = AsyncMock(return_value=expected_health)
        
        health = await cognito_provider.health_check()
        
        assert health == expected_health
        assert health['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_get_provider_config(self, cognito_provider):
        """Test getting provider configuration."""
        config = await cognito_provider.get_provider_config()
        
        assert config['provider_name'] == 'test_cognito'
        assert config['provider_type'] == 'aws_cognito'
        assert config['region'] == 'us-east-1'
        assert config['user_pool_id'] == 'us-east-1_TEST123'
        assert config['client_id'] == 'test-client-id'
        assert 'client_secret' not in config  # Should not expose sensitive data


class TestCognitoHIPAACompliance:
    """Test HIPAA compliance features of Cognito provider."""
    
    @pytest.mark.asyncio
    async def test_audit_logging_on_authentication(self, cognito_provider):
        """Test that authentication events are properly logged for audit."""
        # Setup successful authentication
        auth_response = {
            'AuthenticationResult': {
                'AccessToken': 'test-access-token',
                'RefreshToken': 'test-refresh-token',
                'ExpiresIn': 3600
            }
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = auth_response
        
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()
        })
        
        client_info = {
            'ip_address': '127.0.0.1',
            'user_agent': 'TestAgent/1.0'
        }
        
        await cognito_provider.authenticate_user(
            'test@example.com', 
            'password123',
            client_info
        )
        
        # Verify audit logging was called
        cognito_provider.audit_logger.log_authentication_event.assert_called_with(
            'user_authentication_success', 
            'test-user-id', 
            True, 
            client_info
        )
    
    @pytest.mark.asyncio
    async def test_audit_logging_on_failed_authentication(self, cognito_provider):
        """Test that failed authentication events are properly logged."""
        # Setup failed authentication
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'NotAuthorizedException',
                    'Message': 'Incorrect username or password'
                }
            },
            operation_name='InitiateAuth'
        )
        
        cognito_provider.client_manager.cognito_client.initiate_auth.side_effect = client_error
        
        client_info = {'ip_address': '127.0.0.1'}
        
        with pytest.raises(AuthenticationError):
            await cognito_provider.authenticate_user(
                'test@example.com', 
                'wrong-password',
                client_info
            )
        
        # Verify audit logging was called for failure
        cognito_provider.audit_logger.log_authentication_event.assert_called()
        call_args = cognito_provider.audit_logger.log_authentication_event.call_args
        assert call_args[0][0] == 'user_authentication_failure'  # event_type
        assert call_args[0][1] == 'test@example.com'  # user_id
        assert call_args[0][2] is False  # success
    
    @pytest.mark.asyncio
    async def test_phi_protection_in_error_messages(self, cognito_provider):
        """Test that error messages don't expose PHI."""
        # Setup authentication error
        client_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'UserNotFoundException',
                    'Message': 'User test@example.com does not exist'  # Contains PHI
                }
            },
            operation_name='AdminGetUser'
        )
        
        cognito_provider.client_manager.cognito_client.list_users.side_effect = client_error
        cognito_provider.client_manager.cognito_client.admin_get_user.side_effect = client_error
        
        user = await cognito_provider.get_user('test@example.com')
        
        # User should be None (not found), not raise an exception that could expose PHI
        assert user is None
    
    @pytest.mark.asyncio
    async def test_secure_token_generation(self, cognito_provider):
        """Test that tokens meet security requirements."""
        # Mock password reset token creation
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        cognito_provider.client_manager.cognito_client.admin_reset_user_password.return_value = {}
        
        token = await cognito_provider.create_token(
            'test-user-id',
            TokenType.PASSWORD_RESET,
            expires_in=timedelta(hours=1)
        )
        
        # Verify token properties
        assert token.token_type == TokenType.PASSWORD_RESET
        assert token.user_id == 'test-user-id'
        assert len(token.token_value) >= 32  # Minimum security requirement
        assert token.expires_at > datetime.utcnow()


class TestCognitoIntegration:
    """Integration tests for Cognito provider."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_authentication_flow(self, cognito_provider):
        """Test complete authentication flow from login to token validation."""
        # Step 1: Authenticate user
        auth_response = {
            'AuthenticationResult': {
                'AccessToken': 'test-access-token',
                'RefreshToken': 'test-refresh-token',
                'ExpiresIn': 3600
            }
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = auth_response
        
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow(),
            metadata={'cognito_username': 'test@example.com'}
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()
        })
        
        # Authenticate
        auth_result = await cognito_provider.authenticate_user('test@example.com', 'password123')
        assert auth_result.success is True
        
        # Step 2: Validate the access token
        token_result = await cognito_provider.authenticate_token(auth_result.access_token.token_value)
        assert token_result.success is True
        assert token_result.user.id == 'test-user-id'
        
        # Step 3: Refresh the token
        refresh_response = {
            'AuthenticationResult': {
                'AccessToken': 'new-access-token',
                'ExpiresIn': 3600
            }
        }
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = refresh_response
        
        refresh_result = await cognito_provider.refresh_token(auth_result.refresh_token.token_value)
        assert refresh_result.success is True
        assert refresh_result.access_token.token_value == 'new-access-token'
    
    @pytest.mark.asyncio
    async def test_mfa_flow(self, cognito_provider):
        """Test MFA authentication flow."""
        # Step 1: Initial authentication triggers MFA
        auth_response = {
            'ChallengeName': 'SMS_MFA',
            'Session': 'mfa-session-token'
        }
        
        cognito_provider.client_manager.cognito_client.initiate_auth.return_value = auth_response
        
        auth_result = await cognito_provider.authenticate_user('test@example.com', 'password123')
        assert auth_result.success is False
        assert auth_result.mfa_required is True
        assert auth_result.mfa_challenge_token is not None
        
        # Step 2: Verify MFA challenge
        mfa_response = {
            'AuthenticationResult': {
                'AccessToken': 'test-access-token',
                'RefreshToken': 'test-refresh-token',
                'ExpiresIn': 3600
            }
        }
        
        cognito_provider.client_manager.cognito_client.respond_to_auth_challenge.return_value = mfa_response
        
        mock_user = AuthUser(
            id='test-user-id',
            email='test@example.com',
            roles=[UserRole.PATIENT],
            created_at=datetime.utcnow()
        )
        cognito_provider.get_user = AsyncMock(return_value=mock_user)
        cognito_provider.jwt_validator.validate_token = AsyncMock(return_value={
            'sub': 'test-user-id',
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp()
        })
        
        mfa_result = await cognito_provider.verify_mfa_challenge(
            auth_result.mfa_challenge_token.token_value,
            '123456'
        )
        
        assert mfa_result.success is True
        assert mfa_result.user is not None
        assert mfa_result.access_token is not None


if __name__ == '__main__':
    pytest.main(['-v', __file__])
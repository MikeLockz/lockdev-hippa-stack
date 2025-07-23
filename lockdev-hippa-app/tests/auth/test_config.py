"""
Unit tests for authentication configuration management.

Tests cover configuration validation, environment variable loading,
provider-specific configuration, and HIPAA compliance settings.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from src.auth.config import AuthConfig, AuthProviderType, ProviderHealthConfig
from pydantic import ValidationError


class TestAuthConfig:
    """Test cases for AuthConfig class."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        # Mock environment to avoid validation errors
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'test_secret_key_that_is_long_enough_for_validation'}):
            config = AuthConfig()
            
            assert config.provider_type == AuthProviderType.CUSTOM
            assert config.jwt_algorithm == "HS256"
            assert config.access_token_expire_minutes == 15
            assert config.refresh_token_expire_days == 30
            assert config.session_expire_hours == 8
            assert config.max_concurrent_sessions == 3
            assert config.require_mfa is True
            assert config.password_min_length == 8
            assert config.max_login_attempts == 3
            assert config.lockout_duration_minutes == 30
            assert config.audit_all_events is True
            assert config.encrypt_audit_logs is True
            assert config.require_password_history == 12
            assert config.password_expire_days == 90
    
    def test_jwt_secret_validation(self):
        """Test JWT secret key validation."""
        # Test valid secret
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}):
            config = AuthConfig()
            assert len(config.jwt_secret_key) >= 32
        
        # Test invalid secret (too short)
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'short'}):
            with pytest.raises(ValidationError) as exc_info:
                AuthConfig()
            assert "JWT secret key must be at least 32 characters long" in str(exc_info.value)
    
    def test_access_token_expiry_validation(self):
        """Test access token expiry validation."""
        base_env = {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}
        
        # Test valid values
        for minutes in [1, 15, 60, 1440]:
            with patch.dict(os.environ, {**base_env, 'ACCESS_TOKEN_EXPIRE_MINUTES': str(minutes)}):
                config = AuthConfig()
                assert config.access_token_expire_minutes == minutes
        
        # Test invalid values
        for minutes in [0, -1, 1441]:
            with patch.dict(os.environ, {**base_env, 'ACCESS_TOKEN_EXPIRE_MINUTES': str(minutes)}):
                with pytest.raises(ValidationError) as exc_info:
                    AuthConfig()
                assert "Access token expiry must be between 1 and 1440 minutes" in str(exc_info.value)
    
    def test_refresh_token_expiry_validation(self):
        """Test refresh token expiry validation."""
        base_env = {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}
        
        # Test valid values
        for days in [1, 30, 90, 365]:
            with patch.dict(os.environ, {**base_env, 'REFRESH_TOKEN_EXPIRE_DAYS': str(days)}):
                config = AuthConfig()
                assert config.refresh_token_expire_days == days
        
        # Test invalid values
        for days in [0, -1, 366]:
            with patch.dict(os.environ, {**base_env, 'REFRESH_TOKEN_EXPIRE_DAYS': str(days)}):
                with pytest.raises(ValidationError) as exc_info:
                    AuthConfig()
                assert "Refresh token expiry must be between 1 and 365 days" in str(exc_info.value)
    
    def test_password_length_validation(self):
        """Test password minimum length validation."""
        base_env = {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}
        
        # Test valid values
        for length in [8, 12, 16]:
            with patch.dict(os.environ, {**base_env, 'PASSWORD_MIN_LENGTH': str(length)}):
                config = AuthConfig()
                assert config.password_min_length == length
        
        # Test invalid values
        for length in [0, 7]:
            with patch.dict(os.environ, {**base_env, 'PASSWORD_MIN_LENGTH': str(length)}):
                with pytest.raises(ValidationError) as exc_info:
                    AuthConfig()
                assert "Password minimum length must be at least 8 characters" in str(exc_info.value)
    
    def test_max_login_attempts_validation(self):
        """Test max login attempts validation."""
        base_env = {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}
        
        # Test valid values
        for attempts in [1, 3, 5, 10]:
            with patch.dict(os.environ, {**base_env, 'MAX_LOGIN_ATTEMPTS': str(attempts)}):
                config = AuthConfig()
                assert config.max_login_attempts == attempts
        
        # Test invalid values
        for attempts in [0, -1, 11]:
            with patch.dict(os.environ, {**base_env, 'MAX_LOGIN_ATTEMPTS': str(attempts)}):
                with pytest.raises(ValidationError) as exc_info:
                    AuthConfig()
                assert "Max login attempts must be between 1 and 10" in str(exc_info.value)
    
    def test_aws_cognito_config_validation(self):
        """Test AWS Cognito configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'aws_cognito'
        }
        
        # Test valid configuration
        cognito_env = {
            **base_env,
            'AWS_COGNITO_USER_POOL_ID': 'us-east-1_abcdef123',
            'AWS_COGNITO_CLIENT_ID': 'test_client_id',
            'AWS_COGNITO_REGION': 'us-east-1'
        }
        with patch.dict(os.environ, cognito_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.AWS_COGNITO
            cognito_config = config.get_provider_config()
            assert cognito_config['user_pool_id'] == 'us-east-1_abcdef123'
            assert cognito_config['client_id'] == 'test_client_id'
            assert cognito_config['region'] == 'us-east-1'
        
        # Test missing required fields
        incomplete_env = {
            **base_env,
            'AWS_COGNITO_USER_POOL_ID': 'us-east-1_abcdef123'
            # Missing client_id and region
        }
        with patch.dict(os.environ, incomplete_env):
            with pytest.raises(ValidationError) as exc_info:
                AuthConfig()
            assert "AWS Cognito config missing required fields" in str(exc_info.value)
    
    def test_auth0_config_validation(self):
        """Test Auth0 configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'auth0'
        }
        
        # Test valid configuration
        auth0_env = {
            **base_env,
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_CLIENT_ID': 'test_client_id',
            'AUTH0_CLIENT_SECRET': 'test_client_secret'
        }
        with patch.dict(os.environ, auth0_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.AUTH0
            auth0_config = config.get_provider_config()
            assert auth0_config['domain'] == 'test.auth0.com'
            assert auth0_config['client_id'] == 'test_client_id'
            assert auth0_config['client_secret'] == 'test_client_secret'
        
        # Test missing required fields
        incomplete_env = {
            **base_env,
            'AUTH0_DOMAIN': 'test.auth0.com'
            # Missing client_id and client_secret
        }
        with patch.dict(os.environ, incomplete_env):
            with pytest.raises(ValidationError) as exc_info:
                AuthConfig()
            assert "Auth0 config missing required fields" in str(exc_info.value)
    
    def test_supabase_config_validation(self):
        """Test Supabase configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'supabase'
        }
        
        # Test valid configuration
        supabase_env = {
            **base_env,
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_ANON_KEY': 'test_anon_key'
        }
        with patch.dict(os.environ, supabase_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.SUPABASE
            supabase_config = config.get_provider_config()
            assert supabase_config['url'] == 'https://test.supabase.co'
            assert supabase_config['anon_key'] == 'test_anon_key'
    
    def test_firebase_config_validation(self):
        """Test Firebase configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'firebase'
        }
        
        # Test valid configuration
        firebase_env = {
            **base_env,
            'FIREBASE_PROJECT_ID': 'test-project-id'
        }
        with patch.dict(os.environ, firebase_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.FIREBASE
            firebase_config = config.get_provider_config()
            assert firebase_config['project_id'] == 'test-project-id'
    
    def test_oauth2_config_validation(self):
        """Test OAuth2 configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'oauth2'
        }
        
        # Test valid configuration
        oauth2_env = {
            **base_env,
            'OAUTH2_CLIENT_ID': 'test_client_id',
            'OAUTH2_CLIENT_SECRET': 'test_client_secret',
            'OAUTH2_AUTHORIZATION_URL': 'https://example.com/auth',
            'OAUTH2_TOKEN_URL': 'https://example.com/token'
        }
        with patch.dict(os.environ, oauth2_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.OAUTH2
            oauth2_config = config.get_provider_config()
            assert oauth2_config['client_id'] == 'test_client_id'
            assert oauth2_config['authorization_url'] == 'https://example.com/auth'
    
    def test_saml_config_validation(self):
        """Test SAML configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'saml'
        }
        
        # Test valid configuration
        saml_env = {
            **base_env,
            'SAML_ENTITY_ID': 'test-entity-id',
            'SAML_SSO_URL': 'https://example.com/sso',
            'SAML_X509_CERT': 'test_certificate'
        }
        with patch.dict(os.environ, saml_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.SAML
            saml_config = config.get_provider_config()
            assert saml_config['entity_id'] == 'test-entity-id'
            assert saml_config['sso_url'] == 'https://example.com/sso'
    
    def test_ldap_config_validation(self):
        """Test LDAP configuration validation."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'ldap'
        }
        
        # Test valid configuration
        ldap_env = {
            **base_env,
            'LDAP_SERVER': 'ldap.example.com',
            'LDAP_BIND_DN': 'cn=admin,dc=example,dc=com',
            'LDAP_BIND_PASSWORD': 'test_password',
            'LDAP_USER_SEARCH_BASE': 'ou=users,dc=example,dc=com'
        }
        with patch.dict(os.environ, ldap_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.LDAP
            ldap_config = config.get_provider_config()
            assert ldap_config['server'] == 'ldap.example.com'
            assert ldap_config['bind_dn'] == 'cn=admin,dc=example,dc=com'
    
    def test_custom_config_loading(self):
        """Test custom provider configuration from environment."""
        base_env = {
            'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'custom',
            'CUSTOM_API_KEY': 'test_api_key',
            'CUSTOM_BASE_URL': 'https://api.example.com',
            'CUSTOM_TIMEOUT': '30'
        }
        
        with patch.dict(os.environ, base_env):
            config = AuthConfig()
            assert config.provider_type == AuthProviderType.CUSTOM
            custom_config = config.get_provider_config()
            assert custom_config['api_key'] == 'test_api_key'
            assert custom_config['base_url'] == 'https://api.example.com'
            assert custom_config['timeout'] == '30'
    
    def test_get_security_config(self):
        """Test getting security configuration."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}):
            config = AuthConfig()
            security_config = config.get_security_config()
            
            expected_keys = [
                'jwt_secret_key', 'jwt_algorithm', 'access_token_expire_minutes',
                'refresh_token_expire_days', 'session_expire_hours', 'max_concurrent_sessions',
                'require_mfa', 'password_min_length', 'max_login_attempts', 'lockout_duration_minutes'
            ]
            
            for key in expected_keys:
                assert key in security_config
    
    def test_get_hipaa_config(self):
        """Test getting HIPAA configuration."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}):
            config = AuthConfig()
            hipaa_config = config.get_hipaa_config()
            
            expected_keys = [
                'audit_all_events', 'encrypt_audit_logs', 'require_password_history', 'password_expire_days'
            ]
            
            for key in expected_keys:
                assert key in hipaa_config
    
    def test_validate_configuration_success(self):
        """Test successful configuration validation."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}):
            config = AuthConfig()
            assert config.validate_configuration() is True
    
    def test_validate_configuration_jwt_secret_failure(self):
        """Test configuration validation failure for JWT secret."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'valid_secret_key_that_is_32_chars_long'}):
            config = AuthConfig()
            config.jwt_secret_key = 'short'  # Override with short secret
            
            with pytest.raises(ValueError) as exc_info:
                config.validate_configuration()
            assert "JWT secret key must be at least 32 characters" in str(exc_info.value)
    
    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            'JWT_SECRET_KEY': 'test_jwt_secret_key_32_chars_long',
            'AUTH_PROVIDER_TYPE': 'auth0',
            'JWT_ALGORITHM': 'RS256',
            'ACCESS_TOKEN_EXPIRE_MINUTES': '30',
            'REFRESH_TOKEN_EXPIRE_DAYS': '7',
            'SESSION_EXPIRE_HOURS': '12',
            'REQUIRE_MFA': 'false',
            'PASSWORD_MIN_LENGTH': '12',
            'MAX_LOGIN_ATTEMPTS': '5',
            'AUDIT_ALL_EVENTS': 'false'
        }
        
        with patch.dict(os.environ, env_vars):
            config = AuthConfig()
            
            assert config.jwt_secret_key == 'test_jwt_secret_key_32_chars_long'
            assert config.provider_type == AuthProviderType.AUTH0
            assert config.jwt_algorithm == 'RS256'
            assert config.access_token_expire_minutes == 30
            assert config.refresh_token_expire_days == 7
            assert config.session_expire_hours == 12
            assert config.require_mfa is False
            assert config.password_min_length == 12
            assert config.max_login_attempts == 5
            assert config.audit_all_events is False


class TestProviderHealthConfig:
    """Test cases for ProviderHealthConfig class."""
    
    def test_default_health_config(self):
        """Test default health configuration values."""
        config = ProviderHealthConfig()
        
        assert config.health_check_enabled is True
        assert config.health_check_interval_seconds == 300
        assert config.health_check_timeout_seconds == 30
        assert config.health_check_retries == 3
    
    def test_health_config_from_environment(self):
        """Test loading health configuration from environment."""
        env_vars = {
            'HEALTH_CHECK_ENABLED': 'false',
            'HEALTH_CHECK_INTERVAL_SECONDS': '600',
            'HEALTH_CHECK_TIMEOUT_SECONDS': '60',
            'HEALTH_CHECK_RETRIES': '5'
        }
        
        with patch.dict(os.environ, env_vars):
            config = ProviderHealthConfig()
            
            assert config.health_check_enabled is False
            assert config.health_check_interval_seconds == 600
            assert config.health_check_timeout_seconds == 60
            assert config.health_check_retries == 5


class TestAuthProviderType:
    """Test cases for AuthProviderType enum."""
    
    def test_provider_type_values(self):
        """Test provider type enum values."""
        assert AuthProviderType.CUSTOM.value == "custom"
        assert AuthProviderType.AWS_COGNITO.value == "aws_cognito"
        assert AuthProviderType.AUTH0.value == "auth0"
        assert AuthProviderType.SUPABASE.value == "supabase"
        assert AuthProviderType.FIREBASE.value == "firebase"
        assert AuthProviderType.OAUTH2.value == "oauth2"
        assert AuthProviderType.SAML.value == "saml"
        assert AuthProviderType.LDAP.value == "ldap"
    
    def test_provider_type_from_string(self):
        """Test creating provider type from string."""
        assert AuthProviderType("custom") == AuthProviderType.CUSTOM
        assert AuthProviderType("aws_cognito") == AuthProviderType.AWS_COGNITO
        assert AuthProviderType("auth0") == AuthProviderType.AUTH0
    
    def test_invalid_provider_type(self):
        """Test invalid provider type raises error."""
        with pytest.raises(ValueError):
            AuthProviderType("invalid_provider")


@pytest.fixture
def mock_env_config():
    """Fixture providing mock environment configuration."""
    return {
        'JWT_SECRET_KEY': 'test_jwt_secret_key_that_is_32_characters_long',
        'AUTH_PROVIDER_TYPE': 'custom',
        'ACCESS_TOKEN_EXPIRE_MINUTES': '15',
        'REFRESH_TOKEN_EXPIRE_DAYS': '30'
    }


def test_config_integration(mock_env_config):
    """Integration test for configuration loading and validation."""
    with patch.dict(os.environ, mock_env_config):
        config = AuthConfig()
        
        # Test basic configuration
        assert config.provider_type == AuthProviderType.CUSTOM
        assert config.access_token_expire_minutes == 15
        assert config.refresh_token_expire_days == 30
        
        # Test provider config retrieval
        provider_config = config.get_provider_config()
        assert isinstance(provider_config, dict)
        
        # Test security config
        security_config = config.get_security_config()
        assert 'jwt_secret_key' in security_config
        assert 'require_mfa' in security_config
        
        # Test HIPAA config
        hipaa_config = config.get_hipaa_config()
        assert 'audit_all_events' in hipaa_config
        assert 'encrypt_audit_logs' in hipaa_config
        
        # Test validation
        assert config.validate_configuration() is True
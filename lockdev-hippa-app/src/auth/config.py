"""
Authentication provider configuration management.

This module defines Pydantic settings-based configuration classes for
authentication providers with environment variable support and validation.
"""

import os
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class AuthProviderType(str, Enum):
    """Supported authentication provider types."""
    CUSTOM = "custom"
    AWS_COGNITO = "aws_cognito"
    AUTH0 = "auth0"
    SUPABASE = "supabase"
    FIREBASE = "firebase"
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"


class AuthConfig(BaseSettings):
    """
    Main authentication configuration class.
    
    This class manages all authentication-related configuration using
    Pydantic settings with environment variable support and validation.
    """
    
    # Primary provider configuration
    provider_type: AuthProviderType = Field(
        default=AuthProviderType.CUSTOM,
        env="AUTH_PROVIDER_TYPE",
        description="Primary authentication provider type"
    )
    
    # Security settings
    jwt_secret_key: str = Field(
        ...,
        env="JWT_SECRET_KEY",
        description="Secret key for JWT token signing"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        env="JWT_ALGORITHM",
        description="Algorithm for JWT token signing"
    )
    access_token_expire_minutes: int = Field(
        default=15,
        env="ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=30,
        env="REFRESH_TOKEN_EXPIRE_DAYS",
        description="Refresh token expiration in days"
    )
    
    # Session management
    session_expire_hours: int = Field(
        default=8,
        env="SESSION_EXPIRE_HOURS",
        description="Session expiration in hours"
    )
    max_concurrent_sessions: int = Field(
        default=3,
        env="MAX_CONCURRENT_SESSIONS",
        description="Maximum concurrent sessions per user"
    )
    
    # Security policies
    require_mfa: bool = Field(
        default=True,
        env="REQUIRE_MFA",
        description="Whether MFA is required for all users"
    )
    password_min_length: int = Field(
        default=8,
        env="PASSWORD_MIN_LENGTH",
        description="Minimum password length"
    )
    max_login_attempts: int = Field(
        default=3,
        env="MAX_LOGIN_ATTEMPTS",
        description="Maximum failed login attempts before lockout"
    )
    lockout_duration_minutes: int = Field(
        default=30,
        env="LOCKOUT_DURATION_MINUTES",
        description="Account lockout duration in minutes"
    )
    
    # HIPAA compliance settings
    audit_all_events: bool = Field(
        default=True,
        env="AUDIT_ALL_EVENTS",
        description="Log all authentication events for HIPAA compliance"
    )
    encrypt_audit_logs: bool = Field(
        default=True,
        env="ENCRYPT_AUDIT_LOGS",
        description="Encrypt audit logs"
    )
    require_password_history: int = Field(
        default=12,
        env="REQUIRE_PASSWORD_HISTORY",
        description="Number of previous passwords to prevent reuse"
    )
    password_expire_days: int = Field(
        default=90,
        env="PASSWORD_EXPIRE_DAYS",
        description="Password expiration period in days"
    )
    
    # Provider-specific configurations
    custom_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom provider configuration"
    )
    aws_cognito_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="AWS Cognito provider configuration"
    )
    auth0_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Auth0 provider configuration"
    )
    supabase_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supabase provider configuration"
    )
    firebase_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Firebase provider configuration"
    )
    oauth2_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="OAuth2 provider configuration"
    )
    saml_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="SAML provider configuration"
    )
    ldap_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="LDAP provider configuration"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }
        
    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret key meets security requirements."""
        if len(v) < 32:
            raise ValueError('JWT secret key must be at least 32 characters long')
        return v
    
    @field_validator('access_token_expire_minutes')
    @classmethod
    def validate_access_token_expiry(cls, v: int) -> int:
        """Validate access token expiry is reasonable."""
        if v < 1 or v > 1440:  # 1 minute to 24 hours
            raise ValueError('Access token expiry must be between 1 and 1440 minutes')
        return v
    
    @field_validator('refresh_token_expire_days')
    @classmethod
    def validate_refresh_token_expiry(cls, v: int) -> int:
        """Validate refresh token expiry is reasonable."""
        if v < 1 or v > 365:  # 1 day to 1 year
            raise ValueError('Refresh token expiry must be between 1 and 365 days')
        return v
    
    @field_validator('password_min_length')
    @classmethod
    def validate_password_length(cls, v: int) -> int:
        """Validate password minimum length meets security standards."""
        if v < 8:
            raise ValueError('Password minimum length must be at least 8 characters')
        return v
    
    @field_validator('max_login_attempts')
    @classmethod
    def validate_max_login_attempts(cls, v: int) -> int:
        """Validate max login attempts is reasonable."""
        if v < 1 or v > 10:
            raise ValueError('Max login attempts must be between 1 and 10')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_provider_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate provider-specific configuration based on provider type."""
        provider_type = values.get('provider_type')
        if not provider_type:
            return values
        
        # Load provider-specific configuration from environment
        config_key = f"{provider_type.value}_config"
        if config_key in values:
            config = values[config_key]
        else:
            config = {}
        
        # Validate provider-specific configurations
        if provider_type == AuthProviderType.AWS_COGNITO:
            config = cls._validate_aws_cognito_config(config, values)
        elif provider_type == AuthProviderType.AUTH0:
            config = cls._validate_auth0_config(config, values)
        elif provider_type == AuthProviderType.SUPABASE:
            config = cls._validate_supabase_config(config, values)
        elif provider_type == AuthProviderType.FIREBASE:
            config = cls._validate_firebase_config(config, values)
        elif provider_type == AuthProviderType.OAUTH2:
            config = cls._validate_oauth2_config(config, values)
        elif provider_type == AuthProviderType.SAML:
            config = cls._validate_saml_config(config, values)
        elif provider_type == AuthProviderType.LDAP:
            config = cls._validate_ldap_config(config, values)
        elif provider_type == AuthProviderType.CUSTOM:
            config = cls._validate_custom_config(config, values)
        
        values[config_key] = config
        return values
    
    @classmethod
    def _validate_aws_cognito_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate AWS Cognito configuration."""
        # Load from environment if not provided
        required_fields = ['user_pool_id', 'client_id', 'region']
        for field in required_fields:
            env_key = f"AWS_COGNITO_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        # Validate required fields
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"AWS Cognito config missing required fields: {missing_fields}")
        
        # Set defaults
        config.setdefault('client_secret', os.getenv('AWS_COGNITO_CLIENT_SECRET'))
        config.setdefault('scope', 'openid email profile')
        
        return config
    
    @classmethod
    def _validate_auth0_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Auth0 configuration."""
        required_fields = ['domain', 'client_id', 'client_secret']
        for field in required_fields:
            env_key = f"AUTH0_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"Auth0 config missing required fields: {missing_fields}")
        
        config.setdefault('scope', 'openid email profile')
        config.setdefault('audience', os.getenv('AUTH0_AUDIENCE', f"https://{config['domain']}/api/v2/"))
        
        return config
    
    @classmethod
    def _validate_supabase_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Supabase configuration."""
        required_fields = ['url', 'anon_key']
        for field in required_fields:
            env_key = f"SUPABASE_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"Supabase config missing required fields: {missing_fields}")
        
        config.setdefault('service_role_key', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
        
        return config
    
    @classmethod
    def _validate_firebase_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Firebase configuration."""
        required_fields = ['project_id']
        for field in required_fields:
            env_key = f"FIREBASE_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"Firebase config missing required fields: {missing_fields}")
        
        config.setdefault('credentials_path', os.getenv('FIREBASE_CREDENTIALS_PATH'))
        config.setdefault('web_api_key', os.getenv('FIREBASE_WEB_API_KEY'))
        
        return config
    
    @classmethod
    def _validate_oauth2_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate OAuth2 configuration."""
        required_fields = ['client_id', 'client_secret', 'authorization_url', 'token_url']
        for field in required_fields:
            env_key = f"OAUTH2_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"OAuth2 config missing required fields: {missing_fields}")
        
        config.setdefault('scope', 'openid email profile')
        config.setdefault('userinfo_url', os.getenv('OAUTH2_USERINFO_URL'))
        
        return config
    
    @classmethod
    def _validate_saml_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SAML configuration."""
        required_fields = ['entity_id', 'sso_url', 'x509_cert']
        for field in required_fields:
            env_key = f"SAML_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"SAML config missing required fields: {missing_fields}")
        
        config.setdefault('attribute_mapping', {
            'email': 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
            'first_name': 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
            'last_name': 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname'
        })
        
        return config
    
    @classmethod
    def _validate_ldap_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate LDAP configuration."""
        required_fields = ['server', 'bind_dn', 'bind_password', 'user_search_base']
        for field in required_fields:
            env_key = f"LDAP_{field.upper()}"
            if field not in config:
                config[field] = os.getenv(env_key)
        
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"LDAP config missing required fields: {missing_fields}")
        
        config.setdefault('port', 389)
        config.setdefault('use_ssl', False)
        config.setdefault('user_filter', '(uid={username})')
        config.setdefault('attributes', ['uid', 'cn', 'mail', 'memberOf'])
        
        return config
    
    @classmethod
    def _validate_custom_config(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom provider configuration."""
        # Custom providers can have flexible configuration
        # Load any CUSTOM_* environment variables
        for key, value in os.environ.items():
            if key.startswith('CUSTOM_'):
                config_key = key[7:].lower()  # Remove 'CUSTOM_' prefix
                if config_key not in config:
                    config[config_key] = value
        
        return config
    
    def get_provider_config(self, provider_type: Optional[AuthProviderType] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific provider type.
        
        Args:
            provider_type: Provider type to get config for (defaults to current provider)
            
        Returns:
            Provider-specific configuration dictionary
        """
        if provider_type is None:
            provider_type = self.provider_type
        
        config_key = f"{provider_type.value}_config"
        return getattr(self, config_key, {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """
        Get security-related configuration.
        
        Returns:
            Dictionary containing security configuration
        """
        return {
            'jwt_secret_key': self.jwt_secret_key,
            'jwt_algorithm': self.jwt_algorithm,
            'access_token_expire_minutes': self.access_token_expire_minutes,
            'refresh_token_expire_days': self.refresh_token_expire_days,
            'session_expire_hours': self.session_expire_hours,
            'max_concurrent_sessions': self.max_concurrent_sessions,
            'require_mfa': self.require_mfa,
            'password_min_length': self.password_min_length,
            'max_login_attempts': self.max_login_attempts,
            'lockout_duration_minutes': self.lockout_duration_minutes,
        }
    
    def get_hipaa_config(self) -> Dict[str, Any]:
        """
        Get HIPAA compliance-related configuration.
        
        Returns:
            Dictionary containing HIPAA configuration
        """
        return {
            'audit_all_events': self.audit_all_events,
            'encrypt_audit_logs': self.encrypt_audit_logs,
            'require_password_history': self.require_password_history,
            'password_expire_days': self.password_expire_days,
        }
    
    def validate_configuration(self) -> bool:
        """
        Validate the entire configuration for consistency and completeness.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate JWT secret exists and is secure
        if not self.jwt_secret_key or len(self.jwt_secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        
        # Validate provider configuration
        provider_config = self.get_provider_config()
        if not provider_config and self.provider_type != AuthProviderType.CUSTOM:
            raise ValueError(f"Provider configuration required for {self.provider_type}")
        
        # Validate HIPAA compliance settings
        if self.require_mfa and not any([
            self.provider_type in [AuthProviderType.AWS_COGNITO, AuthProviderType.AUTH0],
            'mfa_enabled' in provider_config
        ]):
            raise ValueError("MFA is required but provider does not support MFA")
        
        return True


class ProviderHealthConfig(BaseSettings):
    """Configuration for provider health checks."""
    
    health_check_enabled: bool = Field(
        default=True,
        env="HEALTH_CHECK_ENABLED",
        description="Enable provider health checks"
    )
    health_check_interval_seconds: int = Field(
        default=300,  # 5 minutes
        env="HEALTH_CHECK_INTERVAL_SECONDS",
        description="Health check interval in seconds"
    )
    health_check_timeout_seconds: int = Field(
        default=30,
        env="HEALTH_CHECK_TIMEOUT_SECONDS",
        description="Health check timeout in seconds"
    )
    health_check_retries: int = Field(
        default=3,
        env="HEALTH_CHECK_RETRIES",
        description="Number of health check retries"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }
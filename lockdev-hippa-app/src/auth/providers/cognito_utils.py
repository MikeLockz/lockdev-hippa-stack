"""
AWS Cognito utilities and configuration management.

This module provides utility functions, configuration validation, and helper classes
specifically for AWS Cognito authentication integration with HIPAA compliance features.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

import boto3
import cognitojwt
from botocore.exceptions import ClientError, NoCredentialsError
from cognitojwt.exceptions import CognitoJWTException

from ..exceptions import AuthenticationError, ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class CognitoConfig:
    """Configuration container for AWS Cognito settings."""
    
    # Required Cognito settings
    region: str
    user_pool_id: str
    client_id: str
    client_secret: Optional[str] = None
    
    # Optional Cognito settings
    identity_pool_id: Optional[str] = None
    domain: Optional[str] = None
    
    # AWS credentials (optional - can use IAM roles/profiles)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    
    # HIPAA compliance settings
    enable_advanced_security: bool = True
    enable_audit_logging: bool = True
    enable_mfa_enforcement: bool = True
    password_policy_enabled: bool = True
    
    # Connection settings
    connection_timeout: int = 30
    read_timeout: int = 30
    retry_attempts: int = 3
    
    # Health check settings
    health_check_interval: int = 300  # 5 minutes
    
    @classmethod
    def from_env(cls) -> 'CognitoConfig':
        """Create configuration from environment variables."""
        return cls(
            region=os.getenv('AWS_COGNITO_REGION', 'us-east-1'),
            user_pool_id=os.getenv('AWS_COGNITO_USER_POOL_ID', ''),
            client_id=os.getenv('AWS_COGNITO_CLIENT_ID', ''),
            client_secret=os.getenv('AWS_COGNITO_CLIENT_SECRET'),
            identity_pool_id=os.getenv('AWS_COGNITO_IDENTITY_POOL_ID'),
            domain=os.getenv('AWS_COGNITO_DOMAIN'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
            enable_advanced_security=os.getenv('COGNITO_ENABLE_ADVANCED_SECURITY', 'true').lower() == 'true',
            enable_audit_logging=os.getenv('COGNITO_ENABLE_AUDIT_LOGGING', 'true').lower() == 'true',
            enable_mfa_enforcement=os.getenv('COGNITO_ENABLE_MFA_ENFORCEMENT', 'true').lower() == 'true',
            password_policy_enabled=os.getenv('COGNITO_PASSWORD_POLICY_ENABLED', 'true').lower() == 'true',
            connection_timeout=int(os.getenv('COGNITO_CONNECTION_TIMEOUT', '30')),
            read_timeout=int(os.getenv('COGNITO_READ_TIMEOUT', '30')),
            retry_attempts=int(os.getenv('COGNITO_RETRY_ATTEMPTS', '3')),
            health_check_interval=int(os.getenv('COGNITO_HEALTH_CHECK_INTERVAL', '300')),
        )
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if not self.region:
            raise ConfigurationError("AWS region is required")
        if not self.user_pool_id:
            raise ConfigurationError("Cognito User Pool ID is required")
        if not self.client_id:
            raise ConfigurationError("Cognito Client ID is required")
        
        # Validate region format
        if not self.region.replace('-', '').replace('_', '').isalnum():
            raise ConfigurationError(f"Invalid AWS region format: {self.region}")
        
        # Validate timeouts
        if self.connection_timeout <= 0 or self.read_timeout <= 0:
            raise ConfigurationError("Timeout values must be positive")
        
        if self.retry_attempts < 0:
            raise ConfigurationError("Retry attempts must be non-negative")


class CognitoClientManager:
    """Manages AWS Cognito client connections with pooling and retry logic."""
    
    def __init__(self, config: CognitoConfig):
        self.config = config
        self._cognito_client = None
        self._cognito_identity_client = None
        self._cloudtrail_client = None
        self._last_health_check = None
        self._is_healthy = True
        
    def _create_session(self) -> boto3.Session:
        """Create AWS session with configuration."""
        session_kwargs = {}
        
        if self.config.aws_access_key_id and self.config.aws_secret_access_key:
            session_kwargs.update({
                'aws_access_key_id': self.config.aws_access_key_id,
                'aws_secret_access_key': self.config.aws_secret_access_key,
            })
            if self.config.aws_session_token:
                session_kwargs['aws_session_token'] = self.config.aws_session_token
        
        return boto3.Session(**session_kwargs)
    
    @property
    def cognito_client(self):
        """Get or create Cognito Identity Provider client."""
        if self._cognito_client is None:
            session = self._create_session()
            self._cognito_client = session.client(
                'cognito-idp',
                region_name=self.config.region,
                config=boto3.session.Config(
                    connect_timeout=self.config.connection_timeout,
                    read_timeout=self.config.read_timeout,
                    retries={'max_attempts': self.config.retry_attempts}
                )
            )
        return self._cognito_client
    
    @property
    def cognito_identity_client(self):
        """Get or create Cognito Identity client."""
        if self._cognito_identity_client is None and self.config.identity_pool_id:
            session = self._create_session()
            self._cognito_identity_client = session.client(
                'cognito-identity',
                region_name=self.config.region,
                config=boto3.session.Config(
                    connect_timeout=self.config.connection_timeout,
                    read_timeout=self.config.read_timeout,
                    retries={'max_attempts': self.config.retry_attempts}
                )
            )
        return self._cognito_identity_client
    
    @property
    def cloudtrail_client(self):
        """Get or create CloudTrail client for audit logging."""
        if self._cloudtrail_client is None and self.config.enable_audit_logging:
            session = self._create_session()
            self._cloudtrail_client = session.client(
                'cloudtrail',
                region_name=self.config.region,
                config=boto3.session.Config(
                    connect_timeout=self.config.connection_timeout,
                    read_timeout=self.config.read_timeout,
                    retries={'max_attempts': self.config.retry_attempts}
                )
            )
        return self._cloudtrail_client
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Cognito service."""
        now = datetime.utcnow()
        
        # Return cached result if recent
        if (self._last_health_check and 
            (now - self._last_health_check).total_seconds() < self.config.health_check_interval):
            return {
                'status': 'healthy' if self._is_healthy else 'unhealthy',
                'last_check': self._last_health_check.isoformat(),
                'cached': True
            }
        
        try:
            # Test basic connectivity
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cognito_client.describe_user_pool(
                    UserPoolId=self.config.user_pool_id
                )
            )
            
            self._is_healthy = True
            self._last_health_check = now
            
            return {
                'status': 'healthy',
                'last_check': now.isoformat(),
                'user_pool_id': self.config.user_pool_id,
                'region': self.config.region,
                'cached': False
            }
            
        except Exception as e:
            self._is_healthy = False
            self._last_health_check = now
            
            logger.error(f"Cognito health check failed: {str(e)}")
            
            return {
                'status': 'unhealthy',
                'last_check': now.isoformat(),
                'error': str(e),
                'cached': False
            }


class CognitoJWTValidator:
    """Handles JWT token validation using Cognito public keys."""
    
    def __init__(self, config: CognitoConfig):
        self.config = config
        self._jwt_verifier = None
        
    @property
    def jwt_verifier(self):
        """Get or create JWT verifier."""
        if self._jwt_verifier is None:
            self._jwt_verifier = cognitojwt.CognitoJWT(
                'us-west-2',  # This is ignored when verifying tokens, but required by library
                self.config.user_pool_id,
                self.config.client_id
            )
        return self._jwt_verifier
    
    async def validate_token(self, token: str, token_use: str = 'access') -> Dict[str, Any]:
        """
        Validate JWT token using Cognito public keys.
        
        Args:
            token: JWT token to validate
            token_use: Expected token use ('access' or 'id')
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token validation fails
        """
        try:
            # Validate token asynchronously
            payload = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: cognitojwt.decode(
                    token,
                    self.config.region,
                    self.config.user_pool_id,
                    app_client_id=self.config.client_id
                )
            )
            
            # Verify token use
            if payload.get('token_use') != token_use:
                raise AuthenticationError(f"Invalid token use: expected {token_use}, got {payload.get('token_use')}")
            
            # Verify expiration
            exp = payload.get('exp', 0)
            if datetime.utcnow().timestamp() > exp:
                raise AuthenticationError("Token has expired")
            
            return payload
            
        except CognitoJWTException as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during JWT validation: {str(e)}")
            raise AuthenticationError(f"Token validation error: {str(e)}")


class CognitoErrorHandler:
    """Handles and translates AWS Cognito errors to authentication errors."""
    
    @staticmethod
    def handle_cognito_error(error: Exception, operation: str = "cognito_operation") -> AuthenticationError:
        """
        Convert Cognito exceptions to AuthenticationError instances.
        
        Args:
            error: The original exception
            operation: Description of the operation that failed
            
        Returns:
            Appropriate AuthenticationError
        """
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            error_message = error.response['Error']['Message']
            
            # Map common Cognito errors
            error_mapping = {
                'UserNotFoundException': 'User not found',
                'NotAuthorizedException': 'Invalid credentials',
                'UserNotConfirmedException': 'User email not verified',
                'PasswordResetRequiredException': 'Password reset required',
                'UserStatusNotConfirmedException': 'User status not confirmed',
                'UsernameExistsException': 'Username already exists',
                'InvalidPasswordException': 'Invalid password format',
                'TooManyRequestsException': 'Too many requests, please try again later',
                'LimitExceededException': 'Service limit exceeded',
                'InvalidParameterException': 'Invalid parameter provided',
                'CodeMismatchException': 'Invalid verification code',
                'ExpiredCodeException': 'Verification code has expired',
                'CodeDeliveryFailureException': 'Failed to deliver verification code',
                'AliasExistsException': 'Email address already in use',
                'InvalidUserPoolConfigurationException': 'Invalid user pool configuration',
                'MFAMethodNotFoundException': 'MFA method not found',
                'SoftwareTokenMFANotFoundException': 'Software token MFA not set up',
                'EnableSoftwareTokenMFAException': 'Failed to enable software token MFA',
                'NotAuthorizedError': 'Operation not authorized',
                'ResourceNotFoundException': 'Resource not found',
                'InternalErrorException': 'Internal service error',
            }
            
            user_message = error_mapping.get(error_code, error_message)
            
            logger.warning(f"Cognito error in {operation}: {error_code} - {error_message}")
            
            return AuthenticationError(
                message=user_message,
                error_code=error_code,
                details={'operation': operation, 'aws_error': error_message}
            )
        
        elif isinstance(error, NoCredentialsError):
            logger.error(f"AWS credentials not found for {operation}")
            return AuthenticationError(
                message="AWS credentials not configured",
                error_code="NO_CREDENTIALS",
                details={'operation': operation}
            )
        
        else:
            logger.error(f"Unexpected error in {operation}: {str(error)}")
            return AuthenticationError(
                message=f"Unexpected error during {operation}",
                error_code="UNKNOWN_ERROR",
                details={'operation': operation, 'error_type': type(error).__name__}
            )


class CognitoAuditLogger:
    """Handles HIPAA-compliant audit logging for Cognito operations."""
    
    def __init__(self, config: CognitoConfig, client_manager: CognitoClientManager):
        self.config = config
        self.client_manager = client_manager
        
    async def log_authentication_event(
        self,
        event_type: str,
        user_id: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log authentication event for HIPAA audit compliance.
        
        Args:
            event_type: Type of authentication event
            user_id: User involved in the event
            success: Whether the event was successful
            metadata: Additional non-sensitive metadata
        """
        if not self.config.enable_audit_logging:
            return
        
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'success': success,
            'provider': 'aws_cognito',
            'user_pool_id': self.config.user_pool_id,
            'region': self.config.region,
            'metadata': metadata or {}
        }
        
        # Log to structured logger
        logger.info(f"Cognito audit event: {event_type}", extra=audit_entry)
        
        # Optional: Send to CloudTrail or other audit systems
        if self.config.enable_audit_logging and self.client_manager.cloudtrail_client:
            try:
                # Note: In production, you might send this to CloudWatch Logs or S3
                # This is a simplified example
                await self._send_to_cloudtrail(audit_entry)
            except Exception as e:
                logger.error(f"Failed to send audit log to CloudTrail: {str(e)}")
    
    async def _send_to_cloudtrail(self, audit_entry: Dict[str, Any]) -> None:
        """Send audit entry to CloudTrail (simplified implementation)."""
        # In a real implementation, you would format this as a CloudTrail event
        # and send it to CloudWatch Logs or directly to CloudTrail
        pass


def get_cognito_user_pool_url(region: str, user_pool_id: str) -> str:
    """Get the Cognito User Pool URL for JWT validation."""
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def parse_cognito_username(username: str) -> Dict[str, str]:
    """
    Parse Cognito username which might contain provider prefix.
    
    Example: 'google_12345' or 'facebook_67890' or regular username
    """
    if '_' in username and len(username.split('_')) == 2:
        provider, user_id = username.split('_', 1)
        return {'provider': provider, 'user_id': user_id, 'federated': True}
    else:
        return {'provider': 'cognito', 'user_id': username, 'federated': False}


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password that meets Cognito requirements."""
    import secrets
    import string
    
    # Cognito password requirements: at least 8 chars, with uppercase, lowercase, number, special char
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"
    
    # Ensure at least one character from each required category
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill remaining length with random characters
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Shuffle the password list
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)
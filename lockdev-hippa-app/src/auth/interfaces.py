"""
Abstract authentication provider interface.

This module defines the vendor-agnostic authentication provider interface
that can be implemented by various authentication backends (JWT, OAuth2, SAML, etc.)
while maintaining HIPAA compliance requirements.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .models import AuthUser, AuthToken, AuthResult, TokenType, MFAMethod
from .exceptions import AuthenticationError


class AuthenticationProvider(ABC):
    """
    Abstract base class for authentication providers.
    
    This interface defines the contract that all authentication providers
    must implement to ensure consistent behavior across different
    authentication backends while maintaining HIPAA compliance.
    """
    
    def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
        """
        Initialize authentication provider.
        
        Args:
            provider_name: Unique identifier for this provider
            config: Provider-specific configuration
        """
        self.provider_name = provider_name
        self.config = config
    
    # Core authentication operations
    
    @abstractmethod
    async def authenticate_user(
        self,
        identifier: str,
        credential: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Authenticate a user with their credentials.
        
        Args:
            identifier: User identifier (email, username, etc.)
            credential: User credential (password, etc.)
            client_info: Additional client information for audit
            
        Returns:
            Authentication result with user data and tokens
            
        Raises:
            AuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def authenticate_token(
        self,
        token: str,
        token_type: TokenType = TokenType.ACCESS
    ) -> AuthResult:
        """
        Authenticate using an existing token.
        
        Args:
            token: Token value to authenticate
            token_type: Type of token being authenticated
            
        Returns:
            Authentication result with user data
            
        Raises:
            AuthenticationError: If token authentication fails
        """
        pass
    
    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token value
            client_info: Additional client information for audit
            
        Returns:
            Authentication result with new tokens
            
        Raises:
            AuthenticationError: If token refresh fails
        """
        pass
    
    @abstractmethod
    async def revoke_token(
        self,
        token: str,
        token_type: TokenType,
        revoked_by: Optional[str] = None
    ) -> bool:
        """
        Revoke an authentication token.
        
        Args:
            token: Token value to revoke
            token_type: Type of token being revoked
            revoked_by: User or system that initiated revocation
            
        Returns:
            True if token was successfully revoked
            
        Raises:
            AuthenticationError: If token revocation fails
        """
        pass
    
    # User management operations
    
    @abstractmethod
    async def get_user(
        self,
        user_id: str
    ) -> Optional[AuthUser]:
        """
        Retrieve user by ID.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            User object if found, None otherwise
            
        Raises:
            AuthenticationError: If user retrieval fails
        """
        pass
    
    @abstractmethod
    async def create_user(
        self,
        user_data: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> AuthUser:
        """
        Create a new user account.
        
        Args:
            user_data: User creation data
            created_by: User or system that created the account
            
        Returns:
            Created user object
            
        Raises:
            AuthenticationError: If user creation fails
        """
        pass
    
    @abstractmethod
    async def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> AuthUser:
        """
        Update user account information.
        
        Args:
            user_id: Unique user identifier
            updates: Fields to update
            updated_by: User or system that made the update
            
        Returns:
            Updated user object
            
        Raises:
            AuthenticationError: If user update fails
        """
        pass
    
    @abstractmethod
    async def deactivate_user(
        self,
        user_id: str,
        deactivated_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user_id: Unique user identifier
            deactivated_by: User or system that deactivated the account
            reason: Reason for deactivation (for audit)
            
        Returns:
            True if user was successfully deactivated
            
        Raises:
            AuthenticationError: If user deactivation fails
        """
        pass
    
    # Multi-factor authentication operations
    
    @abstractmethod
    async def initiate_mfa_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Initiate a multi-factor authentication challenge.
        
        Args:
            user_id: Unique user identifier
            method: MFA method to use
            client_info: Additional client information for audit
            
        Returns:
            Authentication result with MFA challenge token
            
        Raises:
            AuthenticationError: If MFA challenge initiation fails
        """
        pass
    
    @abstractmethod
    async def verify_mfa_challenge(
        self,
        challenge_token: str,
        verification_code: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Verify a multi-factor authentication challenge.
        
        Args:
            challenge_token: MFA challenge token
            verification_code: User-provided verification code
            client_info: Additional client information for audit
            
        Returns:
            Authentication result with access tokens
            
        Raises:
            AuthenticationError: If MFA verification fails
        """
        pass
    
    @abstractmethod
    async def setup_mfa_method(
        self,
        user_id: str,
        method: MFAMethod,
        method_data: Dict[str, Any]
    ) -> bool:
        """
        Set up a new MFA method for a user.
        
        Args:
            user_id: Unique user identifier
            method: MFA method to set up
            method_data: Method-specific configuration data
            
        Returns:
            True if MFA method was successfully set up
            
        Raises:
            AuthenticationError: If MFA method setup fails
        """
        pass
    
    @abstractmethod
    async def remove_mfa_method(
        self,
        user_id: str,
        method: MFAMethod,
        removed_by: Optional[str] = None
    ) -> bool:
        """
        Remove an MFA method from a user.
        
        Args:
            user_id: Unique user identifier
            method: MFA method to remove
            removed_by: User or system that removed the method
            
        Returns:
            True if MFA method was successfully removed
            
        Raises:
            AuthenticationError: If MFA method removal fails
        """
        pass
    
    # Token management operations
    
    @abstractmethod
    async def create_token(
        self,
        user_id: str,
        token_type: TokenType,
        expires_in: Optional[timedelta] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuthToken:
        """
        Create a new authentication token.
        
        Args:
            user_id: Unique user identifier
            token_type: Type of token to create
            expires_in: Token expiration duration
            scopes: Token permissions/scopes
            metadata: Additional token metadata
            
        Returns:
            Created authentication token
            
        Raises:
            AuthenticationError: If token creation fails
        """
        pass
    
    @abstractmethod
    async def validate_token(
        self,
        token: str,
        token_type: TokenType,
        required_scopes: Optional[List[str]] = None
    ) -> AuthToken:
        """
        Validate an authentication token.
        
        Args:
            token: Token value to validate
            token_type: Expected token type
            required_scopes: Required token permissions/scopes
            
        Returns:
            Validated authentication token
            
        Raises:
            AuthenticationError: If token validation fails
        """
        pass
    
    @abstractmethod
    async def get_user_tokens(
        self,
        user_id: str,
        token_type: Optional[TokenType] = None,
        active_only: bool = True
    ) -> List[AuthToken]:
        """
        Get all tokens for a user.
        
        Args:
            user_id: Unique user identifier
            token_type: Filter by token type (optional)
            active_only: Only return non-expired, non-revoked tokens
            
        Returns:
            List of user's authentication tokens
            
        Raises:
            AuthenticationError: If token retrieval fails
        """
        pass
    
    # Password management operations
    
    @abstractmethod
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        changed_by: Optional[str] = None
    ) -> bool:
        """
        Change a user's password.
        
        Args:
            user_id: Unique user identifier
            current_password: User's current password
            new_password: New password to set
            changed_by: User or system that changed the password
            
        Returns:
            True if password was successfully changed
            
        Raises:
            AuthenticationError: If password change fails
        """
        pass
    
    @abstractmethod
    async def reset_password(
        self,
        user_id: str,
        reset_token: str,
        new_password: str
    ) -> bool:
        """
        Reset a user's password using a reset token.
        
        Args:
            user_id: Unique user identifier
            reset_token: Password reset token
            new_password: New password to set
            
        Returns:
            True if password was successfully reset
            
        Raises:
            AuthenticationError: If password reset fails
        """
        pass
    
    @abstractmethod
    async def initiate_password_reset(
        self,
        identifier: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Initiate password reset process.
        
        Args:
            identifier: User identifier (email, username, etc.)
            client_info: Additional client information for audit
            
        Returns:
            True if password reset was initiated
            
        Raises:
            AuthenticationError: If password reset initiation fails
        """
        pass
    
    # Session management operations
    
    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new user session.
        
        Args:
            user_id: Unique user identifier
            client_info: Client information for audit
            
        Returns:
            Session identifier
            
        Raises:
            AuthenticationError: If session creation fails
        """
        pass
    
    @abstractmethod
    async def validate_session(
        self,
        session_id: str
    ) -> Optional[AuthUser]:
        """
        Validate a user session.
        
        Args:
            session_id: Session identifier to validate
            
        Returns:
            User object if session is valid, None otherwise
            
        Raises:
            AuthenticationError: If session validation fails
        """
        pass
    
    @abstractmethod
    async def invalidate_session(
        self,
        session_id: str,
        invalidated_by: Optional[str] = None
    ) -> bool:
        """
        Invalidate a user session.
        
        Args:
            session_id: Session identifier to invalidate
            invalidated_by: User or system that invalidated the session
            
        Returns:
            True if session was successfully invalidated
            
        Raises:
            AuthenticationError: If session invalidation fails
        """
        pass
    
    @abstractmethod
    async def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: Unique user identifier
            active_only: Only return active sessions
            
        Returns:
            List of user's sessions
            
        Raises:
            AuthenticationError: If session retrieval fails
        """
        pass
    
    # Audit and compliance operations
    
    @abstractmethod
    async def log_authentication_event(
        self,
        event_type: str,
        user_id: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an authentication event for audit purposes.
        
        Args:
            event_type: Type of authentication event
            user_id: User involved in the event (if applicable)
            success: Whether the event was successful
            metadata: Additional event metadata (non-sensitive)
            
        Raises:
            AuthenticationError: If event logging fails
        """
        pass
    
    @abstractmethod
    async def get_user_audit_log(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries for a user.
        
        Args:
            user_id: Unique user identifier
            start_date: Start of date range filter
            end_date: End of date range filter
            event_types: Filter by event types
            
        Returns:
            List of audit log entries
            
        Raises:
            AuthenticationError: If audit log retrieval fails
        """
        pass
    
    # Provider-specific operations
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the authentication provider.
        
        Returns:
            Health status information
            
        Raises:
            AuthenticationError: If health check fails
        """
        pass
    
    @abstractmethod
    async def get_provider_config(self) -> Dict[str, Any]:
        """
        Get non-sensitive provider configuration.
        
        Returns:
            Provider configuration (with sensitive data excluded)
        """
        pass
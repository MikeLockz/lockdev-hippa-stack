"""
Vendor-agnostic authentication data models.

This module defines Pydantic models for authentication operations that are
independent of specific authentication providers. All models include HIPAA-specific
fields and validation rules.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class UserRole(str, Enum):
    """User roles for HIPAA-compliant access control."""
    ADMIN = "admin"
    CLINICIAN = "clinician" 
    NURSE = "nurse"
    TECHNICIAN = "technician"
    PATIENT = "patient"
    AUDIT_USER = "audit_user"
    SYSTEM = "system"


class MFAMethod(str, Enum):
    """Multi-factor authentication methods."""
    SMS = "sms"
    EMAIL = "email"
    TOTP = "totp"
    HARDWARE_TOKEN = "hardware_token"
    BIOMETRIC = "biometric"


class TokenType(str, Enum):
    """Authentication token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    MFA_CHALLENGE = "mfa_challenge"
    PASSWORD_RESET = "password_reset"


class AuthUser(BaseModel):
    """
    Vendor-agnostic user model for authentication operations.
    
    This model represents a user with HIPAA-specific fields and
    validation rules for healthcare applications.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=False,
        extra="forbid"
    )
    
    # Core user identification
    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    username: Optional[str] = Field(None, description="Optional username")
    
    # HIPAA-specific fields
    roles: List[UserRole] = Field(default_factory=lambda: [UserRole.PATIENT], description="User roles for access control")
    permissions: List[str] = Field(default=[], description="Specific permissions")
    is_active: bool = Field(True, description="Whether user account is active")
    is_verified: bool = Field(False, description="Whether user email is verified")
    
    # Multi-factor authentication
    mfa_enabled: bool = Field(False, description="Whether MFA is enabled")
    mfa_methods: List[MFAMethod] = Field(default=[], description="Available MFA methods")
    
    # Audit and compliance fields
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last successful login")
    last_password_change: Optional[datetime] = Field(None, description="Last password change")
    password_expires_at: Optional[datetime] = Field(None, description="Password expiration date")
    account_locked_until: Optional[datetime] = Field(None, description="Account lock expiration")
    failed_login_attempts: int = Field(0, description="Count of failed login attempts")
    
    # Healthcare-specific metadata
    department: Optional[str] = Field(None, description="User's department")
    license_number: Optional[str] = Field(None, description="Professional license number")
    supervisor_id: Optional[str] = Field(None, description="Supervisor user ID")
    
    # Additional metadata (non-sensitive)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if not v or '@' not in v or len(v) < 3:
            raise ValueError('Invalid email format')
        
        # Split by @ and check both parts exist
        parts = v.split('@')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError('Invalid email format')
        
        # Check domain part has at least one dot
        domain = parts[1]
        if '.' not in domain or domain.startswith('.') or domain.endswith('.'):
            raise ValueError('Invalid email format')
        
        return v.lower()
    
    @field_validator('roles')
    @classmethod
    def validate_roles(cls, v: List[UserRole]) -> List[UserRole]:
        """Ensure roles list is not empty for active users."""
        if not v:
            # Default role for users with no explicit roles
            return [UserRole.PATIENT]
        return v
    
    @field_validator('failed_login_attempts')
    @classmethod
    def validate_failed_attempts(cls, v: int) -> int:
        """Ensure failed login attempts is non-negative."""
        if v < 0:
            raise ValueError('Failed login attempts must be non-negative')
        return v


class AuthToken(BaseModel):
    """
    Vendor-agnostic authentication token model.
    
    Represents authentication tokens with HIPAA-compliant metadata
    and security attributes.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Token identification
    token_id: str = Field(..., description="Unique token identifier")
    token_type: TokenType = Field(..., description="Type of authentication token")
    token_value: str = Field(..., description="Actual token value")
    
    # Token lifecycle
    issued_at: datetime = Field(..., description="Token issuance timestamp")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    not_before: Optional[datetime] = Field(None, description="Token not valid before timestamp")
    
    # User and session information
    user_id: str = Field(..., description="ID of the user this token belongs to")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    # Security metadata
    issued_by: str = Field(..., description="Token issuer identifier")
    audience: List[str] = Field(default=[], description="Intended token audiences")
    scopes: List[str] = Field(default=[], description="Token permissions/scopes")
    
    # HIPAA audit fields
    client_id: Optional[str] = Field(None, description="Client application identifier")
    ip_address: Optional[str] = Field(None, description="IP address where token was issued")
    user_agent: Optional[str] = Field(None, description="User agent where token was issued")
    
    # Token state
    is_revoked: bool = Field(False, description="Whether token has been revoked")
    revoked_at: Optional[datetime] = Field(None, description="Token revocation timestamp")
    revoked_by: Optional[str] = Field(None, description="Who revoked the token")
    
    @model_validator(mode='after')
    def validate_token_timestamps(self) -> 'AuthToken':
        """Validate token timestamp consistency."""
        if self.expires_at <= self.issued_at:
            raise ValueError('Token expiration must be after issuance')
        return self
    
    @field_validator('token_value')
    @classmethod
    def validate_token_value(cls, v: str) -> str:
        """Ensure token value meets minimum security requirements."""
        if len(v) < 32:
            raise ValueError('Token value must be at least 32 characters')
        return v


class AuthResult(BaseModel):
    """
    Result of an authentication operation.
    
    Contains the authenticated user, tokens, and additional metadata
    about the authentication process.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Authentication outcome
    success: bool = Field(..., description="Whether authentication was successful")
    user: Optional[AuthUser] = Field(None, description="Authenticated user (if successful)")
    
    # Tokens (if authentication successful)
    access_token: Optional[AuthToken] = Field(None, description="Access token")
    refresh_token: Optional[AuthToken] = Field(None, description="Refresh token")
    
    # Multi-factor authentication
    mfa_required: bool = Field(False, description="Whether MFA is required")
    mfa_challenge_token: Optional[AuthToken] = Field(None, description="MFA challenge token")
    mfa_methods: List[MFAMethod] = Field(default=[], description="Available MFA methods")
    
    # Authentication metadata
    authentication_method: str = Field(..., description="Method used for authentication")
    provider: str = Field(..., description="Authentication provider")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Authentication timestamp")
    
    # Security and audit information
    session_id: Optional[str] = Field(None, description="Session identifier")
    client_info: Dict[str, Any] = Field(default_factory=dict, description="Client information")
    
    # Error information (if authentication failed)
    error_code: Optional[str] = Field(None, description="Error code if authentication failed")
    error_message: Optional[str] = Field(None, description="Error message if authentication failed")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional authentication metadata")
    
    @model_validator(mode='after')
    def validate_authentication_consistency(self) -> 'AuthResult':
        """Validate consistency between success status and provided fields."""
        # User consistency check - but allow MFA-required scenarios without user
        if self.success and not self.mfa_required and self.user is None:
            raise ValueError('User must be provided when authentication is successful and MFA not required')
        if not self.success and self.user is not None:
            raise ValueError('User should not be provided when authentication fails')
        
        # Access token consistency check
        if (self.success and 
            not self.mfa_required and 
            self.access_token is None):
            raise ValueError('Access token must be provided when authentication is successful and MFA not required')
        
        return self
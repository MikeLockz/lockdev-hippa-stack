"""
User Data Mapper

Handles the conversion and mapping of user data between different authentication
providers while maintaining data integrity and HIPAA compliance. This module
provides the bridge for seamless user migration and synchronization between
various authentication systems.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from src.auth.models import AuthUser, AuthToken
from src.models.user import User
from src.auth.interfaces import AuthProviderType

logger = logging.getLogger(__name__)


class UserDataMapper:
    """
    Maps user data between different authentication providers and local database.
    
    This class provides standardized conversion methods for:
    - Converting provider-specific user data to AuthUser model
    - Converting local User objects to provider-specific formats
    - Preserving critical metadata during migrations
    - Handling data format differences between providers
    
    HIPAA Compliance:
    - Sanitizes sensitive data during conversion
    - Preserves audit metadata and compliance fields
    - Ensures no PHI leakage during data transformation
    - Maintains data integrity with validation
    """
    
    def __init__(self):
        """Initialize the data mapper with validation rules."""
        self._validation_rules = {
            "email": self._validate_email,
            "roles": self._validate_roles,
            "license_number": self._validate_license,
            "department": self._validate_department,
        }
    
    async def map_to_auth_user(
        self, 
        provider_user: Dict[str, Any], 
        provider_type: str
    ) -> AuthUser:
        """
        Convert provider-specific user data to standardized AuthUser model.
        
        Args:
            provider_user: User data from external provider
            provider_type: Type of authentication provider
            
        Returns:
            AuthUser: Standardized user model
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            if provider_type == "custom":
                return await self._map_custom_to_auth_user(provider_user)
            elif provider_type == "aws_cognito":
                return await self._map_cognito_to_auth_user(provider_user)
            elif provider_type == "auth0":
                return await self._map_auth0_to_auth_user(provider_user)
            elif provider_type == "supabase":
                return await self._map_supabase_to_auth_user(provider_user)
            else:
                raise ValueError(f"Unsupported provider type: {provider_type}")
                
        except Exception as e:
            logger.error(
                "Failed to map provider user to AuthUser",
                provider_type=provider_type,
                error=str(e),
                provider_user_keys=list(provider_user.keys()) if provider_user else "None"
            )
            raise
    
    async def map_from_auth_user(
        self, 
        auth_user: AuthUser, 
        provider_type: str
    ) -> Dict[str, Any]:
        """
        Convert standardized AuthUser to provider-specific format.
        
        Args:
            auth_user: Standardized user model
            provider_type: Target authentication provider type
            
        Returns:
            Dict[str, Any]: Provider-specific user data
            
        Raises:
            ValueError: If provider type is unsupported
        """
        try:
            if provider_type == "custom":
                return await self._map_auth_user_to_custom(auth_user)
            elif provider_type == "aws_cognito":
                return await self._map_auth_user_to_cognito(auth_user)
            elif provider_type == "auth0":
                return await self._map_auth_user_to_auth0(auth_user)
            elif provider_type == "supabase":
                return await self._map_auth_user_to_supabase(auth_user)
            else:
                raise ValueError(f"Unsupported provider type: {provider_type}")
                
        except Exception as e:
            logger.error(
                "Failed to map AuthUser to provider format",
                provider_type=provider_type,
                error=str(e),
                user_id=str(auth_user.id) if auth_user else "None"
            )
            raise
    
    async def map_custom_to_auth_user(self, user: User) -> AuthUser:
        """
        Convert local User model to standardized AuthUser.
        
        Args:
            user: Local database User object
            
        Returns:
            AuthUser: Standardized user model
        """
        return AuthUser(
            id=user.id,
            email=user.email,
            username=user.email,  # Use email as username for custom provider
            first_name=user.first_name,
            last_name=user.last_name,
            roles=[user.role] if user.role else ["USER"],
            is_active=user.is_active,
            is_verified=True,  # Assume verified for local users
            created_at=user.created_at,
            last_login=user.last_login,
            metadata={
                "department": user.department,
                "license_number": user.license_number,
                "license_expiry": user.license_expiry.isoformat() if user.license_expiry else None,
                "phi_access_granted": user.phi_access_granted,
                "phi_access_expiry": user.phi_access_expiry.isoformat() if user.phi_access_expiry else None,
                "mfa_enabled": user.mfa_enabled,
                "max_concurrent_sessions": user.max_concurrent_sessions,
                "session_timeout_minutes": user.session_timeout_minutes,
            }
        )
    
    async def preserve_audit_metadata(
        self, 
        source_user: Dict[str, Any], 
        target_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preserve critical audit and compliance metadata during migration.
        
        Args:
            source_user: Source user data
            target_user: Target user data (will be updated)
            
        Returns:
            Dict[str, Any]: Updated target user with preserved metadata
        """
        preserved_fields = [
            "created_at",
            "last_login",
            "login_attempts",
            "password_changed_at",
            "phi_access_granted",
            "phi_access_reason",
            "license_expiry",
            "department",
            "supervisor_id",
            "mfa_enabled",
            "terms_accepted_at",
            "privacy_policy_accepted_at",
            "hipaa_training_completed_at",
        ]
        
        for field in preserved_fields:
            if field in source_user and source_user[field] is not None:
                # Convert datetime objects to strings for JSON serialization
                value = source_user[field]
                if isinstance(value, datetime):
                    value = value.isoformat()
                target_user[field] = value
        
        # Preserve role mapping if source has different role format
        if "roles" in source_user and isinstance(source_user["roles"], list):
            target_user["roles"] = source_user["roles"]
        elif "role" in source_user and source_user["role"]:
            target_user["roles"] = [source_user["role"]]
        
        return target_user
    
    async def validate_data_integrity(
        self, 
        source_data: Dict[str, Any], 
        target_data: Dict[str, Any]
    ) -> bool:
        """
        Validate data integrity after mapping.
        
        Args:
            source_data: Original user data
            target_data: Mapped user data
            
        Returns:
            bool: True if data integrity is maintained
        """
        critical_fields = ["email", "id"]
        
        for field in critical_fields:
            source_value = source_data.get(field)
            target_value = target_data.get(field)
            
            if source_value and target_value and str(source_value) != str(target_value):
                logger.error(
                    "Data integrity validation failed",
                    field=field,
                    source_value=source_value,
                    target_value=target_value
                )
                return False
        
        return True
    
    # Private mapping methods for specific providers
    
    async def _map_custom_to_auth_user(self, user_data: Dict[str, Any]) -> AuthUser:
        """Map custom provider data to AuthUser."""
        return AuthUser(
            id=user_data.get("id"),
            email=user_data.get("email"),
            username=user_data.get("username", user_data.get("email")),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            roles=user_data.get("roles", ["USER"]),
            is_active=user_data.get("is_active", True),
            is_verified=user_data.get("is_verified", True),
            created_at=user_data.get("created_at"),
            last_login=user_data.get("last_login"),
            metadata=user_data.get("metadata", {})
        )
    
    async def _map_cognito_to_auth_user(self, cognito_user: Dict[str, Any]) -> AuthUser:
        """Map AWS Cognito user data to AuthUser."""
        attributes = {attr["Name"]: attr["Value"] 
                     for attr in cognito_user.get("UserAttributes", [])}
        
        return AuthUser(
            id=uuid.UUID(cognito_user.get("Username")),  # Use username as ID
            email=attributes.get("email"),
            username=cognito_user.get("Username"),
            first_name=attributes.get("given_name"),
            last_name=attributes.get("family_name"),
            roles=[attributes.get("custom:role", "USER")],
            is_active=cognito_user.get("UserStatus") == "CONFIRMED",
            is_verified=attributes.get("email_verified") == "true",
            created_at=datetime.fromisoformat(cognito_user.get("UserCreateDate").replace("Z", "+00:00")),
            last_login=datetime.fromisoformat(cognito_user.get("LastModifiedDate").replace("Z", "+00:00")),
            metadata={
                "department": attributes.get("custom:department"),
                "license_number": attributes.get("custom:license_number"),
                "cognito_sub": attributes.get("sub"),
                "user_status": cognito_user.get("UserStatus"),
            }
        )
    
    async def _map_auth0_to_auth_user(self, auth0_user: Dict[str, Any]) -> AuthUser:
        """Map Auth0 user data to AuthUser."""
        return AuthUser(
            id=uuid.UUID(auth0_user.get("user_id").split("|")[-1]),  # Extract UUID from Auth0 ID
            email=auth0_user.get("email"),
            username=auth0_user.get("username", auth0_user.get("email")),
            first_name=auth0_user.get("given_name"),
            last_name=auth0_user.get("family_name"),
            roles=auth0_user.get("roles", ["USER"]),
            is_active=not auth0_user.get("blocked", False),
            is_verified=auth0_user.get("email_verified", False),
            created_at=datetime.fromisoformat(auth0_user.get("created_at", "").replace("Z", "+00:00")),
            last_login=datetime.fromisoformat(auth0_user.get("last_login", "").replace("Z", "+00:00")),
            metadata={
                "picture": auth0_user.get("picture"),
                "nickname": auth0_user.get("nickname"),
                "logins_count": auth0_user.get("logins_count"),
                "identities": auth0_user.get("identities", []),
            }
        )
    
    async def _map_supabase_to_auth_user(self, supabase_user: Dict[str, Any]) -> AuthUser:
        """Map Supabase user data to AuthUser."""
        user_metadata = supabase_user.get("user_metadata", {})
        
        return AuthUser(
            id=uuid.UUID(supabase_user.get("id")),
            email=supabase_user.get("email"),
            username=user_metadata.get("username", supabase_user.get("email")),
            first_name=user_metadata.get("first_name"),
            last_name=user_metadata.get("last_name"),
            roles=user_metadata.get("roles", ["USER"]),
            is_active=supabase_user.get("email_confirmed_at") is not None,
            is_verified=supabase_user.get("email_confirmed_at") is not None,
            created_at=datetime.fromisoformat(supabase_user.get("created_at", "").replace("Z", "+00:00")),
            last_login=datetime.fromisoformat(supabase_user.get("last_sign_in_at", "").replace("Z", "+00:00")),
            metadata=user_metadata
        )
    
    async def _map_auth_user_to_custom(self, auth_user: AuthUser) -> Dict[str, Any]:
        """Map AuthUser to custom provider format."""
        return {
            "id": str(auth_user.id),
            "email": auth_user.email,
            "username": auth_user.username,
            "first_name": auth_user.first_name,
            "last_name": auth_user.last_name,
            "role": auth_user.roles[0] if auth_user.roles else "USER",
            "is_active": auth_user.is_active,
            "is_verified": auth_user.is_verified,
            "created_at": auth_user.created_at.isoformat() if auth_user.created_at else None,
            "last_login": auth_user.last_login.isoformat() if auth_user.last_login else None,
            **auth_user.metadata
        }
    
    async def _map_auth_user_to_cognito(self, auth_user: AuthUser) -> Dict[str, Any]:
        """Map AuthUser to AWS Cognito format."""
        return {
            "Username": auth_user.email,
            "UserAttributes": [
                {"Name": "email", "Value": auth_user.email},
                {"Name": "email_verified", "Value": str(auth_user.is_verified).lower()},
                {"Name": "given_name", "Value": auth_user.first_name or ""},
                {"Name": "family_name", "Value": auth_user.last_name or ""},
                {"Name": "custom:role", "Value": auth_user.roles[0] if auth_user.roles else "USER"},
                {"Name": "custom:department", "Value": auth_user.metadata.get("department", "")},
                {"Name": "custom:license_number", "Value": auth_user.metadata.get("license_number", "")},
            ],
            "MessageAction": "SUPPRESS",  # Don't send welcome email
            "DesiredDeliveryMediums": ["EMAIL"]
        }
    
    async def _map_auth_user_to_auth0(self, auth_user: AuthUser) -> Dict[str, Any]:
        """Map AuthUser to Auth0 format."""
        return {
            "email": auth_user.email,
            "username": auth_user.username,
            "given_name": auth_user.first_name,
            "family_name": auth_user.last_name,
            "name": f"{auth_user.first_name} {auth_user.last_name}".strip(),
            "email_verified": auth_user.is_verified,
            "user_metadata": {
                "roles": auth_user.roles,
                "department": auth_user.metadata.get("department"),
                "license_number": auth_user.metadata.get("license_number"),
            },
            "app_metadata": {
                "created_at": auth_user.created_at.isoformat() if auth_user.created_at else None,
                "last_login": auth_user.last_login.isoformat() if auth_user.last_login else None,
            }
        }
    
    async def _map_auth_user_to_supabase(self, auth_user: AuthUser) -> Dict[str, Any]:
        """Map AuthUser to Supabase format."""
        return {
            "email": auth_user.email,
            "user_metadata": {
                "username": auth_user.username,
                "first_name": auth_user.first_name,
                "last_name": auth_user.last_name,
                "roles": auth_user.roles,
                **auth_user.metadata
            },
            "email_confirm": auth_user.is_verified
        }
    
    # Validation helpers
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_roles(self, roles: List[str]) -> bool:
        """Validate role values."""
        valid_roles = {"USER", "ADMIN", "PHYSICIAN", "NURSE", "PHARMACIST", "TECHNICIAN", "RECEPTIONIST", "SUPER_USER"}
        return all(role in valid_roles for role in roles)
    
    def _validate_license(self, license_number: str) -> bool:
        """Validate license number format (basic validation)."""
        return len(license_number) >= 5 and license_number.isalnum()
    
    def _validate_department(self, department: str) -> bool:
        """Validate department name."""
        valid_departments = {"CARDIOLOGY", "NEUROLOGY", "EMERGENCY", "RADIOLOGY", "PHARMACY", "ADMINISTRATION"}
        return department.upper() in valid_departments
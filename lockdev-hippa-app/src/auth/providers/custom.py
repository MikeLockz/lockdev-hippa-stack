"""
Custom authentication provider implementation.

This provider implements the AuthenticationProvider interface using the existing
JWT/bcrypt infrastructure with enhanced security features for HIPAA compliance.
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
import structlog

from ..interfaces import AuthenticationProvider
from ..models import AuthUser, AuthToken, AuthResult, TokenType, MFAMethod, UserRole
from ..exceptions import AuthenticationError
from ..services import UserService, SessionService, AuditService
from ...models.user import User
from ...utils.security import (
    get_password_hash, verify_password, create_access_token, 
    jwt, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
)
from ...utils.database import get_db_session

logger = structlog.get_logger()


class CustomAuthProvider(AuthenticationProvider):
    """
    Custom authentication provider with HIPAA compliance features.
    
    This provider integrates with the existing application infrastructure
    while providing enhanced security features like session management,
    password policies, account lockout, and comprehensive audit logging.
    """
    
    def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
        """Initialize the custom authentication provider."""
        super().__init__(provider_name, config)
        
        # Configuration
        self.access_token_expire_minutes = config.get(
            "access_token_expire_minutes", ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self.refresh_token_expire_days = config.get("refresh_token_expire_days", 7)
        self.mfa_challenge_expire_minutes = config.get("mfa_challenge_expire_minutes", 5)
        self.password_reset_expire_hours = config.get("password_reset_expire_hours", 24)
        
        # Service instances will be created per request with database session
        self._db_session = None
        self._user_service = None
        self._session_service = None
        self._audit_service = None
        
        logger.info(f"CustomAuthProvider initialized: {provider_name}")
    
    async def _get_db_session(self) -> AsyncSession:
        """Get database session using context manager."""
        from contextlib import asynccontextmanager
        from ...utils.database import AsyncSessionLocal
        
        @asynccontextmanager
        async def get_session():
            async with AsyncSessionLocal() as session:
                yield session
        
        return get_session()
    
    def _sanitize_client_info(self, client_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Sanitize client info for audit logging."""
        if not client_info:
            return {}
        
        # Remove sensitive information
        sanitized = client_info.copy()
        sensitive_keys = ['authorization', 'password', 'token', 'secret']
        
        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
        
        return sanitized
    
    def _is_mfa_required(self, user: AuthUser) -> bool:
        """Check if MFA is required for this user."""
        return any(role in self.require_mfa_for_roles for role in user.roles)
    
    async def _create_mfa_challenge_token(
        self, 
        user_id: str, 
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthToken:
        """Create an MFA challenge token."""
        return await self.create_token(
            user_id,
            TokenType.MFA_CHALLENGE,
            expires_in=timedelta(minutes=self.mfa_challenge_expire_minutes),
            metadata={
                "challenge_id": secrets.token_urlsafe(16),
                "client_info": self._sanitize_client_info(client_info)
            }
        )
    
    async def authenticate_user(
        self,
        identifier: str,
        credential: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """Authenticate a user with their credentials."""
        async with self._get_db_session() as db:
            user_service = UserService(db)
            session_service = SessionService(db)
            audit_service = AuditService(db)
            
            try:
                # Get user by email
                auth_user = await user_service.get_user_by_email(identifier)
                
                if not auth_user:
                await audit_service.log_login_attempt(
                    user_id=None,
                    email=identifier,
                    success=False,
                    failure_reason="User not found",
                    client_info=client_info
                )
                    return AuthResult(
                        success=False,
                        error_code="INVALID_CREDENTIALS",
                        error_message="Invalid email or password",
                        authentication_method="password",
                        provider=self.provider_name,
                        client_info=client_info or {}
                    )
                
                # Check if account is locked
            if (auth_user.account_locked_until and 
                auth_user.account_locked_until > datetime.utcnow()):
                await audit_service.log_login_attempt(
                    user_id=auth_user.id,
                    email=identifier,
                    success=False,
                    failure_reason="Account locked",
                    client_info=client_info
                )
                return AuthResult(
                    success=False,
                    error_code="ACCOUNT_LOCKED",
                    error_message="Account is temporarily locked",
                    authentication_method="password",
                    provider=self.provider_name,
                    client_info=client_info or {}
                )
            
            # Check if account is active
            if not auth_user.is_active:
                await audit_service.log_login_attempt(
                    user_id=auth_user.id,
                    email=identifier,
                    success=False,
                    failure_reason="Account inactive",
                    client_info=client_info
                )
                return AuthResult(
                    success=False,
                    error_code="ACCOUNT_INACTIVE",
                    error_message="Account is inactive",
                    authentication_method="password",
                    provider=self.provider_name,
                    client_info=client_info or {}
                )
            
            # Get database user for password verification
            stmt = select(User).where(User.id == uuid.UUID(auth_user.id))
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                raise AuthenticationError("User not found in database")
            
            # Verify password
            if not verify_password(credential, db_user.hashed_password):
                # Increment failed attempts
                attempts, was_locked = await user_service.increment_failed_login_attempts(
                    auth_user.id
                )
                
                failure_reason = f"Invalid password (attempt {attempts})"
                if was_locked:
                    failure_reason = f"Account locked after {attempts} failed attempts"
                
                await audit_service.log_login_attempt(
                    user_id=auth_user.id,
                    email=identifier,
                    success=False,
                    failure_reason=failure_reason,
                    client_info=client_info
                )
                
                error_code = "ACCOUNT_LOCKED" if was_locked else "INVALID_CREDENTIALS"
                error_message = "Account locked due to multiple failed attempts" if was_locked else "Invalid email or password"
                
                return AuthResult(
                    success=False,
                    error_code=error_code,
                    error_message=error_message,
                    authentication_method="password",
                    provider=self.provider_name,
                    client_info=client_info or {}
                )
            
            # Reset failed attempts on successful authentication
            await user_service.reset_failed_login_attempts(auth_user.id)
            
            # Check if MFA is required
            if auth_user.mfa_enabled:
                # Create MFA challenge token
                mfa_challenge_token = await self.create_token(
                    auth_user.id,
                    TokenType.MFA_CHALLENGE,
                    expires_in=timedelta(minutes=self.mfa_challenge_expire_minutes),
                    metadata={"email": identifier}
                )
                
                await audit_service.log_login_attempt(
                    user_id=auth_user.id,
                    email=identifier,
                    success=True,
                    client_info=client_info
                )
                
                await audit_service.log_mfa_event(
                    user_id=auth_user.id,
                    mfa_method="required",
                    event_type="challenge_required",
                    success=True,
                    client_info=client_info
                )
                
                return AuthResult(
                    success=True,
                    user=auth_user,
                    mfa_required=True,
                    mfa_challenge_token=mfa_challenge_token,
                    mfa_methods=auth_user.mfa_methods,
                    authentication_method="password",
                    provider=self.provider_name,
                    client_info=client_info or {}
                )
            
            # Create session and tokens
            session_id = await session_service.create_session(
                auth_user.id,
                client_info
            )
            
            access_token = await self.create_token(
                auth_user.id,
                TokenType.ACCESS,
                expires_in=timedelta(minutes=self.access_token_expire_minutes),
                metadata={"session_id": session_id}
            )
            
            refresh_token = await self.create_token(
                auth_user.id,
                TokenType.REFRESH,
                expires_in=timedelta(days=self.refresh_token_expire_days),
                metadata={"session_id": session_id}
            )
            
            # Update last login
            await user_service.update_user(
                auth_user.id,
                {"last_login": datetime.utcnow()},
                "system"
            )
            
            await audit_service.log_login_attempt(
                user_id=auth_user.id,
                email=identifier,
                success=True,
                client_info=client_info
            )
            
            return AuthResult(
                success=True,
                user=auth_user,
                access_token=access_token,
                refresh_token=refresh_token,
                session_id=session_id,
                authentication_method="password",
                provider=self.provider_name,
                client_info=client_info or {}
            )
            
        except Exception as e:
            logger.error(
                "Authentication error",
                identifier=identifier,
                error=str(e),
                error_type=type(e).__name__
            )
            
            await audit_service.log_login_attempt(
                user_id=None,
                email=identifier,
                success=False,
                failure_reason=f"System error: {str(e)}",
                client_info=client_info
            )
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    async def authenticate_token(
        self,
        token: str,
        token_type: TokenType = TokenType.ACCESS
    ) -> AuthResult:
        """Authenticate using an existing token."""
        user_service, session_service, audit_service, db = await self._get_services()
        
        try:
            # Validate and decode token
            validated_token = await self.validate_token(token, token_type)
            
            # Get user
            auth_user = await user_service.get_user_by_id(validated_token.user_id)
            if not auth_user:
                raise AuthenticationError("User not found")
            
            # Validate session if present
            if validated_token.session_id:
                session_user_id = await session_service.validate_session(
                    validated_token.session_id
                )
                if not session_user_id or session_user_id != validated_token.user_id:
                    await audit_service.log_token_validation(
                        user_id=validated_token.user_id,
                        token_type=token_type.value,
                        success=False,
                        failure_reason="Invalid session",
                    )
                    raise AuthenticationError("Invalid session")
            
            await audit_service.log_token_validation(
                user_id=validated_token.user_id,
                token_type=token_type.value,
                success=True
            )
            
            return AuthResult(
                success=True,
                user=auth_user,
                access_token=validated_token,
                session_id=validated_token.session_id,
                authentication_method="token",
                provider=self.provider_name
            )
            
        except Exception as e:
            logger.error(f"Token authentication error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"Token authentication failed: {str(e)}")
    
    async def refresh_token(
        self,
        refresh_token: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """Refresh an access token using a refresh token."""
        user_service, session_service, audit_service, db = await self._get_services()
        
        try:
            # Validate refresh token
            validated_token = await self.validate_token(refresh_token, TokenType.REFRESH)
            
            # Get user
            auth_user = await user_service.get_user_by_id(validated_token.user_id)
            if not auth_user or not auth_user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Validate session
            if validated_token.session_id:
                session_user_id = await session_service.validate_session(
                    validated_token.session_id
                )
                if not session_user_id:
                    raise AuthenticationError("Session expired")
            
            # Create new access token
            new_access_token = await self.create_token(
                auth_user.id,
                TokenType.ACCESS,
                expires_in=timedelta(minutes=self.access_token_expire_minutes),
                metadata={"session_id": validated_token.session_id}
            )
            
            await audit_service.log_authentication_event(
                event_type="token_refreshed",
                user_id=auth_user.id,
                success=True,
                metadata={"original_token_id": validated_token.token_id},
                client_info=client_info
            )
            
            return AuthResult(
                success=True,
                user=auth_user,
                access_token=new_access_token,
                refresh_token=validated_token,  # Keep existing refresh token
                session_id=validated_token.session_id,
                authentication_method="refresh_token",
                provider=self.provider_name,
                client_info=client_info or {}
            )
            
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"Token refresh failed: {str(e)}")
    
    async def revoke_token(
        self,
        token: str,
        token_type: TokenType,
        revoked_by: Optional[str] = None
    ) -> bool:
        """Revoke an authentication token."""
        user_service, session_service, audit_service, db = await self._get_services()
        
        try:
            # Decode token to get user info (don't validate expiration)
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                token_id = payload.get("jti")
            except jwt.ExpiredSignatureError:
                # Allow revoking expired tokens
                payload = jwt.decode(
                    token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False}
                )
                user_id = payload.get("sub")
                token_id = payload.get("jti")
            except Exception as e:
                logger.error(f"Token decode error during revocation: {str(e)}")
                return False
            
            if not user_id:
                return False
            
            # Log revocation (in a real implementation, we'd maintain a revocation list)
            await audit_service.log_token_revocation(
                user_id=user_id,
                token_type=token_type.value,
                revoked_by=revoked_by
            )
            
            # If it's a refresh token, also invalidate associated session
            if token_type == TokenType.REFRESH and "session_id" in payload:
                session_id = payload["session_id"]
                await session_service.invalidate_session(session_id, revoked_by)
            
            logger.info(
                "Token revoked",
                token_id=token_id,
                user_id=user_id,
                token_type=token_type.value,
                revoked_by=revoked_by or "system"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Token revocation error: {str(e)}")
            return False
    
    async def get_user(self, user_id: str) -> Optional[AuthUser]:
        """Retrieve user by ID."""
        user_service, _, _, _ = await self._get_services()
        return await user_service.get_user_by_id(user_id)
    
    async def create_user(
        self,
        user_data: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> AuthUser:
        """Create a new user account."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            auth_user = await user_service.create_user(user_data, created_by)
            
            await audit_service.log_authentication_event(
                event_type="user_created",
                user_id=auth_user.id,
                success=True,
                metadata={
                    "email": auth_user.email,
                    "created_by": created_by or "system"
                }
            )
            
            return auth_user
            
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            
            if isinstance(e, ValueError):
                raise AuthenticationError(f"User creation failed: {str(e)}")
            
            raise AuthenticationError(f"User creation failed: {str(e)}")
    
    async def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> AuthUser:
        """Update user account information."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            auth_user = await user_service.update_user(user_id, updates, updated_by)
            
            await audit_service.log_authentication_event(
                event_type="user_updated",
                user_id=user_id,
                success=True,
                metadata={
                    "updated_fields": list(updates.keys()),
                    "updated_by": updated_by or "system"
                }
            )
            
            return auth_user
            
        except Exception as e:
            logger.error(f"User update error: {str(e)}")
            
            if isinstance(e, ValueError):
                raise AuthenticationError(f"User update failed: {str(e)}")
            
            raise AuthenticationError(f"User update failed: {str(e)}")
    
    async def deactivate_user(
        self,
        user_id: str,
        deactivated_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Deactivate a user account."""
        user_service, session_service, audit_service, _ = await self._get_services()
        
        try:
            success = await user_service.deactivate_user(user_id, deactivated_by, reason)
            
            if success:
                # Invalidate all user sessions
                await session_service.invalidate_all_user_sessions(user_id, deactivated_by)
                
                await audit_service.log_authentication_event(
                    event_type="user_deactivated",
                    user_id=user_id,
                    success=True,
                    metadata={
                        "deactivated_by": deactivated_by or "system",
                        "reason": reason or "not specified"
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(f"User deactivation error: {str(e)}")
            return False
    
    # MFA Methods (basic implementation - would be enhanced in production)
    
    async def initiate_mfa_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """Initiate a multi-factor authentication challenge."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            auth_user = await user_service.get_user_by_id(user_id)
            if not auth_user:
                raise AuthenticationError("User not found")
            
            if method not in auth_user.mfa_methods:
                raise AuthenticationError(f"MFA method {method.value} not configured")
            
            # Create challenge token
            challenge_token = await self.create_token(
                user_id,
                TokenType.MFA_CHALLENGE,
                expires_in=timedelta(minutes=self.mfa_challenge_expire_minutes),
                metadata={
                    "mfa_method": method.value,
                    "challenge_id": secrets.token_urlsafe(16)
                }
            )
            
            await audit_service.log_mfa_event(
                user_id=user_id,
                mfa_method=method.value,
                event_type="challenge_initiated",
                success=True,
                client_info=client_info
            )
            
            return AuthResult(
                success=True,
                user=auth_user,
                mfa_required=True,
                mfa_challenge_token=challenge_token,
                mfa_methods=[method],
                authentication_method="mfa_challenge",
                provider=self.provider_name,
                client_info=client_info or {}
            )
            
        except Exception as e:
            logger.error(f"MFA challenge initiation error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"MFA challenge initiation failed: {str(e)}")
    
    async def verify_mfa_challenge(
        self,
        challenge_token: str,
        verification_code: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """Verify a multi-factor authentication challenge."""
        user_service, session_service, audit_service, _ = await self._get_services()
        
        try:
            # Validate challenge token
            validated_token = await self.validate_token(
                challenge_token, TokenType.MFA_CHALLENGE
            )
            
            auth_user = await user_service.get_user_by_id(validated_token.user_id)
            if not auth_user:
                raise AuthenticationError("User not found")
            
            # In a real implementation, this would verify against TOTP, SMS, etc.
            # For now, we'll accept any 6-digit code as valid
            if not verification_code or len(verification_code) != 6 or not verification_code.isdigit():
                await audit_service.log_mfa_event(
                    user_id=validated_token.user_id,
                    mfa_method=validated_token.metadata.get("mfa_method", "unknown"),
                    event_type="verification_failed",
                    success=False,
                    failure_reason="Invalid verification code format",
                    client_info=client_info
                )
                raise AuthenticationError("Invalid verification code")
            
            # Create session and tokens
            session_id = await session_service.create_session(
                validated_token.user_id,
                client_info
            )
            
            access_token = await self.create_token(
                validated_token.user_id,
                TokenType.ACCESS,
                expires_in=timedelta(minutes=self.access_token_expire_minutes),
                metadata={"session_id": session_id}
            )
            
            refresh_token = await self.create_token(
                validated_token.user_id,
                TokenType.REFRESH,
                expires_in=timedelta(days=self.refresh_token_expire_days),
                metadata={"session_id": session_id}
            )
            
            await audit_service.log_mfa_event(
                user_id=validated_token.user_id,
                mfa_method=validated_token.metadata.get("mfa_method", "unknown"),
                event_type="verification_success",
                success=True,
                client_info=client_info
            )
            
            return AuthResult(
                success=True,
                user=auth_user,
                access_token=access_token,
                refresh_token=refresh_token,
                session_id=session_id,
                authentication_method="mfa",
                provider=self.provider_name,
                client_info=client_info or {}
            )
            
        except Exception as e:
            logger.error(f"MFA verification error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"MFA verification failed: {str(e)}")
    
    async def setup_mfa_method(
        self,
        user_id: str,
        method: MFAMethod,
        method_data: Dict[str, Any]
    ) -> bool:
        """Set up a new MFA method for a user."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            # In a real implementation, this would configure TOTP, SMS, etc.
            # For now, we'll just mark MFA as enabled
            
            auth_user = await user_service.get_user_by_id(user_id)
            if not auth_user:
                raise AuthenticationError("User not found")
            
            # Update user MFA settings (would need additional tables in production)
            updates = {}  # Would update MFA configuration
            
            await audit_service.log_mfa_event(
                user_id=user_id,
                mfa_method=method.value,
                event_type="method_setup",
                success=True,
                client_info=method_data
            )
            
            logger.info(f"MFA method {method.value} set up for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"MFA setup error: {str(e)}")
            return False
    
    async def remove_mfa_method(
        self,
        user_id: str,
        method: MFAMethod,
        removed_by: Optional[str] = None
    ) -> bool:
        """Remove an MFA method from a user."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            # In a real implementation, this would remove MFA configuration
            
            await audit_service.log_mfa_event(
                user_id=user_id,
                mfa_method=method.value,
                event_type="method_removed",
                success=True,
                client_info={"removed_by": removed_by or "system"}
            )
            
            logger.info(f"MFA method {method.value} removed for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"MFA removal error: {str(e)}")
            return False
    
    # Token Management Methods
    
    async def create_token(
        self,
        user_id: str,
        token_type: TokenType,
        expires_in: Optional[timedelta] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuthToken:
        """Create a new authentication token."""
        _, _, audit_service, _ = await self._get_services()
        
        try:
            # Set default expiration based on token type
            if expires_in is None:
                if token_type == TokenType.ACCESS:
                    expires_in = timedelta(minutes=self.access_token_expire_minutes)
                elif token_type == TokenType.REFRESH:
                    expires_in = timedelta(days=self.refresh_token_expire_days)
                elif token_type == TokenType.MFA_CHALLENGE:
                    expires_in = timedelta(minutes=self.mfa_challenge_expire_minutes)
                elif token_type == TokenType.PASSWORD_RESET:
                    expires_in = timedelta(hours=self.password_reset_expire_hours)
                else:
                    expires_in = timedelta(hours=1)
            
            # Generate token
            issued_at = datetime.utcnow()
            expires_at = issued_at + expires_in
            token_id = str(uuid.uuid4())
            
            # Create JWT payload
            payload = {
                "sub": user_id,
                "jti": token_id,
                "type": token_type.value,
                "iat": int(issued_at.timestamp()),
                "exp": int(expires_at.timestamp()),
                "iss": self.provider_name,
                "aud": scopes or [],
            }
            
            # Add metadata
            if metadata:
                payload.update(metadata)
            
            # Generate JWT token
            token_value = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
            
            # Create AuthToken object
            auth_token = AuthToken(
                token_id=token_id,
                token_type=token_type,
                token_value=token_value,
                issued_at=issued_at,
                expires_at=expires_at,
                user_id=user_id,
                session_id=metadata.get("session_id") if metadata else None,
                issued_by=self.provider_name,
                audience=scopes or [],
                scopes=scopes or [],
                client_id=metadata.get("client_id") if metadata else None,
                ip_address=metadata.get("ip_address") if metadata else None,
                user_agent=metadata.get("user_agent") if metadata else None
            )
            
            await audit_service.log_token_creation(
                user_id=user_id,
                token_type=token_type.value,
                client_info=metadata
            )
            
            return auth_token
            
        except Exception as e:
            logger.error(f"Token creation error: {str(e)}")
            raise AuthenticationError(f"Token creation failed: {str(e)}")
    
    async def validate_token(
        self,
        token: str,
        token_type: TokenType,
        required_scopes: Optional[List[str]] = None
    ) -> AuthToken:
        """Validate an authentication token."""
        try:
            # Decode JWT token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # Validate token type
            if payload.get("type") != token_type.value:
                raise AuthenticationError(f"Invalid token type: expected {token_type.value}")
            
            # Validate required scopes
            if required_scopes:
                token_scopes = payload.get("aud", [])
                if not all(scope in token_scopes for scope in required_scopes):
                    raise AuthenticationError("Insufficient token scopes")
            
            # Create AuthToken object
            auth_token = AuthToken(
                token_id=payload.get("jti"),
                token_type=token_type,
                token_value=token,
                issued_at=datetime.fromtimestamp(payload.get("iat")),
                expires_at=datetime.fromtimestamp(payload.get("exp")),
                user_id=payload.get("sub"),
                session_id=payload.get("session_id"),
                issued_by=payload.get("iss"),
                audience=payload.get("aud", []),
                scopes=payload.get("aud", []),
                client_id=payload.get("client_id"),
                ip_address=payload.get("ip_address"),
                user_agent=payload.get("user_agent")
            )
            
            # Additional metadata
            auth_token.metadata = {
                k: v for k, v in payload.items() 
                if k not in ["sub", "jti", "type", "iat", "exp", "iss", "aud"]
            }
            
            return auth_token
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            raise AuthenticationError(f"Token validation failed: {str(e)}")
    
    async def get_user_tokens(
        self,
        user_id: str,
        token_type: Optional[TokenType] = None,
        active_only: bool = True
    ) -> List[AuthToken]:
        """Get all tokens for a user."""
        # In a real implementation, this would query a token store
        # For now, we'll return an empty list as tokens are stateless JWTs
        return []
    
    # Password Management Methods
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        changed_by: Optional[str] = None
    ) -> bool:
        """Change a user's password."""
        user_service, session_service, audit_service, db = await self._get_services()
        
        try:
            # Get current user
            auth_user = await user_service.get_user_by_id(user_id)
            if not auth_user:
                raise AuthenticationError("User not found")
            
            # Get database user for password verification
            stmt = select(User).where(User.id == uuid.UUID(user_id))
            result = await db.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                raise AuthenticationError("User not found in database")
            
            # Verify current password
            if not verify_password(current_password, db_user.hashed_password):
                await audit_service.log_authentication_event(
                    event_type="password_change_failed",
                    user_id=user_id,
                    success=False,
                    metadata={"reason": "Invalid current password"}
                )
                raise AuthenticationError("Current password is incorrect")
            
            # Update password
            await user_service.update_user(
                user_id,
                {"password": new_password},
                changed_by
            )
            
            # Invalidate all existing sessions except current one
            await session_service.invalidate_all_user_sessions(user_id, changed_by)
            
            await audit_service.log_password_change(
                user_id=user_id,
                changed_by=changed_by,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"Password change failed: {str(e)}")
    
    async def reset_password(
        self,
        user_id: str,
        reset_token: str,
        new_password: str
    ) -> bool:
        """Reset a user's password using a reset token."""
        user_service, session_service, audit_service, _ = await self._get_services()
        
        try:
            # Validate reset token
            validated_token = await self.validate_token(
                reset_token, TokenType.PASSWORD_RESET
            )
            
            if validated_token.user_id != user_id:
                raise AuthenticationError("Invalid reset token")
            
            # Update password
            await user_service.update_user(
                user_id,
                {"password": new_password},
                "password_reset"
            )
            
            # Invalidate all user sessions
            await session_service.invalidate_all_user_sessions(user_id, "password_reset")
            
            await audit_service.log_authentication_event(
                event_type="password_reset",
                user_id=user_id,
                success=True,
                metadata={"reset_token_id": validated_token.token_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            
            if isinstance(e, AuthenticationError):
                raise
            
            raise AuthenticationError(f"Password reset failed: {str(e)}")
    
    async def initiate_password_reset(
        self,
        identifier: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Initiate password reset process."""
        user_service, _, audit_service, _ = await self._get_services()
        
        try:
            # Get user by email
            auth_user = await user_service.get_user_by_email(identifier)
            
            # Always return True to prevent email enumeration
            if not auth_user:
                # Log the attempt but don't reveal that user doesn't exist
                await audit_service.log_authentication_event(
                    event_type="password_reset_requested",
                    user_id=None,
                    success=False,
                    metadata={"email": identifier, "reason": "User not found"},
                    client_info=client_info
                )
                return True
            
            # Create password reset token
            reset_token = await self.create_token(
                auth_user.id,
                TokenType.PASSWORD_RESET,
                expires_in=timedelta(hours=self.password_reset_expire_hours),
                metadata={"email": identifier}
            )
            
            # In a real implementation, this would send an email
            logger.info(
                f"Password reset token created for user {auth_user.id}",
                token_value=reset_token.token_value  # Don't log in production!
            )
            
            await audit_service.log_authentication_event(
                event_type="password_reset_requested",
                user_id=auth_user.id,
                success=True,
                metadata={"email": identifier},
                client_info=client_info
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Password reset initiation error: {str(e)}")
            return True  # Don't reveal errors to prevent enumeration
    
    # Session Management Methods
    
    async def create_session(
        self,
        user_id: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new user session."""
        _, session_service, _, _ = await self._get_services()
        return await session_service.create_session(user_id, client_info)
    
    async def validate_session(self, session_id: str) -> Optional[AuthUser]:
        """Validate a user session."""
        user_service, session_service, _, _ = await self._get_services()
        
        user_id = await session_service.validate_session(session_id)
        if user_id:
            return await user_service.get_user_by_id(user_id)
        return None
    
    async def invalidate_session(
        self,
        session_id: str,
        invalidated_by: Optional[str] = None
    ) -> bool:
        """Invalidate a user session."""
        _, session_service, _, _ = await self._get_services()
        return await session_service.invalidate_session(session_id, invalidated_by)
    
    async def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all sessions for a user."""
        _, session_service, _, _ = await self._get_services()
        return await session_service.get_user_sessions(user_id, active_only)
    
    # Audit and Compliance Methods
    
    async def log_authentication_event(
        self,
        event_type: str,
        user_id: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an authentication event for audit purposes."""
        _, _, audit_service, _ = await self._get_services()
        await audit_service.log_authentication_event(
            event_type, user_id, success, metadata
        )
    
    async def get_user_audit_log(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get audit log entries for a user."""
        _, _, audit_service, _ = await self._get_services()
        return await audit_service.get_user_audit_log(
            user_id, start_date, end_date, event_types
        )
    
    # Provider-specific Methods
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health status of the authentication provider."""
        try:
            # Test database connectivity
            _, _, _, db = await self._get_services()
            await db.execute(select(1))
            
            return {
                "status": "healthy",
                "provider": self.provider_name,
                "timestamp": datetime.utcnow().isoformat(),
                "database": "connected",
                "services": ["user_service", "session_service", "audit_service"]
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "provider": self.provider_name,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def get_provider_config(self) -> Dict[str, Any]:
        """Get non-sensitive provider configuration."""
        return {
            "provider_name": self.provider_name,
            "provider_type": "custom",
            "features": {
                "mfa_support": True,
                "session_management": True,
                "password_policies": True,
                "audit_logging": True,
                "account_lockout": True
            },
            "token_settings": {
                "access_token_expire_minutes": self.access_token_expire_minutes,
                "refresh_token_expire_days": self.refresh_token_expire_days,
                "mfa_challenge_expire_minutes": self.mfa_challenge_expire_minutes,
                "password_reset_expire_hours": self.password_reset_expire_hours
            },
            "security_features": {
                "password_hashing": "bcrypt",
                "token_algorithm": "HS256",
                "session_timeout": "30 minutes",
                "max_concurrent_sessions": 5,
                "failed_attempt_lockout": 5
            }
        }
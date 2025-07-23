"""
User service for managing user accounts with HIPAA compliance.

This service handles user creation, updates, validation, and password management
with enhanced security features for healthcare applications.
"""

import uuid
import secrets
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import structlog

from ...models.user import User
from ...utils.security import get_password_hash, verify_password
from ..models import AuthUser, UserRole, MFAMethod

logger = structlog.get_logger()


class PasswordPolicy:
    """Password policy configuration for HIPAA compliance."""
    
    MIN_LENGTH = 12
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    MAX_REUSE_COUNT = 12  # Don't reuse last 12 passwords
    EXPIRY_DAYS = 90
    WARNING_DAYS = 7


class UserService:
    """Service for managing user accounts."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize user service.
        
        Args:
            db_session: Database session for user operations
        """
        self.db = db_session
        self.password_policy = PasswordPolicy()
    
    async def get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID to retrieve
            
        Returns:
            AuthUser object if found, None otherwise
        """
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(User.id == user_uuid)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                return self._convert_to_auth_user(user)
            
            return None
            
        except ValueError as e:
            logger.error(f"Invalid user ID format: {user_id}", error=str(e))
            return None
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user: {user_id}", error=str(e))
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[AuthUser]:
        """
        Get user by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            AuthUser object if found, None otherwise
        """
        try:
            stmt = select(User).where(User.email == email.lower())
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                return self._convert_to_auth_user(user)
            
            return None
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user by email: {email}", error=str(e))
            return None
    
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
            Created AuthUser object
            
        Raises:
            ValueError: If user data is invalid
            RuntimeError: If user creation fails
        """
        try:
            # Validate required fields
            if not user_data.get("email"):
                raise ValueError("Email is required")
            if not user_data.get("password"):
                raise ValueError("Password is required")
            
            # Validate email format and uniqueness
            email = user_data["email"].lower().strip()
            if not self._validate_email_format(email):
                raise ValueError("Invalid email format")
            
            existing_user = await self.get_user_by_email(email)
            if existing_user:
                raise ValueError("Email already exists")
            
            # Validate password policy
            password = user_data["password"]
            password_errors = self.validate_password(password)
            if password_errors:
                raise ValueError(f"Password policy violations: {', '.join(password_errors)}")
            
            # Hash password
            hashed_password = get_password_hash(password)
            
            # Create user object
            user = User(
                id=uuid.uuid4(),
                email=email,
                hashed_password=hashed_password,
                is_active=user_data.get("is_active", True),
                is_superuser=user_data.get("is_superuser", False),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
                role=user_data.get("role", "user"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by=uuid.UUID(created_by) if created_by else None,
                password_changed_at=datetime.utcnow(),
                login_attempts="0"
            )
            
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            
            auth_user = self._convert_to_auth_user(user)
            
            logger.info(
                "User created successfully",
                user_id=str(user.id),
                email=email,
                created_by=created_by or "system"
            )
            
            return auth_user
            
        except ValueError:
            raise
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating user: {email}", error=str(e))
            raise ValueError("User creation failed: email may already exist")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating user: {email}", error=str(e))
            raise RuntimeError(f"User creation failed: {str(e)}")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating user: {email}", error=str(e))
            raise RuntimeError(f"User creation failed: {str(e)}")
    
    async def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> AuthUser:
        """
        Update user account information.
        
        Args:
            user_id: User ID to update
            updates: Fields to update
            updated_by: User or system that made the update
            
        Returns:
            Updated AuthUser object
            
        Raises:
            ValueError: If user not found or update data invalid
            RuntimeError: If update fails
        """
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(User.id == user_uuid)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Apply updates with validation
            for field, value in updates.items():
                if field == "email":
                    # Validate email format and uniqueness
                    email = value.lower().strip()
                    if not self._validate_email_format(email):
                        raise ValueError("Invalid email format")
                    
                    # Check uniqueness (excluding current user)
                    existing_stmt = select(User).where(
                        and_(User.email == email, User.id != user_uuid)
                    )
                    existing_result = await self.db.execute(existing_stmt)
                    if existing_result.scalar_one_or_none():
                        raise ValueError("Email already exists")
                    
                    user.email = email
                
                elif field == "password":
                    # Validate password policy
                    password_errors = self.validate_password(value)
                    if password_errors:
                        raise ValueError(f"Password policy violations: {', '.join(password_errors)}")
                    
                    # Check password history (simplified - would need password history table)
                    if verify_password(value, user.hashed_password):
                        raise ValueError("Cannot reuse current password")
                    
                    user.hashed_password = get_password_hash(value)
                    user.password_changed_at = datetime.utcnow()
                    user.login_attempts = "0"  # Reset failed attempts on password change
                
                elif field in ["first_name", "last_name", "role"]:
                    setattr(user, field, value)
                
                elif field in ["is_active", "is_superuser"]:
                    setattr(user, field, bool(value))
                
                elif field == "account_locked_until":
                    if value is None:
                        user.account_locked_until = None
                    else:
                        user.account_locked_until = value
                
                # Add other updatable fields as needed
            
            # Update metadata
            user.updated_at = datetime.utcnow()
            user.updated_by = uuid.UUID(updated_by) if updated_by else None
            
            await self.db.commit()
            await self.db.refresh(user)
            
            auth_user = self._convert_to_auth_user(user)
            
            logger.info(
                "User updated successfully",
                user_id=user_id,
                updated_fields=list(updates.keys()),
                updated_by=updated_by or "system"
            )
            
            return auth_user
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error updating user: {user_id}", error=str(e))
            raise RuntimeError(f"User update failed: {str(e)}")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error updating user: {user_id}", error=str(e))
            raise RuntimeError(f"User update failed: {str(e)}")
    
    async def deactivate_user(
        self,
        user_id: str,
        deactivated_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user_id: User ID to deactivate
            deactivated_by: User or system that deactivated the account
            reason: Reason for deactivation (for audit)
            
        Returns:
            True if user was successfully deactivated
        """
        try:
            updates = {
                "is_active": False,
                "account_locked_until": None  # Clear any existing lock
            }
            
            await self.update_user(user_id, updates, deactivated_by)
            
            logger.info(
                "User deactivated",
                user_id=user_id,
                reason=reason or "not specified",
                deactivated_by=deactivated_by or "system"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate user: {user_id}", error=str(e))
            return False
    
    async def lock_user_account(
        self,
        user_id: str,
        lock_duration_minutes: int = 30,
        reason: str = "Security policy violation"
    ) -> bool:
        """
        Temporarily lock a user account.
        
        Args:
            user_id: User ID to lock
            lock_duration_minutes: Duration to lock account
            reason: Reason for lock
            
        Returns:
            True if account was successfully locked
        """
        try:
            locked_until = datetime.utcnow() + timedelta(minutes=lock_duration_minutes)
            updates = {"account_locked_until": locked_until}
            
            await self.update_user(user_id, updates, "system")
            
            logger.info(
                "User account locked",
                user_id=user_id,
                locked_until=locked_until.isoformat(),
                duration_minutes=lock_duration_minutes,
                reason=reason
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to lock user account: {user_id}", error=str(e))
            return False
    
    async def unlock_user_account(
        self,
        user_id: str,
        unlocked_by: Optional[str] = None
    ) -> bool:
        """
        Unlock a user account.
        
        Args:
            user_id: User ID to unlock
            unlocked_by: User or system that unlocked the account
            
        Returns:
            True if account was successfully unlocked
        """
        try:
            updates = {
                "account_locked_until": None,
                "login_attempts": "0"  # Reset failed attempts
            }
            
            await self.update_user(user_id, updates, unlocked_by)
            
            logger.info(
                "User account unlocked",
                user_id=user_id,
                unlocked_by=unlocked_by or "system"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock user account: {user_id}", error=str(e))
            return False
    
    async def increment_failed_login_attempts(
        self,
        user_id: str,
        auto_lock_threshold: int = 5
    ) -> Tuple[int, bool]:
        """
        Increment failed login attempts and optionally lock account.
        
        Args:
            user_id: User ID to update
            auto_lock_threshold: Number of attempts before auto-lock
            
        Returns:
            Tuple of (attempt_count, was_locked)
        """
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(User.id == user_uuid)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                return (0, False)
            
            # Increment attempts
            try:
                current_attempts = int(user.login_attempts)
            except (ValueError, TypeError):
                current_attempts = 0
            
            new_attempts = current_attempts + 1
            user.login_attempts = str(new_attempts)
            
            # Auto-lock if threshold reached
            was_locked = False
            if new_attempts >= auto_lock_threshold:
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
                was_locked = True
                
                logger.warning(
                    "User account auto-locked due to failed login attempts",
                    user_id=user_id,
                    attempt_count=new_attempts,
                    threshold=auto_lock_threshold
                )
            
            user.updated_at = datetime.utcnow()
            await self.db.commit()
            
            return (new_attempts, was_locked)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to increment login attempts: {user_id}",
                error=str(e)
            )
            return (0, False)
    
    async def reset_failed_login_attempts(self, user_id: str) -> bool:
        """
        Reset failed login attempts counter.
        
        Args:
            user_id: User ID to reset
            
        Returns:
            True if successfully reset
        """
        try:
            updates = {"login_attempts": "0"}
            await self.update_user(user_id, updates, "system")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset login attempts: {user_id}", error=str(e))
            return False
    
    def validate_password(self, password: str) -> List[str]:
        """
        Validate password against policy.
        
        Args:
            password: Password to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if len(password) < self.password_policy.MIN_LENGTH:
            errors.append(f"Password must be at least {self.password_policy.MIN_LENGTH} characters")
        
        if len(password) > self.password_policy.MAX_LENGTH:
            errors.append(f"Password must be no more than {self.password_policy.MAX_LENGTH} characters")
        
        if self.password_policy.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.password_policy.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.password_policy.REQUIRE_DIGITS and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if (self.password_policy.REQUIRE_SPECIAL_CHARS and 
            not any(c in self.password_policy.SPECIAL_CHARS for c in password)):
            errors.append(f"Password must contain at least one special character: {self.password_policy.SPECIAL_CHARS}")
        
        # Check for common patterns
        if password.lower() in ["password", "123456", "qwerty", "admin"]:
            errors.append("Password is too common")
        
        return errors
    
    async def is_password_expired(self, user_id: str) -> bool:
        """
        Check if user's password has expired.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if password is expired
        """
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(User.id == user_uuid)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.password_changed_at:
                return True  # Force password change if no change date
            
            expiry_date = user.password_changed_at + timedelta(
                days=self.password_policy.EXPIRY_DAYS
            )
            
            return datetime.utcnow() > expiry_date
            
        except Exception as e:
            logger.error(f"Error checking password expiry: {user_id}", error=str(e))
            return True  # Err on the side of caution
    
    async def get_password_expiry_warning(self, user_id: str) -> Optional[int]:
        """
        Get days until password expires (if within warning period).
        
        Args:
            user_id: User ID to check
            
        Returns:
            Days until expiry if within warning period, None otherwise
        """
        try:
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(User.id == user_uuid)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.password_changed_at:
                return 0  # Immediate expiry warning
            
            expiry_date = user.password_changed_at + timedelta(
                days=self.password_policy.EXPIRY_DAYS
            )
            
            days_until_expiry = (expiry_date - datetime.utcnow()).days
            
            if days_until_expiry <= self.password_policy.WARNING_DAYS:
                return max(0, days_until_expiry)
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking password expiry warning: {user_id}", error=str(e))
            return 0  # Show warning on error
    
    def _validate_email_format(self, email: str) -> bool:
        """Validate email format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def _convert_to_auth_user(self, user: User) -> AuthUser:
        """Convert database User to AuthUser model."""
        # Map database role to UserRole enum
        role_mapping = {
            "admin": UserRole.ADMIN,
            "clinician": UserRole.CLINICIAN,
            "nurse": UserRole.NURSE,
            "technician": UserRole.TECHNICIAN,
            "patient": UserRole.PATIENT,
            "audit_user": UserRole.AUDIT_USER,
            "system": UserRole.SYSTEM,
            "user": UserRole.PATIENT  # Default mapping
        }
        
        user_role = role_mapping.get(user.role, UserRole.PATIENT)
        
        # Parse failed login attempts
        try:
            failed_attempts = int(user.login_attempts)
        except (ValueError, TypeError):
            failed_attempts = 0
        
        return AuthUser(
            id=str(user.id),
            email=user.email,
            username=user.email,  # Use email as username
            roles=[user_role],
            permissions=[],  # Would be loaded from separate permissions table
            is_active=user.is_active,
            is_verified=True,  # Assume verified for existing users
            mfa_enabled=False,  # Would be loaded from MFA settings
            mfa_methods=[],
            created_at=user.created_at,
            last_login=user.last_login,
            last_password_change=user.password_changed_at,
            password_expires_at=None,  # Would calculate based on policy
            account_locked_until=user.account_locked_until,
            failed_login_attempts=failed_attempts,
            department=None,  # Would be loaded from profile table
            license_number=None,  # Would be loaded from profile table
            supervisor_id=str(user.created_by) if user.created_by else None,
            metadata={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat()
            }
        )
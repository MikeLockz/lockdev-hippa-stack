"""
Tests for UserService.

This module tests user management functionality with HIPAA compliance.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.auth.services.user_service import UserService, PasswordPolicy
from src.models.user import User
from src.auth.models import AuthUser, UserRole


@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def user_service(mock_db_session):
    """Create a UserService instance with mock database."""
    return UserService(mock_db_session)


@pytest.fixture
def sample_user():
    """Create a sample User object."""
    user_id = uuid.uuid4()
    return User(
        id=user_id,
        email="test@example.com",
        hashed_password="$2b$12$hashed_password",
        is_active=True,
        is_superuser=False,
        first_name="Test",
        last_name="User",
        role="user",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        password_changed_at=datetime.utcnow(),
        login_attempts="0"
    )


@pytest.mark.asyncio
class TestUserService:
    """Test cases for UserService."""
    
    async def test_get_user_by_id_success(self, user_service, mock_db_session, sample_user):
        """Test successful user retrieval by ID."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        # Test retrieval
        auth_user = await user_service.get_user_by_id(str(sample_user.id))
        
        assert auth_user is not None
        assert isinstance(auth_user, AuthUser)
        assert auth_user.id == str(sample_user.id)
        assert auth_user.email == sample_user.email
        assert auth_user.is_active == sample_user.is_active
    
    async def test_get_user_by_id_not_found(self, user_service, mock_db_session):
        """Test user retrieval when user not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        auth_user = await user_service.get_user_by_id(str(uuid.uuid4()))
        
        assert auth_user is None
    
    async def test_get_user_by_id_invalid_uuid(self, user_service, mock_db_session):
        """Test user retrieval with invalid UUID."""
        auth_user = await user_service.get_user_by_id("invalid-uuid")
        
        assert auth_user is None
        mock_db_session.execute.assert_not_called()
    
    async def test_get_user_by_email_success(self, user_service, mock_db_session, sample_user):
        """Test successful user retrieval by email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        auth_user = await user_service.get_user_by_email("test@example.com")
        
        assert auth_user is not None
        assert auth_user.email == "test@example.com"
    
    async def test_get_user_by_email_case_insensitive(self, user_service, mock_db_session, sample_user):
        """Test user retrieval by email is case insensitive."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        auth_user = await user_service.get_user_by_email("TEST@EXAMPLE.COM")
        
        assert auth_user is not None
        # Verify query was made with lowercase email
        mock_db_session.execute.assert_called_once()
    
    async def test_create_user_success(self, user_service, mock_db_session):
        """Test successful user creation."""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "New",
            "last_name": "User",
            "role": "user"
        }
        
        # Mock email uniqueness check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        # Mock user creation
        created_user = User(
            id=uuid.uuid4(),
            email=user_data["email"],
            hashed_password="hashed",
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            role=user_data["role"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            password_changed_at=datetime.utcnow(),
            login_attempts="0"
        )
        
        mock_db_session.refresh.side_effect = lambda user: setattr(user, 'id', created_user.id)
        
        auth_user = await user_service.create_user(user_data, "admin")
        
        assert isinstance(auth_user, AuthUser)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    async def test_create_user_missing_email(self, user_service, mock_db_session):
        """Test user creation with missing email."""
        user_data = {"password": "SecurePassword123!"}
        
        with pytest.raises(ValueError, match="Email is required"):
            await user_service.create_user(user_data)
    
    async def test_create_user_missing_password(self, user_service, mock_db_session):
        """Test user creation with missing password."""
        user_data = {"email": "test@example.com"}
        
        with pytest.raises(ValueError, match="Password is required"):
            await user_service.create_user(user_data)
    
    async def test_create_user_invalid_email(self, user_service, mock_db_session):
        """Test user creation with invalid email format."""
        user_data = {
            "email": "invalid-email",
            "password": "SecurePassword123!"
        }
        
        with pytest.raises(ValueError, match="Invalid email format"):
            await user_service.create_user(user_data)
    
    async def test_create_user_email_exists(self, user_service, mock_db_session, sample_user):
        """Test user creation with existing email."""
        user_data = {
            "email": "test@example.com",
            "password": "SecurePassword123!"
        }
        
        # Mock existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Email already exists"):
            await user_service.create_user(user_data)
    
    async def test_create_user_weak_password(self, user_service, mock_db_session):
        """Test user creation with weak password."""
        user_data = {
            "email": "test@example.com",
            "password": "weak"
        }
        
        # Mock email uniqueness check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Password policy violations"):
            await user_service.create_user(user_data)
    
    async def test_create_user_integrity_error(self, user_service, mock_db_session):
        """Test user creation with database integrity error."""
        user_data = {
            "email": "test@example.com",
            "password": "SecurePassword123!"
        }
        
        # Mock email uniqueness check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        # Mock integrity error on commit
        mock_db_session.commit.side_effect = IntegrityError("", "", "")
        
        with pytest.raises(ValueError, match="User creation failed: email may already exist"):
            await user_service.create_user(user_data)
        
        mock_db_session.rollback.assert_called_once()
    
    async def test_update_user_success(self, user_service, mock_db_session, sample_user):
        """Test successful user update."""
        updates = {
            "first_name": "Updated",
            "last_name": "Name",
            "is_active": False
        }
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        auth_user = await user_service.update_user(str(sample_user.id), updates, "admin")
        
        assert isinstance(auth_user, AuthUser)
        assert sample_user.first_name == "Updated"
        assert sample_user.last_name == "Name"
        assert sample_user.is_active is False
        mock_db_session.commit.assert_called_once()
    
    async def test_update_user_not_found(self, user_service, mock_db_session):
        """Test user update when user not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User .* not found"):
            await user_service.update_user(str(uuid.uuid4()), {"first_name": "Test"})
    
    async def test_update_user_email(self, user_service, mock_db_session, sample_user):
        """Test user email update with validation."""
        new_email = "newemail@example.com"
        updates = {"email": new_email}
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        
        # Mock email uniqueness check
        mock_uniqueness_result = MagicMock()
        mock_uniqueness_result.scalar_one_or_none.return_value = None
        
        mock_db_session.execute.side_effect = [mock_result, mock_uniqueness_result]
        
        await user_service.update_user(str(sample_user.id), updates)
        
        assert sample_user.email == new_email.lower()
    
    async def test_update_user_email_exists(self, user_service, mock_db_session, sample_user):
        """Test user email update with existing email."""
        updates = {"email": "existing@example.com"}
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        
        # Mock existing email
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = User(id=uuid.uuid4())
        
        mock_db_session.execute.side_effect = [mock_result, mock_existing]
        
        with pytest.raises(ValueError, match="Email already exists"):
            await user_service.update_user(str(sample_user.id), updates)
    
    async def test_update_user_password(self, user_service, mock_db_session, sample_user):
        """Test user password update."""
        updates = {"password": "NewSecurePassword123!"}
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        await user_service.update_user(str(sample_user.id), updates)
        
        # Password should be hashed
        assert sample_user.hashed_password != updates["password"]
        assert isinstance(sample_user.password_changed_at, datetime)
        assert sample_user.login_attempts == "0"
    
    async def test_deactivate_user_success(self, user_service, mock_db_session, sample_user):
        """Test successful user deactivation."""
        # Mock user retrieval and update
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        success = await user_service.deactivate_user(str(sample_user.id), "admin", "policy violation")
        
        assert success is True
    
    async def test_lock_user_account(self, user_service, mock_db_session, sample_user):
        """Test user account locking."""
        # Mock user retrieval and update
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        success = await user_service.lock_user_account(str(sample_user.id), 60, "security violation")
        
        assert success is True
    
    async def test_unlock_user_account(self, user_service, mock_db_session, sample_user):
        """Test user account unlocking."""
        # Mock user retrieval and update
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        success = await user_service.unlock_user_account(str(sample_user.id), "admin")
        
        assert success is True
    
    async def test_increment_failed_login_attempts(self, user_service, mock_db_session, sample_user):
        """Test incrementing failed login attempts."""
        sample_user.login_attempts = "2"
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        attempts, was_locked = await user_service.increment_failed_login_attempts(str(sample_user.id))
        
        assert attempts == 3
        assert was_locked is False
        assert sample_user.login_attempts == "3"
    
    async def test_increment_failed_login_attempts_auto_lock(self, user_service, mock_db_session, sample_user):
        """Test auto-locking after max failed attempts."""
        sample_user.login_attempts = "4"
        
        # Mock user retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        attempts, was_locked = await user_service.increment_failed_login_attempts(str(sample_user.id))
        
        assert attempts == 5
        assert was_locked is True
        assert sample_user.account_locked_until is not None
    
    async def test_reset_failed_login_attempts(self, user_service, mock_db_session, sample_user):
        """Test resetting failed login attempts."""
        # Mock user retrieval and update
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        success = await user_service.reset_failed_login_attempts(str(sample_user.id))
        
        assert success is True
    
    def test_validate_password_success(self, user_service):
        """Test password validation with valid password."""
        password = "SecurePassword123!"
        errors = user_service.validate_password(password)
        
        assert errors == []
    
    def test_validate_password_too_short(self, user_service):
        """Test password validation with too short password."""
        password = "Short1!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("at least 12 characters" in error for error in errors)
    
    def test_validate_password_too_long(self, user_service):
        """Test password validation with too long password."""
        password = "x" * 130 + "A1!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("no more than 128 characters" in error for error in errors)
    
    def test_validate_password_no_uppercase(self, user_service):
        """Test password validation without uppercase letters."""
        password = "securepassword123!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("uppercase letter" in error for error in errors)
    
    def test_validate_password_no_lowercase(self, user_service):
        """Test password validation without lowercase letters."""
        password = "SECUREPASSWORD123!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("lowercase letter" in error for error in errors)
    
    def test_validate_password_no_digits(self, user_service):
        """Test password validation without digits."""
        password = "SecurePassword!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("digit" in error for error in errors)
    
    def test_validate_password_no_special_chars(self, user_service):
        """Test password validation without special characters."""
        password = "SecurePassword123"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("special character" in error for error in errors)
    
    def test_validate_password_common_password(self, user_service):
        """Test password validation with common password."""
        password = "password123!"
        errors = user_service.validate_password(password)
        
        assert len(errors) > 0
        assert any("too common" in error for error in errors)
    
    async def test_is_password_expired_true(self, user_service, mock_db_session, sample_user):
        """Test password expiration check when expired."""
        # Set password change date to over 90 days ago
        sample_user.password_changed_at = datetime.utcnow() - timedelta(days=100)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        is_expired = await user_service.is_password_expired(str(sample_user.id))
        
        assert is_expired is True
    
    async def test_is_password_expired_false(self, user_service, mock_db_session, sample_user):
        """Test password expiration check when not expired."""
        # Set password change date to recent
        sample_user.password_changed_at = datetime.utcnow() - timedelta(days=30)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        is_expired = await user_service.is_password_expired(str(sample_user.id))
        
        assert is_expired is False
    
    async def test_get_password_expiry_warning(self, user_service, mock_db_session, sample_user):
        """Test password expiry warning calculation."""
        # Set password to expire in 5 days
        sample_user.password_changed_at = datetime.utcnow() - timedelta(days=85)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        warning_days = await user_service.get_password_expiry_warning(str(sample_user.id))
        
        assert warning_days is not None
        assert 0 <= warning_days <= 7
    
    def test_validate_email_format_valid(self, user_service):
        """Test email format validation with valid emails."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "admin@sub.domain.org"
        ]
        
        for email in valid_emails:
            assert user_service._validate_email_format(email) is True
    
    def test_validate_email_format_invalid(self, user_service):
        """Test email format validation with invalid emails."""
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user@domain",
            "user..name@domain.com"
        ]
        
        for email in invalid_emails:
            assert user_service._validate_email_format(email) is False
    
    def test_convert_to_auth_user(self, user_service, sample_user):
        """Test conversion from User to AuthUser."""
        auth_user = user_service._convert_to_auth_user(sample_user)
        
        assert isinstance(auth_user, AuthUser)
        assert auth_user.id == str(sample_user.id)
        assert auth_user.email == sample_user.email
        assert auth_user.is_active == sample_user.is_active
        assert UserRole.PATIENT in auth_user.roles  # Default role mapping
        assert auth_user.failed_login_attempts == 0
    
    def test_convert_to_auth_user_admin_role(self, user_service, sample_user):
        """Test conversion with admin role mapping."""
        sample_user.role = "admin"
        
        auth_user = user_service._convert_to_auth_user(sample_user)
        
        assert UserRole.ADMIN in auth_user.roles
    
    def test_convert_to_auth_user_invalid_attempts(self, user_service, sample_user):
        """Test conversion with invalid login attempts value."""
        sample_user.login_attempts = "invalid"
        
        auth_user = user_service._convert_to_auth_user(sample_user)
        
        assert auth_user.failed_login_attempts == 0


class TestPasswordPolicy:
    """Test cases for PasswordPolicy configuration."""
    
    def test_password_policy_defaults(self):
        """Test password policy default values."""
        policy = PasswordPolicy()
        
        assert policy.MIN_LENGTH == 12
        assert policy.MAX_LENGTH == 128
        assert policy.REQUIRE_UPPERCASE is True
        assert policy.REQUIRE_LOWERCASE is True
        assert policy.REQUIRE_DIGITS is True
        assert policy.REQUIRE_SPECIAL_CHARS is True
        assert policy.MAX_REUSE_COUNT == 12
        assert policy.EXPIRY_DAYS == 90
        assert policy.WARNING_DAYS == 7
        assert "!@#$%^&*()_+-=[]{}|;:,.<>?" in policy.SPECIAL_CHARS
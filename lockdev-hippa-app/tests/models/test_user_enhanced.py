"""
Tests for enhanced User model with HIPAA compliance fields.

Tests cover:
- HIPAA compliance field validation
- PHI access management
- Password policy enforcement fields
- Professional license validation
- MFA and security settings
- Compliance status checking methods
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.user import User


class TestUserHIPAAFields:
    """Test HIPAA-specific user fields and methods."""
    
    @pytest.fixture
    def base_user_data(self):
        """Base user data for testing."""
        return {
            "id": uuid4(),
            "email": "test@hospital.com",
            "hashed_password": "hashed_password_123",
            "is_active": True,
            "role": "PHYSICIAN",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "password_changed_at": datetime.utcnow()
        }
    
    def test_user_with_phi_access(self, base_user_data):
        """Test user with PHI access granted."""
        phi_expiry = datetime.utcnow() + timedelta(hours=8)
        supervisor_id = uuid4()
        
        user_data = {
            **base_user_data,
            "phi_access_granted": True,
            "phi_access_reason": "Patient treatment",
            "phi_access_expiry": phi_expiry,
            "phi_access_supervisor": supervisor_id
        }
        
        user = User(**user_data)
        
        assert user.phi_access_granted is True
        assert user.phi_access_reason == "Patient treatment"
        assert user.phi_access_expiry == phi_expiry
        assert user.phi_access_supervisor == supervisor_id
    
    def test_user_password_history(self, base_user_data):
        """Test password history tracking."""
        password_history = [
            "old_hash_1",
            "old_hash_2", 
            "old_hash_3"
        ]
        
        user_data = {
            **base_user_data,
            "password_history": password_history,
            "password_expires_at": datetime.utcnow() + timedelta(days=90),
            "password_must_change": False
        }
        
        user = User(**user_data)
        
        assert user.password_history == password_history
        assert len(user.password_history) == 3
        assert user.password_must_change is False
        assert user.password_expires_at is not None
    
    def test_user_professional_fields(self, base_user_data):
        """Test professional healthcare worker fields."""
        license_expiry = datetime.utcnow() + timedelta(days=365)
        supervisor_id = uuid4()
        
        user_data = {
            **base_user_data,
            "license_number": "MD123456",
            "license_expiry": license_expiry,
            "department": "Emergency Medicine",
            "supervisor_id": supervisor_id
        }
        
        user = User(**user_data)
        
        assert user.license_number == "MD123456"
        assert user.license_expiry == license_expiry
        assert user.department == "Emergency Medicine"
        assert user.supervisor_id == supervisor_id
    
    def test_user_access_control_fields(self, base_user_data):
        """Test access control restriction fields."""
        workstation_restrictions = ["WS001", "WS002"]
        ip_restrictions = ["192.168.1.100", "10.0.0.50"]
        time_access = {
            "start_time": "08:00",
            "end_time": "18:00",
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
        }
        
        user_data = {
            **base_user_data,
            "workstation_restrictions": workstation_restrictions,
            "ip_address_restrictions": ip_restrictions,
            "time_based_access": time_access
        }
        
        user = User(**user_data)
        
        assert user.workstation_restrictions == workstation_restrictions
        assert user.ip_address_restrictions == ip_restrictions
        assert user.time_based_access == time_access
    
    def test_user_mfa_fields(self, base_user_data):
        """Test multi-factor authentication fields."""
        mfa_secret = "JBSWY3DPEHPK3PXP"
        backup_codes = ["123456", "789012", "345678"]
        mfa_last_used = datetime.utcnow() - timedelta(hours=2)
        
        user_data = {
            **base_user_data,
            "mfa_enabled": True,
            "mfa_secret": mfa_secret,
            "mfa_backup_codes": backup_codes,
            "mfa_last_used": mfa_last_used
        }
        
        user = User(**user_data)
        
        assert user.mfa_enabled is True
        assert user.mfa_secret == mfa_secret
        assert user.mfa_backup_codes == backup_codes
        assert user.mfa_last_used == mfa_last_used
    
    def test_user_session_management_fields(self, base_user_data):
        """Test session management configuration fields."""
        user_data = {
            **base_user_data,
            "max_concurrent_sessions": 3,
            "session_timeout_minutes": 240  # 4 hours
        }
        
        user = User(**user_data)
        
        assert user.max_concurrent_sessions == 3
        assert user.session_timeout_minutes == 240
    
    def test_user_compliance_tracking_fields(self, base_user_data):
        """Test compliance tracking fields."""
        terms_accepted = datetime.utcnow() - timedelta(days=30)
        privacy_accepted = datetime.utcnow() - timedelta(days=25)
        hipaa_training = datetime.utcnow() - timedelta(days=180)
        security_review = datetime.utcnow() - timedelta(days=90)
        
        user_data = {
            **base_user_data,
            "terms_accepted_at": terms_accepted,
            "privacy_policy_accepted_at": privacy_accepted,
            "hipaa_training_completed_at": hipaa_training,
            "last_security_review": security_review
        }
        
        user = User(**user_data)
        
        assert user.terms_accepted_at == terms_accepted
        assert user.privacy_policy_accepted_at == privacy_accepted
        assert user.hipaa_training_completed_at == hipaa_training
        assert user.last_security_review == security_review


class TestUserComplianceMethods:
    """Test User model compliance checking methods."""
    
    @pytest.fixture
    def user_with_valid_phi_access(self):
        """User with valid PHI access."""
        return User(
            id=uuid4(),
            email="physician@hospital.com",
            hashed_password="hash",
            phi_access_granted=True,
            phi_access_expiry=datetime.utcnow() + timedelta(hours=4),
            role="PHYSICIAN"
        )
    
    @pytest.fixture
    def user_with_expired_phi_access(self):
        """User with expired PHI access."""
        return User(
            id=uuid4(),
            email="expired@hospital.com",
            hashed_password="hash",
            phi_access_granted=True,
            phi_access_expiry=datetime.utcnow() - timedelta(hours=1),
            role="PHYSICIAN"
        )
    
    @pytest.fixture
    def user_without_phi_access(self):
        """User without PHI access."""
        return User(
            id=uuid4(),
            email="noaccess@hospital.com",
            hashed_password="hash",
            phi_access_granted=False,
            phi_access_expiry=None,
            role="ADMIN"
        )
    
    @pytest.fixture
    def user_with_valid_license(self):
        """User with valid professional license."""
        return User(
            id=uuid4(),
            email="licensed@hospital.com",
            hashed_password="hash",
            license_number="MD123456",
            license_expiry=datetime.utcnow() + timedelta(days=180),
            role="PHYSICIAN"
        )
    
    @pytest.fixture
    def user_with_expired_license(self):
        """User with expired professional license."""
        return User(
            id=uuid4(),
            email="expiredlic@hospital.com",
            hashed_password="hash",
            license_number="MD789012",
            license_expiry=datetime.utcnow() - timedelta(days=30),
            role="PHYSICIAN"
        )
    
    @pytest.fixture
    def user_with_recent_hipaa_training(self):
        """User with recent HIPAA training."""
        return User(
            id=uuid4(),
            email="trained@hospital.com",
            hashed_password="hash",
            hipaa_training_completed_at=datetime.utcnow() - timedelta(days=30),
            role="NURSE"
        )
    
    @pytest.fixture
    def user_with_expired_hipaa_training(self):
        """User with expired HIPAA training."""
        return User(
            id=uuid4(),
            email="oldtraining@hospital.com",
            hashed_password="hash",
            hipaa_training_completed_at=datetime.utcnow() - timedelta(days=400),  # Over 1 year
            role="NURSE"
        )
    
    @pytest.fixture
    def user_without_hipaa_training(self):
        """User without HIPAA training."""
        return User(
            id=uuid4(),
            email="notraining@hospital.com",
            hashed_password="hash",
            hipaa_training_completed_at=None,
            role="NURSE"
        )

    # PHI access validation tests
    
    def test_is_phi_access_valid_granted_and_not_expired(self, user_with_valid_phi_access):
        """Test PHI access validation for valid access."""
        assert user_with_valid_phi_access.is_phi_access_valid() is True
    
    def test_is_phi_access_valid_not_granted(self, user_without_phi_access):
        """Test PHI access validation when not granted."""
        assert user_without_phi_access.is_phi_access_valid() is False
    
    def test_is_phi_access_valid_expired(self, user_with_expired_phi_access):
        """Test PHI access validation for expired access."""
        assert user_with_expired_phi_access.is_phi_access_valid() is False
    
    def test_is_phi_access_valid_granted_no_expiry(self):
        """Test PHI access validation when granted but no expiry set."""
        user = User(
            id=uuid4(),
            email="noexpiry@hospital.com",
            hashed_password="hash",
            phi_access_granted=True,
            phi_access_expiry=None,
            role="PHYSICIAN"
        )
        
        assert user.is_phi_access_valid() is True

    # Password expiration tests
    
    def test_is_password_expired_not_set(self):
        """Test password expiration when no expiry date set."""
        user = User(
            id=uuid4(),
            email="noexpiry@hospital.com",
            hashed_password="hash",
            password_expires_at=None
        )
        
        assert user.is_password_expired() is False
    
    def test_is_password_expired_future_date(self):
        """Test password expiration with future expiry date."""
        user = User(
            id=uuid4(),
            email="future@hospital.com",
            hashed_password="hash",
            password_expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        assert user.is_password_expired() is False
    
    def test_is_password_expired_past_date(self):
        """Test password expiration with past expiry date."""
        user = User(
            id=uuid4(),
            email="expired@hospital.com",
            hashed_password="hash",
            password_expires_at=datetime.utcnow() - timedelta(days=1)
        )
        
        assert user.is_password_expired() is True

    # License validation tests
    
    def test_is_license_valid_no_license_required(self):
        """Test license validation when no license is required."""
        user = User(
            id=uuid4(),
            email="admin@hospital.com",
            hashed_password="hash",
            license_number=None,
            license_expiry=None,
            role="ADMIN"
        )
        
        assert user.is_license_valid() is True
    
    def test_is_license_valid_with_valid_license(self, user_with_valid_license):
        """Test license validation with valid license."""
        assert user_with_valid_license.is_license_valid() is True
    
    def test_is_license_valid_with_expired_license(self, user_with_expired_license):
        """Test license validation with expired license."""
        assert user_with_expired_license.is_license_valid() is False

    # HIPAA training validation tests
    
    def test_needs_hipaa_training_no_training(self, user_without_hipaa_training):
        """Test HIPAA training requirement when never completed."""
        assert user_without_hipaa_training.needs_hipaa_training() is True
    
    def test_needs_hipaa_training_recent_training(self, user_with_recent_hipaa_training):
        """Test HIPAA training requirement with recent training."""
        assert user_with_recent_hipaa_training.needs_hipaa_training() is False
    
    def test_needs_hipaa_training_expired_training(self, user_with_expired_hipaa_training):
        """Test HIPAA training requirement with expired training."""
        assert user_with_expired_hipaa_training.needs_hipaa_training() is True
    
    def test_needs_hipaa_training_exactly_one_year(self):
        """Test HIPAA training requirement exactly one year after completion."""
        # Training completed exactly 365 days ago
        training_date = datetime.utcnow() - timedelta(days=365)
        
        user = User(
            id=uuid4(),
            email="oneyear@hospital.com",
            hashed_password="hash",
            hipaa_training_completed_at=training_date,
            role="NURSE"
        )
        
        # Should still be valid (expires after 1 year + 1 day)
        assert user.needs_hipaa_training() is False
    
    def test_needs_hipaa_training_over_one_year(self):
        """Test HIPAA training requirement over one year after completion."""
        # Training completed over 1 year ago
        training_date = datetime.utcnow() - timedelta(days=366)
        
        user = User(
            id=uuid4(),
            email="overyear@hospital.com",
            hashed_password="hash",
            hipaa_training_completed_at=training_date,
            role="NURSE"
        )
        
        assert user.needs_hipaa_training() is True


class TestUserDictMethods:
    """Test User to_dict methods with sensitive data handling."""
    
    @pytest.fixture
    def full_user(self):
        """User with all fields populated."""
        return User(
            id=uuid4(),
            email="full@hospital.com",
            hashed_password="hash",
            is_active=True,
            role="PHYSICIAN",
            first_name="John",
            last_name="Doe",
            department="Cardiology",
            license_number="MD123456",
            license_expiry=datetime.utcnow() + timedelta(days=180),
            phi_access_granted=True,
            phi_access_expiry=datetime.utcnow() + timedelta(hours=8),
            password_expires_at=datetime.utcnow() + timedelta(days=90),
            password_must_change=False,
            mfa_enabled=True,
            session_timeout_minutes=480,
            max_concurrent_sessions=5,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow() - timedelta(hours=2)
        )
    
    def test_to_dict_basic_fields_only(self, full_user):
        """Test to_dict returns only basic fields by default."""
        user_dict = full_user.to_dict(include_sensitive=False)
        
        # Should include basic fields
        assert "id" in user_dict
        assert "email" in user_dict
        assert "is_active" in user_dict
        assert "role" in user_dict
        assert "created_at" in user_dict
        assert "last_login" in user_dict
        assert "mfa_enabled" in user_dict
        assert "phi_access_granted" in user_dict
        
        # Should NOT include sensitive fields
        assert "first_name" not in user_dict
        assert "last_name" not in user_dict
        assert "license_number" not in user_dict
        assert "password_expires_at" not in user_dict
    
    def test_to_dict_with_sensitive_fields(self, full_user):
        """Test to_dict includes sensitive fields when requested."""
        user_dict = full_user.to_dict(include_sensitive=True)
        
        # Should include all basic fields
        assert "id" in user_dict
        assert "email" in user_dict
        assert "role" in user_dict
        
        # Should include sensitive fields
        assert "first_name" in user_dict
        assert "last_name" in user_dict
        assert "department" in user_dict
        assert "license_number" in user_dict
        assert "license_expiry" in user_dict
        assert "phi_access_expiry" in user_dict
        assert "password_expires_at" in user_dict
        assert "password_must_change" in user_dict
        assert "session_timeout_minutes" in user_dict
        assert "max_concurrent_sessions" in user_dict
    
    def test_to_dict_datetime_serialization(self, full_user):
        """Test datetime fields are properly serialized to ISO format."""
        user_dict = full_user.to_dict(include_sensitive=True)
        
        # Check datetime fields are ISO formatted strings
        assert isinstance(user_dict["created_at"], str)
        assert "T" in user_dict["created_at"]  # ISO format indicator
        
        if user_dict["last_login"]:
            assert isinstance(user_dict["last_login"], str)
            assert "T" in user_dict["last_login"]
        
        if user_dict["license_expiry"]:
            assert isinstance(user_dict["license_expiry"], str)
            assert "T" in user_dict["license_expiry"]
    
    def test_to_dict_uuid_serialization(self, full_user):
        """Test UUID fields are serialized to strings."""
        user_dict = full_user.to_dict()
        
        assert isinstance(user_dict["id"], str)
        # Check it's a valid UUID string format
        assert len(user_dict["id"]) == 36
        assert user_dict["id"].count("-") == 4
    
    def test_to_dict_none_values_handling(self):
        """Test to_dict handles None values properly."""
        user = User(
            id=uuid4(),
            email="minimal@hospital.com",
            hashed_password="hash",
            is_active=True,
            role="USER",
            first_name=None,
            last_name=None,
            last_login=None,
            license_expiry=None,
            phi_access_expiry=None,
            password_expires_at=None
        )
        
        user_dict = user.to_dict(include_sensitive=True)
        
        # None values should be preserved as None, not excluded
        assert user_dict["last_login"] is None
        assert user_dict["license_expiry"] is None
        assert user_dict["phi_access_expiry"] is None
        assert user_dict["password_expires_at"] is None


class TestUserRepr:
    """Test User model string representation."""
    
    def test_user_repr(self):
        """Test User __repr__ method."""
        user_id = uuid4()
        user = User(
            id=user_id,
            email="test@hospital.com",
            hashed_password="hash"
        )
        
        repr_str = repr(user)
        
        assert "User" in repr_str
        assert str(user_id) in repr_str
        assert "test@hospital.com" in repr_str


class TestUserDefaults:
    """Test User model default values."""
    
    def test_user_default_values(self):
        """Test default values are set correctly."""
        user = User(
            email="defaults@test.com",
            hashed_password="hash"
        )
        
        # Test boolean defaults
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.phi_access_granted is False
        assert user.password_must_change is False
        assert user.mfa_enabled is False
        
        # Test numeric defaults
        assert user.max_concurrent_sessions == 5
        assert user.session_timeout_minutes == 480  # 8 hours
        
        # Test list defaults
        assert user.password_history == []
        assert user.workstation_restrictions == []
        assert user.ip_address_restrictions == []
        assert user.mfa_backup_codes == []
        
        # Test string defaults
        assert user.role == "user"
        assert user.login_attempts == "0"
    
    def test_user_required_fields(self):
        """Test that required fields must be provided."""
        # Should be able to create user with minimal required fields
        user = User(
            email="required@test.com",
            hashed_password="hash"
        )
        
        assert user.email == "required@test.com"
        assert user.hashed_password == "hash"
        assert user.id is not None  # Auto-generated UUID
        assert user.created_at is not None  # Auto-generated timestamp
        assert user.updated_at is not None  # Auto-generated timestamp
        assert user.password_changed_at is not None  # Auto-generated timestamp
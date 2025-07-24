"""
Tests for CustomAuthProvider password policy enforcement.

Tests cover:
- Password policy enforcement in change_password
- Password policy enforcement in reset_password  
- HIPAA compliance integration
- Password history tracking
- Password expiration management
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from src.auth.providers.custom import CustomAuthProvider
from src.auth.exceptions import AuthenticationError
from src.models.user import User


class TestCustomProviderPasswordPolicy:
    """Test password policy enforcement in CustomAuthProvider."""
    
    @pytest.fixture
    async def custom_provider(self):
        """Create CustomAuthProvider instance for testing."""
        return CustomAuthProvider()
    
    @pytest.fixture
    def test_user(self):
        """Create test user for password operations."""
        return User(
            id=uuid4(),
            email="test@hospital.com",
            hashed_password="current_hashed_password",
            role="PHYSICIAN",
            is_active=True,
            password_history=["old_hash_1", "old_hash_2"],
            password_changed_at=datetime.utcnow() - timedelta(days=30),
            password_expires_at=datetime.utcnow() + timedelta(days=60)
        )
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        user_service = AsyncMock()
        session_service = AsyncMock()
        audit_service = AsyncMock()
        db = AsyncMock()
        
        return user_service, session_service, audit_service, db


class TestPasswordChangeWithCompliance:
    """Test password change with HIPAA compliance enforcement."""
    
    @pytest.mark.asyncio
    async def test_change_password_success_with_compliance(self, custom_provider, test_user, mock_services):
        """Test successful password change with HIPAA compliance."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "NewCompliantPassword123!"
        user_id = str(test_user.id)
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        # Mock password verification
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hashed_password"):
            
            # Mock compliance engine
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_HISTORY_COUNT = 12
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": []
            }
            mock_compliance_class.return_value = mock_compliance
            
            result = await custom_provider.change_password(
                user_id, "current_password", new_password, "admin"
            )
        
        assert result is True
        
        # Verify compliance engine was used
        mock_compliance.enforce_password_policy.assert_called_once_with(test_user, new_password)
        
        # Verify user service was called to update password
        user_service.update_user.assert_called_once()
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        
        assert "password" in update_data
        assert "password_history" in update_data
        assert "password_changed_at" in update_data
        assert "password_expires_at" in update_data
        assert update_data["password_must_change"] is False
        
        # Verify sessions were invalidated
        session_service.invalidate_all_user_sessions.assert_called_once_with(user_id, "admin")
        
        # Verify audit logging
        audit_service.log_password_change.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_change_password_policy_violation(self, custom_provider, test_user, mock_services):
        """Test password change rejection due to policy violation."""
        user_service, session_service, audit_service, db = mock_services
        weak_password = "weak"
        user_id = str(test_user.id)
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        # Mock password verification
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class:
            
            # Mock compliance engine to reject password
            mock_compliance = AsyncMock()
            mock_compliance.enforce_password_policy.return_value = {
                "success": False,
                "violations": ["Password too short", "Missing special characters"]
            }
            mock_compliance_class.return_value = mock_compliance
            
            with pytest.raises(AuthenticationError) as exc_info:
                await custom_provider.change_password(
                    user_id, "current_password", weak_password, "admin"
                )
        
        # Verify error message contains policy violations
        error_message = str(exc_info.value)
        assert "Password does not meet policy requirements" in error_message
        assert "Password too short" in error_message
        assert "Missing special characters" in error_message
        
        # Verify failure was logged
        audit_service.log_authentication_event.assert_called()
        log_call = audit_service.log_authentication_event.call_args
        assert log_call[1]["event_type"] == "password_change_failed"
        assert log_call[1]["success"] is False
        
        # Verify user was not updated
        user_service.update_user.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_change_password_history_tracking(self, custom_provider, test_user, mock_services):
        """Test password history is properly tracked during password change."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "NewCompliantPassword123!"
        user_id = str(test_user.id)
        
        # Set up existing password history
        test_user.password_history = ["hash1", "hash2", "hash3"]
        current_hash = "current_hash"
        test_user.hashed_password = current_hash
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hash"):
            
            # Mock compliance engine
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_HISTORY_COUNT = 12
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": []
            }
            mock_compliance_class.return_value = mock_compliance
            
            await custom_provider.change_password(
                user_id, "current_password", new_password, "admin"
            )
        
        # Verify password history was updated
        user_service.update_user.assert_called_once()
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        
        expected_history = ["hash1", "hash2", "hash3", current_hash]
        assert update_data["password_history"] == expected_history
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current_password(self, custom_provider, test_user, mock_services):
        """Test password change rejection with wrong current password."""
        user_service, session_service, audit_service, db = mock_services
        user_id = str(test_user.id)
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        with patch('src.auth.providers.custom.verify_password', return_value=False), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)):
            
            with pytest.raises(AuthenticationError) as exc_info:
                await custom_provider.change_password(
                    user_id, "wrong_password", "NewPassword123!", "admin"
                )
        
        assert "Current password is incorrect" in str(exc_info.value)
        
        # Verify failure was logged
        audit_service.log_authentication_event.assert_called()
        log_call = audit_service.log_authentication_event.call_args
        assert log_call[1]["success"] is False


class TestPasswordResetWithCompliance:
    """Test password reset with HIPAA compliance enforcement."""
    
    @pytest.mark.asyncio
    async def test_reset_password_success_with_compliance(self, custom_provider, test_user, mock_services):
        """Test successful password reset with HIPAA compliance."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "ResetCompliantPassword123!"
        user_id = str(test_user.id)
        reset_token = "valid_reset_token"
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        # Mock token validation
        mock_validated_token = MagicMock()
        mock_validated_token.user_id = user_id
        mock_validated_token.token_id = "token_123"
        
        with patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch.object(custom_provider, 'validate_token', return_value=mock_validated_token), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hashed_password"):
            
            # Mock compliance engine
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_HISTORY_COUNT = 12
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": []
            }
            mock_compliance_class.return_value = mock_compliance
            
            result = await custom_provider.reset_password(user_id, reset_token, new_password)
        
        assert result is True
        
        # Verify compliance engine was used
        mock_compliance.enforce_password_policy.assert_called_once_with(test_user, new_password)
        
        # Verify user service was called to update password
        user_service.update_user.assert_called_once()
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        
        assert "password" in update_data
        assert "password_history" in update_data
        assert "password_changed_at" in update_data
        assert "password_expires_at" in update_data
        assert update_data["password_must_change"] is True  # Force change for reset passwords
        
        # Verify all sessions were invalidated
        session_service.invalidate_all_user_sessions.assert_called_once_with(user_id, "password_reset")
        
        # Verify audit logging
        audit_service.log_authentication_event.assert_called()
        log_call = audit_service.log_authentication_event.call_args
        assert log_call[1]["event_type"] == "password_reset"
        assert log_call[1]["success"] is True
    
    @pytest.mark.asyncio
    async def test_reset_password_policy_violation(self, custom_provider, test_user, mock_services):
        """Test password reset rejection due to policy violation."""
        user_service, session_service, audit_service, db = mock_services
        weak_password = "weak"
        user_id = str(test_user.id)
        reset_token = "valid_reset_token"
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        # Mock token validation
        mock_validated_token = MagicMock()
        mock_validated_token.user_id = user_id
        mock_validated_token.token_id = "token_123"
        
        with patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch.object(custom_provider, 'validate_token', return_value=mock_validated_token), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class:
            
            # Mock compliance engine to reject password
            mock_compliance = AsyncMock()
            mock_compliance.enforce_password_policy.return_value = {
                "success": False,
                "violations": ["Password too short", "Missing uppercase letters"]
            }
            mock_compliance_class.return_value = mock_compliance
            
            with pytest.raises(AuthenticationError) as exc_info:
                await custom_provider.reset_password(user_id, reset_token, weak_password)
        
        # Verify error message contains policy violations
        error_message = str(exc_info.value)
        assert "Password does not meet policy requirements" in error_message
        assert "Password too short" in error_message
        assert "Missing uppercase letters" in error_message
        
        # Verify failure was logged
        audit_service.log_authentication_event.assert_called()
        log_call = audit_service.log_authentication_event.call_args
        assert log_call[1]["event_type"] == "password_reset_failed"
        assert log_call[1]["success"] is False
        
        # Verify user was not updated
        user_service.update_user.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, custom_provider, mock_services):
        """Test password reset with invalid token."""
        user_service, session_service, audit_service, db = mock_services
        user_id = str(uuid4())
        reset_token = "invalid_token"
        
        with patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch.object(custom_provider, 'validate_token', side_effect=AuthenticationError("Invalid token")):
            
            with pytest.raises(AuthenticationError) as exc_info:
                await custom_provider.reset_password(user_id, reset_token, "NewPassword123!")
        
        assert "Invalid token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_reset_password_token_user_mismatch(self, custom_provider, mock_services):
        """Test password reset with token for different user."""
        user_service, session_service, audit_service, db = mock_services
        user_id = str(uuid4())
        different_user_id = str(uuid4())
        reset_token = "valid_token_for_different_user"
        
        # Mock token validation for different user
        mock_validated_token = MagicMock()
        mock_validated_token.user_id = different_user_id
        mock_validated_token.token_id = "token_123"
        
        with patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch.object(custom_provider, 'validate_token', return_value=mock_validated_token):
            
            with pytest.raises(AuthenticationError) as exc_info:
                await custom_provider.reset_password(user_id, reset_token, "NewPassword123!")
        
        assert "Invalid reset token" in str(exc_info.value)


class TestPasswordExpirationHandling:
    """Test password expiration handling in password operations."""
    
    @pytest.mark.asyncio
    async def test_password_expiration_set_correctly(self, custom_provider, test_user, mock_services):
        """Test password expiration is set correctly during change."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "NewCompliantPassword123!"
        user_id = str(test_user.id)
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hash"):
            
            # Mock compliance engine
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": []
            }
            mock_compliance_class.return_value = mock_compliance
            
            start_time = datetime.utcnow()
            await custom_provider.change_password(
                user_id, "current_password", new_password, "admin"
            )
            end_time = datetime.utcnow()
        
        # Verify password expiration was set
        user_service.update_user.assert_called_once()
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        
        assert "password_expires_at" in update_data
        password_expires_at = update_data["password_expires_at"]
        
        # Should be approximately 90 days from now
        expected_min = start_time + timedelta(days=89)
        expected_max = end_time + timedelta(days=91)
        
        assert expected_min <= password_expires_at <= expected_max
    
    @pytest.mark.asyncio
    async def test_password_must_change_flag_handling(self, custom_provider, test_user, mock_services):
        """Test password_must_change flag handling in different scenarios."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "NewCompliantPassword123!"
        user_id = str(test_user.id)
        reset_token = "valid_reset_token"
        
        # Test password change - should clear the flag
        test_user.password_must_change = True
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hash"):
            
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": []
            }
            mock_compliance_class.return_value = mock_compliance
            
            await custom_provider.change_password(
                user_id, "current_password", new_password, "admin"
            )
        
        # Verify flag was cleared for password change
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        assert update_data["password_must_change"] is False
        
        # Reset mocks for password reset test
        user_service.reset_mock()
        audit_service.reset_mock()
        
        # Test password reset - should set the flag
        mock_validated_token = MagicMock()
        mock_validated_token.user_id = user_id
        mock_validated_token.token_id = "token_123"
        
        with patch.object(custom_provider, 'validate_token', return_value=mock_validated_token):
            await custom_provider.reset_password(user_id, reset_token, new_password)
        
        # Verify flag was set for password reset
        update_call = user_service.update_user.call_args
        update_data = update_call[0][1]
        assert update_data["password_must_change"] is True


class TestPasswordPolicyIntegration:
    """Test integration with HIPAA compliance engine."""
    
    @pytest.mark.asyncio
    async def test_compliance_engine_integration(self, custom_provider, test_user, mock_services):
        """Test proper integration with HIPAA compliance engine."""
        user_service, session_service, audit_service, db = mock_services
        new_password = "TestPassword123!"
        user_id = str(test_user.id)
        
        # Mock service setup
        user_service.get_user_by_id.return_value = MagicMock(id=test_user.id)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = test_user
        db.execute.return_value = mock_result
        
        with patch('src.auth.providers.custom.verify_password', return_value=True), \
             patch.object(custom_provider, '_get_services', return_value=(user_service, session_service, audit_service, db)), \
             patch('src.auth.compliance.hipaa.HIPAAComplianceEngine') as mock_compliance_class, \
             patch('src.auth.providers.custom.get_password_hash', return_value="new_hash"):
            
            # Verify compliance engine is instantiated with database session
            mock_compliance = AsyncMock()
            mock_compliance.PASSWORD_HISTORY_COUNT = 12
            mock_compliance.PASSWORD_MAX_AGE_DAYS = 90
            mock_compliance.enforce_password_policy.return_value = {
                "success": True,
                "violations": [],
                "policy_requirements": {
                    "min_length": 12,
                    "requires_uppercase": True
                }
            }
            mock_compliance_class.return_value = mock_compliance
            
            await custom_provider.change_password(
                user_id, "current_password", new_password, "admin"
            )
        
        # Verify compliance engine was instantiated with database session
        mock_compliance_class.assert_called_once_with(db)
        
        # Verify enforce_password_policy was called with correct parameters
        mock_compliance.enforce_password_policy.assert_called_once_with(test_user, new_password)
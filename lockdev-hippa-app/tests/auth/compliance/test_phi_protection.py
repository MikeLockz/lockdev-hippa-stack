"""
Tests for PHI Access Control functionality.

Tests cover:
- Role-based access control
- Minimum necessary principle
- PHI access authorization
- Access reason validation
- Audit logging for PHI access
- Account locking and security features
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from src.auth.compliance.phi_protection import (
    PHIAccessController, PHIAccessReason, DataElement,
    PHIAccessRequest, PHIAccessGrant
)
from src.models.user import User
from src.models.audit_log import AuditLog


class TestPHIAccessController:
    """Test PHI access control functionality."""
    
    @pytest.fixture
    async def phi_controller(self, db_session):
        """Create PHI access controller with test database."""
        return PHIAccessController(db_session)
    
    @pytest.fixture
    def physician_user(self):
        """Create a physician user for testing."""
        return User(
            id=uuid4(),
            email="physician@hospital.com",
            role="PHYSICIAN",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Treatment of patients",
            phi_access_expiry=datetime.utcnow() + timedelta(hours=8),
            department="Emergency Medicine"
        )
    
    @pytest.fixture
    def nurse_user(self):
        """Create a nurse user for testing."""
        return User(
            id=uuid4(),
            email="nurse@hospital.com",
            role="NURSE",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Patient care",
            phi_access_expiry=datetime.utcnow() + timedelta(hours=8),
            department="Emergency Medicine"
        )
    
    @pytest.fixture
    def billing_user(self):
        """Create a billing specialist user for testing."""
        return User(
            id=uuid4(),
            email="billing@hospital.com",
            role="BILLING_SPECIALIST",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Payment processing",
            phi_access_expiry=datetime.utcnow() + timedelta(hours=8),
            department="Billing"
        )
    
    @pytest.fixture
    def patient_user(self):
        """Create a patient user for testing."""
        return User(
            id=uuid4(),
            email="patient@example.com",
            role="PATIENT",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Individual access",
            phi_access_expiry=datetime.utcnow() + timedelta(hours=24),
            department=None
        )
    
    @pytest.fixture
    def no_access_user(self):
        """Create a user without PHI access."""
        return User(
            id=uuid4(),
            email="user@hospital.com",
            role="ADMIN",
            is_active=True,
            phi_access_granted=False,
            phi_access_reason=None,
            phi_access_expiry=None,
            department="IT"
        )
    
    @pytest.fixture
    def expired_access_user(self):
        """Create a user with expired PHI access."""
        return User(
            id=uuid4(),
            email="expired@hospital.com",
            role="PHYSICIAN",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Treatment",
            phi_access_expiry=datetime.utcnow() - timedelta(hours=1),
            department="Internal Medicine"
        )

    # Role-based access control tests
    
    @pytest.mark.asyncio
    async def test_physician_access_all_allowed_elements(self, phi_controller, physician_user):
        """Test that physicians can access all their allowed data elements."""
        patient_id = uuid4()
        allowed_elements = [
            DataElement.DEMOGRAPHICS,
            DataElement.MEDICAL_HISTORY,
            DataElement.LAB_RESULTS,
            DataElement.PHYSICIAN_NOTES
        ]
        
        with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                physician_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                allowed_elements
            )
        
        assert result is True
        phi_controller._log_phi_access.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_nurse_limited_access(self, phi_controller, nurse_user):
        """Test that nurses have limited access to specific data elements."""
        patient_id = uuid4()
        allowed_elements = [
            DataElement.DEMOGRAPHICS,
            DataElement.CURRENT_MEDICATIONS,
            DataElement.NURSING_NOTES
        ]
        
        with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                nurse_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                allowed_elements
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_nurse_denied_physician_only_elements(self, phi_controller, nurse_user):
        """Test that nurses cannot access physician-only elements."""
        patient_id = uuid4()
        physician_only_elements = [
            DataElement.PHYSICIAN_NOTES,
            DataElement.DISCHARGE_SUMMARY,
            DataElement.GENETIC_INFO
        ]
        
        with patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                nurse_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                physician_only_elements
            )
        
        assert result is False
        phi_controller._log_access_denial.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_billing_specialist_access(self, phi_controller, billing_user):
        """Test billing specialist can access billing-related data only."""
        patient_id = uuid4()
        billing_elements = [
            DataElement.DEMOGRAPHICS,
            DataElement.BILLING_INFO,
            DataElement.INSURANCE_INFO
        ]
        
        with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                billing_user,
                patient_id,
                PHIAccessReason.PAYMENT,
                billing_elements
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_billing_denied_medical_elements(self, phi_controller, billing_user):
        """Test billing specialist cannot access medical data."""
        patient_id = uuid4()
        medical_elements = [
            DataElement.LAB_RESULTS,
            DataElement.MEDICAL_HISTORY,
            DataElement.PHYSICIAN_NOTES
        ]
        
        with patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                billing_user,
                patient_id,
                PHIAccessReason.PAYMENT,
                medical_elements
            )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_patient_self_access(self, phi_controller, patient_user):
        """Test patients can access all their own data."""
        # Patient accessing their own data
        all_elements = [
            DataElement.DEMOGRAPHICS,
            DataElement.MEDICAL_HISTORY,
            DataElement.LAB_RESULTS,
            DataElement.PHYSICIAN_NOTES,
            DataElement.BILLING_INFO
        ]
        
        with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                patient_user,
                patient_user.id,  # Same user ID - patient accessing own data
                PHIAccessReason.INDIVIDUAL_ACCESS,
                all_elements
            )
        
        assert result is True

    # Access reason validation tests
    
    @pytest.mark.asyncio
    async def test_valid_access_reason_for_role(self, phi_controller, physician_user):
        """Test valid access reasons are accepted."""
        patient_id = uuid4()
        
        with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                physician_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                [DataElement.DEMOGRAPHICS]
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_invalid_access_reason_for_role(self, phi_controller, billing_user):
        """Test invalid access reasons are rejected."""
        patient_id = uuid4()
        
        with patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                billing_user,
                patient_id,
                PHIAccessReason.TREATMENT,  # Invalid for billing role
                [DataElement.BILLING_INFO]
            )
        
        assert result is False

    # PHI access grant/revoke tests
    
    @pytest.mark.asyncio
    async def test_no_phi_access_denied(self, phi_controller, no_access_user):
        """Test users without PHI access are denied."""
        patient_id = uuid4()
        
        with patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                no_access_user,
                patient_id,
                PHIAccessReason.HEALTHCARE_OPERATIONS,
                [DataElement.DEMOGRAPHICS]
            )
        
        assert result is False
        phi_controller._log_access_denial.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_expired_phi_access_denied(self, phi_controller, expired_access_user):
        """Test users with expired PHI access are denied."""
        patient_id = uuid4()
        
        with patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            result = await phi_controller.authorize_phi_access(
                expired_access_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                [DataElement.DEMOGRAPHICS]
            )
        
        assert result is False
        phi_controller._log_access_denial.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_grant_phi_access(self, phi_controller, db_session, no_access_user):
        """Test granting PHI access to a user."""
        supervisor_id = uuid4()
        access_reason = "Emergency patient care"
        
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(db_session, 'commit', new_callable=AsyncMock), \
             patch.object(db_session, 'add'):
            
            # Mock user query result
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = no_access_user
            mock_execute.return_value = mock_result
            
            result = await phi_controller.grant_phi_access(
                no_access_user.id,
                access_reason,
                supervisor_id,
                duration_hours=4
            )
        
        assert result is True
        assert no_access_user.phi_access_granted is True
        assert no_access_user.phi_access_reason == access_reason
        assert no_access_user.phi_access_supervisor == supervisor_id
        assert no_access_user.phi_access_expiry is not None
    
    @pytest.mark.asyncio
    async def test_revoke_phi_access(self, phi_controller, db_session, physician_user):
        """Test revoking PHI access from a user."""
        revoker_id = uuid4()
        revocation_reason = "End of shift"
        
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(db_session, 'commit', new_callable=AsyncMock), \
             patch.object(db_session, 'add'):
            
            # Mock user query result
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = physician_user
            mock_execute.return_value = mock_result
            
            result = await phi_controller.revoke_phi_access(
                physician_user.id,
                revoker_id,
                revocation_reason
            )
        
        assert result is True
        assert physician_user.phi_access_granted is False
        assert physician_user.phi_access_reason is None
        assert physician_user.phi_access_expiry is None

    # Restricted data element tests
    
    @pytest.mark.asyncio
    async def test_restricted_substance_abuse_access_physician(self, phi_controller, physician_user):
        """Test physician can access substance abuse records."""
        patient_id = uuid4()
        restricted_elements = [DataElement.SUBSTANCE_ABUSE_RECORDS]
        
        with patch.object(phi_controller, '_authorize_restricted_access', return_value=True), \
             patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
            
            result = await phi_controller.authorize_phi_access(
                physician_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                restricted_elements
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_restricted_mental_health_access_denied_nurse(self, phi_controller, nurse_user):
        """Test nurse cannot access mental health records without special authorization."""
        patient_id = uuid4()
        restricted_elements = [DataElement.MENTAL_HEALTH_RECORDS]
        
        with patch.object(phi_controller, '_authorize_restricted_access', return_value=False), \
             patch.object(phi_controller, '_log_access_denial', new_callable=AsyncMock):
            
            result = await phi_controller.authorize_phi_access(
                nurse_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                restricted_elements
            )
        
        assert result is False

    # Audit logging tests
    
    @pytest.mark.asyncio
    async def test_successful_access_audit_log(self, phi_controller, db_session, physician_user):
        """Test successful PHI access is properly logged."""
        patient_id = uuid4()
        elements = [DataElement.LAB_RESULTS]
        
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit', new_callable=AsyncMock):
            
            await phi_controller._log_phi_access(
                physician_user.id,
                patient_id,
                elements,
                PHIAccessReason.TREATMENT,
                success=True
            )
        
        # Verify audit log was created
        mock_add.assert_called_once()
        audit_log = mock_add.call_args[0][0]
        assert isinstance(audit_log, AuditLog)
        assert audit_log.user_id == physician_user.id
        assert audit_log.event_type == "phi_access_attempt"
        assert audit_log.phi_accessed is True
        assert audit_log.patient_id == patient_id
        assert audit_log.compliance_status == "compliant"
    
    @pytest.mark.asyncio
    async def test_denied_access_audit_log(self, phi_controller, db_session, nurse_user):
        """Test denied PHI access is properly logged."""
        patient_id = uuid4()
        elements = [DataElement.PHYSICIAN_NOTES]
        denial_reason = "Insufficient privileges"
        
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit', new_callable=AsyncMock):
            
            await phi_controller._log_access_denial(
                nurse_user.id,
                patient_id,
                denial_reason,
                elements
            )
        
        # Verify audit log was created
        mock_add.assert_called_once()
        audit_log = mock_add.call_args[0][0]
        assert isinstance(audit_log, AuditLog)
        assert audit_log.user_id == nurse_user.id
        assert audit_log.event_type == "phi_access_denied"
        assert audit_log.phi_accessed is False
        assert audit_log.compliance_status == "access_denied"

    # Minimum necessary principle tests
    
    @pytest.mark.asyncio
    async def test_minimum_necessary_applied(self, phi_controller, nurse_user):
        """Test minimum necessary principle filters requested elements."""
        # Nurse requests both allowed and disallowed elements
        requested_elements = [
            DataElement.DEMOGRAPHICS,        # Allowed for nurses
            DataElement.CURRENT_MEDICATIONS, # Allowed for nurses  
            DataElement.PHYSICIAN_NOTES,     # Not allowed for nurses
            DataElement.GENETIC_INFO         # Not allowed for nurses
        ]
        
        allowed_elements = await phi_controller._check_minimum_necessary(
            nurse_user.role,
            requested_elements
        )
        
        # Should only return allowed elements
        expected_allowed = [
            DataElement.DEMOGRAPHICS,
            DataElement.CURRENT_MEDICATIONS
        ]
        
        assert len(allowed_elements) == 2
        assert all(elem in expected_allowed for elem in allowed_elements)
        assert DataElement.PHYSICIAN_NOTES not in allowed_elements
        assert DataElement.GENETIC_INFO not in allowed_elements
    
    @pytest.mark.asyncio
    async def test_patient_minimum_necessary_all_elements(self, phi_controller, patient_user):
        """Test patients can access all elements for their own data."""
        all_elements = list(DataElement)
        
        allowed_elements = await phi_controller._check_minimum_necessary(
            patient_user.role,
            all_elements
        )
        
        # Patients should get all requested elements for their own data
        assert len(allowed_elements) == len(all_elements)
        assert set(allowed_elements) == set(all_elements)

    # Access expiry management tests
    
    @pytest.mark.asyncio
    async def test_check_phi_access_expiry(self, phi_controller, db_session):
        """Test automatic expiry of PHI access grants."""
        # Create users with expired access
        expired_user1 = User(
            id=uuid4(),
            email="expired1@hospital.com",
            phi_access_granted=True,
            phi_access_expiry=datetime.utcnow() - timedelta(hours=1)
        )
        expired_user2 = User(
            id=uuid4(),
            email="expired2@hospital.com",
            phi_access_granted=True,
            phi_access_expiry=datetime.utcnow() - timedelta(minutes=30)
        )
        
        expired_users = [expired_user1, expired_user2]
        
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(db_session, 'commit', new_callable=AsyncMock), \
             patch.object(db_session, 'add') as mock_add:
            
            # Mock query result
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = expired_users
            mock_execute.return_value = mock_result
            
            revoked_user_ids = await phi_controller.check_phi_access_expiry()
        
        # Verify both users had access revoked
        assert len(revoked_user_ids) == 2
        assert expired_user1.id in revoked_user_ids
        assert expired_user2.id in revoked_user_ids
        
        # Verify access was revoked
        assert expired_user1.phi_access_granted is False
        assert expired_user2.phi_access_granted is False
        
        # Verify audit logs were created
        assert mock_add.call_count == 2

    # Error handling tests
    
    @pytest.mark.asyncio
    async def test_authorize_phi_access_exception_handling(self, phi_controller, physician_user):
        """Test exception handling in PHI access authorization."""
        patient_id = uuid4()
        
        with patch.object(phi_controller, '_validate_access_reason', side_effect=Exception("Test error")):
            result = await phi_controller.authorize_phi_access(
                physician_user,
                patient_id,
                PHIAccessReason.TREATMENT,
                [DataElement.DEMOGRAPHICS]
            )
        
        # Should return False on exception
        assert result is False
    
    @pytest.mark.asyncio
    async def test_grant_phi_access_user_not_found(self, phi_controller, db_session):
        """Test granting PHI access when user doesn't exist."""
        non_existent_user_id = uuid4()
        supervisor_id = uuid4()
        
        with patch.object(db_session, 'execute') as mock_execute:
            # Mock user not found
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_execute.return_value = mock_result
            
            result = await phi_controller.grant_phi_access(
                non_existent_user_id,
                "Test reason",
                supervisor_id
            )
        
        assert result is False

    # Integration tests
    
    @pytest.mark.asyncio
    async def test_full_phi_access_workflow(self, phi_controller, db_session):
        """Test complete PHI access workflow from grant to access to revoke."""
        # Create user without initial access
        user = User(
            id=uuid4(),
            email="workflow@hospital.com",
            role="PHYSICIAN",
            is_active=True,
            phi_access_granted=False
        )
        
        supervisor_id = uuid4()
        revoker_id = uuid4()
        patient_id = uuid4()
        
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(db_session, 'commit', new_callable=AsyncMock), \
             patch.object(db_session, 'add'):
            
            # Mock user queries
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = user
            mock_execute.return_value = mock_result
            
            # Step 1: Grant PHI access
            grant_result = await phi_controller.grant_phi_access(
                user.id,
                "Emergency treatment",
                supervisor_id,
                duration_hours=2
            )
            assert grant_result is True
            assert user.phi_access_granted is True
            
            # Step 2: Authorize PHI access
            with patch.object(phi_controller, '_log_phi_access', new_callable=AsyncMock):
                access_result = await phi_controller.authorize_phi_access(
                    user,
                    patient_id,
                    PHIAccessReason.TREATMENT,
                    [DataElement.MEDICAL_HISTORY]
                )
            assert access_result is True
            
            # Step 3: Revoke PHI access
            revoke_result = await phi_controller.revoke_phi_access(
                user.id,
                revoker_id,
                "Treatment complete"
            )
            assert revoke_result is True
            assert user.phi_access_granted is False


class TestPHIAccessRequest:
    """Test PHI access request model validation."""
    
    def test_valid_phi_access_request(self):
        """Test creating a valid PHI access request."""
        request = PHIAccessRequest(
            user_id=uuid4(),
            patient_id=uuid4(),
            access_reason=PHIAccessReason.TREATMENT,
            data_elements=[DataElement.DEMOGRAPHICS, DataElement.LAB_RESULTS],
            justification="Patient treatment requires access to demographics and lab results",
            access_duration_hours=4
        )
        
        assert request.user_id is not None
        assert request.access_reason == PHIAccessReason.TREATMENT
        assert len(request.data_elements) == 2
        assert request.access_duration_hours == 4
    
    def test_phi_access_request_validation(self):
        """Test PHI access request validation rules."""
        with pytest.raises(ValueError):
            # Justification too short
            PHIAccessRequest(
                user_id=uuid4(),
                patient_id=uuid4(),
                access_reason=PHIAccessReason.TREATMENT,
                data_elements=[DataElement.DEMOGRAPHICS],
                justification="Short",  # Less than 10 characters
                access_duration_hours=4
            )
        
        with pytest.raises(ValueError):
            # Duration too long
            PHIAccessRequest(
                user_id=uuid4(),
                patient_id=uuid4(),
                access_reason=PHIAccessReason.TREATMENT,
                data_elements=[DataElement.DEMOGRAPHICS],
                justification="Valid justification for access",
                access_duration_hours=100  # More than 72 hours
            )


class TestDataElementEnum:
    """Test PHI data element enumeration."""
    
    def test_all_data_elements_defined(self):
        """Test that all expected data elements are defined."""
        expected_elements = [
            "DEMOGRAPHICS", "CONTACT_INFO", "MEDICAL_HISTORY",
            "CURRENT_MEDICATIONS", "ALLERGIES", "LAB_RESULTS",
            "RADIOLOGY_REPORTS", "PHYSICIAN_NOTES", "NURSING_NOTES",
            "DISCHARGE_SUMMARY", "BILLING_INFO", "INSURANCE_INFO",
            "EMERGENCY_CONTACTS", "ADVANCE_DIRECTIVES", "IMMUNIZATION_RECORDS",
            "MENTAL_HEALTH_RECORDS", "SUBSTANCE_ABUSE_RECORDS", "GENETIC_INFO",
            "SOCIAL_SECURITY_NUMBER", "FULL_FACE_PHOTOS"
        ]
        
        actual_elements = [elem.name for elem in DataElement]
        
        for expected in expected_elements:
            assert expected in actual_elements
    
    def test_data_element_values(self):
        """Test data element enum values are correct."""
        assert DataElement.DEMOGRAPHICS.value == "demographics"
        assert DataElement.MENTAL_HEALTH_RECORDS.value == "mental_health_records"
        assert DataElement.SUBSTANCE_ABUSE_RECORDS.value == "substance_abuse_records"


class TestPHIAccessReason:
    """Test PHI access reason enumeration."""
    
    def test_all_access_reasons_defined(self):
        """Test that all HIPAA-compliant access reasons are defined."""
        expected_reasons = [
            "TREATMENT", "PAYMENT", "HEALTHCARE_OPERATIONS",
            "RESEARCH", "PUBLIC_HEALTH", "JUDICIAL_ADMINISTRATIVE",
            "LAW_ENFORCEMENT", "CORONER_MEDICAL_EXAMINER",
            "ORGAN_DONATION", "WORKERS_COMPENSATION",
            "INDIVIDUAL_ACCESS", "BREACH_NOTIFICATION"
        ]
        
        actual_reasons = [reason.name for reason in PHIAccessReason]
        
        for expected in expected_reasons:
            assert expected in actual_reasons
    
    def test_access_reason_values(self):
        """Test access reason enum values are correct."""
        assert PHIAccessReason.TREATMENT.value == "treatment"
        assert PHIAccessReason.INDIVIDUAL_ACCESS.value == "individual_access"
        assert PHIAccessReason.HEALTHCARE_OPERATIONS.value == "healthcare_operations"
"""
Tests for enhanced Audit Log model with HIPAA compliance fields.

Tests cover:
- HIPAA-specific audit fields
- Data integrity hash generation and verification
- Event categorization and classification
- PHI access logging requirements
- Compliance status tracking
- Audit data sanitization and export
"""

import pytest
import json
import hashlib
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.audit_log import AuditLog


class TestAuditLogHIPAAFields:
    """Test HIPAA-specific audit log fields."""
    
    @pytest.fixture
    def base_audit_data(self):
        """Base audit log data for testing."""
        return {
            "user_id": uuid4(),
            "user_email": "test@hospital.com",
            "action": "login",
            "resource_type": "authentication",
            "timestamp": datetime.utcnow(),
            "ip_address": "192.168.1.100",
            "outcome": "success"
        }
    
    def test_audit_log_with_phi_access(self, base_audit_data):
        """Test audit log with PHI access fields."""
        patient_id = uuid4()
        data_elements = ["demographics", "lab_results", "medical_history"]
        
        phi_audit_data = {
            **base_audit_data,
            "phi_accessed": True,
            "patient_id": patient_id,
            "data_elements_accessed": data_elements,
            "access_reason": "treatment",
            "minimum_necessary_applied": True
        }
        
        audit_log = AuditLog(**phi_audit_data)
        
        assert audit_log.phi_accessed is True
        assert audit_log.patient_id == patient_id
        assert audit_log.data_elements_accessed == data_elements
        assert audit_log.access_reason == "treatment"
        assert audit_log.minimum_necessary_applied is True
    
    def test_audit_log_compliance_fields(self, base_audit_data):
        """Test compliance-specific fields."""
        compliance_data = {
            **base_audit_data,
            "event_type": "phi_access_attempt",
            "event_category": "access",
            "compliance_status": "compliant",
            "retention_period": 2555  # 7 years
        }
        
        audit_log = AuditLog(**compliance_data)
        
        assert audit_log.event_type == "phi_access_attempt"
        assert audit_log.event_category == "access"
        assert audit_log.compliance_status == "compliant"
        assert audit_log.retention_period == 2555
    
    def test_audit_log_security_context(self, base_audit_data):
        """Test security context fields."""
        security_data = {
            **base_audit_data,
            "session_id": "session_12345",
            "device_fingerprint": "device_abc123",
            "geolocation": {"country": "US", "state": "CA", "city": "San Francisco"},
            "risk_score": 25
        }
        
        audit_log = AuditLog(**security_data)
        
        assert audit_log.session_id == "session_12345"
        assert audit_log.device_fingerprint == "device_abc123"
        assert audit_log.geolocation == {"country": "US", "state": "CA", "city": "San Francisco"}
        assert audit_log.risk_score == 25
    
    def test_audit_log_workflow_context(self, base_audit_data):
        """Test workflow context fields."""
        workflow_data = {
            **base_audit_data,
            "workstation_id": "WS001",
            "department": "Emergency Medicine",
            "supervisor_notified": False
        }
        
        audit_log = AuditLog(**workflow_data)
        
        assert audit_log.workstation_id == "WS001"
        assert audit_log.department == "Emergency Medicine"
        assert audit_log.supervisor_notified is False
    
    def test_audit_log_data_integrity_fields(self, base_audit_data):
        """Test data integrity hash fields."""
        audit_log = AuditLog(**base_audit_data)
        
        # Hash should be automatically generated
        assert audit_log.record_hash is not None
        assert len(audit_log.record_hash) == 64  # SHA-256 hex string
        
        # Previous hash can be set
        audit_log.previous_hash = "previous_hash_value"
        assert audit_log.previous_hash == "previous_hash_value"


class TestAuditLogInitialization:
    """Test audit log initialization and automatic field population."""
    
    def test_automatic_event_type_from_action(self):
        """Test event_type is set from action if not provided."""
        audit_log = AuditLog(
            action="user_login",
            resource_type="authentication",
            outcome="success"
        )
        
        assert audit_log.event_type == "user_login"
    
    def test_explicit_event_type_preserved(self):
        """Test explicit event_type is preserved."""
        audit_log = AuditLog(
            action="login",
            event_type="authentication_attempt",
            resource_type="user",
            outcome="success"
        )
        
        assert audit_log.event_type == "authentication_attempt"
    
    def test_automatic_event_category_determination(self):
        """Test event_category is automatically determined from event_type."""
        # Authentication event
        auth_log = AuditLog(
            event_type="login_attempt",
            resource_type="user",
            outcome="success"
        )
        assert auth_log.event_category == "authentication"
        
        # Authorization event
        authz_log = AuditLog(
            event_type="permission_check",
            resource_type="resource",
            outcome="success"
        )
        assert authz_log.event_category == "authorization"
        
        # Access event
        access_log = AuditLog(
            event_type="phi_access",
            resource_type="patient_data",
            outcome="success"
        )
        assert access_log.event_category == "access"
        
        # Other event
        other_log = AuditLog(
            event_type="system_maintenance",
            resource_type="system",
            outcome="success"
        )
        assert other_log.event_category == "other"
    
    def test_automatic_hash_generation(self):
        """Test record hash is automatically generated on initialization."""
        audit_log = AuditLog(
            user_id=uuid4(),
            event_type="test_event",
            resource_type="test",
            outcome="success",
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.1"
        )
        
        assert audit_log.record_hash is not None
        assert len(audit_log.record_hash) == 64


class TestAuditLogIntegrityMethods:
    """Test audit log data integrity methods."""
    
    @pytest.fixture
    def test_audit_log(self):
        """Create a test audit log."""
        return AuditLog(
            user_id=uuid4(),
            event_type="test_event",
            resource_type="test_resource",
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.100",
            phi_accessed=True,
            patient_id=uuid4(),
            details={"test": "data"},
            outcome="success"
        )
    
    def test_generate_record_hash_deterministic(self, test_audit_log):
        """Test that hash generation is deterministic."""
        hash1 = test_audit_log._generate_record_hash()
        hash2 = test_audit_log._generate_record_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string
    
    def test_generate_record_hash_changes_with_data(self, test_audit_log):
        """Test that hash changes when data changes."""
        original_hash = test_audit_log._generate_record_hash()
        
        # Change event type
        test_audit_log.event_type = "different_event"
        new_hash = test_audit_log._generate_record_hash()
        
        assert original_hash != new_hash
    
    def test_verify_integrity_valid_hash(self, test_audit_log):
        """Test integrity verification with valid hash."""
        # Hash is automatically generated on init
        assert test_audit_log.verify_integrity() is True
    
    def test_verify_integrity_invalid_hash(self, test_audit_log):
        """Test integrity verification with invalid hash."""
        # Manually corrupt the hash
        test_audit_log.record_hash = "invalid_hash"
        
        assert test_audit_log.verify_integrity() is False
    
    def test_hash_includes_key_fields(self):
        """Test that hash includes key audit fields."""
        user_id = uuid4()
        patient_id = uuid4()
        timestamp = datetime.utcnow()
        
        audit_log = AuditLog(
            user_id=user_id,
            event_type="phi_access",
            timestamp=timestamp,
            ip_address="192.168.1.100",
            phi_accessed=True,
            patient_id=patient_id,
            details={"accessed_elements": ["demographics"]},
            outcome="success"
        )
        
        # Manually verify hash calculation
        hash_data = {
            'user_id': str(user_id),
            'event_type': 'phi_access',
            'timestamp': timestamp.isoformat(),
            'ip_address': '192.168.1.100',
            'phi_accessed': True,
            'patient_id': str(patient_id),
            'details': json.dumps({"accessed_elements": ["demographics"]}, sort_keys=True)
        }
        
        expected_hash = hashlib.sha256(
            json.dumps(hash_data, sort_keys=True).encode()
        ).hexdigest()
        
        assert audit_log.record_hash == expected_hash


class TestAuditLogUtilityMethods:
    """Test audit log utility and helper methods."""
    
    def test_is_phi_event_with_phi_accessed(self):
        """Test PHI event detection when phi_accessed is True."""
        audit_log = AuditLog(
            event_type="data_access",
            resource_type="patient_data",
            phi_accessed=True,
            outcome="success"
        )
        
        assert audit_log.is_phi_event() is True
    
    def test_is_phi_event_with_patient_id(self):
        """Test PHI event detection when patient_id is present."""
        audit_log = AuditLog(
            event_type="record_view",
            resource_type="medical_record",
            phi_accessed=False,
            patient_id=uuid4(),
            outcome="success"
        )
        
        assert audit_log.is_phi_event() is True
    
    def test_is_phi_event_non_phi_event(self):
        """Test PHI event detection for non-PHI events."""
        audit_log = AuditLog(
            event_type="login",
            resource_type="authentication",
            phi_accessed=False,
            patient_id=None,
            outcome="success"
        )
        
        assert audit_log.is_phi_event() is False
    
    def test_get_retention_date(self):
        """Test retention date calculation."""
        timestamp = datetime(2024, 1, 1, 10, 0, 0)
        audit_log = AuditLog(
            event_type="test",
            resource_type="test",
            timestamp=timestamp,
            retention_period=365,  # 1 year
            outcome="success"
        )
        
        expected_retention_date = timestamp + timedelta(days=365)
        assert audit_log.get_retention_date() == expected_retention_date
    
    def test_is_eligible_for_purge_not_eligible(self):
        """Test purge eligibility for recent records."""
        recent_timestamp = datetime.utcnow() - timedelta(days=30)
        audit_log = AuditLog(
            event_type="test",
            resource_type="test",
            timestamp=recent_timestamp,
            retention_period=365,  # 1 year
            outcome="success"
        )
        
        assert audit_log.is_eligible_for_purge() is False
    
    def test_is_eligible_for_purge_eligible(self):
        """Test purge eligibility for old records."""
        old_timestamp = datetime.utcnow() - timedelta(days=400)  # Over 1 year ago
        audit_log = AuditLog(
            event_type="test",
            resource_type="test",
            timestamp=old_timestamp,
            retention_period=365,  # 1 year
            outcome="success"
        )
        
        assert audit_log.is_eligible_for_purge() is True


class TestAuditLogDictMethods:
    """Test audit log dictionary conversion methods."""
    
    @pytest.fixture
    def comprehensive_audit_log(self):
        """Create audit log with all fields populated."""
        return AuditLog(
            user_id=uuid4(),
            user_email="test@hospital.com",
            action="phi_access",
            event_type="phi_access_attempt",
            event_category="access",
            resource_type="patient_data",
            resource_id="patient_123",
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0...",
            details={"elements": ["demographics", "lab_results"]},
            outcome="success",
            request_method="GET",
            request_url="/api/patients/123",
            response_status="200",
            phi_accessed=True,
            patient_id=uuid4(),
            data_elements_accessed=["demographics", "lab_results"],
            access_reason="treatment",
            minimum_necessary_applied=True,
            compliance_status="compliant",
            retention_period=2555,
            session_id="session_123",
            device_fingerprint="device_abc",
            geolocation={"country": "US", "state": "CA"},
            risk_score=15,
            workstation_id="WS001",
            department="Emergency",
            supervisor_notified=False
        )
    
    def test_to_dict_basic_fields(self, comprehensive_audit_log):
        """Test to_dict returns basic fields by default."""
        audit_dict = comprehensive_audit_log.to_dict(include_sensitive=False)
        
        # Should include basic audit fields
        assert "id" in audit_dict
        assert "user_id" in audit_dict
        assert "user_email" in audit_dict
        assert "action" in audit_dict
        assert "event_type" in audit_dict
        assert "event_category" in audit_dict
        assert "timestamp" in audit_dict
        assert "outcome" in audit_dict
        assert "compliance_status" in audit_dict
        assert "phi_accessed" in audit_dict
        
        # Should NOT include sensitive fields
        assert "record_hash" not in audit_dict
        assert "session_id" not in audit_dict
        assert "device_fingerprint" not in audit_dict
        assert "geolocation" not in audit_dict
    
    def test_to_dict_with_sensitive_fields(self, comprehensive_audit_log):
        """Test to_dict includes sensitive fields when requested."""
        audit_dict = comprehensive_audit_log.to_dict(include_sensitive=True)
        
        # Should include sensitive fields
        assert "record_hash" in audit_dict
        assert "previous_hash" in audit_dict
        assert "session_id" in audit_dict
        assert "device_fingerprint" in audit_dict
        assert "geolocation" in audit_dict
        assert "risk_score" in audit_dict
        assert "workstation_id" in audit_dict
        assert "department" in audit_dict
        assert "request_method" in audit_dict
        assert "request_url" in audit_dict
        assert "retention_period" in audit_dict
    
    def test_to_dict_phi_fields_when_phi_accessed(self, comprehensive_audit_log):
        """Test PHI fields included when PHI was accessed."""
        audit_dict = comprehensive_audit_log.to_dict(include_sensitive=False)
        
        # PHI fields should be included when phi_accessed is True
        assert "patient_id" in audit_dict
        assert "data_elements_accessed" in audit_dict
        assert "access_reason" in audit_dict
    
    def test_to_dict_no_phi_fields_when_not_accessed(self):
        """Test PHI fields not included when PHI not accessed."""
        audit_log = AuditLog(
            event_type="login",
            resource_type="authentication",
            phi_accessed=False,
            outcome="success"
        )
        
        audit_dict = audit_log.to_dict(include_sensitive=False)
        
        # PHI fields should not be included
        assert "patient_id" not in audit_dict
        assert "data_elements_accessed" not in audit_dict
        assert "access_reason" not in audit_dict
    
    def test_to_dict_uuid_serialization(self, comprehensive_audit_log):
        """Test UUID fields are serialized to strings."""
        audit_dict = comprehensive_audit_log.to_dict()
        
        assert isinstance(audit_dict["id"], str)
        assert isinstance(audit_dict["user_id"], str)
        if audit_dict.get("patient_id"):
            assert isinstance(audit_dict["patient_id"], str)
    
    def test_to_dict_datetime_serialization(self, comprehensive_audit_log):
        """Test datetime fields are serialized to ISO format."""
        audit_dict = comprehensive_audit_log.to_dict()
        
        assert isinstance(audit_dict["timestamp"], str)
        assert "T" in audit_dict["timestamp"]  # ISO format indicator
    
    def test_sanitize_for_export(self, comprehensive_audit_log):
        """Test audit log sanitization for external export."""
        sanitized = comprehensive_audit_log.sanitize_for_export()
        
        # Should include non-sensitive fields
        assert "timestamp" in sanitized
        assert "event_type" in sanitized
        assert "event_category" in sanitized
        assert "outcome" in sanitized
        assert "compliance_status" in sanitized
        assert "phi_accessed" in sanitized
        assert "minimum_necessary_applied" in sanitized
        assert "department" in sanitized
        
        # Should NOT include sensitive fields
        assert "user_id" not in sanitized
        assert "patient_id" not in sanitized
        assert "ip_address" not in sanitized
        assert "device_fingerprint" not in sanitized
        assert "record_hash" not in sanitized


class TestAuditLogRepr:
    """Test audit log string representation."""
    
    def test_audit_log_repr(self):
        """Test AuditLog __repr__ method."""
        user_id = uuid4()
        audit_log = AuditLog(
            user_id=user_id,
            event_type="test_event",
            resource_type="test",
            phi_accessed=True,
            outcome="success"
        )
        
        repr_str = repr(audit_log)
        
        assert "AuditLog" in repr_str
        assert "test_event" in repr_str
        assert str(user_id) in repr_str
        assert "phi_accessed=True" in repr_str


class TestAuditLogDefaults:
    """Test audit log default values."""
    
    def test_audit_log_default_values(self):
        """Test default values are set correctly."""
        audit_log = AuditLog(
            event_type="test",
            resource_type="test"
        )
        
        # Test boolean defaults
        assert audit_log.phi_accessed is False
        assert audit_log.minimum_necessary_applied is False
        assert audit_log.supervisor_notified is False
        
        # Test string defaults
        assert audit_log.outcome == "success"
        assert audit_log.compliance_status == "compliant"
        
        # Test numeric defaults
        assert audit_log.retention_period == 2555  # 7 years
        
        # Test required fields are set
        assert audit_log.event_type == "test"
        assert audit_log.event_category is not None  # Auto-determined
        assert audit_log.record_hash is not None  # Auto-generated
        assert audit_log.id is not None  # Auto-generated UUID
        assert audit_log.timestamp is not None  # Auto-generated


class TestAuditLogEventCategorization:
    """Test event type categorization logic."""
    
    def test_authentication_event_categorization(self):
        """Test authentication events are categorized correctly."""
        auth_events = [
            "login", "logout", "password_change", 
            "mfa_setup", "token_validation"
        ]
        
        for event in auth_events:
            audit_log = AuditLog(
                event_type=event,
                resource_type="test",
                outcome="success"
            )
            assert audit_log.event_category == "authentication"
    
    def test_authorization_event_categorization(self):
        """Test authorization events are categorized correctly."""
        authz_events = [
            "permission_check", "role_assignment", "phi_access_check"
        ]
        
        for event in authz_events:
            audit_log = AuditLog(
                event_type=event,
                resource_type="test",
                outcome="success"
            )
            assert audit_log.event_category == "authorization"
    
    def test_access_event_categorization(self):
        """Test access events are categorized correctly."""
        access_events = [
            "phi_access", "data_view", "record_access", "file_download"
        ]
        
        for event in access_events:
            audit_log = AuditLog(
                event_type=event,
                resource_type="test",
                outcome="success"
            )
            assert audit_log.event_category == "access"
    
    def test_other_event_categorization(self):
        """Test unknown events are categorized as 'other'."""
        other_events = [
            "system_maintenance", "backup_complete", "unknown_event"
        ]
        
        for event in other_events:
            audit_log = AuditLog(
                event_type=event,
                resource_type="test",
                outcome="success"
            )
            assert audit_log.event_category == "other"


class TestAuditLogComplexScenarios:
    """Test complex audit log scenarios."""
    
    def test_phi_access_audit_complete_scenario(self):
        """Test complete PHI access audit log scenario."""
        user_id = uuid4()
        patient_id = uuid4()
        
        audit_log = AuditLog(
            user_id=user_id,
            user_email="physician@hospital.com",
            action="patient_record_access",
            event_type="phi_access_attempt",
            resource_type="patient_data",
            resource_id=str(patient_id),
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 (compatible medical app)",
            details={
                "access_method": "direct_lookup",
                "search_criteria": {"patient_mrn": "12345"},
                "session_context": "emergency_treatment"
            },
            outcome="success",
            request_method="GET",
            request_url=f"/api/patients/{patient_id}",
            response_status="200",
            phi_accessed=True,
            patient_id=patient_id,
            data_elements_accessed=[
                "demographics", "medical_history", "current_medications", "allergies"
            ],
            access_reason="treatment",
            minimum_necessary_applied=True,
            compliance_status="compliant",
            session_id="emergency_session_001",
            device_fingerprint="hospital_workstation_er_03",
            geolocation={"country": "US", "state": "CA", "city": "San Francisco"},
            risk_score=10,  # Low risk - authorized physician, normal hours, hospital network
            workstation_id="ER-WS-03",
            department="Emergency Medicine",
            supervisor_notified=False
        )
        
        # Verify all aspects of the audit log
        assert audit_log.is_phi_event() is True
        assert audit_log.event_category == "access"
        assert audit_log.compliance_status == "compliant"
        assert audit_log.verify_integrity() is True
        assert len(audit_log.data_elements_accessed) == 4
        assert audit_log.minimum_necessary_applied is True
        assert audit_log.risk_score == 10
        
        # Test dictionary conversion
        audit_dict = audit_log.to_dict(include_sensitive=True)
        assert audit_dict["phi_accessed"] is True
        assert len(audit_dict["data_elements_accessed"]) == 4
        
        # Test sanitized export
        sanitized = audit_log.sanitize_for_export()
        assert "phi_accessed" in sanitized
        assert "user_id" not in sanitized  # Sensitive data excluded
        assert "patient_id" not in sanitized  # Sensitive data excluded
    
    def test_failed_phi_access_audit_scenario(self):
        """Test failed PHI access attempt audit log."""
        user_id = uuid4()
        patient_id = uuid4()
        
        audit_log = AuditLog(
            user_id=user_id,
            user_email="nurse@hospital.com",
            action="patient_record_access_denied",
            event_type="phi_access_denied",
            resource_type="patient_data",
            resource_id=str(patient_id),
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.75",
            details={
                "denial_reason": "insufficient_privileges",
                "requested_elements": ["physician_notes", "discharge_summary"],
                "user_role": "NURSE"
            },
            outcome="failure",
            phi_accessed=False,
            patient_id=patient_id,
            compliance_status="access_denied",
            risk_score=30,  # Higher risk - access denied
            department="Medical-Surgical Unit"
        )
        
        # Verify failed access logging
        assert audit_log.phi_accessed is False
        assert audit_log.outcome == "failure"
        assert audit_log.compliance_status == "access_denied"
        assert audit_log.risk_score == 30
        assert "insufficient_privileges" in audit_log.details["denial_reason"]
        
        # Should still be considered a PHI event due to patient_id
        assert audit_log.is_phi_event() is True
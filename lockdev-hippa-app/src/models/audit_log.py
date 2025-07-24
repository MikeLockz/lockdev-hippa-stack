"""
Audit log model for HIPAA compliance.
"""

from datetime import datetime
import hashlib
import json

from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..utils.database import Base


class AuditLog(Base):
    """Audit log model for HIPAA compliance tracking."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who performed the action
    user_id = Column(UUID(as_uuid=True), nullable=True)
    user_email = Column(String(255), nullable=True)

    # What action was performed
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)

    # When and where
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Additional details
    details = Column(JSON, nullable=True)
    outcome = Column(
        String(50), default="success", nullable=False
    )  # success, failure, error

    # Request/Response info
    request_method = Column(String(10), nullable=True)
    request_url = Column(Text, nullable=True)
    response_status = Column(String(10), nullable=True)
    
    # HIPAA-Specific Fields
    phi_accessed = Column(Boolean, default=False, nullable=False)
    patient_id = Column(UUID(as_uuid=True), nullable=True)
    data_elements_accessed = Column(JSON, nullable=True)  # List of data elements accessed
    access_reason = Column(String(500), nullable=True)
    minimum_necessary_applied = Column(Boolean, default=False, nullable=False)
    
    # Compliance Fields
    event_type = Column(String(100), nullable=False)  # authentication, authorization, access, modification
    event_category = Column(String(50), nullable=False)  # authentication, authorization, access
    compliance_status = Column(String(20), default='compliant', nullable=False)  # compliant, violation, under_review
    retention_period = Column(Integer, default=2555, nullable=False)  # Days (7 years default for HIPAA)
    
    # Data Integrity Fields
    record_hash = Column(String(256), nullable=False)  # SHA-256 hash for integrity verification
    previous_hash = Column(String(256), nullable=True)  # Blockchain-style linking for tamper detection
    
    # Security Context
    session_id = Column(String(255), nullable=True)
    device_fingerprint = Column(String(500), nullable=True)
    geolocation = Column(JSON, nullable=True)  # Country, state, city from IP
    risk_score = Column(Integer, nullable=True)  # 0-100 risk assessment
    
    # Workflow Context
    workstation_id = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    supervisor_notified = Column(Boolean, default=False, nullable=False)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_audit_logs_phi_accessed', 'phi_accessed', 'timestamp'),
        Index('idx_audit_logs_user_patient', 'user_id', 'patient_id', 'timestamp'),
        Index('idx_audit_logs_event_type', 'event_type', 'timestamp'),
        Index('idx_audit_logs_compliance_status', 'compliance_status', 'timestamp'),
        Index('idx_audit_logs_user_timestamp', 'user_id', 'timestamp'),
    )

    def __init__(self, **kwargs):
        """Initialize audit log with automatic hash generation."""
        super().__init__(**kwargs)
        
        # Set event_type if not provided (backward compatibility)
        if not hasattr(self, 'event_type') or not self.event_type:
            self.event_type = kwargs.get('action', 'unknown')
        
        # Set event_category based on event_type
        if not hasattr(self, 'event_category') or not self.event_category:
            self.event_category = self._determine_event_category(self.event_type)
        
        # Generate record hash for integrity
        self.record_hash = self._generate_record_hash()

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, event_type={self.event_type}, "
            f"user_id={self.user_id}, phi_accessed={self.phi_accessed})>"
        )

    def _determine_event_category(self, event_type: str) -> str:
        """Determine event category based on event type."""
        auth_events = ['login', 'logout', 'password_change', 'mfa_setup', 'token_validation']
        authz_events = ['permission_check', 'role_assignment', 'phi_access_check']
        access_events = ['phi_access', 'data_view', 'record_access', 'file_download']
        
        if any(event in event_type.lower() for event in auth_events):
            return 'authentication'
        elif any(event in event_type.lower() for event in authz_events):
            return 'authorization'
        elif any(event in event_type.lower() for event in access_events):
            return 'access'
        else:
            return 'other'
    
    def _generate_record_hash(self) -> str:
        """Generate SHA-256 hash of record for integrity verification."""
        # Create a deterministic string representation of key fields
        hash_data = {
            'user_id': str(self.user_id) if self.user_id else '',
            'event_type': self.event_type or '',
            'timestamp': self.timestamp.isoformat() if self.timestamp else '',
            'ip_address': self.ip_address or '',
            'phi_accessed': self.phi_accessed,
            'patient_id': str(self.patient_id) if self.patient_id else '',
            'details': json.dumps(self.details, sort_keys=True) if self.details else ''
        }
        
        # Create hash string
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify record integrity by recomputing hash."""
        return self._generate_record_hash() == self.record_hash
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert audit log to dictionary.
        
        Args:
            include_sensitive: Whether to include sensitive fields like hashes
            
        Returns:
            dict: Audit log data dictionary
        """
        base_data = {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "user_email": self.user_email,
            "action": self.action,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "outcome": self.outcome,
            "compliance_status": self.compliance_status,
            "phi_accessed": self.phi_accessed,
            "minimum_necessary_applied": self.minimum_necessary_applied,
            "details": self.details,
        }
        
        # Add PHI-related fields if PHI was accessed
        if self.phi_accessed:
            base_data.update({
                "patient_id": str(self.patient_id) if self.patient_id else None,
                "data_elements_accessed": self.data_elements_accessed,
                "access_reason": self.access_reason,
            })
        
        # Add sensitive fields if requested
        if include_sensitive:
            base_data.update({
                "record_hash": self.record_hash,
                "previous_hash": self.previous_hash,
                "session_id": self.session_id,
                "device_fingerprint": self.device_fingerprint,
                "geolocation": self.geolocation,
                "risk_score": self.risk_score,
                "workstation_id": self.workstation_id,
                "department": self.department,
                "request_method": self.request_method,
                "request_url": self.request_url,
                "response_status": self.response_status,
                "retention_period": self.retention_period,
            })
        
        return base_data
    
    def is_phi_event(self) -> bool:
        """Check if this audit log entry involves PHI access."""
        return self.phi_accessed or self.patient_id is not None
    
    def get_retention_date(self) -> datetime:
        """Get the date when this record can be purged."""
        from datetime import timedelta
        return self.timestamp + timedelta(days=self.retention_period)
    
    def is_eligible_for_purge(self) -> bool:
        """Check if this record is eligible for purging based on retention policy."""
        return datetime.utcnow() > self.get_retention_date()
    
    def sanitize_for_export(self) -> dict:
        """Sanitize audit log data for external export (remove sensitive fields)."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "event_category": self.event_category,
            "outcome": self.outcome,
            "compliance_status": self.compliance_status,
            "phi_accessed": self.phi_accessed,
            "minimum_necessary_applied": self.minimum_necessary_applied,
            "department": self.department,
            # Exclude: user_id, patient_id, IP address, device info, hashes
        }

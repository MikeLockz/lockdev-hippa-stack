"""
User model for HIPAA-compliant application.
"""

from datetime import datetime
from typing import List

from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..utils.database import Base


class User(Base):
    """User model with HIPAA compliance features."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    # HIPAA compliance fields
    last_login = Column(DateTime, nullable=True)
    login_attempts = Column(String(50), default="0", nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Optional profile fields (be careful with PHI)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(String(50), default="user", nullable=False)
    
    # Enhanced HIPAA Compliance Fields
    phi_access_granted = Column(Boolean, default=False, nullable=False)
    phi_access_reason = Column(String(500), nullable=True)
    phi_access_expiry = Column(DateTime, nullable=True)
    phi_access_supervisor = Column(UUID(as_uuid=True), nullable=True)
    
    # Enhanced Security Fields
    password_history = Column(JSON, default=list, nullable=False)  # Last 12 password hashes
    password_must_change = Column(Boolean, default=False, nullable=False)
    password_expires_at = Column(DateTime, nullable=True)
    
    # Professional Fields for Healthcare Workers
    license_number = Column(String(50), nullable=True)
    license_expiry = Column(DateTime, nullable=True)
    department = Column(String(100), nullable=True)
    supervisor_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Access Control Fields
    workstation_restrictions = Column(JSON, default=list, nullable=False)  # Allowed IP ranges/hostnames
    ip_address_restrictions = Column(JSON, default=list, nullable=False)  # Allowed IP addresses
    time_based_access = Column(JSON, nullable=True)  # Business hours restrictions
    
    # Multi-Factor Authentication
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(32), nullable=True)  # TOTP secret
    mfa_backup_codes = Column(JSON, default=list, nullable=False)
    mfa_last_used = Column(DateTime, nullable=True)
    
    # Session Management
    max_concurrent_sessions = Column(Integer, default=5, nullable=False)
    session_timeout_minutes = Column(Integer, default=480, nullable=False)  # 8 hours default
    
    # Compliance Tracking
    terms_accepted_at = Column(DateTime, nullable=True)
    privacy_policy_accepted_at = Column(DateTime, nullable=True)
    hipaa_training_completed_at = Column(DateTime, nullable=True)
    last_security_review = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user to dictionary.
        
        Args:
            include_sensitive: Whether to include sensitive/PHI fields
            
        Returns:
            dict: User data dictionary
        """
        base_data = {
            "id": str(self.id),
            "email": self.email,
            "is_active": self.is_active,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "last_login": (self.last_login.isoformat() if self.last_login else None),
            "mfa_enabled": self.mfa_enabled,
            "phi_access_granted": self.phi_access_granted,
        }
        
        if include_sensitive:
            base_data.update({
                "first_name": self.first_name,
                "last_name": self.last_name,
                "department": self.department,
                "license_number": self.license_number,
                "license_expiry": (self.license_expiry.isoformat() if self.license_expiry else None),
                "phi_access_expiry": (self.phi_access_expiry.isoformat() if self.phi_access_expiry else None),
                "password_expires_at": (self.password_expires_at.isoformat() if self.password_expires_at else None),
                "password_must_change": self.password_must_change,
                "session_timeout_minutes": self.session_timeout_minutes,
                "max_concurrent_sessions": self.max_concurrent_sessions,
            })
        
        return base_data
    
    def is_phi_access_valid(self) -> bool:
        """Check if user's PHI access is currently valid."""
        if not self.phi_access_granted:
            return False
        
        if self.phi_access_expiry and self.phi_access_expiry < datetime.utcnow():
            return False
            
        return True
    
    def is_password_expired(self) -> bool:
        """Check if user's password has expired."""
        if not self.password_expires_at:
            return False
        
        return self.password_expires_at < datetime.utcnow()
    
    def is_license_valid(self) -> bool:
        """Check if user's professional license is valid."""
        if not self.license_number or not self.license_expiry:
            return True  # No license required or not set
        
        return self.license_expiry > datetime.utcnow()
    
    def needs_hipaa_training(self) -> bool:
        """Check if user needs HIPAA training (annual requirement)."""
        if not self.hipaa_training_completed_at:
            return True
        
        # HIPAA training required annually
        training_expires = datetime(
            self.hipaa_training_completed_at.year + 1,
            self.hipaa_training_completed_at.month,
            self.hipaa_training_completed_at.day
        )
        
        return datetime.utcnow() > training_expires

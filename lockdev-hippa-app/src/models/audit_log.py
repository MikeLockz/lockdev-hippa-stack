"""
Audit log model for HIPAA compliance.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Text, JSON
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
    outcome = Column(String(50), default="success", nullable=False)  # success, failure, error
    
    # Request/Response info
    request_method = Column(String(10), nullable=True)
    request_url = Column(Text, nullable=True)
    response_status = Column(String(10), nullable=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id})>"
    
    def to_dict(self) -> dict:
        """Convert audit log to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "user_email": self.user_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "outcome": self.outcome,
            "request_method": self.request_method,
            "request_url": self.request_url,
            "response_status": self.response_status,
            "details": self.details
        }
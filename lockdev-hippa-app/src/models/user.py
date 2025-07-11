"""
User model for HIPAA-compliant application.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, DateTime, Text
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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
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
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
    
    def to_dict(self) -> dict:
        """Convert user to dictionary (excluding sensitive fields)."""
        return {
            "id": str(self.id),
            "email": self.email,
            "is_active": self.is_active,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None
        }
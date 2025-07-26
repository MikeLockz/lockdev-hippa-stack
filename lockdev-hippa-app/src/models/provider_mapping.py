"""
Provider User Mapping Model

This module defines the database model for mapping local users to external
authentication provider users, enabling seamless user migration and synchronization
between different authentication providers while maintaining HIPAA compliance.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, 
    UUID, 
    String, 
    DateTime, 
    ForeignKey, 
    JSON, 
    Boolean,
    Index, 
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.base import Base


class ProviderUserMapping(Base):
    """
    Maps local database users to external authentication provider users.
    
    This model maintains bidirectional relationships between local users and
    users in external authentication providers (Cognito, Auth0, etc.), enabling:
    - Seamless user migration between providers
    - Bidirectional user synchronization
    - Audit trail for provider changes
    - Session preservation during migrations
    
    HIPAA Compliance:
    - All user identifier mappings are stored securely
    - Audit trail tracks all provider changes
    - Data retention policies applied to mapping records
    - No PHI stored in mapping records
    """
    
    __tablename__ = "provider_user_mappings"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        comment="Unique identifier for this mapping record"
    )
    
    # Local user reference
    local_user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to the local user record"
    )
    
    # Provider identification
    provider_type = Column(
        String(50), 
        nullable=False,
        comment="Authentication provider type (custom, aws_cognito, auth0, supabase, etc.)"
    )
    
    # External provider user identifiers
    provider_user_id = Column(
        String(255), 
        nullable=False,
        comment="User ID in the external authentication provider"
    )
    
    provider_username = Column(
        String(255), 
        nullable=True,
        comment="Username in the external provider (may differ from local username)"
    )
    
    # Synchronization metadata
    last_sync_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Last successful synchronization timestamp"
    )
    
    sync_status = Column(
        String(20), 
        default="active",
        comment="Current synchronization status: active, disabled, error"
    )
    
    sync_errors = Column(
        JSON, 
        nullable=True,
        comment="JSON array of synchronization error details"
    )
    
    # Migration tracking
    migration_batch_id = Column(
        UUID(as_uuid=True), 
        nullable=True,
        comment="UUID linking this record to a specific migration batch"
    )
    
    migration_status = Column(
        String(20), 
        nullable=True,
        comment="Migration status: pending, completed, failed, rolled_back"
    )
    
    # Metadata preservation during migration
    provider_metadata = Column(
        JSON, 
        nullable=True,
        comment="Provider-specific metadata preserved during migration"
    )
    
    # Audit fields
    created_at = Column(
        DateTime(timezone=True), 
        default=func.now(),
        comment="Record creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(),
        comment="Record last update timestamp"
    )
    
    # Soft delete for audit trail
    deleted_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Soft delete timestamp - maintains audit trail"
    )
    
    # Relationships
    local_user = relationship(
        "User", 
        back_populates="provider_mappings",
        lazy="select"
    )
    
    # Indexes and constraints
    __table_args__ = (
        # Ensure unique mapping for each user-provider combination
        UniqueConstraint(
            'local_user_id', 
            'provider_type', 
            name='uq_user_provider'
        ),
        
        # Ensure unique provider user ID per provider type
        UniqueConstraint(
            'provider_type', 
            'provider_user_id', 
            name='uq_provider_user'
        ),
        
        # Index for quick lookups by provider and user
        Index(
            'idx_provider_user_lookup', 
            'provider_type', 
            'provider_user_id'
        ),
        
        # Index for finding all mappings for a local user
        Index(
            'idx_local_user_mappings', 
            'local_user_id'
        ),
        
        # Index for migration batch processing
        Index(
            'idx_migration_batch', 
            'migration_batch_id'
        ),
        
        # Index for sync status queries
        Index(
            'idx_sync_status', 
            'sync_status', 
            'last_sync_at'
        ),
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"ProviderUserMapping("
            f"id={self.id}, "
            f"local_user_id={self.local_user_id}, "
            f"provider_type={self.provider_type}, "
            f"provider_user_id={self.provider_user_id}, "
            f"sync_status={self.sync_status}"
            f")"
        )
    
    @property
    def is_active(self) -> bool:
        """Check if this mapping is currently active."""
        return (
            self.sync_status == "active" 
            and self.deleted_at is None
        )
    
    @property
    def is_migrated(self) -> bool:
        """Check if this user has been successfully migrated."""
        return self.migration_status == "completed"
    
    @property
    def sync_age_hours(self) -> Optional[float]:
        """Get age of last sync in hours."""
        if not self.last_sync_at:
            return None
        return (datetime.utcnow() - self.last_sync_at.replace(tzinfo=None)).total_seconds() / 3600
    
    def mark_sync_error(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark this mapping with a sync error."""
        self.sync_status = "error"
        
        if self.sync_errors is None:
            self.sync_errors = []
        
        self.sync_errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": error_message,
            "details": error_details or {}
        })
        
        # Keep only last 5 errors to prevent unbounded growth
        if len(self.sync_errors) > 5:
            self.sync_errors = self.sync_errors[-5:]
    
    def mark_sync_success(self):
        """Mark this mapping as successfully synchronized."""
        self.sync_status = "active"
        self.last_sync_at = datetime.utcnow()
        self.sync_errors = None  # Clear any previous errors
    
    def mark_for_deletion(self):
        """Soft delete this mapping while preserving audit trail."""
        self.deleted_at = datetime.utcnow()
        self.sync_status = "disabled"
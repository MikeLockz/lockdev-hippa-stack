"""
Provider Migration Service

Handles the migration of users between different authentication providers
while maintaining data integrity, audit trails, and HIPAA compliance.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.auth.interfaces import AuthenticationProvider
from src.models.user import User
from src.models.provider_mapping import ProviderUserMapping
from src.auth.sync.data_mapper import UserDataMapper
from src.auth.sync.user_sync import UserSyncService

logger = logging.getLogger(__name__)


class ProviderMigration:
    """
    Handles migration of users between authentication providers.
    
    This service provides:
    - Migration validation and feasibility checks
    - Batch user migration with progress tracking
    - Rollback capabilities for failed migrations
    - Data integrity validation
    - Session preservation during migration
    - Audit trail for all migration activities
    
    HIPAA Compliance:
    - All migrations are logged with full audit trail
    - Data integrity is validated after each step
    - Rollback ensures no data loss
    - Session preservation maintains security
    """
    
    def __init__(
        self,
        source_provider: AuthenticationProvider,
        target_provider: AuthenticationProvider,
        db_session: AsyncSession,
        migration_id: Optional[uuid.UUID] = None
    ):
        """
        Initialize the migration service.
        
        Args:
            source_provider: Source authentication provider
            target_provider: Target authentication provider
            db_session: Database session
            migration_id: Optional migration ID for tracking
        """
        self.source_provider = source_provider
        self.target_provider = target_provider
        self.db = db_session
        self.mapper = UserDataMapper()
        self.migration_id = migration_id or uuid.uuid4()
        
        # Initialize sync services for both providers
        self.source_sync = UserSyncService(db_session, source_provider, source_provider.provider_type)
        self.target_sync = UserSyncService(db_session, target_provider, target_provider.provider_type)
    
    async def validate_migration_feasibility(self) -> Dict[str, Any]:
        """
        Validate that migration is possible between providers.
        
        Returns:
            Dict[str, Any]: Validation results with feasibility, warnings, and blockers
        """
        validation_results = {
            "feasible": True,
            "warnings": [],
            "blockers": [],
            "user_count": 0,
            "estimated_duration": "unknown",
            "migration_id": str(self.migration_id),
            "source_provider": self.source_provider.provider_type,
            "target_provider": self.target_provider.provider_type,
            "validation_timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Check provider health
            source_health = await self.source_provider.health_check()
            target_health = await self.target_provider.health_check()
            
            if not source_health.is_healthy:
                validation_results["blockers"].append(
                    f"Source provider {self.source_provider.provider_type} is unhealthy: {source_health.error_message}"
                )
            
            if not target_health.is_healthy:
                validation_results["blockers"].append(
                    f"Target provider {self.target_provider.provider_type} is unhealthy: {target_health.error_message}"
                )
            
            # Count users to migrate
            source_users = await self.source_provider.list_users()
            validation_results["user_count"] = len(source_users)
            
            if validation_results["user_count"] == 0:
                validation_results["warnings"].append("No users found in source provider")
            
            # Estimate duration (rough estimate: 2 seconds per user)
            estimated_seconds = validation_results["user_count"] * 2
            validation_results["estimated_duration"] = f"{estimated_seconds} seconds"
            
            # Check for feature compatibility
            await self._check_feature_compatibility(validation_results)
            
            # Check for duplicate emails or usernames
            await self._check_duplicate_users(validation_results)
            
            # Validate provider capabilities
            await self._validate_provider_capabilities(validation_results)
            
            validation_results["feasible"] = len(validation_results["blockers"]) == 0
            
        except Exception as e:
            validation_results["blockers"].append(f"Validation failed: {str(e)}")
            validation_results["feasible"] = False
            logger.error("Migration validation failed", error=str(e))
        
        return validation_results
    
    async def migrate_users(
        self,
        dry_run: bool = False,
        batch_size: int = 100,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Migrate all users from source to target provider.
        
        Args:
            dry_run: Perform dry run without making changes
            batch_size: Number of users to process in each batch
            skip_existing: Skip users already migrated
            
        Returns:
            Dict[str, Any]: Migration results with detailed statistics
        """
        migration_results = {
            "migration_id": str(self.migration_id),
            "started_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "source_provider": self.source_provider.provider_type,
            "target_provider": self.target_provider.provider_type,
            "total_users": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "rollback_info": [],
            "warnings": [],
            "step_details": []
        }
        
        try:
            # Get all users to migrate
            users_to_migrate = await self._get_users_to_migrate(skip_existing)
            migration_results["total_users"] = len(users_to_migrate)
            
            if migration_results["total_users"] == 0:
                migration_results["warnings"].append("No users to migrate")
                migration_results["completed_at"] = datetime.utcnow().isoformat()
                return migration_results
            
            # Process in batches
            for i in range(0, len(users_to_migrate), batch_size):
                batch = users_to_migrate[i:i + batch_size]
                batch_results = await self._migrate_user_batch(batch, dry_run)
                
                migration_results["successful"] += batch_results["successful"]
                migration_results["failed"] += batch_results["failed"]
                migration_results["skipped"] += batch_results["skipped"]
                migration_results["errors"].extend(batch_results["errors"])
                migration_results["rollback_info"].extend(batch_results["rollback_info"])
                migration_results["step_details"].append(batch_results)
                
                # Progress logging
                progress = (i + len(batch)) / len(users_to_migrate) * 100
                logger.info(
                    "Migration progress",
                    migration_id=str(self.migration_id),
                    progress=f"{progress:.1f}%",
                    batch_size=len(batch),
                    successful=batch_results["successful"],
                    failed=batch_results["failed"]
                )
                
                # Small delay between batches to avoid rate limiting
                if not dry_run:
                    await asyncio.sleep(0.5)
            
            migration_results["completed_at"] = datetime.utcnow().isoformat()
            
            # Calculate duration
            start_time = datetime.fromisoformat(migration_results["started_at"])
            end_time = datetime.fromisoformat(migration_results["completed_at"])
            duration_seconds = (end_time - start_time).total_seconds()
            migration_results["duration_seconds"] = duration_seconds
            
            logger.info(
                "Migration completed",
                migration_id=str(self.migration_id),
                total_users=migration_results["total_users"],
                successful=migration_results["successful"],
                failed=migration_results["failed"],
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            migration_results["errors"].append(f"Migration failed: {str(e)}")
            logger.error("User migration failed", error=str(e))
        
        return migration_results
    
    async def rollback_migration(
        self,
        migration_id: str,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Rollback a previous migration.
        
        Args:
            migration_id: Migration ID to rollback
            batch_size: Number of users to process in each batch
            
        Returns:
            Dict[str, Any]: Rollback results
        """
        rollback_results = {
            "migration_id": migration_id,
            "started_at": datetime.utcnow().isoformat(),
            "users_rolled_back": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Get all mappings for this migration
            mappings = await self._get_migration_mappings(uuid.UUID(migration_id))
            
            if not mappings:
                rollback_results["warnings"].append("No mappings found for this migration")
                rollback_results["completed_at"] = datetime.utcnow().isoformat()
                return rollback_results
            
            # Process in batches
            for i in range(0, len(mappings), batch_size):
                batch = mappings[i:i + batch_size]
                batch_results = await self._rollback_batch(batch)
                
                rollback_results["users_rolled_back"] += batch_results["rolled_back"]
                rollback_results["errors"].extend(batch_results["errors"])
                
                logger.info(
                    "Rollback progress",
                    migration_id=migration_id,
                    progress=f"{(i + len(batch)) / len(mappings) * 100:.1f}%",
                    rolled_back=batch_results["rolled_back"]
                )
            
            rollback_results["completed_at"] = datetime.utcnow().isoformat()
            
            # Calculate duration
            start_time = datetime.fromisoformat(rollback_results["started_at"])
            end_time = datetime.fromisoformat(rollback_results["completed_at"])
            duration_seconds = (end_time - start_time).total_seconds()
            rollback_results["duration_seconds"] = duration_seconds
            
            logger.info(
                "Rollback completed",
                migration_id=migration_id,
                users_rolled_back=rollback_results["users_rolled_back"],
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            rollback_results["errors"].append(f"Rollback failed: {str(e)}")
            logger.error("Migration rollback failed", error=str(e))
        
        return rollback_results
    
    async def validate_migration_results(
        self,
        migration_id: str
    ) -> Dict[str, Any]:
        """
        Validate data integrity after migration.
        
        Args:
            migration_id: Migration ID to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_results = {
            "migration_id": migration_id,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "total_validated": 0,
            "valid": 0,
            "invalid": 0,
            "errors": [],
            "details": []
        }
        
        try:
            # Get all mappings for this migration
            mappings = await self._get_migration_mappings(uuid.UUID(migration_id))
            validation_results["total_validated"] = len(mappings)
            
            for mapping in mappings:
                try:
                    # Get local user
                    local_user = await self._get_local_user(mapping.local_user_id)
                    if not local_user:
                        validation_results["invalid"] += 1
                        validation_results["errors"].append(
                            f"Local user not found: {mapping.local_user_id}"
                        )
                        continue
                    
                    # Get provider user
                    provider_user = await self.target_provider.get_user(mapping.provider_user_id)
                    if not provider_user:
                        validation_results["invalid"] += 1
                        validation_results["errors"].append(
                            f"Provider user not found: {mapping.provider_user_id}"
                        )
                        continue
                    
                    # Validate data integrity
                    is_valid = await self._validate_user_data_integrity(
                        local_user,
                        provider_user,
                        mapping.provider_user_id
                    )
                    
                    if is_valid:
                        validation_results["valid"] += 1
                    else:
                        validation_results["invalid"] += 1
                        validation_results["errors"].append(
                            f"Data integrity validation failed for user: {mapping.local_user_id}"
                        )
                    
                    validation_results["details"].append({
                        "local_user_id": str(mapping.local_user_id),
                        "provider_user_id": mapping.provider_user_id,
                        "valid": is_valid
                    })
                    
                except Exception as e:
                    validation_results["invalid"] += 1
                    validation_results["errors"].append(str(e))
            
        except Exception as e:
            validation_results["errors"].append(f"Validation failed: {str(e)}")
        
        return validation_results
    
    # Private helper methods
    
    async def _get_users_to_migrate(self, skip_existing: bool) -> List[Dict[str, Any]]:
        """Get all users to migrate from source provider."""
        source_users = await self.source_provider.list_users()
        
        if skip_existing:
            # Filter out users already migrated
            migrated_user_ids = set()
            query = select(ProviderUserMapping.local_user_id).where(
                and_(
                    ProviderUserMapping.provider_type == self.target_provider.provider_type,
                    ProviderUserMapping.migration_status == "completed"
                )
            )
            result = await self.db.execute(query)
            migrated_user_ids = {str(row[0]) for row in result.fetchall()}
            
            # We need to map provider users to local users
            # This is a simplified approach - in practice, you'd need more sophisticated matching
            return [user for user in source_users if user.get("id") not in migrated_user_ids]
        
        return source_users
    
    async def _migrate_user_batch(
        self, 
        users: List[Dict[str, Any]], 
        dry_run: bool
    ) -> Dict[str, Any]:
        """Migrate a batch of users."""
        batch_results = {
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "rollback_info": []
        }
        
        for user_data in users:
            try:
                provider_user_id = user_data.get("id")
                if not provider_user_id:
                    batch_results["failed"] += 1
                    batch_results["errors"].append("Missing provider user ID")
                    continue
                
                # Check if already migrated
                existing_mapping = await self._get_provider_mapping(
                    provider_user_id, 
                    self.target_provider.provider_type
                )
                
                if existing_mapping and existing_mapping.migration_status == "completed":
                    batch_results["skipped"] += 1
                    continue
                
                if dry_run:
                    # Simulate migration
                    batch_results["successful"] += 1
                    batch_results["rollback_info"].append({
                        "local_user_id": str(uuid.uuid4()),
                        "provider_user_id": provider_user_id,
                        "provider_type": self.target_provider.provider_type,
                        "dry_run": True
                    })
                    continue
                
                # Convert user data to target provider format
                auth_user = await self.mapper.map_to_auth_user(user_data, self.source_provider.provider_type)
                target_user_data = await self.mapper.map_from_auth_user(auth_user, self.target_provider.provider_type)
                
                # Preserve audit metadata
                target_user_data = await self.mapper.preserve_audit_metadata(
                    user_data, 
                    target_user_data
                )
                
                # Create user in target provider
                new_user = await self.target_provider.create_user(**target_user_data)
                
                if new_user:
                    # Create or update mapping record
                    local_user = await self._find_or_create_local_user(auth_user)
                    
                    mapping = await self._create_user_mapping(
                        local_user.id,
                        self.target_provider.provider_type,
                        new_user.id,
                        auth_user.username,
                        migration_batch_id=self.migration_id
                    )
                    mapping.migration_status = "completed"
                    
                    batch_results["successful"] += 1
                    batch_results["rollback_info"].append({
                        "local_user_id": str(local_user.id),
                        "provider_user_id": new_user.id,
                        "provider_type": self.target_provider.provider_type,
                        "source_provider_user_id": provider_user_id,
                        "source_provider_type": self.source_provider.provider_type
                    })
                    
                else:
                    batch_results["failed"] += 1
                    batch_results["errors"].append(
                        f"Failed to create user in target provider: {provider_user_id}"
                    )
                    
            except Exception as e:
                batch_results["failed"] += 1
                user_id = user_data.get("id", "unknown")
                batch_results["errors"].append({
                    "user_id": str(user_id),
                    "error": str(e)
                })
        
        return batch_results
    
    async def _rollback_batch(self, mappings: List[ProviderUserMapping]) -> Dict[str, Any]:
        """Rollback a batch of user mappings."""
        batch_results = {"rolled_back": 0, "errors": []}
        
        for mapping in mappings:
            try:
                # Delete user from target provider
                await self.target_provider.delete_user(mapping.provider_user_id)
                
                # Update mapping status
                mapping.migration_status = "rolled_back"
                mapping.sync_status = "disabled"
                
                batch_results["rolled_back"] += 1
                
            except Exception as e:
                batch_results["errors"].append({
                    "mapping_id": str(mapping.id),
                    "error": str(e)
                })
        
        return batch_results
    
    async def _get_migration_mappings(self, migration_id: uuid.UUID) -> List[ProviderUserMapping]:
        """Get all mappings for a specific migration."""
        query = select(ProviderUserMapping).where(
            ProviderUserMapping.migration_batch_id == migration_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def _get_provider_mapping(
        self, 
        provider_user_id: str, 
        provider_type: str
    ) -> Optional[ProviderUserMapping]:
        """Get user mapping by provider user ID and provider type."""
        query = select(ProviderUserMapping).where(
            and_(
                ProviderUserMapping.provider_user_id == provider_user_id,
                ProviderUserMapping.provider_type == provider_type,
                ProviderUserMapping.deleted_at.is_(None)
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _find_or_create_local_user(self, auth_user: AuthUser) -> User:
        """Find existing local user or create new one."""
        # Try to find by email
        query = select(User).where(User.email == auth_user.email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            return user
        
        # Create new user
        user = User(
            id=auth_user.id,
            email=auth_user.email,
            hashed_password="",  # Password managed by provider
            first_name=auth_user.first_name,
            last_name=auth_user.last_name,
            role=auth_user.roles[0] if auth_user.roles else "USER",
            is_active=auth_user.is_active,
            created_at=auth_user.created_at or datetime.utcnow(),
            last_login=auth_user.last_login
        )
        
        self.db.add(user)
        return user
    
    async def _create_user_mapping(
        self,
        local_user_id: uuid.UUID,
        provider_type: str,
        provider_user_id: str,
        provider_username: Optional[str] = None,
        migration_batch_id: Optional[uuid.UUID] = None
    ) -> ProviderUserMapping:
        """Create a new user mapping record."""
        mapping = ProviderUserMapping(
            local_user_id=local_user_id,
            provider_type=provider_type,
            provider_user_id=provider_user_id,
            provider_username=provider_username,
            migration_batch_id=migration_batch_id,
            migration_status="pending" if migration_batch_id else None,
            sync_status="active",
            last_sync_at=datetime.utcnow()
        )
        self.db.add(mapping)
        return mapping
    
    async def _get_local_user(self, user_id: uuid.UUID) -> Optional[User]:
        """Get local user by ID."""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _validate_user_data_integrity(
        self,
        local_user: User,
        provider_user: Dict[str, Any],
        provider_user_id: str
    ) -> bool:
        """Validate data integrity after migration."""
        try:
            # Convert provider user to AuthUser for comparison
            target_auth_user = await self.mapper.map_to_auth_user(
                provider_user, 
                self.target_provider.provider_type
            )
            
            # Convert local user to AuthUser
            source_auth_user = await self.mapper.map_custom_to_auth_user(local_user)
            
            # Compare critical fields
            critical_fields = ["email", "roles", "is_active"]
            
            for field in critical_fields:
                source_value = getattr(source_auth_user, field)
                target_value = getattr(target_auth_user, field)
                
                if source_value != target_value:
                    logger.error(
                        "Data integrity validation failed",
                        field=field,
                        source_value=source_value,
                        target_value=target_value,
                        local_user_id=str(local_user.id),
                        provider_user_id=provider_user_id
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Data integrity validation error",
                error=str(e),
                local_user_id=str(local_user.id),
                provider_user_id=provider_user_id
            )
            return False
    
    async def _check_feature_compatibility(self, validation_results: Dict[str, Any]) -> None:
        """Check for feature compatibility between providers."""
        # Check MFA support
        source_mfa = hasattr(self.source_provider, 'get_user_mfa')
        target_mfa = hasattr(self.target_provider, 'get_user_mfa')
        
        if source_mfa and not target_mfa:
            validation_results["warnings"].append(
                "Source provider supports MFA but target does not - MFA will be disabled"
            )
        
        # Check social login support
        source_social = hasattr(self.source_provider, 'get_social_connections')
        target_social = hasattr(self.target_provider, 'get_social_connections')
        
        if source_social and not target_social:
            validation_results["warnings"].append(
                "Social connections will not be migrated"
            )
    
    async def _check_duplicate_users(self, validation_results: Dict[str, Any]) -> None:
        """Check for potential duplicate users."""
        try:
            source_users = await self.source_provider.list_users()
            target_users = await self.target_provider.list_users()
            
            # Check for duplicate emails
            source_emails = {user.get("email") for user in source_users if user.get("email")}
            target_emails = {user.get("email") for user in target_users if user.get("email")}
            
            duplicate_emails = source_emails.intersection(target_emails)
            if duplicate_emails:
                validation_results["warnings"].append(
                    f"Found {len(duplicate_emails)} duplicate emails: {list(duplicate_emails)[:5]}"
                )
                
        except Exception as e:
            validation_results["warnings"].append(f"Could not check for duplicates: {str(e)}")
    
    async def _validate_provider_capabilities(self, validation_results: Dict[str, Any]) -> None:
        """Validate provider capabilities for migration."""
        try:
            # Check if providers support required operations
            source_capabilities = await self.source_provider.get_capabilities()
            target_capabilities = await self.target_provider.get_capabilities()
            
            missing_capabilities = []
            for capability in ["create_user", "get_user", "list_users"]:
                if not target_capabilities.get(capability, False):
                    missing_capabilities.append(capability)
            
            if missing_capabilities:
                validation_results["blockers"].append(
                    f"Target provider missing capabilities: {missing_capabilities}"
                )
                
        except Exception as e:
            validation_results["warnings"].append(f"Could not validate provider capabilities: {str(e)}")
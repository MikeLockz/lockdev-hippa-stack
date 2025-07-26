"""
User Synchronization Service

Handles bidirectional user synchronization between local database and external
authentication providers while maintaining data consistency and HIPAA compliance.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.auth.interfaces import AuthenticationProvider
from src.models.user import User
from src.models.provider_mapping import ProviderUserMapping
from src.auth.sync.data_mapper import UserDataMapper

logger = logging.getLogger(__name__)


class UserSyncService:
    """
    Handles bidirectional user synchronization between providers and local database.
    
    This service provides:
    - Bidirectional sync (local ↔ provider)
    - Conflict resolution
    - Batch processing
    - Error handling and recovery
    - Audit trail maintenance
    - HIPAA-compliant data handling
    
    HIPAA Compliance:
    - All sync operations are logged
    - Data integrity is validated
    - No PHI leakage during sync
    - Audit trail for all changes
    """
    
    def __init__(
        self, 
        db_session: AsyncSession, 
        provider: AuthenticationProvider,
        provider_type: str
    ):
        """
        Initialize the sync service.
        
        Args:
            db_session: Database session
            provider: Authentication provider instance
            provider_type: Type of authentication provider
        """
        self.db = db_session
        self.provider = provider
        self.provider_type = provider_type
        self.mapper = UserDataMapper()
    
    async def sync_user_to_provider(
        self, 
        local_user: User, 
        force_update: bool = False
    ) -> bool:
        """
        Sync local user changes to external provider.
        
        Args:
            local_user: Local user object to sync
            force_update: Force update even if sync is recent
            
        Returns:
            bool: True if sync successful
        """
        try:
            # Get existing mapping
            mapping = await self._get_user_mapping(local_user.id, self.provider_type)
            
            # Check if sync is needed
            if not force_update and mapping and mapping.sync_age_hours and mapping.sync_age_hours < 1:
                logger.info(
                    "User sync not needed - recently synced",
                    user_id=str(local_user.id),
                    provider_type=self.provider_type,
                    last_sync_age_hours=mapping.sync_age_hours
                )
                return True
            
            # Convert to provider format
            provider_data = await self.mapper.map_from_auth_user(
                await self.mapper.map_custom_to_auth_user(local_user),
                self.provider_type
            )
            
            if mapping:
                # Update existing user in provider
                success = await self.provider.update_user(
                    mapping.provider_user_id,
                    **provider_data
                )
                
                if success:
                    mapping.mark_sync_success()
                    logger.info(
                        "Updated user in provider",
                        user_id=str(local_user.id),
                        provider_user_id=mapping.provider_user_id,
                        provider_type=self.provider_type
                    )
                else:
                    mapping.mark_sync_error("Failed to update user in provider")
                    logger.error(
                        "Failed to update user in provider",
                        user_id=str(local_user.id),
                        provider_user_id=mapping.provider_user_id,
                        provider_type=self.provider_type
                    )
            else:
                # Create new user in provider
                new_user = await self.provider.create_user(**provider_data)
                
                if new_user:
                    # Create mapping record
                    await self._create_user_mapping(
                        local_user.id,
                        self.provider_type,
                        new_user.id,
                        new_user.get("username", local_user.email)
                    )
                    logger.info(
                        "Created user in provider",
                        user_id=str(local_user.id),
                        provider_user_id=new_user.id,
                        provider_type=self.provider_type
                    )
                    success = True
                else:
                    logger.error(
                        "Failed to create user in provider",
                        user_id=str(local_user.id),
                        provider_type=self.provider_type
                    )
                    success = False
            
            await self.db.commit()
            return success
            
        except Exception as e:
            logger.error(
                "Error syncing user to provider",
                user_id=str(local_user.id),
                provider_type=self.provider_type,
                error=str(e)
            )
            await self.db.rollback()
            return False
    
    async def sync_user_from_provider(
        self, 
        provider_user_id: str,
        force_update: bool = False
    ) -> bool:
        """
        Sync provider user changes to local database.
        
        Args:
            provider_user_id: Provider's user ID
            force_update: Force update even if sync is recent
            
        Returns:
            bool: True if sync successful
        """
        try:
            # Get user from provider
            provider_user = await self.provider.get_user(provider_user_id)
            if not provider_user:
                logger.error(
                    "User not found in provider",
                    provider_user_id=provider_user_id,
                    provider_type=self.provider_type
                )
                return False
            
            # Find local mapping
            mapping = await self._get_provider_mapping(provider_user_id, self.provider_type)
            
            # Convert to AuthUser
            auth_user = await self.mapper.map_to_auth_user(provider_user, self.provider_type)
            
            if mapping:
                # Update existing local user
                local_user = await self._get_local_user(mapping.local_user_id)
                if not local_user:
                    logger.error(
                        "Local user not found for mapping",
                        mapping_id=str(mapping.id),
                        local_user_id=str(mapping.local_user_id)
                    )
                    return False
                
                await self._update_local_user(local_user, auth_user)
                mapping.mark_sync_success()
                
                logger.info(
                    "Updated local user from provider",
                    local_user_id=str(local_user.id),
                    provider_user_id=provider_user_id,
                    provider_type=self.provider_type
                )
                
            else:
                # Create new local user
                local_user = await self._create_local_user_from_auth_user(auth_user)
                
                # Create mapping record
                await self._create_user_mapping(
                    local_user.id,
                    self.provider_type,
                    provider_user_id,
                    auth_user.username
                )
                
                logger.info(
                    "Created local user from provider",
                    local_user_id=str(local_user.id),
                    provider_user_id=provider_user_id,
                    provider_type=self.provider_type
                )
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(
                "Error syncing user from provider",
                provider_user_id=provider_user_id,
                provider_type=self.provider_type,
                error=str(e)
            )
            await self.db.rollback()
            return False
    
    async def bulk_sync_users(
        self, 
        direction: str = "both",
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Perform bulk synchronization of all users.
        
        Args:
            direction: Sync direction - "to_provider", "from_provider", or "both"
            batch_size: Number of users to process in each batch
            
        Returns:
            Dict[str, Any]: Sync results with counts and errors
        """
        results = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "direction": direction,
            "provider_type": self.provider_type,
            "started_at": datetime.utcnow(),
            "completed_at": None
        }
        
        try:
            if direction in ["to_provider", "both"]:
                # Sync all local users to provider
                local_users = await self._get_all_local_users()
                
                for i in range(0, len(local_users), batch_size):
                    batch = local_users[i:i + batch_size]
                    batch_results = await self._process_batch(
                        batch, 
                        self.sync_user_to_provider,
                        "to_provider"
                    )
                    
                    results["total_processed"] += batch_results["total"]
                    results["successful"] += batch_results["successful"]
                    results["failed"] += batch_results["failed"]
                    results["errors"].extend(batch_results["errors"])
                    
                    logger.info(
                        "Batch sync to provider completed",
                        batch_size=len(batch),
                        successful=batch_results["successful"],
                        failed=batch_results["failed"]
                    )
            
            if direction in ["from_provider", "both"]:
                # Sync all provider users to local
                provider_users = await self.provider.list_users()
                
                for i in range(0, len(provider_users), batch_size):
                    batch = provider_users[i:i + batch_size]
                    batch_results = await self._process_batch(
                        batch,
                        lambda user_id: self.sync_user_from_provider(user_id),
                        "from_provider"
                    )
                    
                    results["total_processed"] += batch_results["total"]
                    results["successful"] += batch_results["successful"]
                    results["failed"] += batch_results["failed"]
                    results["errors"].extend(batch_results["errors"])
                    
                    logger.info(
                        "Batch sync from provider completed",
                        batch_size=len(batch),
                        successful=batch_results["successful"],
                        failed=batch_results["failed"]
                    )
            
            results["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            logger.error(
                "Bulk sync failed",
                provider_type=self.provider_type,
                direction=direction,
                error=str(e)
            )
            results["errors"].append(str(e))
        
        return results
    
    async def get_sync_status(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get synchronization status for a specific user.
        
        Args:
            user_id: Local user ID
            
        Returns:
            Dict[str, Any]: Sync status information
        """
        mapping = await self._get_user_mapping(user_id, self.provider_type)
        
        if not mapping:
            return {
                "user_id": str(user_id),
                "provider_type": self.provider_type,
                "status": "not_mapped",
                "last_sync_at": None,
                "sync_age_hours": None,
                "sync_errors": []
            }
        
        return {
            "user_id": str(user_id),
            "provider_type": self.provider_type,
            "status": mapping.sync_status,
            "last_sync_at": mapping.last_sync_at.isoformat() if mapping.last_sync_at else None,
            "sync_age_hours": mapping.sync_age_hours,
            "sync_errors": mapping.sync_errors or [],
            "provider_user_id": mapping.provider_user_id,
            "migration_status": mapping.migration_status
        }
    
    async def resolve_sync_conflicts(
        self, 
        user_id: uuid.UUID,
        conflict_resolution: str = "provider_wins"
    ) -> bool:
        """
        Resolve synchronization conflicts.
        
        Args:
            user_id: Local user ID
            conflict_resolution: Resolution strategy ("provider_wins", "local_wins", "manual")
            
        Returns:
            bool: True if conflicts resolved
        """
        try:
            mapping = await self._get_user_mapping(user_id, self.provider_type)
            if not mapping:
                return False
            
            if conflict_resolution == "provider_wins":
                return await self.sync_user_from_provider(mapping.provider_user_id, force_update=True)
            elif conflict_resolution == "local_wins":
                local_user = await self._get_local_user(user_id)
                return await self.sync_user_to_provider(local_user, force_update=True)
            else:
                logger.warning(
                    "Manual conflict resolution not implemented",
                    user_id=str(user_id)
                )
                return False
                
        except Exception as e:
            logger.error(
                "Error resolving sync conflicts",
                user_id=str(user_id),
                error=str(e)
            )
            return False
    
    # Private helper methods
    
    async def _get_user_mapping(
        self, 
        local_user_id: uuid.UUID, 
        provider_type: str
    ) -> Optional[ProviderUserMapping]:
        """Get user mapping by local user ID and provider type."""
        query = select(ProviderUserMapping).where(
            and_(
                ProviderUserMapping.local_user_id == local_user_id,
                ProviderUserMapping.provider_type == provider_type,
                ProviderUserMapping.deleted_at.is_(None)
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
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
    
    async def _create_user_mapping(
        self,
        local_user_id: uuid.UUID,
        provider_type: str,
        provider_user_id: str,
        provider_username: Optional[str] = None
    ) -> ProviderUserMapping:
        """Create a new user mapping record."""
        mapping = ProviderUserMapping(
            local_user_id=local_user_id,
            provider_type=provider_type,
            provider_user_id=provider_user_id,
            provider_username=provider_username,
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
    
    async def _get_all_local_users(self) -> List[User]:
        """Get all local users."""
        query = select(User).where(User.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def _update_local_user(self, local_user: User, auth_user: AuthUser) -> None:
        """Update local user with data from AuthUser."""
        local_user.email = auth_user.email
        local_user.first_name = auth_user.first_name
        local_user.last_name = auth_user.last_name
        local_user.role = auth_user.roles[0] if auth_user.roles else "USER"
        local_user.is_active = auth_user.is_active
        
        # Update metadata from provider
        if auth_user.metadata:
            local_user.department = auth_user.metadata.get("department")
            local_user.license_number = auth_user.metadata.get("license_number")
            license_expiry = auth_user.metadata.get("license_expiry")
            if license_expiry:
                local_user.license_expiry = datetime.fromisoformat(license_expiry.replace("Z", "+00:00"))
            
            local_user.phi_access_granted = auth_user.metadata.get("phi_access_granted", False)
            phi_expiry = auth_user.metadata.get("phi_access_expiry")
            if phi_expiry:
                local_user.phi_access_expiry = datetime.fromisoformat(phi_expiry.replace("Z", "+00:00"))
    
    async def _create_local_user_from_auth_user(self, auth_user: AuthUser) -> User:
        """Create new local user from AuthUser."""
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
        
        # Set metadata from AuthUser
        if auth_user.metadata:
            user.department = auth_user.metadata.get("department")
            user.license_number = auth_user.metadata.get("license_number")
            license_expiry = auth_user.metadata.get("license_expiry")
            if license_expiry:
                user.license_expiry = datetime.fromisoformat(license_expiry.replace("Z", "+00:00"))
            
            user.phi_access_granted = auth_user.metadata.get("phi_access_granted", False)
            phi_expiry = auth_user.metadata.get("phi_access_expiry")
            if phi_expiry:
                user.phi_access_expiry = datetime.fromisoformat(phi_expiry.replace("Z", "+00:00"))
        
        self.db.add(user)
        return user
    
    async def _process_batch(
        self, 
        items: List[Any], 
        process_func, 
        direction: str
    ) -> Dict[str, Any]:
        """Process a batch of items."""
        results = {"total": len(items), "successful": 0, "failed": 0, "errors": []}
        
        for item in items:
            try:
                if direction == "to_provider":
                    success = await process_func(item)
                else:  # from_provider
                    success = await process_func(item.get("id", item))
                
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                results["failed"] += 1
                item_id = str(item.id) if hasattr(item, 'id') else str(item)
                results["errors"].append({
                    "item_id": item_id,
                    "error": str(e)
                })
        
        return results
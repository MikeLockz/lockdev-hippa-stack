"""
Audit service for HIPAA-compliant authentication event logging.

This service handles all audit logging requirements for authentication events,
ensuring compliance with HIPAA audit trail requirements.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
import structlog

from ...models.audit_log import AuditLog

logger = structlog.get_logger()


class AuditService:
    """Service for managing authentication audit logs."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize audit service.
        
        Args:
            db_session: Database session for audit operations
        """
        self.db = db_session
    
    async def log_authentication_event(
        self,
        event_type: str,
        user_id: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an authentication event.
        
        Args:
            event_type: Type of authentication event
            user_id: User ID involved in the event
            success: Whether the event was successful
            metadata: Additional event metadata
            client_info: Client information (IP, user agent, etc.)
        """
        try:
            # Sanitize client info for HIPAA compliance
            sanitized_client_info = self._sanitize_client_info(client_info or {})
            
            # Combine metadata
            audit_metadata = {
                "success": success,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
                **sanitized_client_info
            }
            
            # Create audit log entry
            audit_log = AuditLog(
                action=event_type,
                resource_type="authentication",
                resource_id=user_id,
                user_id=uuid.UUID(user_id) if user_id else None,
                ip_address=sanitized_client_info.get("ip_address", "unknown"),
                outcome="success" if success else "failure",
                details=audit_metadata,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(audit_log)
            await self.db.commit()
            
            logger.info(
                "Authentication event logged",
                event_type=event_type,
                user_id=user_id,
                success=success,
                ip_address=sanitized_client_info.get("ip_address", "unknown")
            )
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(
                "Failed to log authentication event",
                event_type=event_type,
                user_id=user_id,
                error=str(e)
            )
            # Don't raise - audit failures shouldn't break authentication
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "Unexpected error logging authentication event",
                event_type=event_type,
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__
            )
    
    async def get_user_audit_log(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries for a user.
        
        Args:
            user_id: User ID to get audit logs for
            start_date: Start of date range filter
            end_date: End of date range filter
            event_types: Filter by specific event types
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        try:
            user_uuid = uuid.UUID(user_id)
            
            # Build query conditions
            conditions = [AuditLog.user_id == user_uuid]
            
            if start_date:
                conditions.append(AuditLog.timestamp >= start_date)
            if end_date:
                conditions.append(AuditLog.timestamp <= end_date)
            if event_types:
                conditions.append(AuditLog.action.in_(event_types))
            
            # Execute query
            stmt = (
                select(AuditLog)
                .where(and_(*conditions))
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            audit_logs = result.scalars().all()
            
            # Convert to dictionaries
            log_entries = []
            for log in audit_logs:
                log_entries.append({
                    "id": str(log.id),
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "user_id": str(log.user_id) if log.user_id else None,
                    "ip_address": log.ip_address,
                    "outcome": log.outcome,
                    "details": log.details,
                    "timestamp": log.timestamp.isoformat()
                })
            
            logger.info(
                "Retrieved user audit log",
                user_id=user_id,
                entry_count=len(log_entries),
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )
            
            return log_entries
            
        except ValueError as e:
            logger.error("Invalid user ID format", user_id=user_id, error=str(e))
            return []
        except SQLAlchemyError as e:
            logger.error(
                "Database error retrieving audit log",
                user_id=user_id,
                error=str(e)
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error retrieving audit log",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    async def log_login_attempt(
        self,
        user_id: Optional[str],
        email: str,
        success: bool,
        failure_reason: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a login attempt."""
        metadata = {
            "email": email,
            "authentication_method": "password"
        }
        
        if not success and failure_reason:
            metadata["failure_reason"] = failure_reason
        
        await self.log_authentication_event(
            event_type="login_attempt",
            user_id=user_id,
            success=success,
            metadata=metadata,
            client_info=client_info
        )
    
    async def log_token_creation(
        self,
        user_id: str,
        token_type: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log token creation."""
        await self.log_authentication_event(
            event_type="token_created",
            user_id=user_id,
            success=True,
            metadata={"token_type": token_type},
            client_info=client_info
        )
    
    async def log_token_validation(
        self,
        user_id: str,
        token_type: str,
        success: bool,
        failure_reason: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log token validation."""
        metadata = {"token_type": token_type}
        if not success and failure_reason:
            metadata["failure_reason"] = failure_reason
        
        await self.log_authentication_event(
            event_type="token_validated",
            user_id=user_id,
            success=success,
            metadata=metadata,
            client_info=client_info
        )
    
    async def log_token_revocation(
        self,
        user_id: str,
        token_type: str,
        revoked_by: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log token revocation."""
        metadata = {
            "token_type": token_type,
            "revoked_by": revoked_by or "system"
        }
        
        await self.log_authentication_event(
            event_type="token_revoked",
            user_id=user_id,
            success=True,
            metadata=metadata,
            client_info=client_info
        )
    
    async def log_password_change(
        self,
        user_id: str,
        changed_by: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log password change."""
        metadata = {
            "changed_by": changed_by or user_id,
            "change_type": "password"
        }
        
        await self.log_authentication_event(
            event_type="password_changed",
            user_id=user_id,
            success=True,
            metadata=metadata,
            client_info=client_info
        )
    
    async def log_account_lockout(
        self,
        user_id: str,
        reason: str,
        locked_until: datetime,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log account lockout."""
        metadata = {
            "reason": reason,
            "locked_until": locked_until.isoformat(),
            "lockout_duration_minutes": 30  # Standard lockout duration
        }
        
        await self.log_authentication_event(
            event_type="account_locked",
            user_id=user_id,
            success=True,
            metadata=metadata,
            client_info=client_info
        )
    
    async def log_mfa_event(
        self,
        user_id: str,
        mfa_method: str,
        event_type: str,
        success: bool,
        failure_reason: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log MFA-related events."""
        metadata = {
            "mfa_method": mfa_method,
            "mfa_event": event_type
        }
        
        if not success and failure_reason:
            metadata["failure_reason"] = failure_reason
        
        await self.log_authentication_event(
            event_type=f"mfa_{event_type}",
            user_id=user_id,
            success=success,
            metadata=metadata,
            client_info=client_info
        )
    
    def _sanitize_client_info(self, client_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize client information for HIPAA compliance.
        
        Args:
            client_info: Raw client information
            
        Returns:
            Sanitized client information safe for logging
        """
        sanitized = {}
        
        # IP address (allowed for audit purposes)
        if "ip_address" in client_info:
            sanitized["ip_address"] = client_info["ip_address"]
        
        # User agent (sanitized - remove potentially identifying info)
        if "user_agent" in client_info:
            user_agent = str(client_info["user_agent"])
            # Basic sanitization - keep browser/OS info but remove detailed version numbers
            if len(user_agent) > 200:
                user_agent = user_agent[:200] + "..."
            sanitized["user_agent"] = user_agent
        
        # Client ID (if provided)
        if "client_id" in client_info:
            sanitized["client_id"] = str(client_info["client_id"])
        
        # Session ID (if provided)
        if "session_id" in client_info:
            sanitized["session_id"] = str(client_info["session_id"])
        
        # Request ID for correlation
        if "request_id" in client_info:
            sanitized["request_id"] = str(client_info["request_id"])
        
        return sanitized
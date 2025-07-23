"""
Session service for managing user sessions with HIPAA compliance.

This service handles session creation, validation, and management with
security features like timeout, concurrent session limits, and audit logging.
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, text
from sqlalchemy.exc import SQLAlchemyError
import structlog

from ...models.user import User

logger = structlog.get_logger()


@dataclass
class SessionInfo:
    """Information about a user session."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    client_info: Dict[str, Any]
    is_active: bool


class SessionService:
    """Service for managing user sessions."""
    
    # Session configuration
    DEFAULT_SESSION_TIMEOUT_MINUTES = 30
    MAX_CONCURRENT_SESSIONS = 5
    SESSION_CLEANUP_INTERVAL_MINUTES = 60
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize session service.
        
        Args:
            db_session: Database session for session operations
        """
        self.db = db_session
        self._sessions: Dict[str, SessionInfo] = {}  # In-memory session store
    
    async def create_session(
        self,
        user_id: str,
        client_info: Optional[Dict[str, Any]] = None,
        timeout_minutes: Optional[int] = None
    ) -> str:
        """
        Create a new user session.
        
        Args:
            user_id: User ID to create session for
            client_info: Client information for audit
            timeout_minutes: Session timeout in minutes
            
        Returns:
            Session identifier
            
        Raises:
            ValueError: If user_id is invalid
            RuntimeError: If session creation fails
        """
        try:
            # Validate user exists and is active
            user_uuid = uuid.UUID(user_id)
            stmt = select(User).where(
                User.id == user_uuid,
                User.is_active == True
            )
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {user_id} not found or inactive")
            
            # Check account lockout
            if user.account_locked_until and user.account_locked_until > datetime.utcnow():
                raise ValueError(f"User {user_id} account is locked")
            
            # Clean up expired sessions and enforce concurrent session limits
            await self._cleanup_user_sessions(user_id)
            await self._enforce_session_limits(user_id)
            
            # Generate secure session ID
            session_id = self._generate_session_id()
            
            # Calculate expiration
            timeout = timeout_minutes or self.DEFAULT_SESSION_TIMEOUT_MINUTES
            expires_at = datetime.utcnow() + timedelta(minutes=timeout)
            
            # Create session info
            session_info = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                expires_at=expires_at,
                client_info=client_info or {},
                is_active=True
            )
            
            # Store session in memory
            self._sessions[session_id] = session_info
            
            # Optional: Store session in database for persistence across restarts
            await self._persist_session(session_info)
            
            logger.info(
                "Session created",
                session_id=session_id,
                user_id=user_id,
                expires_at=expires_at.isoformat(),
                client_ip=client_info.get("ip_address", "unknown") if client_info else "unknown"
            )
            
            return session_id
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create session",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Session creation failed: {str(e)}")
    
    async def validate_session(
        self,
        session_id: str,
        update_activity: bool = True
    ) -> Optional[str]:
        """
        Validate a user session.
        
        Args:
            session_id: Session identifier to validate
            update_activity: Whether to update last activity timestamp
            
        Returns:
            User ID if session is valid, None otherwise
        """
        try:
            # Check in-memory sessions first
            session_info = self._sessions.get(session_id)
            
            if not session_info:
                # Try to load from database if not in memory
                session_info = await self._load_session_from_db(session_id)
                if session_info:
                    self._sessions[session_id] = session_info
            
            if not session_info:
                logger.debug("Session not found", session_id=session_id)
                return None
            
            # Check if session is expired
            if datetime.utcnow() > session_info.expires_at:
                logger.debug("Session expired", session_id=session_id)
                await self._remove_session(session_id)
                return None
            
            # Check if session is active
            if not session_info.is_active:
                logger.debug("Session inactive", session_id=session_id)
                return None
            
            # Update last activity if requested
            if update_activity:
                session_info.last_activity = datetime.utcnow()
                # Optionally extend expiration on activity
                session_info.expires_at = datetime.utcnow() + timedelta(
                    minutes=self.DEFAULT_SESSION_TIMEOUT_MINUTES
                )
                await self._persist_session(session_info)
            
            logger.debug(
                "Session validated",
                session_id=session_id,
                user_id=session_info.user_id
            )
            
            return session_info.user_id
            
        except Exception as e:
            logger.error(
                "Session validation error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    async def invalidate_session(
        self,
        session_id: str,
        invalidated_by: Optional[str] = None
    ) -> bool:
        """
        Invalidate a user session.
        
        Args:
            session_id: Session identifier to invalidate
            invalidated_by: User or system that invalidated the session
            
        Returns:
            True if session was successfully invalidated
        """
        try:
            session_info = self._sessions.get(session_id)
            
            if not session_info:
                # Try to load from database
                session_info = await self._load_session_from_db(session_id)
            
            if not session_info:
                logger.debug("Session to invalidate not found", session_id=session_id)
                return False
            
            # Mark as inactive
            session_info.is_active = False
            
            # Remove from memory
            await self._remove_session(session_id)
            
            logger.info(
                "Session invalidated",
                session_id=session_id,
                user_id=session_info.user_id,
                invalidated_by=invalidated_by or "system"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Session invalidation error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID to get sessions for
            active_only: Only return active sessions
            
        Returns:
            List of user's sessions
        """
        try:
            sessions = []
            
            # Get sessions from memory
            for session_info in self._sessions.values():
                if session_info.user_id == user_id:
                    if not active_only or (session_info.is_active and 
                                         datetime.utcnow() <= session_info.expires_at):
                        sessions.append(self._session_to_dict(session_info))
            
            # Also check database for persisted sessions
            db_sessions = await self._get_user_sessions_from_db(user_id, active_only)
            
            # Merge and deduplicate
            session_ids = {s["session_id"] for s in sessions}
            for db_session in db_sessions:
                if db_session["session_id"] not in session_ids:
                    sessions.append(db_session)
            
            logger.debug(
                "Retrieved user sessions",
                user_id=user_id,
                session_count=len(sessions),
                active_only=active_only
            )
            
            return sessions
            
        except Exception as e:
            logger.error(
                "Error retrieving user sessions",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    async def invalidate_all_user_sessions(
        self,
        user_id: str,
        invalidated_by: Optional[str] = None
    ) -> int:
        """
        Invalidate all sessions for a user.
        
        Args:
            user_id: User ID to invalidate sessions for
            invalidated_by: User or system that invalidated the sessions
            
        Returns:
            Number of sessions invalidated
        """
        try:
            invalidated_count = 0
            
            # Invalidate memory sessions
            sessions_to_remove = []
            for session_id, session_info in self._sessions.items():
                if session_info.user_id == user_id:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                if await self.invalidate_session(session_id, invalidated_by):
                    invalidated_count += 1
            
            # Invalidate database sessions
            db_invalidated = await self._invalidate_user_sessions_in_db(user_id)
            invalidated_count += db_invalidated
            
            logger.info(
                "Invalidated all user sessions",
                user_id=user_id,
                session_count=invalidated_count,
                invalidated_by=invalidated_by or "system"
            )
            
            return invalidated_count
            
        except Exception as e:
            logger.error(
                "Error invalidating user sessions",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return 0
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            cleaned_count = 0
            current_time = datetime.utcnow()
            
            # Clean up memory sessions
            expired_sessions = []
            for session_id, session_info in self._sessions.items():
                if current_time > session_info.expires_at:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                await self._remove_session(session_id)
                cleaned_count += 1
            
            # Clean up database sessions
            db_cleaned = await self._cleanup_expired_sessions_in_db()
            cleaned_count += db_cleaned
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(
                "Error cleaning up expired sessions",
                error=str(e),
                error_type=type(e).__name__
            )
            return 0
    
    def _generate_session_id(self) -> str:
        """Generate a cryptographically secure session ID."""
        return secrets.token_urlsafe(32)
    
    async def _cleanup_user_sessions(self, user_id: str) -> None:
        """Clean up expired sessions for a user."""
        current_time = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session_info in self._sessions.items():
            if (session_info.user_id == user_id and 
                current_time > session_info.expires_at):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self._remove_session(session_id)
    
    async def _enforce_session_limits(self, user_id: str) -> None:
        """Enforce concurrent session limits for a user."""
        user_sessions = []
        
        for session_id, session_info in self._sessions.items():
            if (session_info.user_id == user_id and 
                session_info.is_active and
                datetime.utcnow() <= session_info.expires_at):
                user_sessions.append((session_id, session_info))
        
        # If at limit, remove oldest session
        if len(user_sessions) >= self.MAX_CONCURRENT_SESSIONS:
            # Sort by creation time and remove oldest
            user_sessions.sort(key=lambda x: x[1].created_at)
            oldest_session_id = user_sessions[0][0]
            await self._remove_session(oldest_session_id)
            
            logger.info(
                "Removed oldest session due to concurrent session limit",
                user_id=user_id,
                removed_session_id=oldest_session_id,
                limit=self.MAX_CONCURRENT_SESSIONS
            )
    
    async def _remove_session(self, session_id: str) -> None:
        """Remove session from memory and database."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        # Remove from database
        await self._delete_session_from_db(session_id)
    
    def _session_to_dict(self, session_info: SessionInfo) -> Dict[str, Any]:
        """Convert SessionInfo to dictionary."""
        return {
            "session_id": session_info.session_id,
            "user_id": session_info.user_id,
            "created_at": session_info.created_at.isoformat(),
            "last_activity": session_info.last_activity.isoformat(),
            "expires_at": session_info.expires_at.isoformat(),
            "is_active": session_info.is_active,
            "client_info": session_info.client_info
        }
    
    # Database persistence methods (optional for production deployment)
    
    async def _persist_session(self, session_info: SessionInfo) -> None:
        """Persist session to database (if table exists)."""
        # Note: This would require a sessions table in production
        # For now, we'll just log that we would persist
        logger.debug(
            "Would persist session to database",
            session_id=session_info.session_id
        )
    
    async def _load_session_from_db(self, session_id: str) -> Optional[SessionInfo]:
        """Load session from database."""
        # Note: This would query the sessions table in production
        logger.debug(f"Would load session {session_id} from database")
        return None
    
    async def _get_user_sessions_from_db(
        self,
        user_id: str,
        active_only: bool
    ) -> List[Dict[str, Any]]:
        """Get user sessions from database."""
        # Note: This would query the sessions table in production
        logger.debug(f"Would get user {user_id} sessions from database")
        return []
    
    async def _invalidate_user_sessions_in_db(self, user_id: str) -> int:
        """Invalidate user sessions in database."""
        # Note: This would update the sessions table in production
        logger.debug(f"Would invalidate user {user_id} sessions in database")
        return 0
    
    async def _cleanup_expired_sessions_in_db(self) -> int:
        """Clean up expired sessions from database."""
        # Note: This would delete from sessions table in production
        logger.debug("Would cleanup expired sessions from database")
        return 0
    
    async def _delete_session_from_db(self, session_id: str) -> None:
        """Delete session from database."""
        # Note: This would delete from sessions table in production
        logger.debug(f"Would delete session {session_id} from database")
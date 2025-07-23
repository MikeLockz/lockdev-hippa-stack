"""
Tests for SessionService.

This module tests session management functionality with security controls.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.services.session_service import SessionService, SessionInfo
from src.models.user import User


@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def session_service(mock_db_session):
    """Create a SessionService instance with mock database."""
    return SessionService(mock_db_session)


@pytest.fixture
def sample_user():
    """Create a sample User object."""
    user_id = uuid.uuid4()
    return User(
        id=user_id,
        email="test@example.com",
        hashed_password="$2b$12$hashed_password",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        login_attempts="0"
    )


@pytest.mark.asyncio
class TestSessionService:
    """Test cases for SessionService."""
    
    async def test_create_session_success(self, session_service, mock_db_session, sample_user):
        """Test successful session creation."""
        user_id = str(sample_user.id)
        client_info = {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0 Test Browser"
        }
        
        # Mock user lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id, client_info)
        
        assert session_id is not None
        assert len(session_id) > 0
        assert session_id in session_service._sessions
        
        # Verify session info
        session_info = session_service._sessions[session_id]
        assert session_info.user_id == user_id
        assert session_info.is_active is True
        assert session_info.client_info == client_info
    
    async def test_create_session_user_not_found(self, session_service, mock_db_session):
        """Test session creation when user not found."""
        user_id = str(uuid.uuid4())
        
        # Mock user not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User .* not found or inactive"):
            await session_service.create_session(user_id)
    
    async def test_create_session_user_inactive(self, session_service, mock_db_session, sample_user):
        """Test session creation for inactive user."""
        sample_user.is_active = False
        user_id = str(sample_user.id)
        
        # Mock inactive user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User .* not found or inactive"):
            await session_service.create_session(user_id)
    
    async def test_create_session_user_locked(self, session_service, mock_db_session, sample_user):
        """Test session creation for locked user."""
        sample_user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
        user_id = str(sample_user.id)
        
        # Mock locked user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="User .* account is locked"):
            await session_service.create_session(user_id)
    
    async def test_create_session_custom_timeout(self, session_service, mock_db_session, sample_user):
        """Test session creation with custom timeout."""
        user_id = str(sample_user.id)
        
        # Mock user lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id, timeout_minutes=60)
        
        session_info = session_service._sessions[session_id]
        expected_expiry = session_info.created_at + timedelta(minutes=60)
        
        # Allow for small time differences
        assert abs((session_info.expires_at - expected_expiry).total_seconds()) < 2
    
    async def test_validate_session_success(self, session_service, mock_db_session, sample_user):
        """Test successful session validation."""
        user_id = str(sample_user.id)
        
        # Create session first
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Validate session
        validated_user_id = await session_service.validate_session(session_id)
        
        assert validated_user_id == user_id
    
    async def test_validate_session_not_found(self, session_service):
        """Test session validation when session not found."""
        non_existent_session = "non-existent-session-id"
        
        validated_user_id = await session_service.validate_session(non_existent_session)
        
        assert validated_user_id is None
    
    async def test_validate_session_expired(self, session_service, mock_db_session, sample_user):
        """Test session validation when session is expired."""
        user_id = str(sample_user.id)
        
        # Create session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Manually expire the session
        session_info = session_service._sessions[session_id]
        session_info.expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Validate expired session
        validated_user_id = await session_service.validate_session(session_id)
        
        assert validated_user_id is None
        assert session_id not in session_service._sessions  # Should be removed
    
    async def test_validate_session_inactive(self, session_service, mock_db_session, sample_user):
        """Test session validation when session is inactive."""
        user_id = str(sample_user.id)
        
        # Create session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Mark session as inactive
        session_info = session_service._sessions[session_id]
        session_info.is_active = False
        
        # Validate inactive session
        validated_user_id = await session_service.validate_session(session_id)
        
        assert validated_user_id is None
    
    async def test_validate_session_update_activity(self, session_service, mock_db_session, sample_user):
        """Test session validation with activity update."""
        user_id = str(sample_user.id)
        
        # Create session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Get initial activity time
        session_info = session_service._sessions[session_id]
        initial_activity = session_info.last_activity
        initial_expiry = session_info.expires_at
        
        # Wait a tiny bit to ensure time difference
        import asyncio
        await asyncio.sleep(0.01)
        
        # Validate with activity update
        validated_user_id = await session_service.validate_session(session_id, update_activity=True)
        
        assert validated_user_id == user_id
        assert session_info.last_activity > initial_activity
        assert session_info.expires_at > initial_expiry
    
    async def test_validate_session_no_activity_update(self, session_service, mock_db_session, sample_user):
        """Test session validation without activity update."""
        user_id = str(sample_user.id)
        
        # Create session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Get initial activity time
        session_info = session_service._sessions[session_id]
        initial_activity = session_info.last_activity
        
        # Validate without activity update
        validated_user_id = await session_service.validate_session(session_id, update_activity=False)
        
        assert validated_user_id == user_id
        assert session_info.last_activity == initial_activity
    
    async def test_invalidate_session_success(self, session_service, mock_db_session, sample_user):
        """Test successful session invalidation."""
        user_id = str(sample_user.id)
        
        # Create session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id = await session_service.create_session(user_id)
        
        # Invalidate session
        success = await session_service.invalidate_session(session_id, "admin")
        
        assert success is True
        assert session_id not in session_service._sessions
    
    async def test_invalidate_session_not_found(self, session_service):
        """Test session invalidation when session not found."""
        success = await session_service.invalidate_session("non-existent-session")
        
        assert success is False
    
    async def test_get_user_sessions(self, session_service, mock_db_session, sample_user):
        """Test retrieving user sessions."""
        user_id = str(sample_user.id)
        
        # Create multiple sessions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id, {"client": "web"})
        session_id2 = await session_service.create_session(user_id, {"client": "mobile"})
        
        # Get user sessions
        sessions = await session_service.get_user_sessions(user_id)
        
        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert session_id1 in session_ids
        assert session_id2 in session_ids
    
    async def test_get_user_sessions_active_only(self, session_service, mock_db_session, sample_user):
        """Test retrieving only active user sessions."""
        user_id = str(sample_user.id)
        
        # Create sessions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id)
        session_id2 = await session_service.create_session(user_id)
        
        # Invalidate one session
        await session_service.invalidate_session(session_id2)
        
        # Get active sessions only
        sessions = await session_service.get_user_sessions(user_id, active_only=True)
        
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id1
    
    async def test_get_user_sessions_include_inactive(self, session_service, mock_db_session, sample_user):
        """Test retrieving all user sessions including inactive."""
        user_id = str(sample_user.id)
        
        # Create sessions  
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id)
        session_id2 = await session_service.create_session(user_id)
        
        # Mark one as inactive (but don't remove from memory)
        session_service._sessions[session_id2].is_active = False
        
        # Get all sessions
        sessions = await session_service.get_user_sessions(user_id, active_only=False)
        
        assert len(sessions) == 2
    
    async def test_invalidate_all_user_sessions(self, session_service, mock_db_session, sample_user):
        """Test invalidating all sessions for a user."""
        user_id = str(sample_user.id)
        
        # Create multiple sessions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id)
        session_id2 = await session_service.create_session(user_id)
        session_id3 = await session_service.create_session(user_id)
        
        # Invalidate all user sessions
        invalidated_count = await session_service.invalidate_all_user_sessions(user_id, "admin")
        
        assert invalidated_count == 3
        assert session_id1 not in session_service._sessions
        assert session_id2 not in session_service._sessions
        assert session_id3 not in session_service._sessions
    
    async def test_cleanup_expired_sessions(self, session_service, mock_db_session, sample_user):
        """Test cleanup of expired sessions."""
        user_id = str(sample_user.id)
        
        # Create sessions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id)
        session_id2 = await session_service.create_session(user_id)
        
        # Manually expire one session
        session_service._sessions[session_id1].expires_at = datetime.utcnow() - timedelta(minutes=1)
        
        # Cleanup expired sessions
        cleaned_count = await session_service.cleanup_expired_sessions()
        
        assert cleaned_count >= 1  # At least one expired session
        assert session_id1 not in session_service._sessions
        assert session_id2 in session_service._sessions  # Still active
    
    async def test_enforce_session_limits(self, session_service, mock_db_session, sample_user):
        """Test enforcement of concurrent session limits."""
        user_id = str(sample_user.id)
        
        # Mock user lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        # Create sessions up to the limit
        session_ids = []
        for i in range(session_service.MAX_CONCURRENT_SESSIONS):
            session_id = await session_service.create_session(user_id)
            session_ids.append(session_id)
        
        # All sessions should exist
        assert len([sid for sid in session_ids if sid in session_service._sessions]) == session_service.MAX_CONCURRENT_SESSIONS
        
        # Create one more session (should remove oldest)
        new_session_id = await session_service.create_session(user_id)
        
        # Should still have MAX_CONCURRENT_SESSIONS sessions
        user_sessions = [sid for sid, info in session_service._sessions.items() if info.user_id == user_id]
        assert len(user_sessions) == session_service.MAX_CONCURRENT_SESSIONS
        assert new_session_id in user_sessions
        # First session should be removed
        assert session_ids[0] not in session_service._sessions
    
    def test_generate_session_id(self, session_service):
        """Test session ID generation."""
        session_id1 = session_service._generate_session_id()
        session_id2 = session_service._generate_session_id()
        
        assert session_id1 != session_id2
        assert len(session_id1) > 32  # Should be a secure length
        assert len(session_id2) > 32
    
    def test_session_to_dict(self, session_service):
        """Test conversion of SessionInfo to dictionary."""
        session_info = SessionInfo(
            session_id="test-session-id",
            user_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            client_info={"ip_address": "192.168.1.1"},
            is_active=True
        )
        
        session_dict = session_service._session_to_dict(session_info)
        
        assert session_dict["session_id"] == session_info.session_id
        assert session_dict["user_id"] == session_info.user_id
        assert session_dict["is_active"] == session_info.is_active
        assert "created_at" in session_dict
        assert "last_activity" in session_dict
        assert "expires_at" in session_dict
        assert session_dict["client_info"] == session_info.client_info
    
    async def test_cleanup_user_sessions(self, session_service, mock_db_session, sample_user):
        """Test cleanup of expired sessions for a specific user."""
        user_id = str(sample_user.id)
        other_user_id = str(uuid.uuid4())
        
        # Mock user lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db_session.execute.return_value = mock_result
        
        session_id1 = await session_service.create_session(user_id)
        
        # Create sessions for different users and expire one
        session_service._sessions[session_id1].expires_at = datetime.utcnow() - timedelta(minutes=1)
        session_service._sessions["other_session"] = SessionInfo(
            session_id="other_session",
            user_id=other_user_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            client_info={},
            is_active=True
        )
        
        # Cleanup sessions for specific user
        await session_service._cleanup_user_sessions(user_id)
        
        # User's expired session should be removed
        assert session_id1 not in session_service._sessions
        # Other user's session should remain
        assert "other_session" in session_service._sessions
    
    async def test_session_service_configuration(self):
        """Test session service configuration constants."""
        assert SessionService.DEFAULT_SESSION_TIMEOUT_MINUTES == 30
        assert SessionService.MAX_CONCURRENT_SESSIONS == 5
        assert SessionService.SESSION_CLEANUP_INTERVAL_MINUTES == 60
    
    async def test_create_session_error_handling(self, session_service, mock_db_session):
        """Test error handling in session creation."""
        user_id = "invalid-uuid"
        
        with pytest.raises(RuntimeError, match="Session creation failed"):
            await session_service.create_session(user_id)
    
    async def test_validate_session_error_handling(self, session_service):
        """Test error handling in session validation."""
        # Create a mock session that would cause an error
        session_service._sessions["error_session"] = None  # Invalid session info
        
        validated_user_id = await session_service.validate_session("error_session")
        
        assert validated_user_id is None
    
    async def test_invalidate_session_error_handling(self, session_service):
        """Test error handling in session invalidation."""
        # Should handle gracefully even with errors
        success = await session_service.invalidate_session("non-existent", "admin")
        
        assert success is False
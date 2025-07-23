"""
Tests for AuditService.

This module tests HIPAA-compliant audit logging functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.services.audit_service import AuditService
from src.models.audit_log import AuditLog


@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def audit_service(mock_db_session):
    """Create an AuditService instance with mock database."""
    return AuditService(mock_db_session)


@pytest.mark.asyncio
class TestAuditService:
    """Test cases for AuditService."""
    
    async def test_log_authentication_event_success(self, audit_service, mock_db_session):
        """Test successful authentication event logging."""
        user_id = str(uuid.uuid4())
        client_info = {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0 Test Browser"
        }
        
        await audit_service.log_authentication_event(
            event_type="login_attempt",
            user_id=user_id,
            success=True,
            metadata={"email": "test@example.com"},
            client_info=client_info
        )
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Check the audit log entry
        call_args = mock_db_session.add.call_args[0][0]
        assert isinstance(call_args, AuditLog)
        assert call_args.action == "login_attempt"
        assert call_args.resource_type == "authentication"
        assert call_args.resource_id == user_id
        assert call_args.user_id == uuid.UUID(user_id)
        assert call_args.ip_address == "192.168.1.1"
        assert call_args.outcome == "success"
    
    async def test_log_authentication_event_failure(self, audit_service, mock_db_session):
        """Test failed authentication event logging."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_authentication_event(
            event_type="login_attempt",
            user_id=user_id,
            success=False,
            metadata={"failure_reason": "Invalid password"}
        )
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Check the audit log entry
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.outcome == "failure"
        assert "failure_reason" in call_args.details
    
    async def test_log_authentication_event_no_user(self, audit_service, mock_db_session):
        """Test authentication event logging without user ID."""
        await audit_service.log_authentication_event(
            event_type="login_attempt",
            user_id=None,
            success=False,
            metadata={"email": "nonexistent@example.com"}
        )
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Check the audit log entry
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.user_id is None
        assert call_args.resource_id is None
    
    async def test_log_authentication_event_database_error(self, audit_service, mock_db_session):
        """Test handling of database errors during logging."""
        mock_db_session.commit.side_effect = Exception("Database error")
        
        # Should not raise exception - audit failures shouldn't break auth
        await audit_service.log_authentication_event(
            event_type="login_attempt",
            user_id=str(uuid.uuid4()),
            success=True
        )
        
        mock_db_session.rollback.assert_called_once()
    
    async def test_get_user_audit_log_success(self, audit_service, mock_db_session):
        """Test successful retrieval of user audit log."""
        user_id = str(uuid.uuid4())
        
        # Mock database response
        mock_audit_log = MagicMock()
        mock_audit_log.id = uuid.uuid4()
        mock_audit_log.action = "login_attempt"
        mock_audit_log.resource_type = "authentication"
        mock_audit_log.resource_id = user_id
        mock_audit_log.user_id = uuid.UUID(user_id)
        mock_audit_log.ip_address = "192.168.1.1"
        mock_audit_log.outcome = "success"
        mock_audit_log.details = {"test": "data"}
        mock_audit_log.timestamp = datetime.utcnow()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_audit_log]
        mock_db_session.execute.return_value = mock_result
        
        # Test retrieval
        logs = await audit_service.get_user_audit_log(user_id)
        
        assert len(logs) == 1
        assert logs[0]["action"] == "login_attempt"
        assert logs[0]["user_id"] == user_id
        assert logs[0]["outcome"] == "success"
    
    async def test_get_user_audit_log_with_filters(self, audit_service, mock_db_session):
        """Test audit log retrieval with date and event type filters."""
        user_id = str(uuid.uuid4())
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        event_types = ["login_attempt", "logout"]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        await audit_service.get_user_audit_log(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
            limit=50
        )
        
        # Verify query was executed with filters
        mock_db_session.execute.assert_called_once()
    
    async def test_get_user_audit_log_invalid_user_id(self, audit_service, mock_db_session):
        """Test audit log retrieval with invalid user ID."""
        logs = await audit_service.get_user_audit_log("invalid-uuid")
        
        assert logs == []
        mock_db_session.execute.assert_not_called()
    
    async def test_get_user_audit_log_database_error(self, audit_service, mock_db_session):
        """Test handling of database errors during audit log retrieval."""
        mock_db_session.execute.side_effect = Exception("Database error")
        
        logs = await audit_service.get_user_audit_log(str(uuid.uuid4()))
        
        assert logs == []
    
    async def test_log_login_attempt(self, audit_service, mock_db_session):
        """Test login attempt logging helper method."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        await audit_service.log_login_attempt(
            user_id=user_id,
            email=email,
            success=True,
            client_info={"ip_address": "192.168.1.1"}
        )
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Verify correct event type and metadata
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "login_attempt"
        assert "email" in call_args.details
        assert call_args.details["email"] == email
    
    async def test_log_login_attempt_with_failure_reason(self, audit_service, mock_db_session):
        """Test login attempt logging with failure reason."""
        await audit_service.log_login_attempt(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            success=False,
            failure_reason="Invalid password"
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.outcome == "failure"
        assert "failure_reason" in call_args.details
        assert call_args.details["failure_reason"] == "Invalid password"
    
    async def test_log_token_creation(self, audit_service, mock_db_session):
        """Test token creation logging."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_token_creation(
            user_id=user_id,
            token_type="access",
            client_info={"ip_address": "192.168.1.1"}
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "token_created"
        assert call_args.details["token_type"] == "access"
    
    async def test_log_token_validation(self, audit_service, mock_db_session):
        """Test token validation logging."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_token_validation(
            user_id=user_id,
            token_type="access",
            success=True
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "token_validated"
        assert call_args.outcome == "success"
    
    async def test_log_token_revocation(self, audit_service, mock_db_session):
        """Test token revocation logging."""
        user_id = str(uuid.uuid4())
        revoked_by = str(uuid.uuid4())
        
        await audit_service.log_token_revocation(
            user_id=user_id,
            token_type="refresh",
            revoked_by=revoked_by
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "token_revoked"
        assert call_args.details["revoked_by"] == revoked_by
    
    async def test_log_password_change(self, audit_service, mock_db_session):
        """Test password change logging."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_password_change(
            user_id=user_id,
            changed_by=user_id
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "password_changed"
        assert call_args.details["changed_by"] == user_id
    
    async def test_log_account_lockout(self, audit_service, mock_db_session):
        """Test account lockout logging."""
        user_id = str(uuid.uuid4())
        locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        await audit_service.log_account_lockout(
            user_id=user_id,
            reason="Multiple failed login attempts",
            locked_until=locked_until
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "account_locked"
        assert "reason" in call_args.details
        assert "locked_until" in call_args.details
    
    async def test_log_mfa_event(self, audit_service, mock_db_session):
        """Test MFA event logging."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_mfa_event(
            user_id=user_id,
            mfa_method="totp",
            event_type="verification_success",
            success=True
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "mfa_verification_success"
        assert call_args.details["mfa_method"] == "totp"
        assert call_args.outcome == "success"
    
    async def test_log_mfa_event_with_failure(self, audit_service, mock_db_session):
        """Test MFA event logging with failure."""
        user_id = str(uuid.uuid4())
        
        await audit_service.log_mfa_event(
            user_id=user_id,
            mfa_method="sms",
            event_type="verification_failed",
            success=False,
            failure_reason="Invalid code"
        )
        
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.action == "mfa_verification_failed"
        assert call_args.outcome == "failure"
        assert "failure_reason" in call_args.details
    
    def test_sanitize_client_info(self, audit_service):
        """Test client information sanitization."""
        client_info = {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "client_id": "test-client",
            "session_id": "session-123",
            "request_id": "req-456",
            "sensitive_data": "should_be_removed"
        }
        
        sanitized = audit_service._sanitize_client_info(client_info)
        
        # Should include allowed fields
        assert "ip_address" in sanitized
        assert "user_agent" in sanitized
        assert "client_id" in sanitized
        assert "session_id" in sanitized
        assert "request_id" in sanitized
        
        # Should exclude sensitive data
        assert "sensitive_data" not in sanitized
    
    def test_sanitize_client_info_long_user_agent(self, audit_service):
        """Test user agent truncation for long strings."""
        long_user_agent = "x" * 300
        client_info = {"user_agent": long_user_agent}
        
        sanitized = audit_service._sanitize_client_info(client_info)
        
        assert len(sanitized["user_agent"]) <= 203  # 200 + "..."
        assert sanitized["user_agent"].endswith("...")
    
    def test_sanitize_client_info_empty(self, audit_service):
        """Test sanitization of empty client info."""
        sanitized = audit_service._sanitize_client_info({})
        
        assert sanitized == {}
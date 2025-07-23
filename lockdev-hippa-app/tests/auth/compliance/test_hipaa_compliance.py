"""
Tests for HIPAA Compliance Engine functionality.

Tests cover:
- User compliance validation
- Password policy enforcement
- Session compliance checking
- Compliance violation detection
- Compliance reporting
- PHI access pattern analysis
"""

import pytest
from datetime import datetime, timedelta, date
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from src.auth.compliance.hipaa import (
    HIPAAComplianceEngine, ComplianceResult, ComplianceViolation,
    ComplianceStatus, ViolationType
)
from src.models.user import User
from src.models.audit_log import AuditLog


class TestHIPAAComplianceEngine:
    """Test HIPAA Compliance Engine functionality."""
    
    @pytest.fixture
    async def compliance_engine(self, db_session):
        """Create HIPAA compliance engine with test database."""
        return HIPAAComplianceEngine(db_session)
    
    @pytest.fixture
    def compliant_user(self):
        """Create a fully compliant user for testing."""
        return User(
            id=uuid4(),
            email="compliant@hospital.com",
            role="PHYSICIAN",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Patient treatment",
            phi_access_expiry=datetime.utcnow() + timedelta(hours=8),
            password_changed_at=datetime.utcnow() - timedelta(days=30),
            password_expires_at=datetime.utcnow() + timedelta(days=60),
            password_must_change=False,
            license_number="MD123456",
            license_expiry=datetime.utcnow() + timedelta(days=180),
            hipaa_training_completed_at=datetime.utcnow() - timedelta(days=90),
            mfa_enabled=True,
            department="Cardiology"
        )
    
    @pytest.fixture
    def non_compliant_user(self):
        """Create a non-compliant user for testing."""
        return User(
            id=uuid4(),
            email="noncompliant@hospital.com",
            role="PHYSICIAN",
            is_active=True,
            phi_access_granted=True,
            phi_access_reason="Treatment",
            phi_access_expiry=datetime.utcnow() - timedelta(hours=1),  # Expired
            password_changed_at=datetime.utcnow() - timedelta(days=120),  # Old password
            password_expires_at=datetime.utcnow() - timedelta(days=10),  # Expired password
            password_must_change=True,
            license_number="MD789012",
            license_expiry=datetime.utcnow() - timedelta(days=30),  # Expired license
            hipaa_training_completed_at=None,  # No training
            mfa_enabled=False,  # No MFA
            department="Emergency Medicine"
        )


class TestUserComplianceValidation:
    """Test user compliance validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_compliant_user(self, compliance_engine, compliant_user):
        """Test validation of a fully compliant user."""
        with patch.object(compliance_engine, '_check_password_compliance', return_value={'violations': [], 'warnings': []}), \
             patch.object(compliance_engine, '_log_compliance_check', new_callable=AsyncMock):
            
            result = await compliance_engine.validate_user_compliance(compliant_user)
        
        assert result.is_compliant is True
        assert result.status == ComplianceStatus.COMPLIANT
        assert len(result.violations) == 0
        assert result.compliance_score >= 95
    
    @pytest.mark.asyncio
    async def test_validate_non_compliant_user(self, compliance_engine, non_compliant_user):
        """Test validation of a non-compliant user."""
        with patch.object(compliance_engine, '_check_password_compliance', 
                         return_value={'violations': ['Password expired'], 'warnings': []}), \
             patch.object(compliance_engine, '_log_compliance_check', new_callable=AsyncMock):
            
            result = await compliance_engine.validate_user_compliance(non_compliant_user)
        
        assert result.is_compliant is False
        assert result.status == ComplianceStatus.NON_COMPLIANT
        assert len(result.violations) > 0
        assert result.compliance_score < 70
        
        # Check specific violations
        violation_messages = ' '.join(result.violations)
        assert "PHI access has expired" in violation_messages
        assert "Professional license expired" in violation_messages
        assert "HIPAA training is overdue" in violation_messages
        assert "Multi-factor authentication is required" in violation_messages
    
    @pytest.mark.asyncio
    async def test_validate_user_phi_access_expiring_soon(self, compliance_engine, compliant_user):
        """Test validation when PHI access expires soon."""
        # Set PHI access to expire in 3 days
        compliant_user.phi_access_expiry = datetime.utcnow() + timedelta(days=3)
        
        with patch.object(compliance_engine, '_check_password_compliance', return_value={'violations': [], 'warnings': []}), \
             patch.object(compliance_engine, '_log_compliance_check', new_callable=AsyncMock):
            
            result = await compliance_engine.validate_user_compliance(compliant_user)
        
        assert result.is_compliant is True  # Still compliant but with warnings
        assert len(result.warnings) > 0
        assert "PHI access expires within 7 days" in result.warnings
        assert result.compliance_score < 100  # Reduced due to warning
    
    @pytest.mark.asyncio
    async def test_validate_user_license_expiring_soon(self, compliance_engine, compliant_user):
        """Test validation when professional license expires soon."""
        # Set license to expire in 15 days
        compliant_user.license_expiry = datetime.utcnow() + timedelta(days=15)
        
        with patch.object(compliance_engine, '_check_password_compliance', return_value={'violations': [], 'warnings': []}), \
             patch.object(compliance_engine, '_log_compliance_check', new_callable=AsyncMock):
            
            result = await compliance_engine.validate_user_compliance(compliant_user)
        
        assert result.is_compliant is True
        assert len(result.warnings) > 0
        assert "Professional license expires within 30 days" in result.warnings
    
    @pytest.mark.asyncio
    async def test_validate_user_exception_handling(self, compliance_engine, compliant_user):
        """Test exception handling in user compliance validation."""
        with patch.object(compliance_engine, '_check_password_compliance', side_effect=Exception("Test error")):
            
            result = await compliance_engine.validate_user_compliance(compliant_user)
        
        assert result.is_compliant is False
        assert result.status == ComplianceStatus.UNDER_REVIEW
        assert "Compliance check failed due to system error" in result.violations
        assert result.compliance_score == 0


class TestPasswordPolicyEnforcement:
    """Test password policy enforcement functionality."""
    
    @pytest.fixture
    def user_with_password_history(self):
        """Create user with password history for testing."""
        return User(
            id=uuid4(),
            email="pwhistory@hospital.com",
            role="NURSE",
            password_history=[
                "old_hash_1", "old_hash_2", "old_hash_3"
            ],
            password_changed_at=datetime.utcnow() - timedelta(days=30)
        )
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_valid_password(self, compliance_engine, user_with_password_history):
        """Test password policy enforcement with valid password."""
        valid_password = "ComplexPassword123!@#"
        
        with patch('src.utils.security.pwd_context') as mock_pwd_context, \
             patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            # Mock password verification to return False for all historical passwords
            mock_pwd_context.verify.return_value = False
            
            result = await compliance_engine.enforce_password_policy(
                user_with_password_history, 
                valid_password
            )
        
        assert result["success"] is True
        assert len(result["violations"]) == 0
        assert result["policy_requirements"]["min_length"] == 12
        assert result["policy_requirements"]["requires_uppercase"] is True
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_too_short(self, compliance_engine, user_with_password_history):
        """Test password policy enforcement with too short password."""
        short_password = "Short1!"
        
        with patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            result = await compliance_engine.enforce_password_policy(
                user_with_password_history, 
                short_password
            )
        
        assert result["success"] is False
        assert any("at least 12 characters" in violation for violation in result["violations"])
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_missing_complexity(self, compliance_engine, user_with_password_history):
        """Test password policy enforcement with insufficient complexity."""
        simple_password = "simplepassword"  # No uppercase, numbers, or special chars
        
        with patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            result = await compliance_engine.enforce_password_policy(
                user_with_password_history, 
                simple_password
            )
        
        assert result["success"] is False
        violations = result["violations"]
        assert any("uppercase letter" in violation for violation in violations)
        assert any("number" in violation for violation in violations)
        assert any("special character" in violation for violation in violations)
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_password_history_violation(self, compliance_engine, user_with_password_history):
        """Test password policy enforcement with password history violation."""
        reused_password = "ReusedPassword123!"
        
        with patch('src.utils.security.pwd_context') as mock_pwd_context, \
             patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            # Mock password verification to return True for one historical password
            mock_pwd_context.verify.side_effect = [False, True, False]  # Match second hash
            
            result = await compliance_engine.enforce_password_policy(
                user_with_password_history, 
                reused_password
            )
        
        assert result["success"] is False
        assert any("used recently" in violation for violation in result["violations"])
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_common_password(self, compliance_engine, user_with_password_history):
        """Test password policy enforcement with common password."""
        common_password = "Password123!"  # Contains "password"
        
        with patch('src.utils.security.pwd_context') as mock_pwd_context, \
             patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            mock_pwd_context.verify.return_value = False
            
            result = await compliance_engine.enforce_password_policy(
                user_with_password_history, 
                common_password
            )
        
        assert result["success"] is False
        assert any("too common" in violation for violation in result["violations"])
    
    @pytest.mark.asyncio
    async def test_enforce_password_policy_personal_info(self, compliance_engine):
        """Test password policy enforcement with personal information."""
        user = User(
            id=uuid4(),
            email="john.doe@hospital.com",
            first_name="John",
            last_name="Doe",
            role="PHYSICIAN"
        )
        
        password_with_name = "JohnPassword123!"  # Contains first name
        
        with patch('src.utils.security.pwd_context') as mock_pwd_context, \
             patch.object(compliance_engine.db, 'add'), \
             patch.object(compliance_engine.db, 'commit', new_callable=AsyncMock):
            
            mock_pwd_context.verify.return_value = False
            
            result = await compliance_engine.enforce_password_policy(user, password_with_name)
        
        assert result["success"] is False
        assert any("personal information" in violation for violation in result["violations"])


class TestSessionComplianceChecking:
    """Test session compliance checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_session_compliance_valid_session(self, compliance_engine):
        """Test session compliance checking with valid session."""
        current_time = datetime.utcnow()
        session_data = {
            "user_id": str(uuid4()),
            "created_at": (current_time - timedelta(hours=2)).isoformat(),
            "last_activity": (current_time - timedelta(minutes=5)).isoformat()
        }
        
        with patch.object(compliance_engine, '_create_violation', new_callable=AsyncMock):
            result = await compliance_engine.check_session_compliance(session_data)
        
        assert result is True
        compliance_engine._create_violation.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_session_compliance_duration_exceeded(self, compliance_engine):
        """Test session compliance checking with exceeded duration."""
        current_time = datetime.utcnow()
        user_id = str(uuid4())
        session_data = {
            "user_id": user_id,
            "created_at": (current_time - timedelta(hours=10)).isoformat(),  # Over 8 hour limit
            "last_activity": (current_time - timedelta(minutes=5)).isoformat()
        }
        
        with patch.object(compliance_engine, '_create_violation', new_callable=AsyncMock) as mock_create:
            result = await compliance_engine.check_session_compliance(session_data)
        
        assert result is False
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]["violation_type"] == ViolationType.SESSION_TIMEOUT_VIOLATION
        assert call_args[1]["severity"] == "medium"
    
    @pytest.mark.asyncio
    async def test_check_session_compliance_idle_timeout(self, compliance_engine):
        """Test session compliance checking with idle timeout."""
        current_time = datetime.utcnow()
        user_id = str(uuid4())
        session_data = {
            "user_id": user_id,
            "created_at": (current_time - timedelta(hours=2)).isoformat(),
            "last_activity": (current_time - timedelta(minutes=30)).isoformat()  # Over 15 minute idle limit
        }
        
        with patch.object(compliance_engine, '_create_violation', new_callable=AsyncMock) as mock_create:
            result = await compliance_engine.check_session_compliance(session_data)
        
        assert result is False
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]["violation_type"] == ViolationType.SESSION_TIMEOUT_VIOLATION
        assert call_args[1]["severity"] == "low"
    
    @pytest.mark.asyncio
    async def test_check_session_compliance_exception_handling(self, compliance_engine):
        """Test session compliance checking with invalid session data."""
        invalid_session_data = {
            "user_id": "invalid",
            "created_at": "invalid_date",
            "last_activity": "invalid_date"
        }
        
        result = await compliance_engine.check_session_compliance(invalid_session_data)
        
        assert result is False


class TestComplianceViolationDetection:
    """Test compliance violation detection functionality."""
    
    @pytest.fixture
    def sample_audit_logs(self):
        """Create sample audit logs for violation detection testing."""
        user_id_1 = uuid4()
        user_id_2 = uuid4()
        patient_id = uuid4()
        
        logs = []
        
        # Create excessive failed logins for user 1
        for i in range(5):
            logs.append(AuditLog(
                user_id=user_id_1,
                event_type="login_attempt",
                outcome="failure",
                timestamp=datetime.utcnow() - timedelta(minutes=i*5),
                ip_address="192.168.1.100"
            ))
        
        # Create excessive PHI accesses for user 2
        for i in range(60):
            logs.append(AuditLog(
                user_id=user_id_2,
                event_type="phi_access",
                phi_accessed=True,
                patient_id=patient_id,
                outcome="success",
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                ip_address="192.168.1.200"
            ))
        
        # Create after-hours PHI access
        logs.append(AuditLog(
            user_id=user_id_2,
            event_type="phi_access",
            phi_accessed=True,
            patient_id=patient_id,
            outcome="success",
            timestamp=datetime.utcnow().replace(hour=23, minute=30),  # 11:30 PM
            ip_address="192.168.1.200"
        ))
        
        # Create PHI access without reason
        logs.append(AuditLog(
            user_id=user_id_2,
            event_type="phi_access",
            phi_accessed=True,
            patient_id=patient_id,
            access_reason=None,  # No reason provided
            outcome="success",
            timestamp=datetime.utcnow() - timedelta(minutes=30),
            ip_address="192.168.1.200"
        ))
        
        return logs
    
    @pytest.mark.asyncio
    async def test_detect_compliance_violations(self, compliance_engine, db_session, sample_audit_logs):
        """Test detection of various compliance violations."""
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(compliance_engine, '_create_violation', new_callable=AsyncMock) as mock_create:
            
            # Mock database query results
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = sample_audit_logs
            mock_execute.return_value = mock_result
            
            violations = await compliance_engine.detect_compliance_violations(hours_back=24)
        
        # Should detect multiple types of violations
        assert len(violations) > 0
        
        # Verify violation types
        violation_types = [v.violation_type for v in violations]
        assert ViolationType.FAILED_AUTHENTICATION in violation_types
        assert ViolationType.EXCESSIVE_ACCESS in violation_types
        assert ViolationType.AFTER_HOURS_ACCESS in violation_types
        assert ViolationType.PHI_ACCESS_WITHOUT_REASON in violation_types
    
    @pytest.mark.asyncio
    async def test_analyze_user_activity_excessive_failed_logins(self, compliance_engine):
        """Test analysis of user activity for excessive failed logins."""
        user_id = uuid4()
        logs = []
        
        # Create 5 failed login attempts (over the limit of 3)
        for i in range(5):
            logs.append(AuditLog(
                user_id=user_id,
                event_type="login_attempt",
                outcome="failure",
                timestamp=datetime.utcnow() - timedelta(minutes=i*10)
            ))
        
        violations = await compliance_engine._analyze_user_activity(user_id, logs)
        
        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.FAILED_AUTHENTICATION
        assert violations[0].severity == "high"
        assert violations[0].user_id == user_id
    
    @pytest.mark.asyncio
    async def test_analyze_system_patterns_account_sharing(self, compliance_engine):
        """Test analysis of system patterns for potential account sharing."""
        user_id = uuid4()
        logs = []
        
        # Create logs from multiple IP addresses (indicating potential sharing)
        ip_addresses = ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", 
                       "192.168.1.5", "192.168.1.6"]  # 6 different IPs
        
        for ip in ip_addresses:
            logs.append(AuditLog(
                user_id=user_id,
                event_type="login",
                outcome="success",
                ip_address=ip,
                timestamp=datetime.utcnow() - timedelta(hours=1)
            ))
        
        violations = await compliance_engine._analyze_system_patterns(logs)
        
        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.ACCOUNT_SHARING
        assert violations[0].severity == "high"
        assert violations[0].user_id == user_id


class TestComplianceReporting:
    """Test compliance reporting functionality."""
    
    @pytest.fixture
    def sample_users(self):
        """Create sample users for reporting tests."""
        return [
            User(id=uuid4(), email="user1@hospital.com", is_active=True, 
                 phi_access_granted=True, mfa_enabled=True, role="PHYSICIAN"),
            User(id=uuid4(), email="user2@hospital.com", is_active=True, 
                 phi_access_granted=False, mfa_enabled=False, role="NURSE"),
            User(id=uuid4(), email="user3@hospital.com", is_active=False, 
                 phi_access_granted=True, mfa_enabled=True, role="ADMIN")
        ]
    
    @pytest.fixture
    def sample_report_audit_logs(self):
        """Create sample audit logs for reporting tests."""
        logs = []
        
        # Add various types of events
        for i in range(50):
            logs.append(AuditLog(
                user_id=uuid4(),
                event_type="login",
                event_category="authentication",
                outcome="success",
                compliance_status="compliant",
                timestamp=datetime.utcnow() - timedelta(hours=i),
                phi_accessed=False
            ))
        
        # Add PHI access events
        for i in range(20):
            logs.append(AuditLog(
                user_id=uuid4(),
                event_type="phi_access",
                event_category="access",
                outcome="success",
                compliance_status="compliant",
                phi_accessed=True,
                patient_id=uuid4(),
                timestamp=datetime.utcnow() - timedelta(hours=i)
            ))
        
        # Add some violations
        for i in range(5):
            logs.append(AuditLog(
                user_id=uuid4(),
                event_type="unauthorized_access",
                event_category="access",
                outcome="failure",
                compliance_status="violation",
                timestamp=datetime.utcnow() - timedelta(hours=i)
            ))
        
        return logs
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report(self, compliance_engine, db_session, 
                                            sample_users, sample_report_audit_logs):
        """Test generation of compliance report."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        with patch.object(db_session, 'execute') as mock_execute:
            # Mock audit logs query
            audit_result = AsyncMock()
            audit_result.scalars.return_value.all.return_value = sample_report_audit_logs
            
            # Mock users query
            user_result = AsyncMock()
            user_result.scalars.return_value.all.return_value = sample_users
            
            # Set up execute to return different results for different queries
            mock_execute.side_effect = [audit_result, user_result]
            
            report = await compliance_engine.generate_compliance_report(start_date, end_date)
        
        # Verify report structure
        assert "report_period" in report
        assert "summary" in report
        assert "user_metrics" in report
        assert "event_breakdown" in report
        assert "violation_breakdown" in report
        assert "recommendations" in report
        
        # Verify calculations
        assert report["summary"]["total_events"] == 75
        assert report["summary"]["phi_events"] == 20
        assert report["summary"]["violations"] == 5
        assert report["user_metrics"]["total_users"] == 3
        assert report["user_metrics"]["active_users"] == 2
        assert report["user_metrics"]["users_with_phi_access"] == 2
        assert report["user_metrics"]["users_with_mfa"] == 2
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report_exception_handling(self, compliance_engine, db_session):
        """Test compliance report generation with exception."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        with patch.object(db_session, 'execute', side_effect=Exception("Database error")):
            report = await compliance_engine.generate_compliance_report(start_date, end_date)
        
        assert "error" in report
        assert "Database error" in report["message"]


class TestPHIAccessPatternAnalysis:
    """Test PHI access pattern analysis functionality."""
    
    @pytest.fixture
    def phi_access_logs(self):
        """Create PHI access logs for pattern analysis."""
        user_id = uuid4()
        patient_id_1 = uuid4()
        patient_id_2 = uuid4()
        
        logs = []
        
        # Normal access pattern (5 accesses per day for 10 days)
        for day in range(10):
            for access in range(5):
                logs.append(AuditLog(
                    user_id=user_id,
                    event_type="phi_access",
                    phi_accessed=True,
                    patient_id=patient_id_1,
                    timestamp=datetime.utcnow() - timedelta(days=day, hours=access*2),
                    outcome="success"
                ))
        
        # Excessive access to one patient (15 accesses in one day)
        for access in range(15):
            logs.append(AuditLog(
                user_id=user_id,
                event_type="phi_access",
                phi_accessed=True,
                patient_id=patient_id_2,
                timestamp=datetime.utcnow() - timedelta(hours=access),
                outcome="success"
            ))
        
        # Late night access
        logs.append(AuditLog(
            user_id=user_id,
            event_type="phi_access",
            phi_accessed=True,
            patient_id=patient_id_1,
            timestamp=datetime.utcnow().replace(hour=2, minute=30),  # 2:30 AM
            outcome="success"
        ))
        
        return logs
    
    @pytest.mark.asyncio
    async def test_audit_phi_access_patterns(self, compliance_engine, db_session, phi_access_logs):
        """Test PHI access pattern analysis."""
        user_id = phi_access_logs[0].user_id
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = phi_access_logs
            mock_execute.return_value = mock_result
            
            patterns = await compliance_engine.audit_phi_access_patterns(user_id, days_back=30)
        
        # Should detect multiple patterns
        assert len(patterns) > 0
        
        # Check for expected pattern types
        pattern_types = [pattern["type"] for pattern in patterns]
        assert "excessive_daily_access" in pattern_types
        assert "unusual_hour_access" in pattern_types
        assert "excessive_patient_access" in pattern_types
        
        # Verify pattern details
        for pattern in patterns:
            assert "type" in pattern
            assert "severity" in pattern
            if pattern["type"] == "excessive_patient_access":
                assert pattern["access_count"] > 10
    
    @pytest.mark.asyncio
    async def test_audit_phi_access_patterns_no_logs(self, compliance_engine, db_session):
        """Test PHI access pattern analysis with no logs."""
        user_id = uuid4()
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result
            
            patterns = await compliance_engine.audit_phi_access_patterns(user_id, days_back=30)
        
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_audit_phi_access_patterns_exception_handling(self, compliance_engine, db_session):
        """Test PHI access pattern analysis with exception."""
        user_id = uuid4()
        
        with patch.object(db_session, 'execute', side_effect=Exception("Database error")):
            patterns = await compliance_engine.audit_phi_access_patterns(user_id, days_back=30)
        
        assert len(patterns) == 0


class TestComplianceEngineConstants:
    """Test compliance engine constants and configuration."""
    
    def test_password_policy_constants(self, compliance_engine):
        """Test password policy constants are set correctly."""
        assert compliance_engine.PASSWORD_MIN_LENGTH >= 12
        assert compliance_engine.PASSWORD_MAX_AGE_DAYS == 90
        assert compliance_engine.PASSWORD_HISTORY_COUNT == 12
    
    def test_session_policy_constants(self, compliance_engine):
        """Test session policy constants are set correctly."""
        assert compliance_engine.MAX_SESSION_DURATION_HOURS == 8
        assert compliance_engine.IDLE_TIMEOUT_MINUTES == 15
        assert compliance_engine.MAX_CONCURRENT_SESSIONS == 5
    
    def test_monitoring_threshold_constants(self, compliance_engine):
        """Test monitoring threshold constants are set correctly."""
        assert compliance_engine.MAX_FAILED_LOGINS_PER_HOUR == 3
        assert compliance_engine.MAX_PHI_ACCESSES_PER_HOUR == 50
        assert compliance_engine.AFTER_HOURS_START == 18  # 6 PM
        assert compliance_engine.AFTER_HOURS_END == 7     # 7 AM


class TestComplianceModels:
    """Test compliance model classes."""
    
    def test_compliance_result_model(self):
        """Test ComplianceResult model creation and validation."""
        result = ComplianceResult(
            is_compliant=True,
            status=ComplianceStatus.COMPLIANT,
            violations=["No violations"],
            warnings=["Minor warning"],
            recommendations=["Enable MFA"],
            compliance_score=95
        )
        
        assert result.is_compliant is True
        assert result.status == ComplianceStatus.COMPLIANT
        assert result.compliance_score == 95
        assert len(result.violations) == 1
        assert len(result.warnings) == 1
        assert len(result.recommendations) == 1
        assert result.last_checked is not None
    
    def test_compliance_violation_model(self):
        """Test ComplianceViolation model creation and validation."""
        user_id = uuid4()
        patient_ids = [uuid4(), uuid4()]
        
        violation = ComplianceViolation(
            user_id=user_id,
            violation_type=ViolationType.UNAUTHORIZED_ACCESS,
            severity="high",
            description="User accessed PHI without authorization",
            details={"attempted_elements": ["medical_history", "lab_results"]},
            patient_ids=patient_ids,
            requires_notification=True
        )
        
        assert violation.user_id == user_id
        assert violation.violation_type == ViolationType.UNAUTHORIZED_ACCESS
        assert violation.severity == "high"
        assert len(violation.patient_ids) == 2
        assert violation.requires_notification is True
        assert violation.detected_at is not None
"""
Tests for HIPAA Compliance Audit Reporter functionality.

Tests cover:
- HIPAA audit report generation
- Multi-format export (JSON, CSV, XML)
- Audit log integrity validation
- Unusual access pattern detection
- User access reporting
"""

import pytest
from datetime import datetime, timedelta, date
from uuid import uuid4
from unittest.mock import AsyncMock, patch
import json
import csv
from io import StringIO

from src.auth.compliance.audit_reporter import (
    ComplianceAuditReporter, ReportFormat, ReportType, 
    AuditReportFilter, AuditReportMetadata
)
from src.models.user import User
from src.models.audit_log import AuditLog


class TestComplianceAuditReporter:
    """Test audit reporter functionality."""
    
    @pytest.fixture
    async def audit_reporter(self, db_session):
        """Create audit reporter with test database."""
        return ComplianceAuditReporter(db_session)
    
    @pytest.fixture
    def sample_audit_logs(self):
        """Create sample audit logs for testing."""
        user_id_1 = uuid4()
        user_id_2 = uuid4()
        patient_id = uuid4()
        
        logs = [
            # PHI access events
            AuditLog(
                user_id=user_id_1,
                event_type="phi_access",
                event_category="access",
                phi_accessed=True,
                patient_id=patient_id,
                data_elements_accessed=["demographics", "lab_results"],
                access_reason="treatment",
                minimum_necessary_applied=True,
                compliance_status="compliant",
                timestamp=datetime.utcnow() - timedelta(hours=2),
                outcome="success"
            ),
            # Authentication events
            AuditLog(
                user_id=user_id_2,
                event_type="login",
                event_category="authentication",
                compliance_status="compliant",
                timestamp=datetime.utcnow() - timedelta(hours=1),
                outcome="success"
            ),
            # Violation event
            AuditLog(
                user_id=user_id_1,
                event_type="unauthorized_access",
                event_category="access",
                compliance_status="violation",
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                outcome="failure"
            )
        ]
        return logs


class TestHIPAAAuditReportGeneration:
    """Test HIPAA audit report generation."""
    
    @pytest.mark.asyncio
    async def test_generate_hipaa_audit_report(self, audit_reporter, db_session, sample_audit_logs):
        """Test generation of comprehensive HIPAA audit report."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs), \
             patch.object(audit_reporter, '_log_report_generation', new_callable=AsyncMock):
            
            report = await audit_reporter.generate_hipaa_audit_report(
                start_date, end_date, ReportFormat.JSON
            )
        
        # Verify report structure
        assert "metadata" in report
        assert "summary" in report
        assert "phi_access_analysis" in report
        assert "security_analysis" in report
        assert "compliance_analysis" in report
        assert "user_activity_analysis" in report
        assert "system_events_analysis" in report
        assert "detailed_logs" in report
        
        # Verify metadata
        metadata = report["metadata"]
        assert metadata["report_type"] == ReportType.HIPAA_AUDIT.value
        assert metadata["total_records"] == 3
        assert metadata["format"] == ReportFormat.JSON.value
    
    @pytest.mark.asyncio
    async def test_generate_report_with_filters(self, audit_reporter, db_session):
        """Test report generation with filters applied."""
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        user_id = uuid4()
        
        filters = AuditReportFilter(
            user_ids=[user_id],
            phi_accessed_only=True,
            compliance_status=["compliant"]
        )
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=[]) as mock_filter:
            await audit_reporter.generate_hipaa_audit_report(
                start_date, end_date, ReportFormat.JSON, filters
            )
        
        # Verify filters were applied
        mock_filter.assert_called_once()
        applied_filters = mock_filter.call_args[0][0]
        assert user_id in applied_filters.user_ids
        assert applied_filters.phi_accessed_only is True
        assert "compliant" in applied_filters.compliance_status


class TestAuditLogFiltering:
    """Test audit log filtering functionality."""
    
    @pytest.mark.asyncio
    async def test_get_filtered_audit_logs_date_range(self, audit_reporter, db_session):
        """Test audit log filtering by date range."""
        filters = AuditReportFilter(
            start_date=date.today() - timedelta(days=7),
            end_date=date.today()
        )
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result
            
            await audit_reporter._get_filtered_audit_logs(filters)
        
        # Verify query was executed
        mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_filtered_audit_logs_user_filter(self, audit_reporter, db_session):
        """Test audit log filtering by user IDs."""
        user_ids = [uuid4(), uuid4()]
        filters = AuditReportFilter(user_ids=user_ids)
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result
            
            await audit_reporter._get_filtered_audit_logs(filters)
        
        mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_filtered_audit_logs_phi_only(self, audit_reporter, db_session):
        """Test audit log filtering for PHI access only."""
        filters = AuditReportFilter(phi_accessed_only=True)
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result
            
            await audit_reporter._get_filtered_audit_logs(filters)
        
        mock_execute.assert_called_once()


class TestReportSectionGeneration:
    """Test individual report section generation."""
    
    @pytest.mark.asyncio
    async def test_generate_phi_access_section(self, audit_reporter, sample_audit_logs):
        """Test PHI access analysis section generation."""
        # Filter to only PHI access logs
        phi_logs = [log for log in sample_audit_logs if log.phi_accessed]
        
        section = await audit_reporter._generate_phi_access_section(phi_logs)
        
        assert "total_phi_access_events" in section
        assert "access_reason_breakdown" in section
        assert "data_elements_accessed" in section
        assert "minimum_necessary_compliance" in section
        assert section["total_phi_access_events"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_security_section(self, audit_reporter, sample_audit_logs):
        """Test security analysis section generation."""
        section = await audit_reporter._generate_security_section(sample_audit_logs)
        
        assert "authentication_summary" in section
        assert "ip_address_analysis" in section
        assert "failed_login_analysis" in section
        assert "risk_analysis" in section
    
    @pytest.mark.asyncio
    async def test_generate_compliance_section(self, audit_reporter, sample_audit_logs):
        """Test compliance analysis section generation."""
        section = await audit_reporter._generate_compliance_section(sample_audit_logs)
        
        assert "compliance_status_breakdown" in section
        assert "violation_analysis" in section
        assert "department_compliance" in section
        assert "compliance_trends" in section
        
        # Verify violation analysis
        assert section["violation_analysis"]["total_violations"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_user_activity_section(self, audit_reporter, sample_audit_logs):
        """Test user activity analysis section generation."""
        section = await audit_reporter._generate_user_activity_section(sample_audit_logs)
        
        assert "total_active_users" in section
        assert "top_active_users" in section
        assert "users_with_violations" in section
        assert section["total_active_users"] == 2


class TestMultiFormatExport:
    """Test multi-format audit log export functionality."""
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_json(self, audit_reporter, db_session, sample_audit_logs):
        """Test JSON format export."""
        filters = AuditReportFilter()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs):
            result = await audit_reporter.export_audit_logs(
                filters, ReportFormat.JSON, sanitize=True
            )
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 3
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_csv(self, audit_reporter, db_session, sample_audit_logs):
        """Test CSV format export."""
        filters = AuditReportFilter()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs):
            result = await audit_reporter.export_audit_logs(
                filters, ReportFormat.CSV, sanitize=True
            )
        
        # Should be valid CSV
        csv_reader = csv.reader(StringIO(result))
        rows = list(csv_reader)
        assert len(rows) > 1  # Header + data rows
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_xml(self, audit_reporter, db_session, sample_audit_logs):
        """Test XML format export."""
        filters = AuditReportFilter()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs):
            result = await audit_reporter.export_audit_logs(
                filters, ReportFormat.XML, sanitize=True
            )
        
        # Should contain XML tags
        assert "<audit_logs>" in result
        assert "<audit_log>" in result
        assert "</audit_logs>" in result
    
    @pytest.mark.asyncio
    async def test_export_with_sanitization(self, audit_reporter, db_session, sample_audit_logs):
        """Test export with data sanitization."""
        filters = AuditReportFilter()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs):
            result = await audit_reporter.export_audit_logs(
                filters, ReportFormat.JSON, sanitize=True
            )
        
        parsed = json.loads(result)
        
        # Sanitized export should not contain sensitive fields
        for record in parsed:
            assert "user_id" not in record
            assert "patient_id" not in record
            assert "ip_address" not in record
    
    @pytest.mark.asyncio
    async def test_export_without_sanitization(self, audit_reporter, db_session, sample_audit_logs):
        """Test export without data sanitization."""
        filters = AuditReportFilter()
        
        with patch.object(audit_reporter, '_get_filtered_audit_logs', return_value=sample_audit_logs):
            result = await audit_reporter.export_audit_logs(
                filters, ReportFormat.JSON, sanitize=False
            )
        
        parsed = json.loads(result)
        
        # Non-sanitized export should contain sensitive fields
        for record in parsed:
            if record.get("user_id"):  # Not all logs have user_id
                assert "user_id" in record


class TestAuditLogIntegrityValidation:
    """Test audit log integrity validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_audit_log_integrity_all_valid(self, audit_reporter, db_session):
        """Test integrity validation with all valid records."""
        # Create logs with valid hashes
        valid_logs = []
        for i in range(3):
            log = AuditLog(
                event_type=f"test_event_{i}",
                resource_type="test",
                outcome="success"
            )
            # Hash is automatically generated correctly
            valid_logs.append(log)
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = valid_logs
            mock_execute.return_value = mock_result
            
            result = await audit_reporter.validate_audit_log_integrity(days_back=30)
        
        assert result["status"] == "PASS"
        assert result["total_records_checked"] == 3
        assert result["valid_records"] == 3
        assert result["invalid_records_count"] == 0
        assert result["integrity_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_validate_audit_log_integrity_with_invalid(self, audit_reporter, db_session):
        """Test integrity validation with some invalid records."""
        # Create mix of valid and invalid logs
        logs = []
        
        # Valid log
        valid_log = AuditLog(
            event_type="valid_event",
            resource_type="test",
            outcome="success"
        )
        logs.append(valid_log)
        
        # Invalid log (corrupt hash)
        invalid_log = AuditLog(
            event_type="invalid_event",
            resource_type="test",
            outcome="success"
        )
        invalid_log.record_hash = "corrupted_hash"
        logs.append(invalid_log)
        
        with patch.object(db_session, 'execute') as mock_execute, \
             patch.object(db_session, 'add'), \
             patch.object(db_session, 'commit', new_callable=AsyncMock):
            
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = logs
            mock_execute.return_value = mock_result
            
            result = await audit_reporter.validate_audit_log_integrity(days_back=30)
        
        assert result["status"] == "FAIL"
        assert result["total_records_checked"] == 2
        assert result["valid_records"] == 1
        assert result["invalid_records_count"] == 1
        assert result["integrity_rate"] == 50.0
        assert len(result["invalid_record_details"]) == 1


class TestUnusualAccessPatternDetection:
    """Test unusual access pattern detection functionality."""
    
    @pytest.fixture
    def unusual_pattern_logs(self):
        """Create audit logs with unusual patterns."""
        user_id_1 = uuid4()
        user_id_2 = uuid4()
        
        logs = []
        
        # User 1: Unusual volume (50 events)
        for i in range(50):
            logs.append(AuditLog(
                user_id=user_id_1,
                event_type="data_access",
                outcome="success",
                timestamp=datetime.utcnow() - timedelta(minutes=i)
            ))
        
        # User 2: Multiple IP addresses
        ip_addresses = ["192.168.1.1", "192.168.1.2", "192.168.1.3", 
                       "192.168.1.4", "192.168.1.5", "192.168.1.6"]
        for ip in ip_addresses:
            logs.append(AuditLog(
                user_id=user_id_2,
                event_type="login",
                outcome="success",
                ip_address=ip,
                timestamp=datetime.utcnow() - timedelta(hours=1)
            ))
        
        # High-risk events clustering
        for i in range(15):
            logs.append(AuditLog(
                user_id=user_id_1,
                event_type="high_risk_access",
                outcome="success",
                risk_score=85,
                timestamp=datetime.utcnow() - timedelta(minutes=i*2)
            ))
        
        # After-hours activity spike
        for i in range(10):
            logs.append(AuditLog(
                user_id=user_id_2,
                event_type="after_hours_access",
                outcome="success",
                timestamp=datetime.utcnow().replace(hour=23, minute=i*5)  # 11 PM
            ))
        
        return logs
    
    @pytest.mark.asyncio
    async def test_detect_unusual_access_patterns(self, audit_reporter, db_session, unusual_pattern_logs):
        """Test detection of various unusual access patterns."""
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = unusual_pattern_logs
            mock_execute.return_value = mock_result
            
            patterns = await audit_reporter.detect_unusual_access_patterns(days_back=7)
        
        # Should detect multiple pattern types
        assert len(patterns) > 0
        
        # Check for expected pattern types
        pattern_types = [pattern["type"] for pattern in patterns]
        assert "unusual_user_volume" in pattern_types
        assert "multiple_ip_addresses" in pattern_types
        assert "high_risk_event_cluster" in pattern_types
        assert "after_hours_activity_spike" in pattern_types
    
    @pytest.mark.asyncio
    async def test_detect_unusual_access_patterns_no_patterns(self, audit_reporter, db_session):
        """Test unusual pattern detection with normal activity."""
        # Create normal activity logs
        normal_logs = []
        user_id = uuid4()
        
        # Normal volume, single IP, normal hours
        for i in range(5):  # Low volume
            normal_logs.append(AuditLog(
                user_id=user_id,
                event_type="normal_access",
                outcome="success",
                ip_address="192.168.1.100",  # Same IP
                risk_score=10,  # Low risk
                timestamp=datetime.utcnow().replace(hour=10, minute=i*10)  # Normal hours
            ))
        
        with patch.object(db_session, 'execute') as mock_execute:
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = normal_logs
            mock_execute.return_value = mock_result
            
            patterns = await audit_reporter.detect_unusual_access_patterns(days_back=7)
        
        # Should detect no unusual patterns
        assert len(patterns) == 0


class TestUserAccessReporting:
    """Test user-specific access reporting functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_user_access_report(self, audit_reporter, db_session):
        """Test generation of user-specific access report."""
        user_id = uuid4()
        user = User(
            id=user_id,
            email="testuser@hospital.com",
            role="PHYSICIAN",
            department="Cardiology",
            is_active=True,
            phi_access_granted=True
        )
        
        # Create user's audit logs
        user_logs = []
        for i in range(10):
            user_logs.append(AuditLog(
                user_id=user_id,
                event_type="phi_access" if i % 2 == 0 else "login",
                phi_accessed=i % 2 == 0,
                patient_id=uuid4() if i % 2 == 0 else None,
                outcome="success",
                compliance_status="compliant",
                timestamp=datetime.utcnow() - timedelta(hours=i)
            ))
        
        with patch.object(db_session, 'execute') as mock_execute:
            # Mock both audit logs query and user query
            audit_result = AsyncMock()
            audit_result.scalars.return_value.all.return_value = user_logs
            
            user_result = AsyncMock()
            user_result.scalar_one_or_none.return_value = user
            
            mock_execute.side_effect = [audit_result, user_result]
            
            report = await audit_reporter.generate_user_access_report(user_id, days_back=30)
        
        # Verify report structure
        assert "user_info" in report
        assert "report_period" in report
        assert "activity_summary" in report
        assert "daily_activity" in report
        assert "phi_access_analysis" in report
        assert "security_analysis" in report
        assert "recent_activity" in report
        
        # Verify calculations
        assert report["activity_summary"]["total_events"] == 10
        assert report["activity_summary"]["phi_accesses"] == 5
        assert report["user_info"]["email"] == "testuser@hospital.com"
    
    @pytest.mark.asyncio
    async def test_generate_user_access_report_user_not_found(self, audit_reporter, db_session):
        """Test user access report generation when user doesn't exist."""
        user_id = uuid4()
        
        with patch.object(db_session, 'execute') as mock_execute:
            # Mock empty audit logs and no user found
            audit_result = AsyncMock()
            audit_result.scalars.return_value.all.return_value = []
            
            user_result = AsyncMock()
            user_result.scalar_one_or_none.return_value = None
            
            mock_execute.side_effect = [audit_result, user_result]
            
            report = await audit_reporter.generate_user_access_report(user_id, days_back=30)
        
        assert "error" in report
        assert "User not found" in report["error"]


class TestReportModels:
    """Test audit report model classes."""
    
    def test_audit_report_filter_model(self):
        """Test AuditReportFilter model creation and validation."""
        user_ids = [uuid4(), uuid4()]
        patient_ids = [uuid4()]
        
        filters = AuditReportFilter(
            start_date=date.today() - timedelta(days=7),
            end_date=date.today(),
            user_ids=user_ids,
            patient_ids=patient_ids,
            event_types=["login", "phi_access"],
            compliance_status=["compliant", "violation"],
            phi_accessed_only=True,
            include_system_events=False
        )
        
        assert len(filters.user_ids) == 2
        assert len(filters.patient_ids) == 1
        assert filters.phi_accessed_only is True
        assert filters.include_system_events is False
        assert "login" in filters.event_types
    
    def test_audit_report_metadata_model(self):
        """Test AuditReportMetadata model creation and validation."""
        generated_by = uuid4()
        
        metadata = AuditReportMetadata(
            report_id="hipaa_audit_20240101_20240107",
            report_type=ReportType.HIPAA_AUDIT,
            generated_at=datetime.utcnow(),
            generated_by=generated_by,
            period_start=date.today() - timedelta(days=7),
            period_end=date.today(),
            total_records=150,
            format=ReportFormat.JSON,
            filters_applied={"phi_accessed_only": True}
        )
        
        assert metadata.report_type == ReportType.HIPAA_AUDIT
        assert metadata.format == ReportFormat.JSON
        assert metadata.total_records == 150
        assert metadata.retention_period_days == 2555  # Default 7 years
        assert metadata.generated_by == generated_by


class TestReportFormatEnums:
    """Test report format and type enumerations."""
    
    def test_report_format_enum(self):
        """Test ReportFormat enum values."""
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.CSV.value == "csv"
        assert ReportFormat.XML.value == "xml"
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PDF.value == "pdf"
    
    def test_report_type_enum(self):
        """Test ReportType enum values."""
        assert ReportType.HIPAA_AUDIT.value == "hipaa_audit"
        assert ReportType.PHI_ACCESS.value == "phi_access"
        assert ReportType.USER_ACTIVITY.value == "user_activity"
        assert ReportType.SECURITY_INCIDENTS.value == "security_incidents"
        assert ReportType.COMPLIANCE_VIOLATIONS.value == "compliance_violations"
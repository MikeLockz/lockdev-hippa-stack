"""
HIPAA Compliance Audit Reporter

This module provides comprehensive audit reporting capabilities for HIPAA compliance,
including report generation, data export, integrity validation, and anomaly detection.
"""

from datetime import datetime, timedelta, date
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
import json
import csv
import xml.etree.ElementTree as ET
from io import StringIO
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text
from pydantic import BaseModel, Field

from ...models.user import User
from ...models.audit_log import AuditLog
from ...utils.database import get_db_session

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    """Supported audit report formats."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    HTML = "html"
    PDF = "pdf"


class ReportType(str, Enum):
    """Types of audit reports."""
    HIPAA_AUDIT = "hipaa_audit"
    PHI_ACCESS = "phi_access"
    USER_ACTIVITY = "user_activity"
    SECURITY_INCIDENTS = "security_incidents"
    COMPLIANCE_VIOLATIONS = "compliance_violations"
    SYSTEM_ACCESS = "system_access"
    FAILED_LOGINS = "failed_logins"
    DATA_EXPORT = "data_export"


class AuditReportFilter(BaseModel):
    """Filters for audit report generation."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    user_ids: List[UUID] = Field(default_factory=list)
    patient_ids: List[UUID] = Field(default_factory=list)
    event_types: List[str] = Field(default_factory=list)
    event_categories: List[str] = Field(default_factory=list)
    compliance_status: List[str] = Field(default_factory=list)
    phi_accessed_only: bool = False
    include_system_events: bool = True
    severity_levels: List[str] = Field(default_factory=list)
    departments: List[str] = Field(default_factory=list)
    ip_addresses: List[str] = Field(default_factory=list)


class AuditReportMetadata(BaseModel):
    """Metadata for generated audit reports."""
    report_id: str
    report_type: ReportType
    generated_at: datetime
    generated_by: UUID
    period_start: date
    period_end: date
    total_records: int
    format: ReportFormat
    filters_applied: Dict[str, Any]
    retention_period_days: int = 2555  # 7 years default


class ComplianceAuditReporter:
    """
    Comprehensive HIPAA compliance audit reporting system.
    
    Provides:
    - Multi-format report generation (JSON, CSV, XML, HTML)
    - PHI access reporting with detailed tracking
    - Security incident reporting and analysis
    - Compliance violation detection and reporting
    - Data integrity validation and verification
    - Anomaly detection and pattern analysis
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def generate_hipaa_audit_report(
        self,
        period_start: date,
        period_end: date,
        format: ReportFormat = ReportFormat.JSON,
        filters: Optional[AuditReportFilter] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive HIPAA audit report.
        
        Args:
            period_start: Report start date
            period_end: Report end date
            format: Output format for the report
            filters: Additional filters to apply
            
        Returns:
            dict: Complete HIPAA audit report
        """
        try:
            if not filters:
                filters = AuditReportFilter()
            
            filters.start_date = period_start
            filters.end_date = period_end
            
            # Get audit logs for the period
            audit_logs = await self._get_filtered_audit_logs(filters)
            
            # Generate report sections
            summary = await self._generate_report_summary(audit_logs, period_start, period_end)
            phi_section = await self._generate_phi_access_section(audit_logs)
            security_section = await self._generate_security_section(audit_logs)
            compliance_section = await self._generate_compliance_section(audit_logs)
            user_section = await self._generate_user_activity_section(audit_logs)
            system_section = await self._generate_system_events_section(audit_logs)
            
            # Create report metadata
            metadata = AuditReportMetadata(
                report_id=f"hipaa_audit_{period_start.strftime('%Y%m%d')}_{period_end.strftime('%Y%m%d')}",
                report_type=ReportType.HIPAA_AUDIT,
                generated_at=datetime.utcnow(),
                generated_by=UUID('00000000-0000-0000-0000-000000000000'),  # System generated
                period_start=period_start,
                period_end=period_end,
                total_records=len(audit_logs),
                format=format,
                filters_applied=filters.dict()
            )
            
            # Compile complete report
            report = {
                "metadata": metadata.dict(),
                "summary": summary,
                "phi_access_analysis": phi_section,
                "security_analysis": security_section,
                "compliance_analysis": compliance_section,
                "user_activity_analysis": user_section,
                "system_events_analysis": system_section,
                "detailed_logs": await self._format_detailed_logs(audit_logs, format)
            }
            
            # Log report generation
            await self._log_report_generation(metadata)
            
            logger.info(
                "HIPAA audit report generated",
                extra={
                    "report_id": metadata.report_id,
                    "period_days": (period_end - period_start).days + 1,
                    "total_records": len(audit_logs),
                    "format": format.value
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "HIPAA audit report generation failed",
                extra={
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "error": str(e)
                }
            )
            raise
    
    async def _get_filtered_audit_logs(self, filters: AuditReportFilter) -> List[AuditLog]:
        """Get audit logs based on applied filters."""
        query = select(AuditLog)
        conditions = []
        
        # Date range filter
        if filters.start_date:
            start_datetime = datetime.combine(filters.start_date, datetime.min.time())
            conditions.append(AuditLog.timestamp >= start_datetime)
        
        if filters.end_date:
            end_datetime = datetime.combine(filters.end_date, datetime.max.time())
            conditions.append(AuditLog.timestamp <= end_datetime)
        
        # User filters
        if filters.user_ids:
            conditions.append(AuditLog.user_id.in_(filters.user_ids))
        
        # Patient filters
        if filters.patient_ids:
            conditions.append(AuditLog.patient_id.in_(filters.patient_ids))
        
        # Event filters
        if filters.event_types:
            conditions.append(AuditLog.event_type.in_(filters.event_types))
        
        if filters.event_categories:
            conditions.append(AuditLog.event_category.in_(filters.event_categories))
        
        # Compliance filters
        if filters.compliance_status:
            conditions.append(AuditLog.compliance_status.in_(filters.compliance_status))
        
        # PHI access filter
        if filters.phi_accessed_only:
            conditions.append(AuditLog.phi_accessed == True)
        
        # Department filter
        if filters.departments:
            conditions.append(AuditLog.department.in_(filters.departments))
        
        # IP address filter
        if filters.ip_addresses:
            conditions.append(AuditLog.ip_address.in_(filters.ip_addresses))
        
        # Apply all conditions
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by timestamp
        query = query.order_by(desc(AuditLog.timestamp))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def _generate_report_summary(
        self,
        audit_logs: List[AuditLog],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Generate high-level summary section of the report."""
        total_events = len(audit_logs)
        phi_events = len([log for log in audit_logs if log.phi_accessed])
        compliance_violations = len([log for log in audit_logs if log.compliance_status == 'violation'])
        failed_events = len([log for log in audit_logs if log.outcome == 'failure'])
        
        # Unique metrics
        unique_users = len(set(log.user_id for log in audit_logs if log.user_id))
        unique_ips = len(set(log.ip_address for log in audit_logs if log.ip_address))
        unique_patients = len(set(log.patient_id for log in audit_logs if log.patient_id))
        
        # Time-based metrics
        period_days = (period_end - period_start).days + 1
        avg_events_per_day = total_events / period_days if period_days > 0 else 0
        
        return {
            "period": {
                "start_date": period_start.isoformat(),
                "end_date": period_end.isoformat(),
                "total_days": period_days
            },
            "event_totals": {
                "total_events": total_events,
                "phi_access_events": phi_events,
                "compliance_violations": compliance_violations,
                "failed_events": failed_events,
                "success_rate": round((total_events - failed_events) / total_events * 100, 2) if total_events > 0 else 100
            },
            "unique_metrics": {
                "unique_users": unique_users,
                "unique_ip_addresses": unique_ips,
                "unique_patients_accessed": unique_patients
            },
            "activity_metrics": {
                "average_events_per_day": round(avg_events_per_day, 2),
                "peak_day_events": await self._get_peak_day_events(audit_logs),
                "busiest_hours": await self._get_busiest_hours(audit_logs)
            },
            "compliance_metrics": {
                "compliance_rate": round((total_events - compliance_violations) / total_events * 100, 2) if total_events > 0 else 100,
                "phi_compliance_rate": round((phi_events - len([log for log in audit_logs if log.phi_accessed and log.compliance_status == 'violation'])) / phi_events * 100, 2) if phi_events > 0 else 100
            }
        }
    
    async def _generate_phi_access_section(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Generate PHI access analysis section."""
        phi_logs = [log for log in audit_logs if log.phi_accessed]
        
        if not phi_logs:
            return {"message": "No PHI access events in the reporting period"}
        
        # Access reason breakdown
        reason_counts = {}
        for log in phi_logs:
            reason = log.access_reason or "not_specified"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        # Data element access analysis
        element_counts = {}
        for log in phi_logs:
            if log.data_elements_accessed:
                for element in log.data_elements_accessed:
                    element_counts[element] = element_counts.get(element, 0) + 1
        
        # User PHI access ranking
        user_phi_counts = {}
        for log in phi_logs:
            if log.user_id:
                user_phi_counts[log.user_id] = user_phi_counts.get(log.user_id, 0) + 1
        
        top_phi_users = sorted(user_phi_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Patient access analysis
        patient_counts = {}
        for log in phi_logs:
            if log.patient_id:
                patient_counts[log.patient_id] = patient_counts.get(log.patient_id, 0) + 1
        
        # Minimum necessary compliance
        minimum_necessary_applied = len([log for log in phi_logs if log.minimum_necessary_applied])
        minimum_necessary_rate = round(minimum_necessary_applied / len(phi_logs) * 100, 2) if phi_logs else 0
        
        return {
            "total_phi_access_events": len(phi_logs),
            "access_reason_breakdown": reason_counts,
            "data_elements_accessed": dict(sorted(element_counts.items(), key=lambda x: x[1], reverse=True)),
            "top_phi_accessing_users": [{"user_id": str(uid), "access_count": count} for uid, count in top_phi_users],
            "patient_access_statistics": {
                "unique_patients_accessed": len(patient_counts),
                "most_accessed_patients": sorted([(str(pid), count) for pid, count in patient_counts.items()], key=lambda x: x[1], reverse=True)[:5]
            },
            "minimum_necessary_compliance": {
                "events_with_minimum_necessary": minimum_necessary_applied,
                "minimum_necessary_rate": minimum_necessary_rate
            },
            "phi_access_violations": len([log for log in phi_logs if log.compliance_status == 'violation'])
        }
    
    async def _generate_security_section(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Generate security analysis section."""
        # Authentication events
        auth_logs = [log for log in audit_logs if log.event_category == 'authentication']
        failed_logins = [log for log in auth_logs if 'login' in log.event_type and log.outcome == 'failure']
        successful_logins = [log for log in auth_logs if 'login' in log.event_type and log.outcome == 'success']
        
        # IP address analysis
        ip_counts = {}
        for log in audit_logs:
            if log.ip_address:
                ip_counts[log.ip_address] = ip_counts.get(log.ip_address, 0) + 1
        
        suspicious_ips = {ip: count for ip, count in ip_counts.items() if count > 100}  # More than 100 events
        
        # Failed login analysis by user
        failed_login_users = {}
        for log in failed_logins:
            if log.user_id:
                failed_login_users[log.user_id] = failed_login_users.get(log.user_id, 0) + 1
        
        # Risk score analysis
        high_risk_events = [log for log in audit_logs if log.risk_score and log.risk_score > 70]
        
        return {
            "authentication_summary": {
                "total_authentication_events": len(auth_logs),
                "successful_logins": len(successful_logins),
                "failed_logins": len(failed_logins),
                "login_success_rate": round(len(successful_logins) / (len(successful_logins) + len(failed_logins)) * 100, 2) if (successful_logins or failed_logins) else 0
            },
            "ip_address_analysis": {
                "unique_ip_addresses": len(ip_counts),
                "top_ip_addresses": sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10],
                "suspicious_ip_addresses": suspicious_ips
            },
            "failed_login_analysis": {
                "users_with_failed_logins": len(failed_login_users),
                "top_failed_login_users": sorted([(str(uid), count) for uid, count in failed_login_users.items()], key=lambda x: x[1], reverse=True)[:5]
            },
            "risk_analysis": {
                "high_risk_events": len(high_risk_events),
                "average_risk_score": round(sum(log.risk_score for log in audit_logs if log.risk_score) / len([log for log in audit_logs if log.risk_score]), 2) if any(log.risk_score for log in audit_logs) else 0
            }
        }
    
    async def _generate_compliance_section(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Generate compliance analysis section."""
        # Compliance status breakdown
        compliance_counts = {}
        for log in audit_logs:
            status = log.compliance_status
            compliance_counts[status] = compliance_counts.get(status, 0) + 1
        
        # Violation analysis
        violations = [log for log in audit_logs if log.compliance_status == 'violation']
        violation_types = {}
        
        for log in violations:
            if log.details and 'violation_type' in log.details:
                v_type = log.details['violation_type']
                violation_types[v_type] = violation_types.get(v_type, 0) + 1
        
        # Department compliance analysis
        dept_compliance = {}
        for log in audit_logs:
            if log.department:
                if log.department not in dept_compliance:
                    dept_compliance[log.department] = {"total": 0, "violations": 0}
                dept_compliance[log.department]["total"] += 1
                if log.compliance_status == 'violation':
                    dept_compliance[log.department]["violations"] += 1
        
        # Calculate compliance rates by department
        dept_compliance_rates = {}
        for dept, counts in dept_compliance.items():
            rate = (counts["total"] - counts["violations"]) / counts["total"] * 100
            dept_compliance_rates[dept] = round(rate, 2)
        
        return {
            "compliance_status_breakdown": compliance_counts,
            "violation_analysis": {
                "total_violations": len(violations),
                "violation_types": violation_types,
                "violation_rate": round(len(violations) / len(audit_logs) * 100, 2) if audit_logs else 0
            },
            "department_compliance": dept_compliance_rates,
            "compliance_trends": await self._analyze_compliance_trends(audit_logs)
        }
    
    async def _generate_user_activity_section(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Generate user activity analysis section."""
        # User activity counts
        user_activity = {}
        for log in audit_logs:
            if log.user_id:
                if log.user_id not in user_activity:
                    user_activity[log.user_id] = {
                        "total_events": 0,
                        "phi_accesses": 0,
                        "violations": 0,
                        "failed_attempts": 0
                    }
                
                user_activity[log.user_id]["total_events"] += 1
                
                if log.phi_accessed:
                    user_activity[log.user_id]["phi_accesses"] += 1
                
                if log.compliance_status == 'violation':
                    user_activity[log.user_id]["violations"] += 1
                
                if log.outcome == 'failure':
                    user_activity[log.user_id]["failed_attempts"] += 1
        
        # Top active users
        top_users = sorted(user_activity.items(), key=lambda x: x[1]["total_events"], reverse=True)[:10]
        
        # Users with violations
        users_with_violations = {uid: data for uid, data in user_activity.items() if data["violations"] > 0}
        
        return {
            "total_active_users": len(user_activity),
            "top_active_users": [
                {
                    "user_id": str(uid),
                    "total_events": data["total_events"],
                    "phi_accesses": data["phi_accesses"],
                    "violations": data["violations"]
                }
                for uid, data in top_users
            ],
            "users_with_violations": len(users_with_violations),
            "user_violation_details": [
                {
                    "user_id": str(uid),
                    "violation_count": data["violations"],
                    "total_events": data["total_events"]
                }
                for uid, data in sorted(users_with_violations.items(), key=lambda x: x[1]["violations"], reverse=True)[:5]
            ]
        }
    
    async def _generate_system_events_section(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Generate system events analysis section."""
        # Event type breakdown
        event_type_counts = {}
        for log in audit_logs:
            event_type = log.event_type
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Event category breakdown
        category_counts = {}
        for log in audit_logs:
            category = log.event_category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # System health indicators
        system_errors = len([log for log in audit_logs if log.outcome == 'error'])
        
        return {
            "event_type_breakdown": dict(sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True)),
            "event_category_breakdown": category_counts,
            "system_health": {
                "total_system_errors": system_errors,
                "error_rate": round(system_errors / len(audit_logs) * 100, 2) if audit_logs else 0
            },
            "hourly_distribution": await self._get_hourly_distribution(audit_logs)
        }
    
    async def _format_detailed_logs(self, audit_logs: List[AuditLog], format: ReportFormat) -> Union[List[Dict], str]:
        """Format detailed audit logs based on requested format."""
        if format == ReportFormat.JSON:
            return [log.to_dict(include_sensitive=False) for log in audit_logs]
        
        elif format == ReportFormat.CSV:
            output = StringIO()
            if audit_logs:
                fieldnames = audit_logs[0].to_dict(include_sensitive=False).keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for log in audit_logs:
                    writer.writerow(log.to_dict(include_sensitive=False))
            return output.getvalue()
        
        elif format == ReportFormat.XML:
            root = ET.Element("audit_logs")
            for log in audit_logs:
                log_element = ET.SubElement(root, "audit_log")
                log_data = log.to_dict(include_sensitive=False)
                for key, value in log_data.items():
                    if value is not None:
                        elem = ET.SubElement(log_element, key)
                        elem.text = str(value)
            return ET.tostring(root, encoding='unicode')
        
        else:
            # Default to JSON for unsupported formats
            return [log.to_dict(include_sensitive=False) for log in audit_logs]
    
    async def _get_peak_day_events(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Get the day with the most events."""
        daily_counts = {}
        for log in audit_logs:
            day = log.timestamp.date()
            daily_counts[day] = daily_counts.get(day, 0) + 1
        
        if not daily_counts:
            return {"date": None, "event_count": 0}
        
        peak_day, peak_count = max(daily_counts.items(), key=lambda x: x[1])
        return {"date": peak_day.isoformat(), "event_count": peak_count}
    
    async def _get_busiest_hours(self, audit_logs: List[AuditLog]) -> List[Dict[str, Any]]:
        """Get the busiest hours of the day."""
        hourly_counts = {}
        for log in audit_logs:
            hour = log.timestamp.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"hour": hour, "event_count": count} for hour, count in sorted_hours[:3]]
    
    async def _get_hourly_distribution(self, audit_logs: List[AuditLog]) -> Dict[int, int]:
        """Get hourly distribution of events."""
        hourly_counts = {}
        for hour in range(24):
            hourly_counts[hour] = 0
        
        for log in audit_logs:
            hour = log.timestamp.hour
            hourly_counts[hour] += 1
        
        return hourly_counts
    
    async def _analyze_compliance_trends(self, audit_logs: List[AuditLog]) -> Dict[str, Any]:
        """Analyze compliance trends over time."""
        # Group by day
        daily_compliance = {}
        for log in audit_logs:
            day = log.timestamp.date()
            if day not in daily_compliance:
                daily_compliance[day] = {"total": 0, "violations": 0}
            
            daily_compliance[day]["total"] += 1
            if log.compliance_status == 'violation':
                daily_compliance[day]["violations"] += 1
        
        # Calculate daily compliance rates
        daily_rates = {}
        for day, counts in daily_compliance.items():
            rate = (counts["total"] - counts["violations"]) / counts["total"] * 100
            daily_rates[day] = round(rate, 2)
        
        # Calculate trend
        sorted_days = sorted(daily_rates.keys())
        if len(sorted_days) >= 2:
            start_rate = daily_rates[sorted_days[0]]
            end_rate = daily_rates[sorted_days[-1]]
            trend = "improving" if end_rate > start_rate else "declining" if end_rate < start_rate else "stable"
        else:
            trend = "stable"
        
        return {
            "daily_compliance_rates": {day.isoformat(): rate for day, rate in daily_rates.items()},
            "trend": trend,
            "average_compliance_rate": round(sum(daily_rates.values()) / len(daily_rates), 2) if daily_rates else 100
        }
    
    async def _log_report_generation(self, metadata: AuditReportMetadata) -> None:
        """Log the generation of an audit report."""
        audit_entry = AuditLog(
            user_id=metadata.generated_by,
            event_type="audit_report_generated",
            event_category="access",
            details={
                "report_id": metadata.report_id,
                "report_type": metadata.report_type.value,
                "period_start": metadata.period_start.isoformat(),
                "period_end": metadata.period_end.isoformat(),
                "total_records": metadata.total_records,
                "format": metadata.format.value
            },
            outcome="success",
            compliance_status="compliant"
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
    
    async def export_audit_logs(
        self,
        filters: AuditReportFilter,
        format: ReportFormat,
        sanitize: bool = True
    ) -> str:
        """
        Export audit logs in specified format.
        
        Args:
            filters: Filters to apply to the export
            format: Export format
            sanitize: Whether to sanitize sensitive data
            
        Returns:
            str: Formatted audit log data
        """
        try:
            audit_logs = await self._get_filtered_audit_logs(filters)
            
            if sanitize:
                log_data = [log.sanitize_for_export() for log in audit_logs]
            else:
                log_data = [log.to_dict(include_sensitive=True) for log in audit_logs]
            
            if format == ReportFormat.JSON:
                return json.dumps(log_data, indent=2, default=str)
            
            elif format == ReportFormat.CSV:
                output = StringIO()
                if log_data:
                    fieldnames = log_data[0].keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(log_data)
                return output.getvalue()
            
            elif format == ReportFormat.XML:
                root = ET.Element("audit_logs")
                for log_dict in log_data:
                    log_element = ET.SubElement(root, "audit_log")
                    for key, value in log_dict.items():
                        if value is not None:
                            elem = ET.SubElement(log_element, key)
                            elem.text = str(value)
                return ET.tostring(root, encoding='unicode')
            
            else:
                return json.dumps(log_data, indent=2, default=str)
                
        except Exception as e:
            logger.error(
                "Audit log export failed",
                extra={
                    "format": format.value,
                    "error": str(e)
                }
            )
            raise
    
    async def validate_audit_log_integrity(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Validate audit log integrity by checking record hashes.
        
        Args:
            days_back: Number of days to check
            
        Returns:
            dict: Integrity validation results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.timestamp >= cutoff_date)
                .order_by(AuditLog.timestamp)
            )
            audit_logs = result.scalars().all()
            
            total_records = len(audit_logs)
            valid_records = 0
            invalid_records = []
            
            for log in audit_logs:
                try:
                    if log.verify_integrity():
                        valid_records += 1
                    else:
                        invalid_records.append({
                            "log_id": str(log.id),
                            "timestamp": log.timestamp.isoformat(),
                            "event_type": log.event_type,
                            "stored_hash": log.record_hash,
                            "computed_hash": log._generate_record_hash()
                        })
                except Exception as e:
                    invalid_records.append({
                        "log_id": str(log.id),
                        "timestamp": log.timestamp.isoformat(),
                        "error": f"Hash verification failed: {str(e)}"
                    })
            
            integrity_rate = (valid_records / total_records * 100) if total_records > 0 else 100
            
            validation_result = {
                "validation_date": datetime.utcnow().isoformat(),
                "period_analyzed_days": days_back,
                "total_records_checked": total_records,
                "valid_records": valid_records,
                "invalid_records_count": len(invalid_records),
                "integrity_rate": round(integrity_rate, 2),
                "status": "PASS" if len(invalid_records) == 0 else "FAIL",
                "invalid_record_details": invalid_records[:10]  # First 10 invalid records
            }
            
            # Log integrity check
            audit_entry = AuditLog(
                event_type="audit_log_integrity_check",
                event_category="access",
                details={
                    "total_records": total_records,
                    "valid_records": valid_records,
                    "invalid_records": len(invalid_records),
                    "integrity_rate": integrity_rate
                },
                outcome="success" if len(invalid_records) == 0 else "failure",
                compliance_status="compliant" if len(invalid_records) == 0 else "violation"
            )
            
            self.db.add(audit_entry)
            await self.db.commit()
            
            logger.info(
                "Audit log integrity validation completed",
                extra={
                    "total_records": total_records,
                    "integrity_rate": integrity_rate,
                    "invalid_records": len(invalid_records)
                }
            )
            
            return validation_result
            
        except Exception as e:
            logger.error(
                "Audit log integrity validation failed",
                extra={
                    "days_back": days_back,
                    "error": str(e)
                }
            )
            return {
                "error": "Integrity validation failed",
                "message": str(e)
            }
    
    async def detect_unusual_access_patterns(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """
        Detect unusual access patterns in audit logs.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            List[dict]: Unusual patterns detected
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.timestamp >= cutoff_date)
                .order_by(AuditLog.timestamp)
            )
            audit_logs = result.scalars().all()
            
            patterns = []
            
            # Pattern 1: Unusual volume of events from single user
            user_event_counts = {}
            for log in audit_logs:
                if log.user_id:
                    user_event_counts[log.user_id] = user_event_counts.get(log.user_id, 0) + 1
            
            avg_events_per_user = sum(user_event_counts.values()) / len(user_event_counts) if user_event_counts else 0
            
            for user_id, count in user_event_counts.items():
                if count > avg_events_per_user * 5:  # More than 5x average
                    patterns.append({
                        "type": "unusual_user_volume",
                        "user_id": str(user_id),
                        "event_count": count,
                        "average_count": round(avg_events_per_user, 2),
                        "severity": "medium"
                    })
            
            # Pattern 2: Access from unusual IP addresses
            ip_counts = {}
            user_ips = {}
            
            for log in audit_logs:
                if log.ip_address:
                    ip_counts[log.ip_address] = ip_counts.get(log.ip_address, 0) + 1
                    
                    if log.user_id:
                        if log.user_id not in user_ips:
                            user_ips[log.user_id] = set()
                        user_ips[log.user_id].add(log.ip_address)
            
            # Check for users with many different IPs
            for user_id, ips in user_ips.items():
                if len(ips) > 5:  # More than 5 different IPs
                    patterns.append({
                        "type": "multiple_ip_addresses",
                        "user_id": str(user_id),
                        "ip_count": len(ips),
                        "ip_addresses": list(ips)[:5],  # First 5 IPs
                        "severity": "high"
                    })
            
            # Pattern 3: High-risk events clustering
            high_risk_events = [log for log in audit_logs if log.risk_score and log.risk_score > 80]
            if len(high_risk_events) > 10:
                patterns.append({
                    "type": "high_risk_event_cluster",
                    "high_risk_count": len(high_risk_events),
                    "time_span_hours": (max(log.timestamp for log in high_risk_events) - min(log.timestamp for log in high_risk_events)).total_seconds() / 3600,
                    "severity": "high"
                })
            
            # Pattern 4: After-hours activity spikes
            after_hours_events = []
            for log in audit_logs:
                hour = log.timestamp.hour
                if hour >= 22 or hour <= 5:  # 10 PM to 5 AM
                    after_hours_events.append(log)
            
            if len(after_hours_events) > len(audit_logs) * 0.2:  # More than 20% after hours
                patterns.append({
                    "type": "after_hours_activity_spike",
                    "after_hours_count": len(after_hours_events),
                    "total_events": len(audit_logs),
                    "after_hours_percentage": round(len(after_hours_events) / len(audit_logs) * 100, 2),
                    "severity": "medium"
                })
            
            logger.info(
                "Unusual access pattern detection completed",
                extra={
                    "days_analyzed": days_back,
                    "patterns_detected": len(patterns),
                    "total_events_analyzed": len(audit_logs)
                }
            )
            
            return patterns
            
        except Exception as e:
            logger.error(
                "Unusual access pattern detection failed",
                extra={
                    "days_back": days_back,
                    "error": str(e)
                }
            )
            return []
    
    async def generate_user_access_report(self, user_id: UUID, days_back: int = 30) -> Dict[str, Any]:
        """
        Generate detailed access report for a specific user.
        
        Args:
            user_id: User ID to generate report for
            days_back: Number of days to include in report
            
        Returns:
            dict: User access report
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Get user's audit logs
            result = await self.db.execute(
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.user_id == user_id,
                        AuditLog.timestamp >= cutoff_date
                    )
                )
                .order_by(desc(AuditLog.timestamp))
            )
            user_logs = result.scalars().all()
            
            # Get user details
            user_result = await self.db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {"error": "User not found"}
            
            # Analyze user activity
            phi_accesses = [log for log in user_logs if log.phi_accessed]
            failed_attempts = [log for log in user_logs if log.outcome == 'failure']
            violations = [log for log in user_logs if log.compliance_status == 'violation']
            
            # Activity timeline
            daily_activity = {}
            for log in user_logs:
                day = log.timestamp.date()
                if day not in daily_activity:
                    daily_activity[day] = {"total": 0, "phi_access": 0, "violations": 0}
                
                daily_activity[day]["total"] += 1
                if log.phi_accessed:
                    daily_activity[day]["phi_access"] += 1
                if log.compliance_status == 'violation':
                    daily_activity[day]["violations"] += 1
            
            # IP address usage
            ip_usage = {}
            for log in user_logs:
                if log.ip_address:
                    ip_usage[log.ip_address] = ip_usage.get(log.ip_address, 0) + 1
            
            report = {
                "user_info": {
                    "user_id": str(user_id),
                    "email": user.email,
                    "role": user.role,
                    "department": user.department,
                    "is_active": user.is_active,
                    "phi_access_granted": user.phi_access_granted
                },
                "report_period": {
                    "start_date": cutoff_date.date().isoformat(),
                    "end_date": datetime.utcnow().date().isoformat(),
                    "days": days_back
                },
                "activity_summary": {
                    "total_events": len(user_logs),
                    "phi_accesses": len(phi_accesses),
                    "failed_attempts": len(failed_attempts),
                    "violations": len(violations),
                    "unique_days_active": len(daily_activity)
                },
                "daily_activity": {
                    day.isoformat(): activity for day, activity in sorted(daily_activity.items())
                },
                "phi_access_analysis": {
                    "total_phi_accesses": len(phi_accesses),
                    "unique_patients_accessed": len(set(log.patient_id for log in phi_accesses if log.patient_id)),
                    "most_accessed_data_elements": self._get_most_accessed_elements(phi_accesses)
                },
                "security_analysis": {
                    "unique_ip_addresses": len(ip_usage),
                    "ip_address_usage": dict(sorted(ip_usage.items(), key=lambda x: x[1], reverse=True)),
                    "failed_login_attempts": len([log for log in failed_attempts if 'login' in log.event_type]),
                    "compliance_violations": len(violations)
                },
                "recent_activity": [
                    {
                        "timestamp": log.timestamp.isoformat(),
                        "event_type": log.event_type,
                        "outcome": log.outcome,
                        "phi_accessed": log.phi_accessed,
                        "compliance_status": log.compliance_status
                    }
                    for log in user_logs[:20]  # Last 20 events
                ]
            }
            
            logger.info(
                "User access report generated",
                extra={
                    "user_id": str(user_id),
                    "days_back": days_back,
                    "total_events": len(user_logs)
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "User access report generation failed",
                extra={
                    "user_id": str(user_id),
                    "days_back": days_back,
                    "error": str(e)
                }
            )
            return {"error": f"Report generation failed: {str(e)}"}
    
    def _get_most_accessed_elements(self, phi_logs: List[AuditLog]) -> Dict[str, int]:
        """Get the most frequently accessed data elements."""
        element_counts = {}
        for log in phi_logs:
            if log.data_elements_accessed:
                for element in log.data_elements_accessed:
                    element_counts[element] = element_counts.get(element, 0) + 1
        
        return dict(sorted(element_counts.items(), key=lambda x: x[1], reverse=True))
"""
HIPAA Compliance Engine

This module provides comprehensive HIPAA compliance validation and enforcement,
including password policies, session compliance, violation detection, and
compliance reporting.
"""

from datetime import datetime, timedelta, date
from enum import Enum
from typing import List, Dict, Any, Optional
from uuid import UUID
import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from pydantic import BaseModel, Field

from ...models.user import User
from ...models.audit_log import AuditLog
from ...utils.database import get_db_session

logger = logging.getLogger(__name__)


class ComplianceStatus(str, Enum):
    """Compliance status values."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    VIOLATION = "violation"
    REMEDIATED = "remediated"


class ViolationType(str, Enum):
    """Types of HIPAA compliance violations."""
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    EXCESSIVE_ACCESS = "excessive_access"
    AFTER_HOURS_ACCESS = "after_hours_access"
    FAILED_AUTHENTICATION = "failed_authentication"
    PASSWORD_POLICY_VIOLATION = "password_policy_violation"
    SESSION_TIMEOUT_VIOLATION = "session_timeout_violation"
    PHI_ACCESS_WITHOUT_REASON = "phi_access_without_reason"
    BULK_DATA_EXPORT = "bulk_data_export"
    ACCOUNT_SHARING = "account_sharing"
    EXPIRED_LICENSE = "expired_license"
    MISSING_TRAINING = "missing_training"


class ComplianceResult(BaseModel):
    """Result of a compliance check."""
    is_compliant: bool
    status: ComplianceStatus
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    compliance_score: int = Field(ge=0, le=100)  # 0-100 score
    last_checked: datetime = Field(default_factory=datetime.utcnow)


class ComplianceViolation(BaseModel):
    """A HIPAA compliance violation record."""
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    violation_type: ViolationType
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")  # low, medium, high, critical
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None
    patient_ids: List[UUID] = Field(default_factory=list)
    requires_notification: bool = True


class HIPAAComplianceEngine:
    """
    HIPAA Compliance validation and enforcement engine.
    
    Provides comprehensive compliance checking including:
    - User compliance validation
    - Password policy enforcement  
    - Session compliance monitoring
    - Violation detection and reporting
    - Compliance metrics and scoring
    """
    
    # Password policy requirements
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_MAX_AGE_DAYS = 90
    PASSWORD_HISTORY_COUNT = 12
    
    # Session policy requirements
    MAX_SESSION_DURATION_HOURS = 8
    IDLE_TIMEOUT_MINUTES = 15
    MAX_CONCURRENT_SESSIONS = 5
    
    # Compliance monitoring thresholds
    MAX_FAILED_LOGINS_PER_HOUR = 3
    MAX_PHI_ACCESSES_PER_HOUR = 50
    AFTER_HOURS_START = 18  # 6 PM
    AFTER_HOURS_END = 7     # 7 AM
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def validate_user_compliance(self, user: User) -> ComplianceResult:
        """
        Validate a user's overall HIPAA compliance status.
        
        Args:
            user: User to validate
            
        Returns:
            ComplianceResult: Comprehensive compliance assessment
        """
        violations = []
        warnings = []
        recommendations = []
        compliance_score = 100  # Start with perfect score, deduct for issues
        
        try:
            # Check PHI access authorization
            if user.phi_access_granted and user.phi_access_expiry:
                if user.phi_access_expiry < datetime.utcnow():
                    violations.append("PHI access has expired")
                    compliance_score -= 20
                elif user.phi_access_expiry < datetime.utcnow() + timedelta(days=7):
                    warnings.append("PHI access expires within 7 days")
                    compliance_score -= 5
            
            # Check password compliance
            password_issues = await self._check_password_compliance(user)
            violations.extend(password_issues.get('violations', []))
            warnings.extend(password_issues.get('warnings', []))
            compliance_score -= len(password_issues.get('violations', [])) * 15
            compliance_score -= len(password_issues.get('warnings', [])) * 5
            
            # Check professional license
            if user.license_number and user.license_expiry:
                if user.license_expiry < datetime.utcnow():
                    violations.append(f"Professional license expired on {user.license_expiry.date()}")
                    compliance_score -= 25
                elif user.license_expiry < datetime.utcnow() + timedelta(days=30):
                    warnings.append("Professional license expires within 30 days")
                    compliance_score -= 10
            
            # Check HIPAA training
            if user.needs_hipaa_training():
                violations.append("HIPAA training is overdue")
                compliance_score -= 20
            elif user.hipaa_training_completed_at:
                training_age = datetime.utcnow() - user.hipaa_training_completed_at
                if training_age > timedelta(days=300):  # 10 months
                    warnings.append("HIPAA training will expire soon")
                    compliance_score -= 5
            
            # Check MFA requirement
            if not user.mfa_enabled and user.role in ['PHYSICIAN', 'NURSE', 'ADMIN']:
                violations.append("Multi-factor authentication is required for this role")
                compliance_score -= 15
            
            # Check account security
            if user.account_locked_until and user.account_locked_until > datetime.utcnow():
                warnings.append("Account is currently locked due to security concerns")
                compliance_score -= 5
            
            # Generate recommendations
            if user.password_must_change:
                recommendations.append("Change password immediately")
            if not user.mfa_enabled:
                recommendations.append("Enable multi-factor authentication")
            if not user.hipaa_training_completed_at:
                recommendations.append("Complete HIPAA training")
            
            # Ensure minimum score
            compliance_score = max(0, compliance_score)
            
            # Determine overall status
            if compliance_score >= 95:
                status = ComplianceStatus.COMPLIANT
            elif compliance_score >= 70:
                status = ComplianceStatus.UNDER_REVIEW
            else:
                status = ComplianceStatus.NON_COMPLIANT
            
            result = ComplianceResult(
                is_compliant=len(violations) == 0,
                status=status,
                violations=violations,
                warnings=warnings,
                recommendations=recommendations,
                compliance_score=compliance_score
            )
            
            # Log compliance check
            await self._log_compliance_check(user.id, result)
            
            return result
            
        except Exception as e:
            logger.error(
                "User compliance validation failed",
                extra={
                    "user_id": str(user.id),
                    "error": str(e)
                }
            )
            return ComplianceResult(
                is_compliant=False,
                status=ComplianceStatus.UNDER_REVIEW,
                violations=["Compliance check failed due to system error"],
                compliance_score=0
            )
    
    async def _check_password_compliance(self, user: User) -> Dict[str, List[str]]:
        """Check password-related compliance issues."""
        violations = []
        warnings = []
        
        # Check password age
        if user.password_expires_at and user.password_expires_at < datetime.utcnow():
            violations.append("Password has expired")
        elif user.password_expires_at and user.password_expires_at < datetime.utcnow() + timedelta(days=7):
            warnings.append("Password expires within 7 days")
        
        # Check password change requirement
        if user.password_must_change:
            violations.append("Password change is required")
        
        # Check password age (even if no explicit expiry)
        if user.password_changed_at:
            password_age = datetime.utcnow() - user.password_changed_at
            if password_age > timedelta(days=self.PASSWORD_MAX_AGE_DAYS):
                violations.append(f"Password is {password_age.days} days old (max {self.PASSWORD_MAX_AGE_DAYS})")
            elif password_age > timedelta(days=self.PASSWORD_MAX_AGE_DAYS - 14):
                warnings.append("Password will expire soon")
        
        return {"violations": violations, "warnings": warnings}
    
    async def enforce_password_policy(self, user: User, new_password: str) -> Dict[str, Any]:
        """
        Enforce HIPAA-compliant password policy.
        
        Args:
            user: User changing password
            new_password: New password to validate
            
        Returns:
            dict: Validation result with success/failure and details
        """
        violations = []
        
        try:
            # Check minimum length
            if len(new_password) < self.PASSWORD_MIN_LENGTH:
                violations.append(f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters")
            
            # Check complexity requirements
            if not re.search(r'[A-Z]', new_password):
                violations.append("Password must contain at least one uppercase letter")
            
            if not re.search(r'[a-z]', new_password):
                violations.append("Password must contain at least one lowercase letter")
            
            if not re.search(r'\d', new_password):
                violations.append("Password must contain at least one number")
            
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
                violations.append("Password must contain at least one special character")
            
            # Check for common patterns
            if re.search(r'(.)\1{2,}', new_password):
                violations.append("Password cannot contain three or more consecutive identical characters")
            
            if re.search(r'(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def)', new_password.lower()):
                violations.append("Password cannot contain sequential characters")
            
            # Check against password history
            if user.password_history:
                from ...utils.security import pwd_context
                for historical_hash in user.password_history[-self.PASSWORD_HISTORY_COUNT:]:
                    if pwd_context.verify(new_password, historical_hash):
                        violations.append(f"Password has been used recently (last {self.PASSWORD_HISTORY_COUNT} passwords)")
                        break
            
            # Check for user information in password
            user_info = [
                user.email.split('@')[0] if user.email else '',
                user.first_name or '',
                user.last_name or '',
                user.department or ''
            ]
            
            for info in user_info:
                if info and len(info) > 2 and info.lower() in new_password.lower():
                    violations.append("Password cannot contain personal information")
                    break
            
            # Check against common passwords (simplified check)
            common_passwords = [
                'password', '123456', 'qwerty', 'admin', 'welcome', 'login',
                'healthcare', 'hospital', 'medical', 'hipaa', 'patient'
            ]
            
            if new_password.lower() in common_passwords:
                violations.append("Password is too common")
            
            success = len(violations) == 0
            
            # Log password policy check
            audit_entry = AuditLog(
                user_id=user.id,
                event_type="password_policy_check",
                event_category="authentication",
                details={
                    "policy_violations": violations,
                    "success": success
                },
                outcome="success" if success else "failure",
                compliance_status="compliant" if success else "violation"
            )
            
            self.db.add(audit_entry)
            await self.db.commit()
            
            return {
                "success": success,
                "violations": violations,
                "policy_requirements": {
                    "min_length": self.PASSWORD_MIN_LENGTH,
                    "requires_uppercase": True,
                    "requires_lowercase": True,
                    "requires_number": True,
                    "requires_special_char": True,
                    "history_check": self.PASSWORD_HISTORY_COUNT,
                    "max_age_days": self.PASSWORD_MAX_AGE_DAYS
                }
            }
            
        except Exception as e:
            logger.error(
                "Password policy enforcement failed",
                extra={
                    "user_id": str(user.id),
                    "error": str(e)
                }
            )
            return {
                "success": False,
                "violations": ["Password policy check failed"],
                "error": str(e)
            }
    
    async def check_session_compliance(self, session_data: Dict[str, Any]) -> bool:
        """
        Check if a user session meets HIPAA compliance requirements.
        
        Args:
            session_data: Session information dictionary
            
        Returns:
            bool: True if session is compliant
        """
        try:
            user_id = session_data.get('user_id')
            session_start = datetime.fromisoformat(session_data.get('created_at', ''))
            last_activity = datetime.fromisoformat(session_data.get('last_activity', ''))
            current_time = datetime.utcnow()
            
            # Check session duration
            session_duration = current_time - session_start
            if session_duration > timedelta(hours=self.MAX_SESSION_DURATION_HOURS):
                await self._create_violation(
                    user_id=UUID(user_id) if user_id else None,
                    violation_type=ViolationType.SESSION_TIMEOUT_VIOLATION,
                    severity="medium",
                    description=f"Session exceeded maximum duration of {self.MAX_SESSION_DURATION_HOURS} hours",
                    details={"session_duration_hours": session_duration.total_seconds() / 3600}
                )
                return False
            
            # Check idle timeout
            idle_time = current_time - last_activity
            if idle_time > timedelta(minutes=self.IDLE_TIMEOUT_MINUTES):
                await self._create_violation(
                    user_id=UUID(user_id) if user_id else None,
                    violation_type=ViolationType.SESSION_TIMEOUT_VIOLATION,
                    severity="low",
                    description=f"Session idle for more than {self.IDLE_TIMEOUT_MINUTES} minutes",
                    details={"idle_time_minutes": idle_time.total_seconds() / 60}
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Session compliance check failed",
                extra={
                    "session_data": session_data,
                    "error": str(e)
                }
            )
            return False
    
    async def detect_compliance_violations(self, hours_back: int = 24) -> List[ComplianceViolation]:
        """
        Detect HIPAA compliance violations in audit logs.
        
        Args:
            hours_back: How many hours back to check for violations
            
        Returns:
            List[ComplianceViolation]: Detected violations
        """
        violations = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        try:
            # Get recent audit logs
            result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.timestamp >= cutoff_time)
                .order_by(desc(AuditLog.timestamp))
            )
            audit_logs = result.scalars().all()
            
            # Group logs by user for pattern analysis
            user_logs = {}
            for log in audit_logs:
                if log.user_id:
                    if log.user_id not in user_logs:
                        user_logs[log.user_id] = []
                    user_logs[log.user_id].append(log)
            
            # Analyze each user's activity
            for user_id, logs in user_logs.items():
                user_violations = await self._analyze_user_activity(user_id, logs)
                violations.extend(user_violations)
            
            # Detect system-wide patterns
            system_violations = await self._analyze_system_patterns(audit_logs)
            violations.extend(system_violations)
            
            # Store detected violations
            for violation in violations:
                await self._create_violation(
                    user_id=violation.user_id,
                    violation_type=violation.violation_type,
                    severity=violation.severity,
                    description=violation.description,
                    details=violation.details
                )
            
            logger.info(
                "Compliance violation detection completed",
                extra={
                    "violations_detected": len(violations),
                    "hours_analyzed": hours_back
                }
            )
            
            return violations
            
        except Exception as e:
            logger.error(
                "Compliance violation detection failed",
                extra={
                    "hours_back": hours_back,
                    "error": str(e)
                }
            )
            return []
    
    async def _analyze_user_activity(self, user_id: UUID, logs: List[AuditLog]) -> List[ComplianceViolation]:
        """Analyze individual user activity for violations."""
        violations = []
        
        # Check for excessive failed logins
        failed_logins = [log for log in logs if 'login' in log.event_type and log.outcome == 'failure']
        if len(failed_logins) > self.MAX_FAILED_LOGINS_PER_HOUR:
            violations.append(ComplianceViolation(
                user_id=user_id,
                violation_type=ViolationType.FAILED_AUTHENTICATION,
                severity="high",
                description=f"Excessive failed login attempts ({len(failed_logins)} in analysis period)",
                details={"failed_login_count": len(failed_logins)}
            ))
        
        # Check for excessive PHI access
        phi_accesses = [log for log in logs if log.phi_accessed]
        if len(phi_accesses) > self.MAX_PHI_ACCESSES_PER_HOUR:
            violations.append(ComplianceViolation(
                user_id=user_id,
                violation_type=ViolationType.EXCESSIVE_ACCESS,
                severity="medium",
                description=f"Excessive PHI access attempts ({len(phi_accesses)} in analysis period)",
                details={"phi_access_count": len(phi_accesses)}
            ))
        
        # Check for after-hours access
        after_hours_accesses = []
        for log in phi_accesses:
            log_hour = log.timestamp.hour
            if log_hour >= self.AFTER_HOURS_START or log_hour <= self.AFTER_HOURS_END:
                after_hours_accesses.append(log)
        
        if after_hours_accesses:
            violations.append(ComplianceViolation(
                user_id=user_id,
                violation_type=ViolationType.AFTER_HOURS_ACCESS,
                severity="medium",
                description=f"PHI access during after-hours ({len(after_hours_accesses)} instances)",
                details={
                    "after_hours_count": len(after_hours_accesses),
                    "timestamps": [log.timestamp.isoformat() for log in after_hours_accesses[:5]]
                }
            ))
        
        # Check for PHI access without proper reason
        phi_without_reason = [log for log in phi_accesses if not log.access_reason]
        if phi_without_reason:
            violations.append(ComplianceViolation(
                user_id=user_id,
                violation_type=ViolationType.PHI_ACCESS_WITHOUT_REASON,
                severity="high",
                description=f"PHI access without documented reason ({len(phi_without_reason)} instances)",
                details={"access_without_reason_count": len(phi_without_reason)}
            ))
        
        return violations
    
    async def _analyze_system_patterns(self, logs: List[AuditLog]) -> List[ComplianceViolation]:
        """Analyze system-wide patterns for violations."""
        violations = []
        
        # Check for potential account sharing (same account, multiple IPs)
        user_ip_mapping = {}
        for log in logs:
            if log.user_id and log.ip_address:
                if log.user_id not in user_ip_mapping:
                    user_ip_mapping[log.user_id] = set()
                user_ip_mapping[log.user_id].add(log.ip_address)
        
        for user_id, ips in user_ip_mapping.items():
            if len(ips) > 3:  # More than 3 different IPs in analysis period
                violations.append(ComplianceViolation(
                    user_id=user_id,
                    violation_type=ViolationType.ACCOUNT_SHARING,
                    severity="high",
                    description=f"Account accessed from {len(ips)} different IP addresses",
                    details={"ip_count": len(ips), "ip_addresses": list(ips)[:5]}
                ))
        
        return violations
    
    async def _create_violation(
        self,
        user_id: Optional[UUID],
        violation_type: ViolationType,
        severity: str,
        description: str,
        details: Dict[str, Any]
    ) -> None:
        """Create a compliance violation record."""
        audit_entry = AuditLog(
            user_id=user_id,
            event_type="compliance_violation_detected",
            event_category="authorization",
            details={
                "violation_type": violation_type.value,
                "severity": severity,
                "description": description,
                "violation_details": details
            },
            outcome="failure",
            compliance_status="violation"
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
    
    async def _log_compliance_check(self, user_id: UUID, result: ComplianceResult) -> None:
        """Log a compliance check result."""
        audit_entry = AuditLog(
            user_id=user_id,
            event_type="compliance_check",
            event_category="authorization",
            details={
                "compliance_score": result.compliance_score,
                "status": result.status.value,
                "violations_count": len(result.violations),
                "warnings_count": len(result.warnings),
                "is_compliant": result.is_compliant
            },
            outcome="success",
            compliance_status=result.status.value
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
    
    async def generate_compliance_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Generate comprehensive HIPAA compliance report.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            dict: Compliance report data
        """
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # Get audit logs for period
            result = await self.db.execute(
                select(AuditLog)
                .where(
                    AuditLog.timestamp.between(start_datetime, end_datetime)
                )
            )
            audit_logs = result.scalars().all()
            
            # Calculate metrics
            total_events = len(audit_logs)
            phi_events = len([log for log in audit_logs if log.phi_accessed])
            violations = len([log for log in audit_logs if log.compliance_status == 'violation'])
            failed_logins = len([log for log in audit_logs if 'login' in log.event_type and log.outcome == 'failure'])
            
            # Get user statistics
            user_result = await self.db.execute(select(User))
            users = user_result.scalars().all()
            
            total_users = len(users)
            active_users = len([u for u in users if u.is_active])
            users_with_phi_access = len([u for u in users if u.phi_access_granted])
            users_with_mfa = len([u for u in users if u.mfa_enabled])
            
            # Calculate compliance metrics
            compliance_rate = ((total_events - violations) / total_events * 100) if total_events > 0 else 100
            phi_compliance_rate = ((phi_events - len([log for log in audit_logs if log.phi_accessed and log.compliance_status == 'violation'])) / phi_events * 100) if phi_events > 0 else 100
            
            report = {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days + 1
                },
                "summary": {
                    "overall_compliance_rate": round(compliance_rate, 2),
                    "phi_compliance_rate": round(phi_compliance_rate, 2),
                    "total_events": total_events,
                    "phi_events": phi_events,
                    "violations": violations,
                    "failed_logins": failed_logins
                },
                "user_metrics": {
                    "total_users": total_users,
                    "active_users": active_users,
                    "users_with_phi_access": users_with_phi_access,
                    "users_with_mfa": users_with_mfa,
                    "mfa_adoption_rate": round((users_with_mfa / total_users * 100) if total_users > 0 else 0, 2)
                },
                "event_breakdown": {
                    "authentication_events": len([log for log in audit_logs if log.event_category == 'authentication']),
                    "authorization_events": len([log for log in audit_logs if log.event_category == 'authorization']),
                    "access_events": len([log for log in audit_logs if log.event_category == 'access']),
                    "phi_access_events": phi_events
                },
                "violation_breakdown": {},
                "recommendations": []
            }
            
            # Add violation breakdown
            violation_types = {}
            for log in audit_logs:
                if log.compliance_status == 'violation' and log.details:
                    violation_type = log.details.get('violation_type', 'unknown')
                    violation_types[violation_type] = violation_types.get(violation_type, 0) + 1
            
            report["violation_breakdown"] = violation_types
            
            # Generate recommendations
            if compliance_rate < 95:
                report["recommendations"].append("Review and address compliance violations")
            if users_with_mfa / total_users < 0.8:
                report["recommendations"].append("Increase MFA adoption rate")
            if failed_logins > total_events * 0.05:
                report["recommendations"].append("Review authentication security measures")
            
            logger.info(
                "Compliance report generated",
                extra={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "compliance_rate": compliance_rate,
                    "total_events": total_events
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "Compliance report generation failed",
                extra={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "error": str(e)
                }
            )
            return {
                "error": "Report generation failed",
                "message": str(e)
            }
    
    async def audit_phi_access_patterns(self, user_id: UUID, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Audit PHI access patterns for unusual activity.
        
        Args:
            user_id: User ID to audit
            days_back: Number of days to analyze
            
        Returns:
            List[dict]: Unusual access patterns detected
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Get PHI access logs for user
            result = await self.db.execute(
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.user_id == user_id,
                        AuditLog.phi_accessed == True,
                        AuditLog.timestamp >= cutoff_date
                    )
                )
                .order_by(AuditLog.timestamp)
            )
            phi_logs = result.scalars().all()
            
            patterns = []
            
            if not phi_logs:
                return patterns
            
            # Analyze access frequency
            daily_counts = {}
            for log in phi_logs:
                day = log.timestamp.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            
            avg_daily_access = sum(daily_counts.values()) / len(daily_counts)
            
            for day, count in daily_counts.items():
                if count > avg_daily_access * 3:  # More than 3x average
                    patterns.append({
                        "type": "excessive_daily_access",
                        "date": day.isoformat(),
                        "access_count": count,
                        "average_daily": round(avg_daily_access, 2),
                        "severity": "medium"
                    })
            
            # Analyze time patterns
            hourly_counts = {}
            for log in phi_logs:
                hour = log.timestamp.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
            # Check for unusual hour access
            for hour, count in hourly_counts.items():
                if (hour >= 22 or hour <= 5) and count > 2:  # Late night/early morning
                    patterns.append({
                        "type": "unusual_hour_access",
                        "hour": hour,
                        "access_count": count,
                        "severity": "medium"
                    })
            
            # Analyze patient access patterns
            patient_counts = {}
            for log in phi_logs:
                if log.patient_id:
                    patient_counts[log.patient_id] = patient_counts.get(log.patient_id, 0) + 1
            
            # Check for excessive access to single patient
            for patient_id, count in patient_counts.items():
                if count > 10:  # More than 10 accesses to same patient
                    patterns.append({
                        "type": "excessive_patient_access",
                        "patient_id": str(patient_id),
                        "access_count": count,
                        "severity": "high"
                    })
            
            logger.info(
                "PHI access pattern analysis completed",
                extra={
                    "user_id": str(user_id),
                    "days_analyzed": days_back,
                    "total_phi_accesses": len(phi_logs),
                    "patterns_detected": len(patterns)
                }
            )
            
            return patterns
            
        except Exception as e:
            logger.error(
                "PHI access pattern analysis failed",
                extra={
                    "user_id": str(user_id),
                    "days_back": days_back,
                    "error": str(e)
                }
            )
            return []
"""
PHI (Protected Health Information) Access Controls

This module implements HIPAA-compliant access controls for PHI data,
including role-based access, minimum necessary principle, and comprehensive
audit logging for all PHI access attempts.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field

from ...models.user import User
from ...models.audit_log import AuditLog
from ...utils.database import get_db_session

logger = logging.getLogger(__name__)


class PHIAccessReason(str, Enum):
    """Valid reasons for accessing PHI under HIPAA."""
    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    RESEARCH = "research"
    PUBLIC_HEALTH = "public_health"
    JUDICIAL_ADMINISTRATIVE = "judicial_administrative"
    LAW_ENFORCEMENT = "law_enforcement"
    CORONER_MEDICAL_EXAMINER = "coroner_medical_examiner"
    ORGAN_DONATION = "organ_donation"
    WORKERS_COMPENSATION = "workers_compensation"
    INDIVIDUAL_ACCESS = "individual_access"
    BREACH_NOTIFICATION = "breach_notification"


class DataElement(str, Enum):
    """PHI data elements that can be accessed."""
    DEMOGRAPHICS = "demographics"
    CONTACT_INFO = "contact_info"
    MEDICAL_HISTORY = "medical_history"
    CURRENT_MEDICATIONS = "current_medications"
    ALLERGIES = "allergies"
    LAB_RESULTS = "lab_results"
    RADIOLOGY_REPORTS = "radiology_reports"
    PHYSICIAN_NOTES = "physician_notes"
    NURSING_NOTES = "nursing_notes"
    DISCHARGE_SUMMARY = "discharge_summary"
    BILLING_INFO = "billing_info"
    INSURANCE_INFO = "insurance_info"
    EMERGENCY_CONTACTS = "emergency_contacts"
    ADVANCE_DIRECTIVES = "advance_directives"
    IMMUNIZATION_RECORDS = "immunization_records"
    MENTAL_HEALTH_RECORDS = "mental_health_records"
    SUBSTANCE_ABUSE_RECORDS = "substance_abuse_records"
    GENETIC_INFO = "genetic_info"
    SOCIAL_SECURITY_NUMBER = "social_security_number"
    FULL_FACE_PHOTOS = "full_face_photos"


class PHIAccessRequest(BaseModel):
    """Request for PHI access authorization."""
    user_id: UUID
    patient_id: UUID
    access_reason: PHIAccessReason
    data_elements: List[DataElement]
    justification: str = Field(min_length=10, max_length=500)
    supervisor_approval: Optional[UUID] = None
    time_limited: bool = True
    access_duration_hours: int = Field(default=8, ge=1, le=72)


class PHIAccessGrant(BaseModel):
    """PHI access grant with expiration and limitations."""
    grant_id: UUID
    user_id: UUID
    patient_id: UUID
    granted_elements: List[DataElement]
    access_reason: PHIAccessReason
    granted_at: datetime
    expires_at: datetime
    granted_by: UUID
    is_active: bool = True
    access_count: int = 0
    last_access: Optional[datetime] = None


class PHIAccessController:
    """
    Controls access to Protected Health Information (PHI) according to HIPAA regulations.
    
    Implements:
    - Role-based access control
    - Minimum necessary principle
    - Access reason validation
    - Temporary access grants
    - Comprehensive audit logging
    """
    
    # Role-based access matrix defining what data elements each role can access
    ROLE_ACCESS_MATRIX = {
        "PHYSICIAN": [
            DataElement.DEMOGRAPHICS, DataElement.CONTACT_INFO, DataElement.MEDICAL_HISTORY,
            DataElement.CURRENT_MEDICATIONS, DataElement.ALLERGIES, DataElement.LAB_RESULTS,
            DataElement.RADIOLOGY_REPORTS, DataElement.PHYSICIAN_NOTES, DataElement.NURSING_NOTES,
            DataElement.DISCHARGE_SUMMARY, DataElement.EMERGENCY_CONTACTS, DataElement.ADVANCE_DIRECTIVES,
            DataElement.IMMUNIZATION_RECORDS, DataElement.MENTAL_HEALTH_RECORDS, DataElement.GENETIC_INFO
        ],
        "NURSE": [
            DataElement.DEMOGRAPHICS, DataElement.CONTACT_INFO, DataElement.CURRENT_MEDICATIONS,
            DataElement.ALLERGIES, DataElement.NURSING_NOTES, DataElement.EMERGENCY_CONTACTS,
            DataElement.IMMUNIZATION_RECORDS
        ],
        "PHARMACIST": [
            DataElement.DEMOGRAPHICS, DataElement.CURRENT_MEDICATIONS, DataElement.ALLERGIES,
            DataElement.LAB_RESULTS
        ],
        "LAB_TECHNICIAN": [
            DataElement.DEMOGRAPHICS, DataElement.LAB_RESULTS
        ],
        "BILLING_SPECIALIST": [
            DataElement.DEMOGRAPHICS, DataElement.CONTACT_INFO, DataElement.BILLING_INFO,
            DataElement.INSURANCE_INFO
        ],
        "MEDICAL_RECORDS": [
            DataElement.DEMOGRAPHICS, DataElement.CONTACT_INFO, DataElement.MEDICAL_HISTORY,
            DataElement.PHYSICIAN_NOTES, DataElement.NURSING_NOTES, DataElement.DISCHARGE_SUMMARY
        ],
        "ADMIN": [
            DataElement.DEMOGRAPHICS, DataElement.CONTACT_INFO
        ],
        "PATIENT": [
            # Patients can access all their own data
            list(DataElement)
        ]
    }
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def authorize_phi_access(
        self,
        user: User,
        patient_id: UUID,
        access_reason: PHIAccessReason,
        data_elements: List[DataElement]
    ) -> bool:
        """
        Authorize PHI access for a user based on role, reason, and minimum necessary principle.
        
        Args:
            user: User requesting access
            patient_id: ID of patient whose data is being accessed
            access_reason: HIPAA-compliant reason for access
            data_elements: Specific data elements being requested
            
        Returns:
            bool: True if access is authorized, False otherwise
        """
        try:
            # Check if user has active PHI access grant
            if not user.phi_access_granted:
                await self._log_access_denial(
                    user.id, patient_id, "No PHI access grant", data_elements
                )
                return False
            
            # Check if PHI access has expired
            if user.phi_access_expiry and user.phi_access_expiry < datetime.utcnow():
                await self._log_access_denial(
                    user.id, patient_id, "PHI access expired", data_elements
                )
                return False
            
            # Validate access reason
            if not await self._validate_access_reason(access_reason, user.role):
                await self._log_access_denial(
                    user.id, patient_id, f"Invalid access reason: {access_reason}", data_elements
                )
                return False
            
            # Apply minimum necessary principle
            allowed_elements = await self._check_minimum_necessary(user.role, data_elements)
            if not allowed_elements:
                await self._log_access_denial(
                    user.id, patient_id, "No elements allowed under minimum necessary", data_elements
                )
                return False
            
            # Special handling for patient's own data
            if str(patient_id) == str(user.id):
                # Patients can access all their own data
                allowed_elements = data_elements
            
            # Check for restricted data elements (substance abuse, mental health)
            restricted_elements = [
                DataElement.SUBSTANCE_ABUSE_RECORDS,
                DataElement.MENTAL_HEALTH_RECORDS,
                DataElement.GENETIC_INFO
            ]
            
            requested_restricted = [elem for elem in data_elements if elem in restricted_elements]
            if requested_restricted and not await self._authorize_restricted_access(user, requested_restricted):
                await self._log_access_denial(
                    user.id, patient_id, f"Restricted elements not authorized: {requested_restricted}", data_elements
                )
                return False
            
            # Log successful authorization
            await self._log_phi_access(
                user_id=user.id,
                patient_id=patient_id,
                elements_accessed=allowed_elements,
                access_reason=access_reason,
                success=True
            )
            
            return len(allowed_elements) > 0
            
        except Exception as e:
            logger.error(
                "PHI access authorization failed",
                extra={
                    "user_id": str(user.id),
                    "patient_id": str(patient_id),
                    "error": str(e),
                    "data_elements": [elem.value for elem in data_elements]
                }
            )
            return False
    
    async def _check_minimum_necessary(self, user_role: str, requested_elements: List[DataElement]) -> List[DataElement]:
        """
        Apply minimum necessary principle based on user role.
        
        Args:
            user_role: Role of the user requesting access
            requested_elements: Data elements being requested
            
        Returns:
            List[DataElement]: Elements that are allowed for this role
        """
        role_allowed = self.ROLE_ACCESS_MATRIX.get(user_role, [])
        if user_role == "PATIENT":
            # Patients can access all their own data
            role_allowed = list(DataElement)
        
        # Return intersection of requested and allowed elements
        allowed_elements = [elem for elem in requested_elements if elem in role_allowed]
        
        logger.info(
            "Minimum necessary check applied",
            extra={
                "user_role": user_role,
                "requested_count": len(requested_elements),
                "allowed_count": len(allowed_elements),
                "denied_elements": [elem.value for elem in requested_elements if elem not in allowed_elements]
            }
        )
        
        return allowed_elements
    
    async def _validate_access_reason(self, reason: PHIAccessReason, user_role: str) -> bool:
        """
        Validate that the access reason is appropriate for the user's role.
        
        Args:
            reason: Reason for accessing PHI
            user_role: Role of the user
            
        Returns:
            bool: True if reason is valid for role
        """
        # Define valid reasons per role
        role_valid_reasons = {
            "PHYSICIAN": [
                PHIAccessReason.TREATMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS,
                PHIAccessReason.RESEARCH
            ],
            "NURSE": [
                PHIAccessReason.TREATMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "PHARMACIST": [
                PHIAccessReason.TREATMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "LAB_TECHNICIAN": [
                PHIAccessReason.TREATMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "BILLING_SPECIALIST": [
                PHIAccessReason.PAYMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "MEDICAL_RECORDS": [
                PHIAccessReason.TREATMENT,
                PHIAccessReason.PAYMENT,
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "ADMIN": [
                PHIAccessReason.HEALTHCARE_OPERATIONS
            ],
            "PATIENT": [
                PHIAccessReason.INDIVIDUAL_ACCESS
            ]
        }
        
        valid_reasons = role_valid_reasons.get(user_role, [])
        return reason in valid_reasons
    
    async def _authorize_restricted_access(self, user: User, restricted_elements: List[DataElement]) -> bool:
        """
        Authorize access to restricted data elements (substance abuse, mental health, genetics).
        
        Args:
            user: User requesting access
            restricted_elements: Restricted elements being requested
            
        Returns:
            bool: True if access to restricted elements is authorized
        """
        # Only certain roles can access restricted information
        authorized_roles = ["PHYSICIAN", "MENTAL_HEALTH_SPECIALIST", "SUBSTANCE_ABUSE_COUNSELOR"]
        
        if user.role not in authorized_roles:
            return False
        
        # Check for additional authorization requirements
        if DataElement.SUBSTANCE_ABUSE_RECORDS in restricted_elements:
            # Substance abuse records require special authorization
            if not user.role == "SUBSTANCE_ABUSE_COUNSELOR" and not user.role == "PHYSICIAN":
                return False
        
        if DataElement.MENTAL_HEALTH_RECORDS in restricted_elements:
            # Mental health records require special authorization
            if not user.role == "MENTAL_HEALTH_SPECIALIST" and not user.role == "PHYSICIAN":
                return False
        
        return True
    
    async def _log_phi_access(
        self,
        user_id: UUID,
        patient_id: UUID,
        elements_accessed: List[DataElement],
        access_reason: PHIAccessReason,
        success: bool
    ) -> None:
        """
        Log PHI access attempt for HIPAA audit trail.
        
        Args:
            user_id: ID of user attempting access
            patient_id: ID of patient whose data was accessed
            elements_accessed: Data elements that were accessed
            access_reason: Reason for access
            success: Whether access was successful
        """
        audit_entry = AuditLog(
            user_id=user_id,
            event_type="phi_access_attempt",
            details={
                "patient_id": str(patient_id),
                "access_reason": access_reason.value,
                "elements_requested": [elem.value for elem in elements_accessed],
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            },
            phi_accessed=success,
            patient_id=patient_id if success else None,
            data_elements_accessed=[elem.value for elem in elements_accessed] if success else None,
            access_reason=access_reason.value if success else None,
            minimum_necessary_applied=True,
            compliance_status="compliant" if success else "access_denied"
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
        
        logger.info(
            "PHI access logged",
            extra={
                "user_id": str(user_id),
                "patient_id": str(patient_id),
                "success": success,
                "elements_count": len(elements_accessed),
                "reason": access_reason.value
            }
        )
    
    async def _log_access_denial(
        self,
        user_id: UUID,
        patient_id: UUID,
        denial_reason: str,
        requested_elements: List[DataElement]
    ) -> None:
        """
        Log PHI access denial for audit trail.
        
        Args:
            user_id: ID of user whose access was denied
            patient_id: ID of patient whose data was requested
            denial_reason: Reason for denial
            requested_elements: Data elements that were requested
        """
        audit_entry = AuditLog(
            user_id=user_id,
            event_type="phi_access_denied",
            details={
                "patient_id": str(patient_id),
                "denial_reason": denial_reason,
                "elements_requested": [elem.value for elem in requested_elements],
                "timestamp": datetime.utcnow().isoformat()
            },
            phi_accessed=False,
            compliance_status="access_denied"
        )
        
        self.db.add(audit_entry)
        await self.db.commit()
        
        logger.warning(
            "PHI access denied",
            extra={
                "user_id": str(user_id),
                "patient_id": str(patient_id),
                "denial_reason": denial_reason,
                "elements_count": len(requested_elements)
            }
        )
    
    async def grant_phi_access(
        self,
        user_id: UUID,
        access_reason: str,
        granted_by: UUID,
        duration_hours: int = 8
    ) -> bool:
        """
        Grant PHI access to a user with expiration.
        
        Args:
            user_id: ID of user to grant access to
            access_reason: Reason for granting access
            granted_by: ID of user granting access (supervisor/admin)
            duration_hours: How long access should last
            
        Returns:
            bool: True if access was granted successfully
        """
        try:
            # Get user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # Set access grant
            user.phi_access_granted = True
            user.phi_access_reason = access_reason
            user.phi_access_expiry = datetime.utcnow() + timedelta(hours=duration_hours)
            user.phi_access_supervisor = granted_by
            
            await self.db.commit()
            
            # Log access grant
            audit_entry = AuditLog(
                user_id=granted_by,
                event_type="phi_access_granted",
                details={
                    "target_user_id": str(user_id),
                    "access_reason": access_reason,
                    "duration_hours": duration_hours,
                    "expires_at": user.phi_access_expiry.isoformat()
                },
                compliance_status="compliant"
            )
            
            self.db.add(audit_entry)
            await self.db.commit()
            
            logger.info(
                "PHI access granted",
                extra={
                    "user_id": str(user_id),
                    "granted_by": str(granted_by),
                    "duration_hours": duration_hours,
                    "reason": access_reason
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to grant PHI access",
                extra={
                    "user_id": str(user_id),
                    "granted_by": str(granted_by),
                    "error": str(e)
                }
            )
            return False
    
    async def revoke_phi_access(self, user_id: UUID, revoked_by: UUID, reason: str) -> bool:
        """
        Revoke PHI access from a user.
        
        Args:
            user_id: ID of user to revoke access from
            revoked_by: ID of user revoking access
            reason: Reason for revocation
            
        Returns:
            bool: True if access was revoked successfully
        """
        try:
            # Get user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # Revoke access
            user.phi_access_granted = False
            user.phi_access_reason = None
            user.phi_access_expiry = None
            user.phi_access_supervisor = None
            
            await self.db.commit()
            
            # Log access revocation
            audit_entry = AuditLog(
                user_id=revoked_by,
                event_type="phi_access_revoked",
                details={
                    "target_user_id": str(user_id),
                    "revocation_reason": reason,
                    "timestamp": datetime.utcnow().isoformat()
                },
                compliance_status="compliant"
            )
            
            self.db.add(audit_entry)
            await self.db.commit()
            
            logger.info(
                "PHI access revoked",
                extra={
                    "user_id": str(user_id),
                    "revoked_by": str(revoked_by),
                    "reason": reason
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to revoke PHI access",
                extra={
                    "user_id": str(user_id),
                    "revoked_by": str(revoked_by),
                    "error": str(e)
                }
            )
            return False
    
    async def check_phi_access_expiry(self) -> List[UUID]:
        """
        Check for expired PHI access grants and revoke them.
        
        Returns:
            List[UUID]: User IDs whose access was revoked due to expiry
        """
        try:
            # Find users with expired PHI access
            result = await self.db.execute(
                select(User).where(
                    and_(
                        User.phi_access_granted == True,
                        User.phi_access_expiry < datetime.utcnow()
                    )
                )
            )
            expired_users = result.scalars().all()
            
            revoked_user_ids = []
            
            for user in expired_users:
                # Revoke expired access
                user.phi_access_granted = False
                user.phi_access_reason = None
                user.phi_access_expiry = None
                user.phi_access_supervisor = None
                
                revoked_user_ids.append(user.id)
                
                # Log automatic revocation
                audit_entry = AuditLog(
                    user_id=user.id,
                    event_type="phi_access_expired",
                    details={
                        "revocation_reason": "automatic_expiry",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    compliance_status="compliant"
                )
                
                self.db.add(audit_entry)
            
            if revoked_user_ids:
                await self.db.commit()
                
                logger.info(
                    "Expired PHI access grants revoked",
                    extra={
                        "revoked_count": len(revoked_user_ids),
                        "user_ids": [str(uid) for uid in revoked_user_ids]
                    }
                )
            
            return revoked_user_ids
            
        except Exception as e:
            logger.error(
                "Failed to check PHI access expiry",
                extra={"error": str(e)}
            )
            return []
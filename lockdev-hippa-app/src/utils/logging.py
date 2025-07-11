"""
Logging configuration for HIPAA compliance.
"""
import os
import logging
from typing import Dict, Any

import structlog


def setup_logging() -> None:
    """Setup structured logging for HIPAA compliance."""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if os.getenv("LOG_LEVEL", "INFO") == "INFO" else logging.DEBUG,
    )


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize log data to prevent PHI leakage."""
    sensitive_fields = {
        "password", "ssn", "social_security_number", "dob", "date_of_birth",
        "medical_record_number", "mrn", "patient_id", "credit_card", "phone",
        "address", "email", "first_name", "last_name", "full_name"
    }
    
    sanitized = {}
    for key, value in data.items():
        if key.lower() in sensitive_fields:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value
    
    return sanitized
"""
Authentication providers package.

This package contains concrete implementations of authentication providers
for different authentication backends while maintaining HIPAA compliance.
"""

from .custom import CustomAuthProvider

__all__ = ["CustomAuthProvider"]
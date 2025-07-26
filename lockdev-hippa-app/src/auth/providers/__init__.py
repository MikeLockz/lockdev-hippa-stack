"""
Authentication providers package.

This package contains concrete implementations of authentication providers
for different authentication backends while maintaining HIPAA compliance.
"""

# from .custom import CustomAuthProvider  # Temporarily disabled due to syntax issues
from .cognito import CognitoAuthProvider

__all__ = ["CognitoAuthProvider"]  # "CustomAuthProvider", 
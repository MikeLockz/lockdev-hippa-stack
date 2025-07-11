"""Monitoring infrastructure module."""
from .cloudwatch import create_cloudwatch_resources

__all__ = ["create_cloudwatch_resources"]
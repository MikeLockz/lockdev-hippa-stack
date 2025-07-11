"""Database infrastructure module."""
from .rds import create_rds_instance

__all__ = ["create_rds_instance"]
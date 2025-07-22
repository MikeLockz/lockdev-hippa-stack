"""Test configuration for HIPAA application."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from src.main import app
from src.utils.database import get_db_session


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def override_get_db_session(mock_db_session):
    """Override database session dependency."""
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    yield mock_db_session
    app.dependency_overrides.clear()

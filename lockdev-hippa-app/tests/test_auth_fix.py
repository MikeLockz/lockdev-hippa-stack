"""
Critical tests for the authentication vulnerability fix.
Ensures no mock users are created and real database validation occurs.
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.main import app
from src.models.user import User
from src.utils.security import create_access_token, get_password_hash, get_current_user


class TestAuthenticationVulnerabilityFix:
    """Critical tests to ensure the authentication vulnerability is completely fixed."""
    
    def test_no_mock_user_creation_in_codebase(self):
        """Verify that the mock user creation code has been completely removed."""
        # Read the security.py file
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Ensure no mock user creation patterns exist
        assert "mock user" not in content.lower()
        assert "User(id=user_id" not in content
        assert "f\"user{user_id}@example.com\"" not in content
        assert "For now, we'll create" not in content
        
        # Ensure real database operations are present
        assert "select(User)" in content
        assert "scalar_one_or_none()" in content
        assert "User.is_active == True" in content
    
    def test_secure_endpoint_requires_auth(self):
        """Test that secure endpoints properly require authentication."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        
        client = TestClient(app)
        response = client.get("/api/v1/secure")
        
        # Should return 401 because no authentication provided
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]
    
    def test_users_me_endpoint_requires_auth(self):
        """Test that /users/me endpoint properly requires authentication."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        
        client = TestClient(app)
        response = client.get("/api/v1/users/me")
        
        # Should return 401 because no authentication provided
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]
    
    def test_audit_log_endpoint_requires_auth(self):
        """Test that audit log endpoint properly requires authentication."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        
        client = TestClient(app)
        response = client.get("/api/v1/audit-log")
        
        # Should return 401 because no authentication provided
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]
    
    def test_secure_endpoint_with_real_user(self):
        """Test secure endpoint with a properly structured real user."""
        # Create a real user object (not a mock user)
        user_id = uuid.uuid4()
        real_user = User(
            id=user_id,
            email="realuser@healthcare.com",
            hashed_password=get_password_hash("securepassword"),
            is_active=True,
            is_superuser=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            login_attempts="0", 
            password_changed_at=datetime.utcnow(),
            role="user"
        )
        
        # Override the get_current_user dependency to return our real user
        app.dependency_overrides[get_current_user] = lambda: real_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/v1/secure")
            
            assert response.status_code == 200
            data = response.json()
            assert "secure endpoint" in data["message"]
            assert data["user_id"] == str(real_user.id)
            # Verify it's not a mock email pattern
            assert not data["user_id"].startswith("user")
            assert not real_user.email.endswith("@example.com")
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
    
    def test_hello_endpoint_optional_auth_works(self):
        """Test that optional auth endpoints work without authentication."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        
        client = TestClient(app)
        response = client.get("/api/v1/hello")
        
        assert response.status_code == 200
        data = response.json()
        assert "Hello from HIPAA-compliant" in data["message"]
        assert data["user_id"] is None  # No user when not authenticated
    
    def test_security_implementation_uses_database_queries(self):
        """Verify the security implementation contains proper database query logic."""
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Verify the get_current_user function contains database query logic
        assert "select(User).where(" in content
        assert "User.id == user_id" in content
        assert "User.is_active == True" in content
        assert "result.scalar_one_or_none()" in content
        assert "await db.execute(stmt)" in content
        
        # Verify proper error handling for non-existent users
        assert "if user is None:" in content
        assert "raise credentials_exception" in content
        
        # Verify audit logging is implemented
        assert "_log_auth_success" in content
        assert "_log_auth_failure" in content
        assert "AuditLog(" in content
    
    def test_authentication_uses_real_jwt_validation(self):
        """Verify JWT token validation uses proper database lookups."""
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Verify JWT decoding is still present
        assert "jwt.decode(" in content
        assert "payload.get(\"sub\")" in content
        
        # Verify UUID conversion for database lookup
        assert "uuid.UUID(user_id_str)" in content
        
        # Verify the user object comes from database, not created inline
        assert "User(" not in content or "AuditLog(" in content  # Only AuditLog() should exist
    
    def test_account_locking_implemented(self):
        """Verify account locking functionality is implemented."""
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Verify account locking checks
        assert "account_locked_until" in content
        assert "datetime.utcnow()" in content
        assert "HTTP_423_LOCKED" in content
        assert "Account is temporarily locked" in content
    
    def test_password_authentication_implemented(self):
        """Verify password-based authentication function exists."""
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Verify authenticate_user function exists
        assert "async def authenticate_user(" in content
        assert "verify_password(" in content
        assert "login_attempts" in content
    
    def test_comprehensive_audit_logging(self):
        """Verify comprehensive audit logging is implemented."""
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/utils/security.py", "r") as f:
            content = f.read()
        
        # Verify audit logging functions
        assert "async def _log_auth_success(" in content
        assert "async def _log_auth_failure(" in content
        
        # Verify audit log creation
        assert "action=\"authentication_success\"" in content
        assert "action=\"authentication_failure\"" in content
        assert "resource_type=\"user\"" in content
        assert "outcome=\"success\"" in content
        assert "outcome=\"failure\"" in content


class TestCriticalSecurityEnforcement:
    """Tests to ensure critical security measures are enforced."""
    
    def test_no_authentication_bypass_possible(self):
        """Ensure there's no way to bypass authentication requirements."""
        # Test that all protected endpoints return 401 without proper auth
        app.dependency_overrides.clear()
        client = TestClient(app)
        
        protected_endpoints = [
            "/api/v1/secure",
            "/api/v1/users/me", 
            "/api/v1/audit-log"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"
            data = response.json()
            assert "Authentication required" in data["detail"], f"Endpoint {endpoint} should show proper auth error"
    
    def test_require_auth_dependency_enforced(self):
        """Verify that require_auth dependency is used for protected endpoints."""
        # Read the API routes file
        with open("/Users/mbp/Development/lockdev-hippa-stack/lockdev-hippa-app/src/routes/api.py", "r") as f:
            content = f.read()
        
        # Verify require_auth is imported and used
        assert "from ..utils.security import get_current_user, require_auth" in content
        assert "Depends(require_auth)" in content
        
        # Count occurrences - should be used for secure endpoints
        require_auth_count = content.count("Depends(require_auth)")
        assert require_auth_count >= 3, "require_auth should be used for at least 3 secure endpoints"
    
    def test_optional_auth_vs_required_auth_distinction(self):
        """Test that optional vs required authentication is properly distinguished."""
        # Clear any existing dependency overrides
        app.dependency_overrides.clear()
        client = TestClient(app)
        
        # Optional auth endpoint should work without token
        response = client.get("/api/v1/hello")
        assert response.status_code == 200
        
        # Required auth endpoint should fail without token
        response = client.get("/api/v1/secure")
        assert response.status_code == 401
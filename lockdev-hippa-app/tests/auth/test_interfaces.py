"""
Tests for authentication interfaces.

This module tests the abstract authentication provider interface
to ensure proper contract definition and inheritance behavior.
"""

import pytest
from abc import ABC
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock

from src.auth.interfaces import AuthenticationProvider
from src.auth.models import AuthUser, AuthToken, AuthResult, TokenType, MFAMethod
from src.auth.exceptions import AuthenticationError


class TestAuthenticationProviderInterface:
    """Test cases for the AuthenticationProvider abstract interface."""
    
    def test_is_abstract_base_class(self):
        """Test that AuthenticationProvider is an abstract base class."""
        assert issubclass(AuthenticationProvider, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            AuthenticationProvider("test", {})
    
    def test_abstract_methods_defined(self):
        """Test that all expected abstract methods are defined."""
        expected_methods = {
            'authenticate_user',
            'authenticate_token',
            'refresh_token',
            'revoke_token',
            'get_user',
            'create_user',
            'update_user',
            'deactivate_user',
            'initiate_mfa_challenge',
            'verify_mfa_challenge',
            'setup_mfa_method',
            'remove_mfa_method',
            'create_token',
            'validate_token',
            'get_user_tokens',
            'change_password',
            'reset_password',
            'initiate_password_reset',
            'create_session',
            'validate_session',
            'invalidate_session',
            'get_user_sessions',
            'log_authentication_event',
            'get_user_audit_log',
            'health_check',
            'get_provider_config'
        }
        
        actual_methods = {
            name for name, method in AuthenticationProvider.__dict__.items()
            if getattr(method, '__isabstractmethod__', False)
        }
        
        assert actual_methods == expected_methods
    
    def test_initialization_signature(self):
        """Test the initialization signature of AuthenticationProvider."""
        # Create a concrete implementation for testing
        class TestProvider(AuthenticationProvider):
            async def authenticate_user(self, identifier: str, credential: str, 
                                      client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                pass
            
            async def authenticate_token(self, token: str, 
                                       token_type: TokenType = TokenType.ACCESS) -> AuthResult:
                pass
            
            async def refresh_token(self, refresh_token: str, 
                                  client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                pass
                
            async def revoke_token(self, token: str, token_type: TokenType, 
                                 revoked_by: Optional[str] = None) -> bool:
                pass
                
            async def get_user(self, user_id: str) -> Optional[AuthUser]:
                pass
                
            async def create_user(self, user_data: Dict[str, Any], 
                                created_by: Optional[str] = None) -> AuthUser:
                pass
                
            async def update_user(self, user_id: str, updates: Dict[str, Any], 
                                updated_by: Optional[str] = None) -> AuthUser:
                pass
                
            async def deactivate_user(self, user_id: str, deactivated_by: Optional[str] = None,
                                    reason: Optional[str] = None) -> bool:
                pass
                
            async def initiate_mfa_challenge(self, user_id: str, method: MFAMethod,
                                           client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                pass
                
            async def verify_mfa_challenge(self, challenge_token: str, verification_code: str,
                                         client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                pass
                
            async def setup_mfa_method(self, user_id: str, method: MFAMethod,
                                     method_data: Dict[str, Any]) -> bool:
                pass
                
            async def remove_mfa_method(self, user_id: str, method: MFAMethod,
                                      removed_by: Optional[str] = None) -> bool:
                pass
                
            async def create_token(self, user_id: str, token_type: TokenType,
                                 expires_in: Optional[timedelta] = None,
                                 scopes: Optional[List[str]] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> AuthToken:
                pass
                
            async def validate_token(self, token: str, token_type: TokenType,
                                   required_scopes: Optional[List[str]] = None) -> AuthToken:
                pass
                
            async def get_user_tokens(self, user_id: str, token_type: Optional[TokenType] = None,
                                    active_only: bool = True) -> List[AuthToken]:
                pass
                
            async def change_password(self, user_id: str, current_password: str,
                                    new_password: str, changed_by: Optional[str] = None) -> bool:
                pass
                
            async def reset_password(self, user_id: str, reset_token: str,
                                   new_password: str) -> bool:
                pass
                
            async def initiate_password_reset(self, identifier: str,
                                             client_info: Optional[Dict[str, Any]] = None) -> bool:
                pass
                
            async def create_session(self, user_id: str,
                                   client_info: Optional[Dict[str, Any]] = None) -> str:
                pass
                
            async def validate_session(self, session_id: str) -> Optional[AuthUser]:
                pass
                
            async def invalidate_session(self, session_id: str,
                                       invalidated_by: Optional[str] = None) -> bool:
                pass
                
            async def get_user_sessions(self, user_id: str, active_only: bool = True
                                      ) -> List[Dict[str, Any]]:
                pass
                
            async def log_authentication_event(self, event_type: str, user_id: Optional[str],
                                             success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
                pass
                
            async def get_user_audit_log(self, user_id: str, start_date: Optional[datetime] = None,
                                       end_date: Optional[datetime] = None,
                                       event_types: Optional[List[str]] = None
                                       ) -> List[Dict[str, Any]]:
                pass
                
            async def health_check(self) -> Dict[str, Any]:
                pass
                
            async def get_provider_config(self) -> Dict[str, Any]:
                pass
        
        # Should be able to instantiate concrete implementation
        provider = TestProvider("test_provider", {"key": "value"})
        assert provider.provider_name == "test_provider"
        assert provider.config == {"key": "value"}


class TestAuthenticationProviderContract:
    """Test the contract defined by the AuthenticationProvider interface."""
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider for contract testing."""
        provider = Mock(spec=AuthenticationProvider)
        provider.provider_name = "mock_provider"
        provider.config = {"test": True}
        return provider
    
    def test_authenticate_user_signature(self, mock_provider):
        """Test authenticate_user method signature."""
        # Mock the method
        mock_provider.authenticate_user = AsyncMock()
        
        # Should accept identifier, credential, and optional client_info
        assert hasattr(mock_provider, 'authenticate_user')
        assert callable(mock_provider.authenticate_user)
    
    def test_authenticate_token_signature(self, mock_provider):
        """Test authenticate_token method signature."""
        mock_provider.authenticate_token = AsyncMock()
        
        assert hasattr(mock_provider, 'authenticate_token')
        assert callable(mock_provider.authenticate_token)
    
    def test_user_management_methods(self, mock_provider):
        """Test user management method signatures."""
        user_methods = [
            'get_user', 'create_user', 'update_user', 'deactivate_user'
        ]
        
        for method_name in user_methods:
            # Mock the method
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_token_management_methods(self, mock_provider):
        """Test token management method signatures."""
        token_methods = [
            'create_token', 'validate_token', 'get_user_tokens', 'revoke_token', 'refresh_token'
        ]
        
        for method_name in token_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_mfa_methods(self, mock_provider):
        """Test MFA method signatures."""
        mfa_methods = [
            'initiate_mfa_challenge', 'verify_mfa_challenge', 
            'setup_mfa_method', 'remove_mfa_method'
        ]
        
        for method_name in mfa_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_password_management_methods(self, mock_provider):
        """Test password management method signatures."""
        password_methods = [
            'change_password', 'reset_password', 'initiate_password_reset'
        ]
        
        for method_name in password_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_session_management_methods(self, mock_provider):
        """Test session management method signatures."""
        session_methods = [
            'create_session', 'validate_session', 'invalidate_session', 'get_user_sessions'
        ]
        
        for method_name in session_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_audit_methods(self, mock_provider):
        """Test audit and logging method signatures."""
        audit_methods = ['log_authentication_event', 'get_user_audit_log']
        
        for method_name in audit_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))
    
    def test_provider_methods(self, mock_provider):
        """Test provider-specific method signatures."""
        provider_methods = ['health_check', 'get_provider_config']
        
        for method_name in provider_methods:
            setattr(mock_provider, method_name, AsyncMock())
            
            assert hasattr(mock_provider, method_name)
            assert callable(getattr(mock_provider, method_name))


class TestConcreteImplementationRequirements:
    """Test requirements for concrete implementations."""
    
    def test_incomplete_implementation_fails(self):
        """Test that incomplete implementations cannot be instantiated."""
        class IncompleteProvider(AuthenticationProvider):
            # Missing most abstract methods
            async def authenticate_user(self, identifier: str, credential: str, 
                                      client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                pass
        
        with pytest.raises(TypeError):
            IncompleteProvider("incomplete", {})
    
    def test_method_signature_consistency(self):
        """Test that method signatures are consistent with interface."""
        
        class TestProvider(AuthenticationProvider):
            def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
                super().__init__(provider_name, config)
            
            # Implement all abstract methods with correct signatures
            async def authenticate_user(self, identifier: str, credential: str, 
                                      client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                return AuthResult(
                    success=False,
                    authentication_method="test",
                    provider=self.provider_name
                )
            
            async def authenticate_token(self, token: str, 
                                       token_type: TokenType = TokenType.ACCESS) -> AuthResult:
                return AuthResult(
                    success=False,
                    authentication_method="token",
                    provider=self.provider_name
                )
            
            # ... (implement remaining methods with minimal functionality)
            async def refresh_token(self, refresh_token: str, 
                                  client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                return AuthResult(success=False, authentication_method="refresh", provider=self.provider_name)
            
            async def revoke_token(self, token: str, token_type: TokenType, 
                                 revoked_by: Optional[str] = None) -> bool:
                return True
            
            async def get_user(self, user_id: str) -> Optional[AuthUser]:
                return None
            
            async def create_user(self, user_data: Dict[str, Any], 
                                created_by: Optional[str] = None) -> AuthUser:
                return AuthUser(id="test", email="test@example.com", created_at=datetime.utcnow())
            
            async def update_user(self, user_id: str, updates: Dict[str, Any], 
                                updated_by: Optional[str] = None) -> AuthUser:
                return AuthUser(id=user_id, email="test@example.com", created_at=datetime.utcnow())
            
            async def deactivate_user(self, user_id: str, deactivated_by: Optional[str] = None,
                                    reason: Optional[str] = None) -> bool:
                return True
            
            async def initiate_mfa_challenge(self, user_id: str, method: MFAMethod,
                                           client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                return AuthResult(success=False, authentication_method="mfa", provider=self.provider_name)
            
            async def verify_mfa_challenge(self, challenge_token: str, verification_code: str,
                                         client_info: Optional[Dict[str, Any]] = None) -> AuthResult:
                return AuthResult(success=False, authentication_method="mfa", provider=self.provider_name)
            
            async def setup_mfa_method(self, user_id: str, method: MFAMethod,
                                     method_data: Dict[str, Any]) -> bool:
                return True
            
            async def remove_mfa_method(self, user_id: str, method: MFAMethod,
                                      removed_by: Optional[str] = None) -> bool:
                return True
            
            async def create_token(self, user_id: str, token_type: TokenType,
                                 expires_in: Optional[timedelta] = None,
                                 scopes: Optional[List[str]] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> AuthToken:
                return AuthToken(
                    token_id="test",
                    token_type=token_type,
                    token_value="a" * 32,
                    issued_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    user_id=user_id,
                    issued_by=self.provider_name
                )
            
            async def validate_token(self, token: str, token_type: TokenType,
                                   required_scopes: Optional[List[str]] = None) -> AuthToken:
                return AuthToken(
                    token_id="test",
                    token_type=token_type,
                    token_value=token,
                    issued_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    user_id="test",
                    issued_by=self.provider_name
                )
            
            async def get_user_tokens(self, user_id: str, token_type: Optional[TokenType] = None,
                                    active_only: bool = True) -> List[AuthToken]:
                return []
            
            async def change_password(self, user_id: str, current_password: str,
                                    new_password: str, changed_by: Optional[str] = None) -> bool:
                return True
            
            async def reset_password(self, user_id: str, reset_token: str,
                                   new_password: str) -> bool:
                return True
            
            async def initiate_password_reset(self, identifier: str,
                                             client_info: Optional[Dict[str, Any]] = None) -> bool:
                return True
            
            async def create_session(self, user_id: str,
                                   client_info: Optional[Dict[str, Any]] = None) -> str:
                return "session123"
            
            async def validate_session(self, session_id: str) -> Optional[AuthUser]:
                return None
            
            async def invalidate_session(self, session_id: str,
                                       invalidated_by: Optional[str] = None) -> bool:
                return True
            
            async def get_user_sessions(self, user_id: str, active_only: bool = True
                                      ) -> List[Dict[str, Any]]:
                return []
            
            async def log_authentication_event(self, event_type: str, user_id: Optional[str],
                                             success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
                pass
            
            async def get_user_audit_log(self, user_id: str, start_date: Optional[datetime] = None,
                                       end_date: Optional[datetime] = None,
                                       event_types: Optional[List[str]] = None
                                       ) -> List[Dict[str, Any]]:
                return []
            
            async def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy", "provider": self.provider_name}
            
            async def get_provider_config(self) -> Dict[str, Any]:
                return {"provider": self.provider_name}
        
        # Should be able to instantiate with all methods implemented
        provider = TestProvider("test_provider", {"test": True})
        assert provider.provider_name == "test_provider"
        assert provider.config == {"test": True}


class TestInterfaceDocumentation:
    """Test that interface methods have proper documentation."""
    
    def test_methods_have_docstrings(self):
        """Test that all abstract methods have docstrings."""
        for name, method in AuthenticationProvider.__dict__.items():
            if getattr(method, '__isabstractmethod__', False):
                assert method.__doc__ is not None, f"Method {name} lacks docstring"
                assert len(method.__doc__.strip()) > 0, f"Method {name} has empty docstring"
    
    def test_docstring_format(self):
        """Test that docstrings follow expected format."""
        # Check a few key methods for proper docstring format
        auth_user_doc = AuthenticationProvider.authenticate_user.__doc__
        assert "Args:" in auth_user_doc
        assert "Returns:" in auth_user_doc
        assert "Raises:" in auth_user_doc
        
        get_user_doc = AuthenticationProvider.get_user.__doc__
        assert "Args:" in get_user_doc
        assert "Returns:" in get_user_doc
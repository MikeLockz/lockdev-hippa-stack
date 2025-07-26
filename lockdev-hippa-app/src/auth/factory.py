"""
Authentication provider factory system.

This module provides a factory pattern for creating and managing authentication
providers with dynamic registration, configuration validation, and health checks.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Type, List, Callable, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .interfaces import AuthenticationProvider
from .config import AuthConfig, AuthProviderType, ProviderHealthConfig
from .exceptions import AuthenticationError
from .models import AuthUser, AuthToken, AuthResult

logger = logging.getLogger(__name__)


@dataclass
class ProviderRegistration:
    """Registration information for an authentication provider."""
    
    provider_type: AuthProviderType
    provider_class: Type[AuthenticationProvider]
    config_validator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    health_checker: Optional[Callable[[AuthenticationProvider], Dict[str, Any]]] = None
    description: str = ""
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    supports_mfa: bool = False
    supports_sso: bool = False
    registered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProviderHealth:
    """Health status information for a provider."""
    
    provider_type: AuthProviderType
    is_healthy: bool
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProviderRegistry:
    """
    Registry for managing authentication provider registrations.
    
    This class handles provider registration, validation, and metadata management
    with support for runtime provider discovery and plugin architecture.
    """
    
    def __init__(self):
        self._providers: Dict[AuthProviderType, ProviderRegistration] = {}
        self._health_status: Dict[AuthProviderType, ProviderHealth] = {}
        self._lock = asyncio.Lock()
    
    def register_provider(
        self,
        provider_type: AuthProviderType,
        provider_class: Type[AuthenticationProvider],
        config_validator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        health_checker: Optional[Callable[[AuthenticationProvider], Dict[str, Any]]] = None,
        description: str = "",
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        supports_mfa: bool = False,
        supports_sso: bool = False
    ) -> None:
        """
        Register an authentication provider.
        
        Args:
            provider_type: Type of authentication provider
            provider_class: Provider implementation class
            config_validator: Optional configuration validator function
            health_checker: Optional health check function
            description: Human-readable provider description
            version: Provider version
            dependencies: List of required dependencies
            supports_mfa: Whether provider supports MFA
            supports_sso: Whether provider supports SSO
        """
        if not issubclass(provider_class, AuthenticationProvider):
            raise ValueError(f"Provider class must inherit from AuthenticationProvider")
        
        registration = ProviderRegistration(
            provider_type=provider_type,
            provider_class=provider_class,
            config_validator=config_validator,
            health_checker=health_checker,
            description=description,
            version=version,
            dependencies=dependencies or [],
            supports_mfa=supports_mfa,
            supports_sso=supports_sso
        )
        
        self._providers[provider_type] = registration
        logger.info(f"Registered authentication provider: {provider_type.value} v{version}")
    
    def unregister_provider(self, provider_type: AuthProviderType) -> bool:
        """
        Unregister an authentication provider.
        
        Args:
            provider_type: Type of provider to unregister
            
        Returns:
            True if provider was unregistered, False if not found
        """
        if provider_type in self._providers:
            del self._providers[provider_type]
            if provider_type in self._health_status:
                del self._health_status[provider_type]
            logger.info(f"Unregistered authentication provider: {provider_type.value}")
            return True
        return False
    
    def get_provider_registration(self, provider_type: AuthProviderType) -> Optional[ProviderRegistration]:
        """Get registration information for a provider."""
        return self._providers.get(provider_type)
    
    def list_providers(self) -> List[ProviderRegistration]:
        """Get list of all registered providers."""
        return list(self._providers.values())
    
    def is_provider_registered(self, provider_type: AuthProviderType) -> bool:
        """Check if a provider is registered."""
        return provider_type in self._providers
    
    def get_providers_by_capability(
        self,
        supports_mfa: Optional[bool] = None,
        supports_sso: Optional[bool] = None
    ) -> List[ProviderRegistration]:
        """
        Get providers filtered by capabilities.
        
        Args:
            supports_mfa: Filter by MFA support
            supports_sso: Filter by SSO support
            
        Returns:
            List of matching provider registrations
        """
        providers = []
        for registration in self._providers.values():
            if supports_mfa is not None and registration.supports_mfa != supports_mfa:
                continue
            if supports_sso is not None and registration.supports_sso != supports_sso:
                continue
            providers.append(registration)
        
        return providers
    
    async def update_health_status(
        self,
        provider_type: AuthProviderType,
        is_healthy: bool,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update health status for a provider."""
        async with self._lock:
            self._health_status[provider_type] = ProviderHealth(
                provider_type=provider_type,
                is_healthy=is_healthy,
                last_check=datetime.utcnow(),
                response_time_ms=response_time_ms,
                error_message=error_message,
                metadata=metadata or {}
            )
    
    def get_health_status(self, provider_type: AuthProviderType) -> Optional[ProviderHealth]:
        """Get health status for a provider."""
        return self._health_status.get(provider_type)
    
    def get_all_health_status(self) -> Dict[AuthProviderType, ProviderHealth]:
        """Get health status for all providers."""
        return self._health_status.copy()


class AuthProviderFactory:
    """
    Factory for creating and managing authentication providers.
    
    This factory provides dynamic provider creation, configuration validation,
    health monitoring, and lifecycle management for authentication providers.
    """
    
    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        health_config: Optional[ProviderHealthConfig] = None
    ):
        """
        Initialize the authentication provider factory.
        
        Args:
            config: Authentication configuration
            health_config: Health check configuration
        """
        self.config = config or AuthConfig()
        self.health_config = health_config or ProviderHealthConfig()
        self.registry = ProviderRegistry()
        self._provider_instances: Dict[AuthProviderType, AuthenticationProvider] = {}
        self._health_check_tasks: Dict[AuthProviderType, asyncio.Task] = {}
        
        # Register built-in providers
        self._register_builtin_providers()
    
    def _register_builtin_providers(self) -> None:
        """Register built-in authentication providers."""
        from .providers.custom import CustomAuthProvider
        
        # Custom provider (always available)
        self.registry.register_provider(
            provider_type=AuthProviderType.CUSTOM,
            provider_class=CustomAuthProvider,
            description="Custom authentication provider with HIPAA compliance",
            supports_mfa=True,
            supports_sso=False,
            version="1.0.0"
        )
        
        # Try to register AWS Cognito provider if available
        try:
            from .providers.cognito import CognitoAuthProvider
            self.registry.register_provider(
                provider_type=AuthProviderType.AWS_COGNITO,
                provider_class=CognitoAuthProvider,
                description="AWS Cognito authentication provider with HIPAA compliance",
                supports_mfa=True,
                supports_sso=True,
                version="1.0.0",
                dependencies=["boto3", "cognitojwt"]
            )
            logger.info("Registered AWS Cognito authentication provider")
        except ImportError as e:
            logger.warning(f"AWS Cognito provider not available: {str(e)}")
        
        logger.info("Registered built-in authentication providers")
    
    def register_provider(
        self,
        provider_type: AuthProviderType,
        provider_class: Type[AuthenticationProvider],
        config_validator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        health_checker: Optional[Callable[[AuthenticationProvider], Dict[str, Any]]] = None,
        **kwargs
    ) -> None:
        """
        Register a new authentication provider.
        
        Args:
            provider_type: Type of authentication provider
            provider_class: Provider implementation class
            config_validator: Optional configuration validator
            health_checker: Optional health checker
            **kwargs: Additional provider metadata
        """
        self.registry.register_provider(
            provider_type=provider_type,
            provider_class=provider_class,
            config_validator=config_validator,
            health_checker=health_checker,
            **kwargs
        )
    
    async def create_provider(
        self,
        provider_type: Optional[AuthProviderType] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> AuthenticationProvider:
        """
        Create an authentication provider instance.
        
        Args:
            provider_type: Type of provider to create (defaults to config default)
            config_override: Optional configuration override
            
        Returns:
            Configured authentication provider instance
            
        Raises:
            AuthenticationError: If provider creation fails
        """
        if provider_type is None:
            provider_type = self.config.provider_type
        
        # Check if provider is registered
        registration = self.registry.get_provider_registration(provider_type)
        if not registration:
            raise AuthenticationError(f"Provider type {provider_type.value} is not registered")
        
        try:
            # Get provider configuration
            provider_config = self.config.get_provider_config(provider_type)
            if config_override:
                provider_config.update(config_override)
            
            # Validate configuration if validator is provided
            if registration.config_validator:
                provider_config = registration.config_validator(provider_config)
            
            # Create provider instance
            provider = registration.provider_class(
                provider_name=provider_type.value,
                config=provider_config
            )
            
            # Start health monitoring if enabled
            if self.health_config.health_check_enabled:
                await self._start_health_monitoring(provider_type, provider)
            
            # Cache the instance
            self._provider_instances[provider_type] = provider
            
            logger.info(f"Created authentication provider: {provider_type.value}")
            return provider
            
        except Exception as e:
            logger.error(f"Failed to create provider {provider_type.value}: {str(e)}")
            raise AuthenticationError(f"Provider creation failed: {str(e)}")
    
    async def get_provider(
        self,
        provider_type: Optional[AuthProviderType] = None
    ) -> AuthenticationProvider:
        """
        Get or create an authentication provider instance.
        
        Args:
            provider_type: Type of provider to get (defaults to config default)
            
        Returns:
            Authentication provider instance
        """
        if provider_type is None:
            provider_type = self.config.provider_type
        
        # Return cached instance if available
        if provider_type in self._provider_instances:
            return self._provider_instances[provider_type]
        
        # Create new instance
        return await self.create_provider(provider_type)
    
    async def destroy_provider(self, provider_type: AuthProviderType) -> bool:
        """
        Destroy a provider instance and clean up resources.
        
        Args:
            provider_type: Type of provider to destroy
            
        Returns:
            True if provider was destroyed, False if not found
        """
        # Stop health monitoring
        if provider_type in self._health_check_tasks:
            task = self._health_check_tasks[provider_type]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._health_check_tasks[provider_type]
        
        # Remove cached instance
        if provider_type in self._provider_instances:
            del self._provider_instances[provider_type]
            logger.info(f"Destroyed authentication provider: {provider_type.value}")
            return True
        
        return False
    
    async def validate_provider_config(
        self,
        provider_type: AuthProviderType,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate configuration for a provider type.
        
        Args:
            provider_type: Type of provider to validate config for
            config: Configuration to validate (defaults to current config)
            
        Returns:
            Validated configuration
            
        Raises:
            AuthenticationError: If validation fails
        """
        registration = self.registry.get_provider_registration(provider_type)
        if not registration:
            raise AuthenticationError(f"Provider type {provider_type.value} is not registered")
        
        if config is None:
            config = self.config.get_provider_config(provider_type)
        
        try:
            if registration.config_validator:
                return registration.config_validator(config)
            return config
        except Exception as e:
            raise AuthenticationError(f"Configuration validation failed: {str(e)}")
    
    async def health_check_provider(
        self,
        provider_type: AuthProviderType
    ) -> ProviderHealth:
        """
        Perform health check on a provider.
        
        Args:
            provider_type: Type of provider to check
            
        Returns:
            Provider health status
        """
        start_time = datetime.utcnow()
        
        try:
            # Get provider instance
            provider = await self.get_provider(provider_type)
            
            # Perform health check
            health_result = await provider.health_check()
            
            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update health status
            await self.registry.update_health_status(
                provider_type=provider_type,
                is_healthy=True,
                response_time_ms=response_time,
                metadata=health_result
            )
            
            return ProviderHealth(
                provider_type=provider_type,
                is_healthy=True,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                metadata=health_result
            )
            
        except Exception as e:
            logger.error(f"Health check failed for provider {provider_type.value}: {str(e)}")
            
            # Update health status with error
            await self.registry.update_health_status(
                provider_type=provider_type,
                is_healthy=False,
                error_message=str(e)
            )
            
            return ProviderHealth(
                provider_type=provider_type,
                is_healthy=False,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def _start_health_monitoring(
        self,
        provider_type: AuthProviderType,
        provider: AuthenticationProvider
    ) -> None:
        """Start health monitoring task for a provider."""
        async def health_monitor():
            while True:
                try:
                    await asyncio.sleep(self.health_config.health_check_interval_seconds)
                    await self.health_check_provider(provider_type)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health monitoring error for {provider_type.value}: {str(e)}")
        
        # Cancel existing task if running
        if provider_type in self._health_check_tasks:
            self._health_check_tasks[provider_type].cancel()
        
        # Start new monitoring task
        task = asyncio.create_task(health_monitor())
        self._health_check_tasks[provider_type] = task
    
    def list_providers(self) -> List[ProviderRegistration]:
        """Get list of all registered providers."""
        return self.registry.list_providers()
    
    def get_provider_info(self, provider_type: AuthProviderType) -> Optional[Dict[str, Any]]:
        """
        Get information about a provider.
        
        Args:
            provider_type: Type of provider to get info for
            
        Returns:
            Provider information dictionary
        """
        registration = self.registry.get_provider_registration(provider_type)
        if not registration:
            return None
        
        health = self.registry.get_health_status(provider_type)
        
        return {
            'type': registration.provider_type.value,
            'description': registration.description,
            'version': registration.version,
            'supports_mfa': registration.supports_mfa,
            'supports_sso': registration.supports_sso,
            'dependencies': registration.dependencies,
            'registered_at': registration.registered_at.isoformat(),
            'is_healthy': health.is_healthy if health else None,
            'last_health_check': health.last_check.isoformat() if health else None,
            'response_time_ms': health.response_time_ms if health else None
        }
    
    def get_providers_by_capability(
        self,
        supports_mfa: Optional[bool] = None,
        supports_sso: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Get providers filtered by capabilities.
        
        Args:
            supports_mfa: Filter by MFA support
            supports_sso: Filter by SSO support
            
        Returns:
            List of provider information dictionaries
        """
        registrations = self.registry.get_providers_by_capability(supports_mfa, supports_sso)
        return [self.get_provider_info(reg.provider_type) for reg in registrations]
    
    async def shutdown(self) -> None:
        """Shutdown the factory and clean up all resources."""
        # Cancel all health check tasks
        for task in self._health_check_tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(
                *self._health_check_tasks.values(),
                return_exceptions=True
            )
        
        # Clear all cached instances
        self._provider_instances.clear()
        self._health_check_tasks.clear()
        
        logger.info("Authentication provider factory shutdown complete")


# Global factory instance
_factory_instance: Optional[AuthProviderFactory] = None


async def get_auth_factory(
    config: Optional[AuthConfig] = None,
    health_config: Optional[ProviderHealthConfig] = None
) -> AuthProviderFactory:
    """
    Get or create the global authentication provider factory.
    
    Args:
        config: Authentication configuration
        health_config: Health check configuration
        
    Returns:
        Global factory instance
    """
    global _factory_instance
    
    if _factory_instance is None:
        _factory_instance = AuthProviderFactory(config, health_config)
    
    return _factory_instance


async def create_auth_provider(
    provider_type: Optional[AuthProviderType] = None,
    config: Optional[AuthConfig] = None
) -> AuthenticationProvider:
    """
    Convenience function to create an authentication provider.
    
    Args:
        provider_type: Type of provider to create
        config: Authentication configuration
        
    Returns:
        Configured authentication provider
    """
    factory = await get_auth_factory(config)
    return await factory.create_provider(provider_type)
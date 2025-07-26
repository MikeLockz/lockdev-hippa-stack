# HIPAA-Compliant Authentication System - Configuration Reference

## Overview

This document provides comprehensive configuration reference for the vendor-agnostic HIPAA-compliant authentication system. The system uses environment variables and Pydantic settings for configuration management with validation and type safety.

## Table of Contents

1. [Configuration Architecture](#configuration-architecture)
2. [Core Settings](#core-settings)
3. [Authentication Provider Settings](#authentication-provider-settings)
4. [Security Settings](#security-settings)
5. [HIPAA Compliance Settings](#hipaa-compliance-settings)
6. [Database Configuration](#database-configuration)
7. [Performance Tuning](#performance-tuning)
8. [Monitoring Configuration](#monitoring-configuration)
9. [Environment-Specific Examples](#environment-specific-examples)
10. [Validation and Testing](#validation-and-testing)

## Configuration Architecture

### Configuration Loading Order

1. **Default values** from Pydantic model definitions
2. **Environment variables** (highest priority)
3. **.env files** in the following order:
   - `.env.{environment}` (e.g., `.env.production`)
   - `.env.local`
   - `.env`

### Configuration Classes

```python
from src.auth.config import AuthConfig, ProviderHealthConfig
from pydantic_settings import BaseSettings

# Main configuration
config = AuthConfig()

# Health check configuration
health_config = ProviderHealthConfig()
```

## Core Settings

### Application Environment

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | `str` | `development` | Application environment (development, staging, production) |
| `DEBUG` | `bool` | `False` | Enable debug mode (only for development) |
| `LOG_LEVEL` | `str` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

### Authentication Provider Selection

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUTH_PROVIDER_TYPE` | `AuthProviderType` | `custom` | Primary authentication provider |

**Supported Provider Types:**
- `custom` - Custom JWT provider
- `aws_cognito` - AWS Cognito
- `auth0` - Auth0
- `supabase` - Supabase
- `firebase` - Firebase
- `oauth2` - Generic OAuth2
- `saml` - SAML provider
- `ldap` - LDAP provider

### JWT Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_SECRET_KEY` | `str` | **Required** | Secret key for JWT signing (min 32 chars) |
| `JWT_ALGORITHM` | `str` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `15` | Access token expiration (1-1440) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `30` | Refresh token expiration (1-365) |

**Example:**
```bash
JWT_SECRET_KEY="your-super-secure-jwt-secret-key-minimum-32-characters-long"
JWT_ALGORITHM="RS256"  # Use RS256 for production with key rotation
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Authentication Provider Settings

### Custom Provider Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CUSTOM_*` | `any` | `None` | Any variable starting with `CUSTOM_` |

**Example:**
```bash
# Custom provider settings
CUSTOM_ENCRYPTION_KEY="your-encryption-key"
CUSTOM_API_ENDPOINT="https://your-api.com"
CUSTOM_TIMEOUT_SECONDS=30
```

### AWS Cognito Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AWS_COGNITO_USER_POOL_ID` | `str` | **Required** | Cognito User Pool ID |
| `AWS_COGNITO_CLIENT_ID` | `str` | **Required** | Cognito App Client ID |
| `AWS_COGNITO_REGION` | `str` | **Required** | AWS region |
| `AWS_COGNITO_CLIENT_SECRET` | `str` | `None` | Cognito App Client Secret |
| `AWS_COGNITO_SCOPE` | `str` | `openid email profile` | OAuth2 scopes |

**Example:**
```bash
AWS_COGNITO_USER_POOL_ID="us-east-1_XXXXXXXXX"
AWS_COGNITO_CLIENT_ID="1234567890abcdef"
AWS_COGNITO_REGION="us-east-1"
AWS_COGNITO_CLIENT_SECRET="your-client-secret"
AWS_COGNITO_SCOPE="openid email profile aws.cognito.signin.user.admin"
```

### Auth0 Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUTH0_DOMAIN` | `str` | **Required** | Auth0 domain |
| `AUTH0_CLIENT_ID` | `str` | **Required** | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | `str` | **Required** | Auth0 client secret |
| `AUTH0_AUDIENCE` | `str` | `None` | Auth0 API audience |
| `AUTH0_SCOPE` | `str` | `openid email profile` | OAuth2 scopes |

**Example:**
```bash
AUTH0_DOMAIN="your-tenant.auth0.com"
AUTH0_CLIENT_ID="your-client-id"
AUTH0_CLIENT_SECRET="your-client-secret"
AUTH0_AUDIENCE="https://your-api.com"
AUTH0_SCOPE="openid email profile"
```

### Supabase Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SUPABASE_URL` | `str` | **Required** | Supabase project URL |
| `SUPABASE_ANON_KEY` | `str` | **Required** | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | `str` | `None` | Supabase service role key |

**Example:**
```bash
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_ANON_KEY="your-anon-key"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

### Firebase Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FIREBASE_PROJECT_ID` | `str` | **Required** | Firebase project ID |
| `FIREBASE_CREDENTIALS_PATH` | `str` | `None` | Path to service account JSON |
| `FIREBASE_WEB_API_KEY` | `str` | `None` | Firebase web API key |

**Example:**
```bash
FIREBASE_PROJECT_ID="your-project-id"
FIREBASE_CREDENTIALS_PATH="/path/to/serviceAccountKey.json"
FIREBASE_WEB_API_KEY="your-web-api-key"
```

### OAuth2 Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OAUTH2_CLIENT_ID` | `str` | **Required** | OAuth2 client ID |
| `OAUTH2_CLIENT_SECRET` | `str` | **Required** | OAuth2 client secret |
| `OAUTH2_AUTHORIZATION_URL` | `str` | **Required** | Authorization endpoint |
| `OAUTH2_TOKEN_URL` | `str` | **Required** | Token endpoint |
| `OAUTH2_USERINFO_URL` | `str` | `None` | User info endpoint |
| `OAUTH2_SCOPE` | `str` | `openid email profile` | OAuth2 scopes |

**Example:**
```bash
OAUTH2_CLIENT_ID="your-client-id"
OAUTH2_CLIENT_SECRET="your-client-secret"
OAUTH2_AUTHORIZATION_URL="https://auth-server.com/oauth/authorize"
OAUTH2_TOKEN_URL="https://auth-server.com/oauth/token"
OAUTH2_USERINFO_URL="https://auth-server.com/oauth/userinfo"
OAUTH2_SCOPE="openid email profile"
```

### SAML Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SAML_ENTITY_ID` | `str` | **Required** | SAML entity ID |
| `SAML_SSO_URL` | `str` | **Required** | SAML SSO URL |
| `SAML_X509_CERT` | `str` | **Required** | X.509 certificate |

**Example:**
```bash
SAML_ENTITY_ID="https://your-app.com/saml/metadata"
SAML_SSO_URL="https://idp.example.com/sso"
SAML_X509_CERT="-----BEGIN CERTIFICATE-----\nMIIC..."
```

### LDAP Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LDAP_SERVER` | `str` | **Required** | LDAP server hostname |
| `LDAP_BIND_DN` | `str` | **Required** | Bind DN for authentication |
| `LDAP_BIND_PASSWORD` | `str` | **Required** | Bind password |
| `LDAP_USER_SEARCH_BASE` | `str` | **Required** | User search base DN |
| `LDAP_PORT` | `int` | `389` | LDAP port |
| `LDAP_USE_SSL` | `bool` | `False` | Use SSL/TLS |
| `LDAP_USER_FILTER` | `str` | `(uid={username})` | User search filter |

**Example:**
```bash
LDAP_SERVER="ldap.example.com"
LDAP_BIND_DN="cn=admin,dc=example,dc=com"
LDAP_BIND_PASSWORD="admin-password"
LDAP_USER_SEARCH_BASE="ou=users,dc=example,dc=com"
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_USER_FILTER="(uid={username})"
```

## Security Settings

### Password Policy

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PASSWORD_MIN_LENGTH` | `int` | `8` | Minimum password length (min 8) |
| `REQUIRE_PASSWORD_HISTORY` | `int` | `12` | Number of previous passwords to check |
| `PASSWORD_EXPIRE_DAYS` | `int` | `90` | Password expiration period |

### Authentication Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_LOGIN_ATTEMPTS` | `int` | `3` | Maximum failed login attempts (1-10) |
| `LOCKOUT_DURATION_MINUTES` | `int` | `30` | Account lockout duration |
| `REQUIRE_MFA` | `bool` | `True` | Require multi-factor authentication |

### Session Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_EXPIRE_HOURS` | `int` | `8` | Session expiration time |
| `MAX_CONCURRENT_SESSIONS` | `int` | `3` | Maximum concurrent sessions per user |

**Example Security Configuration:**
```bash
# Strong password policy
PASSWORD_MIN_LENGTH=14
REQUIRE_PASSWORD_HISTORY=24
PASSWORD_EXPIRE_DAYS=60

# Strict authentication
MAX_LOGIN_ATTEMPTS=3
LOCKOUT_DURATION_MINUTES=60
REQUIRE_MFA=true

# Secure sessions
SESSION_EXPIRE_HOURS=2
MAX_CONCURRENT_SESSIONS=2
```

## HIPAA Compliance Settings

### Audit and Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUDIT_ALL_EVENTS` | `bool` | `True` | Log all authentication events |
| `ENCRYPT_AUDIT_LOGS` | `bool` | `True` | Encrypt audit logs |

**Example HIPAA Configuration:**
```bash
# HIPAA compliance requirements
AUDIT_ALL_EVENTS=true
ENCRYPT_AUDIT_LOGS=true
REQUIRE_PASSWORD_HISTORY=12
PASSWORD_EXPIRE_DAYS=90
REQUIRE_MFA=true
MAX_LOGIN_ATTEMPTS=3
SESSION_EXPIRE_HOURS=4
```

## Database Configuration

### Connection Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | `str` | **Required** | Database connection URL |
| `REDIS_URL` | `str` | `None` | Redis connection URL (optional) |

### Database URL Formats

```bash
# PostgreSQL
DATABASE_URL="postgresql+asyncpg://user:password@host:5432/database"

# PostgreSQL with SSL
DATABASE_URL="postgresql+asyncpg://user:password@host:5432/database?sslmode=require"

# SQLite (development only)
DATABASE_URL="sqlite+aiosqlite:///./auth.db"

# Redis
REDIS_URL="redis://localhost:6379/0"
REDIS_URL="redis://:password@localhost:6379/0"
REDIS_URL="rediss://localhost:6380/0"  # SSL
```

### Connection Pool Settings

```bash
# Advanced database configuration
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
```

## Performance Tuning

### Application Performance

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WORKERS` | `int` | `4` | Number of worker processes |
| `WORKER_CONNECTIONS` | `int` | `1000` | Connections per worker |
| `KEEPALIVE_TIMEOUT` | `int` | `2` | Keep-alive timeout |

### Caching Configuration

```bash
# Redis caching
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_KEY_PREFIX="auth:"

# Session caching
SESSION_CACHE_ENABLED=true
SESSION_CACHE_TTL_SECONDS=3600
```

### Rate Limiting

```bash
# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

## Monitoring Configuration

### Health Checks

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEALTH_CHECK_ENABLED` | `bool` | `True` | Enable health checks |
| `HEALTH_CHECK_INTERVAL_SECONDS` | `int` | `300` | Health check interval |
| `HEALTH_CHECK_TIMEOUT_SECONDS` | `int` | `30` | Health check timeout |
| `HEALTH_CHECK_RETRIES` | `int` | `3` | Health check retries |

### Metrics and Logging

```bash
# Prometheus metrics
METRICS_ENABLED=true
METRICS_PATH="/metrics"

# Structured logging
LOG_FORMAT="json"
LOG_INCLUDE_TIMESTAMP=true
LOG_INCLUDE_CALLER=true

# External monitoring
SENTRY_DSN="https://your-sentry-dsn"
DATADOG_API_KEY="your-datadog-key"
```

## Environment-Specific Examples

### Development Environment

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Authentication
AUTH_PROVIDER_TYPE=custom
JWT_SECRET_KEY="development-jwt-secret-key-minimum-32-characters-long"
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Security (relaxed for development)
REQUIRE_MFA=false
PASSWORD_MIN_LENGTH=8
MAX_LOGIN_ATTEMPTS=10
SESSION_EXPIRE_HOURS=24

# Database
DATABASE_URL="postgresql+asyncpg://auth_user:auth_pass@localhost:5432/auth_dev"
REDIS_URL="redis://localhost:6379/0"

# HIPAA (enabled for testing)
AUDIT_ALL_EVENTS=true
ENCRYPT_AUDIT_LOGS=false
```

### Staging Environment

```bash
# .env.staging
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO

# Authentication
AUTH_PROVIDER_TYPE=aws_cognito
JWT_SECRET_KEY="${AWS_SECRETS_MANAGER_JWT_SECRET}"
JWT_ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AWS Cognito
AWS_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
AWS_COGNITO_CLIENT_ID=1234567890abcdef
AWS_COGNITO_REGION=us-east-1
AWS_COGNITO_CLIENT_SECRET="${AWS_SECRETS_MANAGER_COGNITO_SECRET}"

# Security (production-like)
REQUIRE_MFA=true
PASSWORD_MIN_LENGTH=12
MAX_LOGIN_ATTEMPTS=3
LOCKOUT_DURATION_MINUTES=30
SESSION_EXPIRE_HOURS=4

# Database
DATABASE_URL="${AWS_SECRETS_MANAGER_DATABASE_URL}"
REDIS_URL="${AWS_ELASTICACHE_REDIS_URL}"

# HIPAA compliance
AUDIT_ALL_EVENTS=true
ENCRYPT_AUDIT_LOGS=true
REQUIRE_PASSWORD_HISTORY=12
PASSWORD_EXPIRE_DAYS=90
```

### Production Environment

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# Authentication
AUTH_PROVIDER_TYPE=aws_cognito
JWT_SECRET_KEY="${AWS_SECRETS_MANAGER_JWT_SECRET}"
JWT_ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AWS Cognito
AWS_COGNITO_USER_POOL_ID="${AWS_SECRETS_MANAGER_USER_POOL_ID}"
AWS_COGNITO_CLIENT_ID="${AWS_SECRETS_MANAGER_CLIENT_ID}"
AWS_COGNITO_REGION=us-east-1
AWS_COGNITO_CLIENT_SECRET="${AWS_SECRETS_MANAGER_COGNITO_SECRET}"

# Security (maximum security)
REQUIRE_MFA=true
PASSWORD_MIN_LENGTH=14
MAX_LOGIN_ATTEMPTS=3
LOCKOUT_DURATION_MINUTES=60
SESSION_EXPIRE_HOURS=2
MAX_CONCURRENT_SESSIONS=2

# Database (encrypted)
DATABASE_URL="${AWS_SECRETS_MANAGER_DATABASE_URL}"
REDIS_URL="${AWS_ELASTICACHE_REDIS_URL}"

# HIPAA compliance (strict)
AUDIT_ALL_EVENTS=true
ENCRYPT_AUDIT_LOGS=true
REQUIRE_PASSWORD_HISTORY=24
PASSWORD_EXPIRE_DAYS=60

# CORS (restrictive)
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
TRUSTED_HOSTS=yourdomain.com,app.yourdomain.com

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true
SENTRY_DSN="${AWS_SECRETS_MANAGER_SENTRY_DSN}"
```

## Validation and Testing

### Configuration Validation

The system provides built-in configuration validation:

```python
from src.auth.config import AuthConfig

# Validate configuration
try:
    config = AuthConfig()
    config.validate_configuration()
    print("Configuration is valid")
except ValueError as e:
    print(f"Configuration error: {e}")
```

### Testing Configuration

```bash
# Test configuration loading
poetry run python -c "
from src.auth.config import AuthConfig
config = AuthConfig()
print('Provider:', config.provider_type)
print('JWT Algorithm:', config.jwt_algorithm)
print('MFA Required:', config.require_mfa)
"

# Test provider-specific configuration
poetry run python -c "
from src.auth.config import AuthConfig
config = AuthConfig()
provider_config = config.get_provider_config()
print('Provider config:', provider_config)
"

# Test security configuration
poetry run python -c "
from src.auth.config import AuthConfig
config = AuthConfig()
security_config = config.get_security_config()
print('Security config:', security_config)
"
```

### Configuration Troubleshooting

#### Common Issues

1. **Invalid JWT Secret**: Must be at least 32 characters
2. **Missing Provider Config**: Required fields for selected provider
3. **Invalid Token Expiry**: Must be within allowed ranges
4. **Environment Variable Not Found**: Check .env file loading

#### Debug Commands

```bash
# Check environment variables
env | grep -E '^(AUTH_|JWT_|AWS_|DATABASE_)'

# Validate specific provider
poetry run python -c "
from src.auth.config import AuthConfig
config = AuthConfig()
try:
    if config.provider_type.value == 'aws_cognito':
        config._validate_aws_cognito_config(config.aws_cognito_config, {})
    print('Provider configuration is valid')
except Exception as e:
    print(f'Provider configuration error: {e}')
"

# Test database connection
poetry run python -c "
import asyncio
from src.utils.database import test_connection
asyncio.run(test_connection())
"
```

## Best Practices

### Security Best Practices

1. **Use environment variables** for all sensitive data
2. **Rotate JWT secrets** regularly in production
3. **Use strong algorithms** (RS256 for production)
4. **Implement proper session management**
5. **Enable all HIPAA compliance features**
6. **Use encrypted database connections**
7. **Implement proper CORS policies**

### Performance Best Practices

1. **Configure connection pooling** appropriately
2. **Use caching** for frequently accessed data
3. **Implement rate limiting**
4. **Monitor health check performance**
5. **Scale workers** based on load

### Operational Best Practices

1. **Use different configurations** per environment
2. **Validate configuration** on startup
3. **Implement comprehensive monitoring**
4. **Test configuration changes** in staging
5. **Document all custom settings**

This configuration reference provides all the information needed to properly configure the authentication system for any environment while maintaining HIPAA compliance and security best practices.
# HIPAA-Compliant Authentication System - Troubleshooting Guide

## Overview

This document provides comprehensive troubleshooting guidance for the vendor-agnostic HIPAA-compliant authentication system. It covers common issues, diagnostic procedures, and resolution steps for deployment, configuration, authentication, and performance problems.

## Table of Contents

1. [Quick Diagnostic Tools](#quick-diagnostic-tools)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Deployment Issues](#deployment-issues)
4. [Configuration Problems](#configuration-problems)
5. [Authentication Failures](#authentication-failures)
6. [Performance Issues](#performance-issues)
7. [Provider-Specific Issues](#provider-specific-issues)
8. [Database Issues](#database-issues)
9. [Network and Security Issues](#network-and-security-issues)
10. [Monitoring and Logging](#monitoring-and-logging)

## Quick Diagnostic Tools

### Health Check Script

```bash
#!/bin/bash
# health_check.sh - Quick system health check

echo "=== Authentication System Health Check ==="
echo "Timestamp: $(date)"
echo

# Check application health
echo "1. Application Health:"
curl -s -f http://localhost:8000/health/ | jq '.' || echo "❌ Application health check failed"
echo

# Check database connectivity
echo "2. Database Connectivity:"
curl -s -f http://localhost:8000/health/ready | jq '.checks.database' || echo "❌ Database check failed"
echo

# Check authentication provider
echo "3. Authentication Provider:"
curl -s -f http://localhost:8000/health/ready | jq '.checks.auth_provider' || echo "❌ Auth provider check failed"
echo

# Check environment variables
echo "4. Environment Configuration:"
env | grep -E '^(AUTH_|JWT_|DATABASE_)' | head -5
echo "..."
echo

# Check disk space
echo "5. Disk Space:"
df -h / | tail -1
echo

# Check memory usage
echo "6. Memory Usage:"
free -h | grep Mem
echo

# Check process status
echo "7. Process Status:"
ps aux | grep -E '(uvicorn|gunicorn|python)' | grep -v grep | head -3
echo

echo "=== Health Check Complete ==="
```

### Configuration Validator

```python
#!/usr/bin/env python3
# config_validator.py - Validate authentication configuration

import os
import sys
import asyncio
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent / "src"))

async def validate_configuration():
    """Validate authentication system configuration"""
    print("🔍 Validating Authentication Configuration...")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    try:
        from auth.config import AuthConfig
        
        # Load configuration
        config = AuthConfig()
        print(f"✅ Configuration loaded successfully")
        print(f"   Provider: {config.provider_type}")
        print(f"   Environment: {os.getenv('ENVIRONMENT', 'development')}")
        print()
        
        # Validate core settings
        print("🔧 Core Settings:")
        
        # JWT Secret validation
        if len(config.jwt_secret_key) >= 32:
            print("✅ JWT secret key length is adequate")
        else:
            errors.append("JWT secret key must be at least 32 characters")
        
        # Token expiration validation
        if 1 <= config.access_token_expire_minutes <= 1440:
            print("✅ Access token expiration is valid")
        else:
            errors.append("Access token expiration must be between 1 and 1440 minutes")
        
        # Password policy validation
        if config.password_min_length >= 8:
            print("✅ Password minimum length is adequate")
        else:
            errors.append("Password minimum length must be at least 8 characters")
        
        print()
        
        # Validate provider configuration
        print("🔌 Provider Configuration:")
        try:
            provider_config = config.get_provider_config()
            if provider_config or config.provider_type.value == "custom":
                print("✅ Provider configuration is valid")
            else:
                errors.append(f"Provider configuration missing for {config.provider_type}")
        except Exception as e:
            errors.append(f"Provider configuration error: {e}")
        
        print()
        
        # Database validation
        print("💾 Database Configuration:")
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            print("✅ Database URL is configured")
            if database_url.startswith(('postgresql', 'sqlite')):
                print("✅ Database URL format is valid")
            else:
                warnings.append("Unsupported database type detected")
        else:
            warnings.append("Database URL not configured")
        
        print()
        
        # HIPAA compliance validation
        print("🏥 HIPAA Compliance:")
        if config.audit_all_events:
            print("✅ Audit logging is enabled")
        else:
            warnings.append("Audit logging should be enabled for HIPAA compliance")
        
        if config.encrypt_audit_logs:
            print("✅ Audit log encryption is enabled")
        else:
            warnings.append("Audit log encryption should be enabled for HIPAA compliance")
        
        if config.require_mfa:
            print("✅ MFA is required")
        else:
            warnings.append("MFA should be required for HIPAA compliance")
        
        print()
        
        # Security validation
        print("🔒 Security Settings:")
        if config.max_login_attempts <= 5:
            print("✅ Login attempt limits are secure")
        else:
            warnings.append("Consider reducing maximum login attempts for better security")
        
        if config.session_expire_hours <= 8:
            print("✅ Session expiration is secure")
        else:
            warnings.append("Consider reducing session expiration for better security")
        
        print()
        
    except ImportError as e:
        errors.append(f"Failed to import configuration module: {e}")
    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")
    
    # Test authentication provider
    print("🔐 Authentication Provider Test:")
    try:
        from auth import create_auth_provider
        provider = await create_auth_provider(config.provider_type)
        health = await provider.health_check()
        
        if health.get('is_healthy', False):
            print("✅ Authentication provider is healthy")
        else:
            errors.append("Authentication provider health check failed")
            
    except Exception as e:
        errors.append(f"Authentication provider test failed: {e}")
    
    print()
    
    # Summary
    print("📊 Validation Summary:")
    print(f"   Errors: {len(errors)}")
    print(f"   Warnings: {len(warnings)}")
    print()
    
    if errors:
        print("❌ ERRORS:")
        for error in errors:
            print(f"   • {error}")
        print()
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   • {warning}")
        print()
    
    if not errors:
        print("✅ Configuration validation passed!")
    else:
        print("❌ Configuration validation failed!")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(validate_configuration())
    sys.exit(0 if success else 1)
```

### Log Analyzer

```bash
#!/bin/bash
# log_analyzer.sh - Analyze application logs for issues

LOG_FILE=${1:-"/var/log/auth-app.log"}
LINES=${2:-1000}

echo "=== Authentication System Log Analysis ==="
echo "Log file: $LOG_FILE"
echo "Analyzing last $LINES lines"
echo "Timestamp: $(date)"
echo

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

echo "🔍 Error Analysis:"
echo "Top errors in the last $LINES lines:"
tail -n $LINES "$LOG_FILE" | grep -i error | cut -d' ' -f4- | sort | uniq -c | sort -nr | head -10
echo

echo "🚫 Authentication Failures:"
echo "Failed login attempts:"
tail -n $LINES "$LOG_FILE" | grep -i "login.*fail" | wc -l
echo "Recent failed logins:"
tail -n $LINES "$LOG_FILE" | grep -i "login.*fail" | tail -5
echo

echo "⚠️  Warning Analysis:"
echo "Top warnings in the last $LINES lines:"
tail -n $LINES "$LOG_FILE" | grep -i warning | cut -d' ' -f4- | sort | uniq -c | sort -nr | head -5
echo

echo "📊 Request Analysis:"
echo "HTTP status code distribution:"
tail -n $LINES "$LOG_FILE" | grep -E "\"[0-9]{3}\"" | sed 's/.*"\([0-9]\{3\}\)".*/\1/' | sort | uniq -c | sort -nr
echo

echo "🐌 Performance Issues:"
echo "Slow requests (>1000ms):"
tail -n $LINES "$LOG_FILE" | grep -E "duration.*[0-9]{4,}" | head -5
echo

echo "🔒 Security Events:"
echo "Rate limiting events:"
tail -n $LINES "$LOG_FILE" | grep -i "rate.limit" | wc -l
echo "Suspicious activities:"
tail -n $LINES "$LOG_FILE" | grep -iE "(suspicious|blocked|banned)" | head -3
echo

echo "=== Log Analysis Complete ==="
```

## Common Issues and Solutions

### Issue: Application Won't Start

**Symptoms:**
- Container fails to start
- HTTP 500 errors on all endpoints
- "Service unavailable" messages

**Diagnostic Steps:**
```bash
# Check application logs
docker logs auth-app-container

# Check configuration
python config_validator.py

# Test database connection
python -c "
import asyncio
from src.utils.database import test_connection
asyncio.run(test_connection())
"

# Check environment variables
env | grep -E '^(AUTH_|JWT_|DATABASE_)'
```

**Common Causes and Solutions:**

1. **Missing Environment Variables:**
   ```bash
   # Check required variables
   echo "JWT_SECRET_KEY: ${JWT_SECRET_KEY:0:10}..."
   echo "DATABASE_URL: ${DATABASE_URL}"
   echo "AUTH_PROVIDER_TYPE: ${AUTH_PROVIDER_TYPE}"
   ```

2. **Database Connection Failure:**
   ```bash
   # Test database connectivity
   pg_isready -h localhost -p 5432
   
   # Check database credentials
   psql "$DATABASE_URL" -c "SELECT 1;"
   ```

3. **Invalid JWT Secret:**
   ```bash
   # Generate new JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. **Port Already in Use:**
   ```bash
   # Check port usage
   netstat -tulpn | grep :8000
   
   # Kill conflicting process
   sudo kill $(lsof -t -i:8000)
   ```

### Issue: Authentication Provider Unavailable

**Symptoms:**
- "Authentication provider not initialized" errors
- Provider health check failures
- 500 errors on auth endpoints

**Diagnostic Steps:**
```bash
# Check provider health
curl -s http://localhost:8000/health/ready | jq '.checks.auth_provider'

# Test provider configuration
python -c "
from src.auth.config import AuthConfig
config = AuthConfig()
print('Provider:', config.provider_type)
print('Config:', config.get_provider_config())
"

# Check provider-specific connectivity
# For AWS Cognito:
aws cognito-idp describe-user-pool --user-pool-id $AWS_COGNITO_USER_POOL_ID

# For custom provider:
python -c "
import asyncio
from src.auth.providers.custom import CustomAuthProvider
provider = CustomAuthProvider('custom', {})
print(asyncio.run(provider.health_check()))
"
```

**Solutions:**

1. **AWS Cognito Issues:**
   ```bash
   # Verify credentials
   aws sts get-caller-identity
   
   # Check Cognito configuration
   aws cognito-idp describe-user-pool --user-pool-id $AWS_COGNITO_USER_POOL_ID
   aws cognito-idp describe-user-pool-client --user-pool-id $AWS_COGNITO_USER_POOL_ID --client-id $AWS_COGNITO_CLIENT_ID
   ```

2. **Custom Provider Issues:**
   ```bash
   # Check database tables
   psql "$DATABASE_URL" -c "\dt"
   
   # Verify user table exists
   psql "$DATABASE_URL" -c "SELECT count(*) FROM users;"
   ```

### Issue: JWT Token Problems

**Symptoms:**
- "Invalid token" errors
- "Token expired" messages
- Authentication works but immediately fails

**Diagnostic Steps:**
```bash
# Decode JWT token (for debugging only)
python -c "
import jwt
token = 'your_token_here'
print(jwt.decode(token, options={'verify_signature': False}))
"

# Check token expiration
python -c "
import jwt
import datetime
token = 'your_token_here'
payload = jwt.decode(token, options={'verify_signature': False})
exp = datetime.datetime.fromtimestamp(payload['exp'])
print('Token expires:', exp)
print('Current time:', datetime.datetime.now())
"

# Verify JWT secret
python -c "
import jwt
token = 'your_token_here'
secret = '$JWT_SECRET_KEY'
try:
    payload = jwt.decode(token, secret, algorithms=['HS256'])
    print('Token is valid')
except Exception as e:
    print('Token validation failed:', e)
"
```

**Solutions:**

1. **Token Expired:**
   ```bash
   # Reduce token expiration for testing
   export ACCESS_TOKEN_EXPIRE_MINUTES=60
   
   # Implement automatic token refresh in client
   # See SDK examples in API documentation
   ```

2. **Invalid JWT Secret:**
   ```bash
   # Generate new secret
   export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   
   # Restart application
   docker-compose restart app
   ```

3. **Algorithm Mismatch:**
   ```bash
   # Use HS256 for development
   export JWT_ALGORITHM=HS256
   
   # Use RS256 for production with key rotation
   export JWT_ALGORITHM=RS256
   ```

## Deployment Issues

### Docker Deployment Problems

**Issue: Container Build Failures**

```bash
# Check Docker build context
docker build --no-cache -t auth-app .

# Inspect build layers
docker history auth-app

# Check for common issues
# 1. Large build context
echo "Build context size:"
tar -czf - . | wc -c

# 2. Missing dependencies
docker run --rm -it auth-app:latest pip list

# 3. Permission issues
docker run --rm -it auth-app:latest whoami
docker run --rm -it auth-app:latest ls -la /app
```

**Solutions:**
```dockerfile
# Optimize Dockerfile
FROM python:3.11-slim

# Create non-root user early
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . /app
WORKDIR /app

USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Issue: Container Runtime Problems**

```bash
# Check container logs
docker logs -f auth-app-container

# Check container resources
docker stats auth-app-container

# Inspect container
docker exec -it auth-app-container /bin/bash

# Check process status inside container
docker exec auth-app-container ps aux

# Check network connectivity
docker exec auth-app-container ping database-host
docker exec auth-app-container curl -I http://localhost:8000/health/
```

### Kubernetes Deployment Issues

**Issue: Pod Startup Failures**

```bash
# Check pod status
kubectl get pods -n healthcare-auth

# Describe problematic pod
kubectl describe pod auth-app-xxx -n healthcare-auth

# Check pod logs
kubectl logs auth-app-xxx -n healthcare-auth

# Check events
kubectl get events -n healthcare-auth --sort-by='.lastTimestamp'

# Check resource limits
kubectl top pods -n healthcare-auth
```

**Common Solutions:**
```yaml
# Increase resource limits
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

# Add health checks
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 5
  failureThreshold: 3

# Configure secrets properly
env:
- name: JWT_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: auth-secrets
      key: jwt-secret
```

## Configuration Problems

### Environment Variable Issues

**Issue: Configuration Not Loading**

```bash
# Debug configuration loading
python -c "
from src.auth.config import AuthConfig
import os
print('Environment:', os.getenv('ENVIRONMENT', 'not set'))
print('Auth Provider:', os.getenv('AUTH_PROVIDER_TYPE', 'not set'))
try:
    config = AuthConfig()
    print('Config loaded successfully')
    print('Provider type:', config.provider_type)
except Exception as e:
    print('Config error:', e)
"

# Check .env file loading
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('JWT Secret set:', 'JWT_SECRET_KEY' in os.environ)
print('Database URL set:', 'DATABASE_URL' in os.environ)
"

# Validate environment variables
env | grep -E '^(AUTH_|JWT_|DATABASE_|AWS_)' | sort
```

**Solutions:**
```bash
# Create proper .env file
cat > .env << EOF
ENVIRONMENT=development
AUTH_PROVIDER_TYPE=custom
JWT_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
DATABASE_URL=postgresql+asyncpg://auth_user:auth_pass@localhost:5432/auth_dev
REQUIRE_MFA=false
PASSWORD_MIN_LENGTH=8
AUDIT_ALL_EVENTS=true
EOF

# Set environment variables in Docker
docker run -e ENVIRONMENT=production \
           -e JWT_SECRET_KEY="your-secret" \
           auth-app:latest

# Use secrets in Kubernetes
kubectl create secret generic auth-secrets \
  --from-literal=jwt-secret="your-secret" \
  --from-literal=database-url="your-db-url"
```

### Provider Configuration Issues

**AWS Cognito Configuration:**
```bash
# Verify Cognito pool configuration
aws cognito-idp describe-user-pool --user-pool-id $AWS_COGNITO_USER_POOL_ID

# Check client configuration
aws cognito-idp describe-user-pool-client \
  --user-pool-id $AWS_COGNITO_USER_POOL_ID \
  --client-id $AWS_COGNITO_CLIENT_ID

# Test authentication
aws cognito-idp admin-initiate-auth \
  --user-pool-id $AWS_COGNITO_USER_POOL_ID \
  --client-id $AWS_COGNITO_CLIENT_ID \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123!
```

## Authentication Failures

### Common Authentication Issues

**Issue: Login Always Fails**

```bash
# Check user exists
python -c "
import asyncio
from src.auth import create_auth_provider, AuthConfig
async def check_user():
    config = AuthConfig()
    provider = await create_auth_provider(config.provider_type)
    user = await provider.get_user('test@example.com')
    print('User found:', user is not None)
asyncio.run(check_user())
"

# Check password hashing
python -c "
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
password = 'test_password'
hashed = pwd_context.hash(password)
print('Hashed:', hashed)
print('Verified:', pwd_context.verify(password, hashed))
"

# Check database connection
psql "$DATABASE_URL" -c "SELECT email, is_active FROM users LIMIT 5;"
```

**Issue: MFA Problems**

```bash
# Check MFA setup
python -c "
import pyotp
secret = 'JBSWY3DPEHPK3PXP'  # Example secret
totp = pyotp.TOTP(secret)
print('Current TOTP code:', totp.now())
print('Valid codes:')
for i in range(-1, 2):
    print(f'  {totp.at(totp.now() + i * 30)}')
"

# Verify backup codes
psql "$DATABASE_URL" -c "
SELECT user_id, backup_codes 
FROM user_mfa_settings 
WHERE user_id = 'user-id-here';
"
```

**Issue: Token Validation Failures**

```bash
# Debug token validation
python -c "
import jwt
from datetime import datetime, timedelta

# Create test token
secret = '$JWT_SECRET_KEY'
payload = {
    'user_id': 'test-user',
    'email': 'test@example.com',
    'exp': datetime.utcnow() + timedelta(minutes=15)
}
token = jwt.encode(payload, secret, algorithm='HS256')
print('Generated token:', token)

# Validate token
try:
    decoded = jwt.decode(token, secret, algorithms=['HS256'])
    print('Token is valid:', decoded)
except Exception as e:
    print('Token validation failed:', e)
"

# Check token in database
psql "$DATABASE_URL" -c "
SELECT token_id, user_id, expires_at, is_revoked 
FROM auth_tokens 
WHERE user_id = 'user-id-here' 
ORDER BY created_at DESC 
LIMIT 5;
"
```

## Performance Issues

### Slow Response Times

**Diagnostic Steps:**
```bash
# Check application metrics
curl -s http://localhost:8000/metrics | grep http_request_duration

# Profile database queries
psql "$DATABASE_URL" -c "
SELECT query, total_time, calls, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Check connection pool status
python -c "
import asyncio
from src.utils.database import get_database
async def check_pool():
    db = get_database()
    pool = db._pool
    if pool:
        print(f'Pool size: {pool.get_size()}')
        print(f'Free connections: {pool.get_idle_size()}')
        print(f'Used connections: {pool.get_size() - pool.get_idle_size()}')
asyncio.run(check_pool())
"

# Monitor system resources
top -p $(pgrep -f uvicorn)
free -h
iostat -x 1 5
```

**Solutions:**
```bash
# Optimize database connections
export DATABASE_POOL_SIZE=20
export DATABASE_MAX_OVERFLOW=30

# Enable query optimization
psql "$DATABASE_URL" -c "
-- Create indexes for frequently queried columns
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_active ON users(is_active);
CREATE INDEX CONCURRENTLY idx_audit_logs_user_id_timestamp ON audit_logs(user_id, timestamp);
"

# Use production ASGI server
pip install gunicorn
gunicorn src.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

### Memory Issues

**Diagnostic Steps:**
```bash
# Check memory usage
ps aux | grep -E '(uvicorn|gunicorn|python)' | awk '{print $6, $11}'

# Check for memory leaks
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
print(f'Memory percent: {process.memory_percent():.2f}%')
"

# Monitor memory over time
while true; do
  ps aux | grep uvicorn | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), $6/1024 \" MB\"}' | head -1
  sleep 60
done
```

**Solutions:**
```python
# Optimize database queries
from sqlalchemy.orm import selectinload

# Use eager loading to prevent N+1 queries
users = await session.execute(
    select(User).options(selectinload(User.audit_logs))
)

# Implement pagination
from sqlalchemy import func

async def get_users_paginated(page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page
    query = select(User).offset(offset).limit(per_page)
    return await session.execute(query)

# Use connection pooling
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600
)
```

## Provider-Specific Issues

### AWS Cognito Issues

**Issue: Cognito Authentication Failures**

```bash
# Check Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id $AWS_COGNITO_USER_POOL_ID

# Check user status
aws cognito-idp admin-get-user \
  --user-pool-id $AWS_COGNITO_USER_POOL_ID \
  --username test@example.com

# Test authentication flow
aws cognito-idp admin-initiate-auth \
  --user-pool-id $AWS_COGNITO_USER_POOL_ID \
  --client-id $AWS_COGNITO_CLIENT_ID \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=TestPassword123!

# Check MFA settings
aws cognito-idp admin-get-user-mfa-options \
  --user-pool-id $AWS_COGNITO_USER_POOL_ID \
  --username test@example.com
```

**Issue: Cognito Token Validation Failures**

```python
# Debug Cognito token validation
import boto3
import jwt
from jwt import PyJWKClient

def validate_cognito_token(token, user_pool_id, region):
    # Get public keys
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_url)
    
    try:
        # Get signing key
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Decode token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        )
        
        print("Token is valid:", payload)
        return payload
    except Exception as e:
        print("Token validation failed:", e)
        return None

# Test with your token
validate_cognito_token("your-token", user_pool_id, region)
```

### Custom Provider Issues

**Issue: Database Schema Problems**

```bash
# Check table existence
psql "$DATABASE_URL" -c "\dt"

# Verify user table schema
psql "$DATABASE_URL" -c "\d users"

# Check for missing columns
psql "$DATABASE_URL" -c "
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users';
"

# Run migrations
poetry run alembic upgrade head

# Create missing tables
python -c "
import asyncio
from src.utils.database import create_tables
asyncio.run(create_tables())
"
```

**Issue: Password Hashing Problems**

```python
# Test password hashing
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# Test password operations
password = "test_password123!"
hashed = pwd_context.hash(password)
print(f"Hashed: {hashed}")
print(f"Verified: {pwd_context.verify(password, hashed)}")
print(f"Needs update: {pwd_context.needs_update(hashed)}")
```

## Database Issues

### Connection Problems

**Issue: Database Connection Failures**

```bash
# Test basic connectivity
pg_isready -h localhost -p 5432

# Test with credentials
psql "postgresql://auth_user:auth_pass@localhost:5432/auth_dev" -c "SELECT 1;"

# Check connection pool
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_db():
    engine = create_async_engine('$DATABASE_URL')
    try:
        async with engine.begin() as conn:
            result = await conn.execute('SELECT 1')
            print('Database connection successful')
    except Exception as e:
        print(f'Database connection failed: {e}')
    finally:
        await engine.dispose()

asyncio.run(test_db())
"

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

**Issue: Migration Problems**

```bash
# Check migration status
poetry run alembic current

# View migration history
poetry run alembic history --verbose

# Create new migration
poetry run alembic revision --autogenerate -m "description"

# Upgrade to latest
poetry run alembic upgrade head

# Downgrade if needed
poetry run alembic downgrade -1

# Stamp current state
poetry run alembic stamp head
```

### Performance Issues

**Issue: Slow Database Queries**

```sql
-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();

-- Check slow queries
SELECT query, total_time, calls, mean_time, rows
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- Check missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation 
FROM pg_stats 
WHERE schemaname = 'public' 
  AND n_distinct > 100 
  AND correlation < 0.1;

-- Check table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Solutions:**
```sql
-- Create indexes for common queries
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_created_at ON users(created_at);
CREATE INDEX CONCURRENTLY idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX CONCURRENTLY idx_auth_tokens_user_id ON auth_tokens(user_id);

-- Optimize frequently used queries
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';

-- Update table statistics
ANALYZE users;
ANALYZE audit_logs;
ANALYZE auth_tokens;
```

## Network and Security Issues

### SSL/TLS Problems

**Issue: SSL Certificate Errors**

```bash
# Check certificate validity
openssl x509 -in /path/to/cert.pem -text -noout

# Test SSL connection
openssl s_client -connect auth.yourdomain.com:443 -servername auth.yourdomain.com

# Check certificate chain
curl -I https://auth.yourdomain.com

# Verify certificate matches private key
openssl x509 -noout -modulus -in certificate.crt | openssl md5
openssl rsa -noout -modulus -in private.key | openssl md5
```

**Issue: CORS Problems**

```bash
# Test CORS headers
curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS \
     https://auth.yourdomain.com/auth/login

# Check CORS configuration
python -c "
from src.main import app
for middleware in app.user_middleware:
    if 'CORS' in str(type(middleware[0])):
        print('CORS middleware configured')
        break
else:
    print('CORS middleware not found')
"
```

### Rate Limiting Issues

**Issue: Rate Limiting Not Working**

```bash
# Test rate limiting
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://auth.yourdomain.com/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
  sleep 1
done

# Check rate limiting configuration
python -c "
import os
print('Rate limiting enabled:', os.getenv('RATE_LIMIT_ENABLED', 'false'))
print('Login rate limit:', os.getenv('RATE_LIMIT_LOGIN_ATTEMPTS', 'not set'))
"
```

## Monitoring and Logging

### Log Analysis Issues

**Issue: Missing or Incomplete Logs**

```bash
# Check log configuration
python -c "
import logging
import structlog
print('Logging configured:', len(logging.getLogger().handlers) > 0)
print('Structlog processors:', len(structlog.get_config()['processors']))
"

# Check log file permissions
ls -la /var/log/auth-app.log

# Check disk space for logs
df -h /var/log

# Verify log rotation
cat /etc/logrotate.d/auth-app
```

**Issue: Monitoring Alerts Not Firing**

```bash
# Check Prometheus metrics
curl -s http://localhost:8000/metrics | grep -E "(http_requests|auth_)"

# Test alert rules
promtool query instant http://prometheus:9090 'up{job="auth-app"}'

# Check Grafana data source
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
     http://grafana:3000/api/datasources

# Verify alert manager configuration
curl http://alertmanager:9093/api/v1/status
```

### Health Check Issues

**Issue: Health Checks Failing**

```bash
# Debug health check endpoints
curl -v http://localhost:8000/health/
curl -v http://localhost:8000/health/ready
curl -v http://localhost:8000/health/live

# Check dependencies
python -c "
import asyncio
from src.utils.database import test_connection
from src.auth import create_auth_provider, AuthConfig

async def check_dependencies():
    # Test database
    try:
        await test_connection()
        print('✅ Database: OK')
    except Exception as e:
        print(f'❌ Database: {e}')
    
    # Test auth provider
    try:
        config = AuthConfig()
        provider = await create_auth_provider(config.provider_type)
        health = await provider.health_check()
        if health.get('is_healthy', False):
            print('✅ Auth Provider: OK')
        else:
            print(f'❌ Auth Provider: {health}')
    except Exception as e:
        print(f'❌ Auth Provider: {e}')

asyncio.run(check_dependencies())
"
```

This troubleshooting guide provides comprehensive solutions for the most common issues encountered when deploying and operating the HIPAA-compliant authentication system. For additional support, consult the API documentation, configuration reference, and security guide.
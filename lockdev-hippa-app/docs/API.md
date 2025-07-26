# HIPAA-Compliant Authentication System - API Documentation

## Overview

This document provides comprehensive API documentation for the vendor-agnostic HIPAA-compliant authentication system. The API follows RESTful principles and includes detailed authentication flows, error handling, and integration examples.

## Table of Contents

1. [API Overview](#api-overview)
2. [Authentication Flows](#authentication-flows)
3. [Endpoints Reference](#endpoints-reference)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [SDK Examples](#sdk-examples)
7. [Integration Patterns](#integration-patterns)
8. [WebSocket Authentication](#websocket-authentication)
9. [Testing Examples](#testing-examples)

## API Overview

### Base URL

```
Development:  http://localhost:8000
Staging:      https://staging-auth.yourdomain.com
Production:   https://auth.yourdomain.com
```

### Content Types

- **Request**: `application/json`
- **Response**: `application/json`
- **Authentication**: `Bearer <token>` in Authorization header

### API Versioning

Current API version: **v1**

All endpoints are prefixed with `/api/v1` or use specific namespaces like `/auth` and `/health`.

### Security Headers

All responses include security headers:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

## Authentication Flows

### 1. Standard Login Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthProvider
    participant Database

    Client->>API: POST /auth/login (email, password)
    API->>AuthProvider: authenticate_user()
    AuthProvider->>Database: verify_credentials()
    Database-->>AuthProvider: user_data
    AuthProvider-->>API: AuthResult
    API-->>Client: JWT tokens + user info
    
    Note over Client: Store tokens securely
    
    Client->>API: GET /api/v1/protected (Authorization: Bearer <token>)
    API->>AuthProvider: validate_token()
    AuthProvider-->>API: valid_user
    API-->>Client: protected_data
```

### 2. Multi-Factor Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthProvider
    participant MFA

    Client->>API: POST /auth/login (email, password)
    API->>AuthProvider: authenticate_user()
    AuthProvider-->>API: MFARequiredError
    API-->>Client: 202 Accepted + MFA challenge
    
    Client->>API: POST /auth/mfa/verify (mfa_token, code)
    API->>AuthProvider: verify_mfa_challenge()
    AuthProvider->>MFA: validate_code()
    MFA-->>AuthProvider: valid
    AuthProvider-->>API: AuthResult
    API-->>Client: JWT tokens + user info
```

### 3. Token Refresh Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthProvider

    Client->>API: POST /auth/refresh (refresh_token)
    API->>AuthProvider: refresh_token()
    AuthProvider-->>API: new_tokens
    API-->>Client: new JWT tokens
    
    Note over Client: Update stored tokens
```

## Endpoints Reference

### Authentication Endpoints

#### POST /auth/login

Authenticate user with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password123!",
  "remember_me": false
}
```

**Response (Success):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "roles": ["user"],
    "mfa_enabled": true,
    "created_at": "2024-01-01T00:00:00Z",
    "last_login": "2024-01-01T12:00:00Z"
  }
}
```

**Response (MFA Required):**
```json
{
  "message": "Multi-factor authentication required",
  "mfa_token": "temp_mfa_token_here",
  "available_methods": ["totp", "sms", "backup_codes"]
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password123!",
    "remember_me": false
  }'
```

#### POST /auth/refresh

Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "your_refresh_token_here"
  }'
```

#### POST /auth/logout

Logout user and invalidate tokens.

**Request Headers:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```json
{
  "message": "Successfully logged out",
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/logout" \
  -H "Authorization: Bearer your_access_token_here"
```

#### GET /auth/me

Get current authenticated user information.

**Request Headers:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "roles": ["user"],
  "mfa_enabled": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-01T12:00:00Z",
  "password_expires_at": "2024-04-01T00:00:00Z",
  "account_locked": false
}
```

**cURL Example:**
```bash
curl -X GET "https://auth.yourdomain.com/auth/me" \
  -H "Authorization: Bearer your_access_token_here"
```

### Password Management Endpoints

#### POST /auth/change-password

Change user password (requires authentication).

**Request Headers:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Request:**
```json
{
  "current_password": "current_secure_password123!",
  "new_password": "new_secure_password456!"
}
```

**Response:**
```json
{
  "message": "Password changed successfully",
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/change-password" \
  -H "Authorization: Bearer your_access_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "current_password",
    "new_password": "new_secure_password456!"
  }'
```

#### POST /auth/forgot-password

Initiate password reset process.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "If an account with that email exists, a password reset link has been sent",
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

#### POST /auth/reset-password

Complete password reset using reset token.

**Request:**
```json
{
  "token": "password_reset_token_here",
  "new_password": "new_secure_password789!"
}
```

**Response:**
```json
{
  "message": "Password has been reset successfully",
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "reset_token_from_email",
    "new_password": "new_secure_password789!"
  }'
```

### Multi-Factor Authentication Endpoints

#### GET /auth/mfa/setup

Setup MFA for current user.

**Request Headers:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```json
{
  "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "backup_codes": [
    "abc123def",
    "def456ghi",
    "ghi789jkl",
    "jkl012mno",
    "mno345pqr"
  ],
  "secret": "JBSWY3DPEHPK3PXP"
}
```

**cURL Example:**
```bash
curl -X GET "https://auth.yourdomain.com/auth/mfa/setup" \
  -H "Authorization: Bearer your_access_token_here"
```

#### POST /auth/mfa/verify

Verify MFA code during login or setup.

**Request:**
```json
{
  "code": "123456",
  "backup_code": null
}
```

**Alternative with backup code:**
```json
{
  "code": null,
  "backup_code": "abc123def"
}
```

**Response:**
```json
{
  "message": "MFA verification successful",
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "https://auth.yourdomain.com/auth/mfa/verify" \
  -H "Authorization: Bearer your_access_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "123456"
  }'
```

### Health Check Endpoints

#### GET /health/

Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

#### GET /health/ready

Readiness probe with dependency checks.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2024-01-01T12:00:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "auth_provider": "healthy"
  },
  "version": "1.0.0"
}
```

#### GET /health/live

Liveness probe.

**Response:**
```json
{
  "status": "alive",
  "timestamp": "2024-01-01T12:00:00Z",
  "uptime_seconds": 86400
}
```

#### GET /metrics

Prometheus metrics endpoint.

**Response:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health/"} 1234

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 1000
http_request_duration_seconds_bucket{le="0.5"} 1200
http_request_duration_seconds_bucket{le="1.0"} 1300
```

### API Endpoints

#### GET /api/v1/hello

Simple API endpoint for testing.

**Request Headers:**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```json
{
  "message": "Hello from HIPAA-compliant API!",
  "timestamp": "2024-01-01T12:00:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "req_123456789"
}
```

## Error Handling

### Error Response Format

All error responses follow a consistent format:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 400
}
```

### Common Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_REQUEST` | Malformed request body or parameters |
| 401 | `INVALID_CREDENTIALS` | Invalid email or password |
| 401 | `TOKEN_EXPIRED` | Access token has expired |
| 401 | `TOKEN_INVALID` | Invalid or malformed token |
| 401 | `MFA_REQUIRED` | Multi-factor authentication required |
| 403 | `INSUFFICIENT_PERMISSIONS` | User lacks required permissions |
| 403 | `ACCOUNT_LOCKED` | Account is locked due to security policy |
| 404 | `USER_NOT_FOUND` | User account does not exist |
| 429 | `RATE_LIMITED` | Too many requests, rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Internal server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### Error Examples

#### Invalid Credentials
```json
{
  "detail": "Invalid email or password",
  "error_code": "INVALID_CREDENTIALS",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 401
}
```

#### Token Expired
```json
{
  "detail": "Access token has expired",
  "error_code": "TOKEN_EXPIRED",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 401
}
```

#### Rate Limited
```json
{
  "detail": "Too many requests. Please try again later.",
  "error_code": "RATE_LIMITED",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 429,
  "retry_after": 60
}
```

#### Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length",
      "ctx": {"limit_value": 8}
    }
  ],
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 422
}
```

## Rate Limiting

### Rate Limit Headers

All responses include rate limiting headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Reset-After: 300
```

### Rate Limit Policies

| Endpoint | Limit | Window |
|----------|-------|---------|
| `/auth/login` | 5 requests | 1 minute |
| `/auth/forgot-password` | 3 requests | 1 hour |
| `/auth/mfa/verify` | 10 requests | 5 minutes |
| `/api/v1/*` | 100 requests | 1 minute |
| Global | 1000 requests | 1 hour |

### Rate Limit Exceeded Response

```json
{
  "detail": "Rate limit exceeded. Maximum 5 requests per minute.",
  "error_code": "RATE_LIMITED",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789",
  "status_code": 429,
  "retry_after": 60
}
```

## SDK Examples

### Python SDK Example

```python
import httpx
import json
from typing import Optional, Dict, Any

class AuthClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    async def login(self, email: str, password: str, remember_me: bool = False) -> Dict[str, Any]:
        """Login with email and password"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": email,
                    "password": password,
                    "remember_me": remember_me
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                return data
            elif response.status_code == 202:
                # MFA required
                return response.json()
            else:
                response.raise_for_status()
    
    async def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                return data
            else:
                response.raise_for_status()
    
    async def logout(self) -> None:
        """Logout and invalidate tokens"""
        if not self.access_token:
            return
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(
                f"{self.base_url}/auth/logout",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
        
        self.access_token = None
        self.refresh_token = None
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current user information"""
        return await self._authenticated_request("GET", "/auth/me")
    
    async def change_password(self, current_password: str, new_password: str) -> Dict[str, Any]:
        """Change user password"""
        return await self._authenticated_request("POST", "/auth/change-password", {
            "current_password": current_password,
            "new_password": new_password
        })
    
    async def _authenticated_request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request with automatic token refresh"""
        if not self.access_token:
            raise ValueError("Not authenticated")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            kwargs = {"headers": headers}
            
            if data:
                kwargs["json"] = data
            
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
            
            if response.status_code == 401 and self.refresh_token:
                # Try to refresh token
                try:
                    await self.refresh_access_token()
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    kwargs["headers"] = headers
                    response = await client.request(method, f"{self.base_url}{path}", **kwargs)
                except Exception:
                    pass
            
            if response.status_code == 200:
                return response.json()
            else:
                response.raise_for_status()

# Usage example
async def main():
    client = AuthClient("https://auth.yourdomain.com")
    
    # Login
    login_result = await client.login("user@example.com", "secure_password123!")
    
    if "mfa_token" in login_result:
        # Handle MFA
        print("MFA required")
        return
    
    # Get user info
    user = await client.get_current_user()
    print(f"Logged in as: {user['email']}")
    
    # Change password
    await client.change_password("secure_password123!", "new_secure_password456!")
    
    # Logout
    await client.logout()
```

### JavaScript/TypeScript SDK Example

```typescript
interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  roles: string[];
  mfa_enabled: boolean;
  created_at: string;
  last_login: string;
}

class AuthClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async login(email: string, password: string, rememberMe: boolean = false): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        password,
        remember_me: rememberMe,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      this.accessToken = data.access_token;
      this.refreshToken = data.refresh_token;
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
  }

  async refreshAccessToken(): Promise<{ access_token: string; refresh_token: string }> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${this.baseUrl}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: this.refreshToken,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      this.accessToken = data.access_token;
      this.refreshToken = data.refresh_token;
      return data;
    } else {
      throw new Error('Token refresh failed');
    }
  }

  async logout(): Promise<void> {
    if (this.accessToken) {
      await fetch(`${this.baseUrl}/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
        },
      });
    }

    this.accessToken = null;
    this.refreshToken = null;
  }

  async getCurrentUser(): Promise<User> {
    return this.authenticatedRequest('GET', '/auth/me');
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.authenticatedRequest('POST', '/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  private async authenticatedRequest(method: string, path: string, body?: any): Promise<any> {
    if (!this.accessToken) {
      throw new Error('Not authenticated');
    }

    let response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && this.refreshToken) {
      // Try to refresh token
      try {
        await this.refreshAccessToken();
        response = await fetch(`${this.baseUrl}${path}`, {
          method,
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json',
          },
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch (error) {
        // Refresh failed, user needs to login again
        throw new Error('Authentication expired');
      }
    }

    if (response.ok) {
      return response.json();
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }
  }
}

// Usage example
const client = new AuthClient('https://auth.yourdomain.com');

async function example() {
  try {
    // Login
    const loginResult = await client.login('user@example.com', 'secure_password123!');
    console.log('Logged in successfully:', loginResult.user.email);

    // Get user info
    const user = await client.getCurrentUser();
    console.log('Current user:', user);

    // Change password
    await client.changePassword('secure_password123!', 'new_secure_password456!');
    console.log('Password changed successfully');

    // Logout
    await client.logout();
    console.log('Logged out successfully');
  } catch (error) {
    console.error('Error:', error.message);
  }
}
```

## Integration Patterns

### React Hook Integration

```typescript
import { useState, useEffect, useContext, createContext } from 'react';

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const client = new AuthClient('https://auth.yourdomain.com');

  useEffect(() => {
    // Check for existing tokens on mount
    const token = localStorage.getItem('access_token');
    if (token) {
      client.accessToken = token;
      client.getCurrentUser()
        .then(setUser)
        .catch(() => localStorage.removeItem('access_token'))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const result = await client.login(email, password);
      setUser(result.user);
      localStorage.setItem('access_token', result.access_token);
      localStorage.setItem('refresh_token', result.refresh_token);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    await client.logout();
    setUser(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        isLoading,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
```

### FastAPI Client Integration

```python
from fastapi import FastAPI, Depends, HTTPException, status
import httpx

app = FastAPI()

class AuthService:
    def __init__(self, auth_url: str):
        self.auth_url = auth_url
    
    async def validate_token(self, token: str) -> dict:
        """Validate token with auth service"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.auth_url}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )

auth_service = AuthService("https://auth.yourdomain.com")

async def get_current_user(authorization: str = Header(...)) -> dict:
    """Dependency to get current user from token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    return await auth_service.validate_token(token)

@app.get("/protected")
async def protected_endpoint(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello {current_user['email']}!"}
```

## WebSocket Authentication

### WebSocket Connection with JWT

```python
from fastapi import WebSocket, WebSocketDisconnect
import jwt

async def websocket_auth(websocket: WebSocket, token: str) -> dict:
    """Authenticate WebSocket connection"""
    try:
        # Validate JWT token
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    user = await websocket_auth(websocket, token)
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            # Process message with authenticated user context
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print(f"User {user['user_id']} disconnected")
```

### JavaScript WebSocket Client

```javascript
class AuthenticatedWebSocket {
  constructor(url, token) {
    this.url = url;
    this.token = token;
    this.ws = null;
  }

  connect() {
    this.ws = new WebSocket(`${this.url}?token=${this.token}`);
    
    this.ws.onopen = (event) => {
      console.log('WebSocket connected');
    };
    
    this.ws.onmessage = (event) => {
      console.log('Message received:', event.data);
    };
    
    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(message);
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const client = new AuthClient('https://auth.yourdomain.com');
await client.login('user@example.com', 'password');

const ws = new AuthenticatedWebSocket('wss://api.yourdomain.com/ws', client.accessToken);
ws.connect();
```

## Testing Examples

### Unit Tests with pytest

```python
import pytest
import httpx
from unittest.mock import patch

class TestAuthAPI:
    
    @pytest.fixture
    async def client(self):
        async with httpx.AsyncClient(
            app=app, 
            base_url="http://test"
        ) as client:
            yield client
    
    async def test_login_success(self, client):
        """Test successful login"""
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "secure_password123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
    
    async def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrong_password"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "INVALID_CREDENTIALS"
    
    async def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without token"""
        response = await client.get("/auth/me")
        
        assert response.status_code == 401
    
    async def test_protected_endpoint_with_valid_token(self, client):
        """Test accessing protected endpoint with valid token"""
        # First login to get token
        login_response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "secure_password123!"
        })
        token = login_response.json()["access_token"]
        
        # Access protected endpoint
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
    
    async def test_token_refresh(self, client):
        """Test token refresh"""
        # Login to get refresh token
        login_response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "secure_password123!"
        })
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = await client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    async def test_rate_limiting(self, client):
        """Test rate limiting on login endpoint"""
        # Make multiple failed login attempts
        for _ in range(6):  # Exceed rate limit of 5
            await client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrong_password"
            })
        
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrong_password"
        })
        
        assert response.status_code == 429
        assert "retry_after" in response.json()
```

### Integration Tests

```python
import pytest
import asyncio
from httpx import AsyncClient

class TestAuthIntegration:
    
    @pytest.fixture(scope="class")
    async def authenticated_client(self):
        """Create authenticated client for integration tests"""
        async with AsyncClient(base_url="https://auth.yourdomain.com") as client:
            # Login
            response = await client.post("/auth/login", json={
                "email": "integration@example.com",
                "password": "integration_password123!"
            })
            
            assert response.status_code == 200
            token = response.json()["access_token"]
            
            # Set authorization header for subsequent requests
            client.headers.update({"Authorization": f"Bearer {token}"})
            yield client
    
    async def test_complete_auth_flow(self):
        """Test complete authentication flow"""
        async with AsyncClient(base_url="https://auth.yourdomain.com") as client:
            # 1. Login
            login_response = await client.post("/auth/login", json={
                "email": "integration@example.com",
                "password": "integration_password123!"
            })
            assert login_response.status_code == 200
            
            tokens = login_response.json()
            access_token = tokens["access_token"]
            refresh_token = tokens["refresh_token"]
            
            # 2. Access protected resource
            me_response = await client.get("/auth/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            assert me_response.status_code == 200
            
            # 3. Refresh token
            refresh_response = await client.post("/auth/refresh", json={
                "refresh_token": refresh_token
            })
            assert refresh_response.status_code == 200
            
            new_access_token = refresh_response.json()["access_token"]
            
            # 4. Use new token
            me_response_2 = await client.get("/auth/me", headers={
                "Authorization": f"Bearer {new_access_token}"
            })
            assert me_response_2.status_code == 200
            
            # 5. Logout
            logout_response = await client.post("/auth/logout", headers={
                "Authorization": f"Bearer {new_access_token}"
            })
            assert logout_response.status_code == 200
    
    async def test_mfa_flow(self, authenticated_client):
        """Test MFA setup and verification flow"""
        # Setup MFA
        setup_response = await authenticated_client.get("/auth/mfa/setup")
        assert setup_response.status_code == 200
        
        mfa_data = setup_response.json()
        assert "qr_code_url" in mfa_data
        assert "backup_codes" in mfa_data
        assert "secret" in mfa_data
        
        # Verify MFA (using backup code for testing)
        verify_response = await authenticated_client.post("/auth/mfa/verify", json={
            "code": None,
            "backup_code": mfa_data["backup_codes"][0]
        })
        assert verify_response.status_code == 200
```

This comprehensive API documentation provides everything needed to integrate with the HIPAA-compliant authentication system, including detailed examples, error handling, and best practices for secure implementation.
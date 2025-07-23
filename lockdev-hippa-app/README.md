# HIPAA-Compliant Web Application

This repository contains a HIPAA-compliant Python web application built with FastAPI, designed to run on containerized infrastructure.

## Repository Structure

```
lockdev-hippa-app/
├── src/
│   ├── routes/        # API route handlers
│   ├── models/        # Data models
│   ├── utils/         # Utility functions
│   └── main.py        # FastAPI application
├── tests/            # Application tests
├── docker/           # Docker-related files
├── Dockerfile        # Container configuration
├── pyproject.toml    # Python dependencies
└── requirements.txt  # Python requirements
```

## Prerequisites

- Python 3.8+
- Poetry package manager
- Docker
- PostgreSQL (for production)

## Setup

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Development

1. Run locally:
   ```bash
   poetry run python -m uvicorn src.main:app --reload
   ```

2. Run tests:
   ```bash
   poetry run pytest tests/
   ```

3. Format code:
   ```bash
   poetry run black .
   poetry run flake8 .
   ```

## Docker

1. Build image:
   ```bash
   docker build -t hipaa-app .
   ```

2. Run container:
   ```bash
   docker run -p 8000:8000 hipaa-app
   ```

3. Test container:
   ```bash
   curl http://localhost:8000/health
   ```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /api/v1/patient/info` - Patient information (mock data)

## Security Features

### HIPAA Compliance
- Secure data handling
- Access controls and authentication
- Audit logging
- Data encryption in transit

### Security Middleware
- CORS protection
- Trusted host validation
- Input validation and sanitization
- Rate limiting (planned)

## Testing

Run the test suite:
```bash
poetry run pytest tests/ -v
```

## Deployment

The application is designed to be deployed on AWS ECS Fargate with:
- Application Load Balancer for HTTPS termination
- RDS PostgreSQL for data storage
- CloudWatch for monitoring and logging
- KMS for encryption key management

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret key for JWT tokens
- `ENVIRONMENT` - Environment (dev/staging/prod)

## Related Repository

This application requires the infrastructure defined in the `lockdev-hippa-iac` repository.

## Repository Status

✅ **Public Repository** - GitHub Code Scanning enabled for free SARIF uploads

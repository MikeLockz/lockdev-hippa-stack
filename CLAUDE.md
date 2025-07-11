# HIPAA-Compliant Infrastructure Stack

## Project Overview
This project creates HIPAA, HITRUST, and SOC2 compliant infrastructure for a health tech company using Infrastructure as Code (IaC) with Pulumi and Python. The architecture supports multi-cloud deployments (AWS primary, GCP secondary) and includes a containerized hello world application.

## Repository Structure
This directory contains two separate repositories:
- `lockdev-hippa-iac/` - Pulumi Python infrastructure code
- `lockdev-hippa-app/` - Hello World Python web application

## Architecture Components

### Core Infrastructure
- **VPC & Networking**: Public/private subnets, NAT gateways, security groups
- **Compute**: ECS Fargate containers with auto-scaling
- **Database**: RDS PostgreSQL with encryption and automated backups
- **Load Balancing**: Application Load Balancer with SSL termination
- **API Gateway**: AWS API Gateway with authentication/authorization
- **Container Registry**: ECR for Docker images

### Security & Compliance
- **Encryption**: KMS key management, encryption at rest and in transit
- **Access Controls**: IAM roles with least privilege, MFA requirements
- **Audit Logging**: CloudTrail, VPC Flow Logs, application logs
- **Monitoring**: CloudWatch, X-Ray tracing, GuardDuty, Config
- **Network Security**: Private subnets, security groups, NACLs, WAF

### HIPAA/HITRUST Compliance Features
- Data encryption at rest and in transit
- Access logging and audit trails
- Network segmentation and isolation
- Automated backup and disaster recovery
- Vulnerability scanning and monitoring
- Data loss prevention (DLP) policies

## Development Environment Setup

### Prerequisites
```bash
# Install Python and Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Install Pulumi
curl -fsSL https://get.pulumi.com | sh
export PATH="$HOME/.pulumi/bin:$PATH"

# Install AWS CLI
pip install awscli
aws configure

# Install Docker
# Follow platform-specific Docker installation instructions
```

### Python Development Environment
```bash
# Create virtual environment
poetry install

# Install development dependencies
poetry add --group dev black flake8 mypy pytest pre-commit

# Setup pre-commit hooks
pre-commit install
```

## Common Commands

### Infrastructure Management (Pulumi)
```bash
# Navigate to IaC repository
cd lockdev-hippa-iac/

# Install dependencies
poetry install

# Login to Pulumi (use your preferred backend)
pulumi login

# Create new stack
pulumi stack init dev

# Preview changes
pulumi preview

# Deploy infrastructure
pulumi up

# View stack outputs
pulumi stack output

# Destroy infrastructure
pulumi destroy
```

### Application Development
```bash
# Navigate to application repository
cd lockdev-hippa-app/

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black .

# Lint code
poetry run flake8 .

# Type check
poetry run mypy .

# Build Docker image
docker build -t hippa-app .

# Run locally
docker run -p 8000:8000 hippa-app
```

### Multi-Environment Management
```bash
# Development environment
pulumi stack select dev
pulumi up

# Staging environment
pulumi stack select staging
pulumi up

# Production environment
pulumi stack select prod
pulumi up
```

## CI/CD Pipeline

### GitHub Actions Workflows
- **IaC Pipeline**: Validates, tests, and deploys infrastructure changes
- **Application Pipeline**: Builds, tests, scans, and deploys containerized application
- **Security Pipeline**: Runs compliance checks and vulnerability scans

### Key Pipeline Features
- Automated testing and linting
- Security scanning with tools like Checkov, Bandit
- Multi-environment deployment with approval gates
- Compliance validation and reporting
- Automated rollback on failures

## Project Structure

### IaC Repository (`lockdev-hippa-iac/`)
```
lockdev-hippa-iac/
├── .github/
│   └── workflows/
│       ├── infrastructure.yml
│       └── security-scan.yml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── networking/
│   ├── compute/
│   ├── database/
│   ├── security/
│   └── monitoring/
├── tests/
├── configs/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
├── pyproject.toml
├── Pulumi.yaml
└── README.md
```

### Application Repository (`lockdev-hippa-app/`)
```
lockdev-hippa-app/
├── .github/
│   └── workflows/
│       ├── application.yml
│       └── security-scan.yml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── routes/
│   ├── models/
│   └── utils/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Security Best Practices

### Code Security
- Use pre-commit hooks for security scanning
- Implement static analysis with Bandit
- Regular dependency vulnerability scanning
- Secrets management with AWS Secrets Manager/Parameter Store

### Infrastructure Security
- Enable CloudTrail in all regions
- Use GuardDuty for threat detection
- Implement Config rules for compliance monitoring
- Regular security assessments and penetration testing

### Data Protection
- Encrypt all data at rest using KMS
- Use TLS 1.2+ for data in transit
- Implement data classification and DLP policies
- Regular backup testing and disaster recovery drills

## Monitoring & Compliance

### Monitoring Stack
- CloudWatch for metrics and logs
- X-Ray for distributed tracing
- Custom dashboards for health metrics
- Alerting for security and compliance violations

### Compliance Reporting
- Automated compliance checks
- Regular audit log reviews
- HITRUST assessment preparation
- SOC2 compliance documentation

## Multi-Cloud Strategy

### AWS Services
- Primary cloud provider
- ECS for container orchestration
- RDS for managed databases
- CloudFront for CDN

### GCP Services
- Secondary cloud provider
- Cloud Run for containers
- Cloud SQL for databases
- Cloud CDN for content delivery

### Abstraction Layer
- Pulumi providers for multi-cloud support
- Common interfaces for cloud services
- Environment-specific configurations

## Getting Started

1. **Clone repositories**:
   ```bash
   git clone <iac-repo-url> lockdev-hippa-iac
   git clone <app-repo-url> lockdev-hippa-app
   ```

2. **Setup development environment**:
   ```bash
   # Install prerequisites (Python, Poetry, Pulumi, Docker)
   # Configure AWS credentials
   # Setup GitHub Actions secrets
   ```

3. **Deploy infrastructure**:
   ```bash
   cd lockdev-hippa-iac
   poetry install
   pulumi stack init dev
   pulumi up
   ```

4. **Deploy application**:
   ```bash
   cd lockdev-hippa-app
   poetry install
   # Build and push Docker image
   # Deploy via GitHub Actions
   ```

## Support & Documentation

### Resources
- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [HITRUST CSF](https://hitrustalliance.net/csf/)

### Common Issues
- Check AWS credentials configuration
- Verify Pulumi stack configuration
- Review CloudWatch logs for application errors
- Validate security group rules and network connectivity

## Environment Variables

### Required Environment Variables
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_DEFAULT_REGION=us-east-1

# Pulumi Configuration
PULUMI_ACCESS_TOKEN=<your-pulumi-token>

# Application Configuration
DATABASE_URL=<database-connection-string>
JWT_SECRET=<jwt-secret-key>
```

### GitHub Actions Secrets
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `PULUMI_ACCESS_TOKEN`
- `DOCKER_REGISTRY_URL`
- `DATABASE_PASSWORD`

## Testing Strategy

### Infrastructure Testing
- Unit tests for Pulumi components
- Integration tests for AWS resources
- Compliance tests for security configurations
- Performance tests for load balancers

### Application Testing
- Unit tests with pytest
- Integration tests with test database
- Security tests with OWASP ZAP
- Load testing with Locust

## Deployment Strategy

### Blue-Green Deployment
- Zero-downtime deployments
- Automated rollback on failures
- Health checks and monitoring
- Gradual traffic shifting

### Environment Promotion
- Development → Staging → Production
- Approval gates for production
- Automated testing at each stage
- Compliance validation before promotion
# HIPAA-Compliant Infrastructure as Code

This repository contains the Infrastructure as Code (IaC) for a HIPAA, HITRUST, and SOC2 compliant health tech infrastructure using Pulumi and Python.

## Repository Structure

```
lockdev-hippa-iac/
├── src/
│   ├── networking/     # VPC, subnets, security groups
│   ├── compute/        # ECS, ALB, auto-scaling
│   ├── database/       # RDS PostgreSQL
│   ├── security/       # KMS, IAM, security configurations
│   └── monitoring/     # CloudWatch, CloudTrail
├── tests/             # Infrastructure tests
├── configs/           # Environment-specific configurations
├── docs/             # Documentation
├── pyproject.toml    # Python dependencies
└── Pulumi.yaml       # Pulumi project configuration
```

## Prerequisites

- Python 3.8+
- Poetry package manager
- Pulumi CLI
- AWS CLI configured with appropriate credentials

## Setup

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Login to Pulumi:
   ```bash
   pulumi login
   ```

3. Create and configure stack:
   ```bash
   pulumi stack init dev
   pulumi config set aws:region us-east-1
   ```

## Deployment

1. Preview changes:
   ```bash
   pulumi preview
   ```

2. Deploy infrastructure:
   ```bash
   pulumi up
   ```

3. View outputs:
   ```bash
   pulumi stack output
   ```

## Compliance Features

### HIPAA Compliance
- Data encryption at rest and in transit
- Access logging and audit trails
- Network segmentation
- Automated backup and recovery

### HITRUST Compliance
- Information security governance
- Risk management
- Compliance monitoring

### SOC2 Compliance
- Security controls
- Availability monitoring
- Processing integrity
- Confidentiality measures

## Architecture

The infrastructure creates:
- **VPC** with public/private subnets across multiple AZs
- **Security Groups** with least-privilege access
- **KMS** encryption keys for data protection
- **RDS PostgreSQL** with encryption and automated backups
- **CloudWatch** monitoring and alerting
- **CloudTrail** audit logging

## Testing

Run tests:
```bash
poetry run pytest tests/
```

## Security

- All data encrypted at rest using KMS
- SSL/TLS encryption for data in transit
- Least privilege IAM policies
- Regular security scanning and compliance checks

## Related Repository

This infrastructure supports the application in the `lockdev-hippa-app` repository.
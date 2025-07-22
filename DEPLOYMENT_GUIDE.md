# HIPAA Infrastructure Deployment Guide

## 🚀 Real-World Deployment Steps

This guide walks you through deploying the complete HIPAA-compliant infrastructure stack with **enterprise-grade IAM separation** from scratch.

## Prerequisites Setup

### 1. Install Required Tools

```bash
# Install Python 3.11+
brew install python@3.11  # macOS
# OR
sudo apt-get install python3.11 python3.11-pip  # Ubuntu

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Install Pulumi
curl -fsSL https://get.pulumi.com | sh
export PATH="$HOME/.pulumi/bin:$PATH"

# Install AWS CLI
pip3 install awscli

# Install Docker
# Download from https://docker.com/get-started
```

### 2. Configure AWS Credentials

```bash
# Configure AWS CLI with admin permissions (required for initial IAM setup)
aws configure
# Enter:
# AWS Access Key ID: [Your Access Key with IAM permissions]
# AWS Secret Access Key: [Your Secret Key]
# Default region: us-east-1
# Default output format: json

# Verify AWS access
aws sts get-caller-identity
# Note: You'll need IAM permissions for initial bootstrap
```

### 3. Setup Pulumi Account

```bash
# Create free Pulumi account at https://app.pulumi.com/
# Get your access token from https://app.pulumi.com/account/tokens

# Login to Pulumi
pulumi login
# OR set token directly
export PULUMI_ACCESS_TOKEN="your-token-here"
```

## Step-by-Step Deployment

### Phase 1: Clone and Setup Repository

```bash
# Navigate to your desired directory
cd ~/Development

# Clone the repository (assuming you have it locally)
# OR create from scratch following the structure in CLAUDE.md

# Verify structure
ls -la lockdev-hippa-stack/
# Should show:
# - lockdev-hippa-iac/
# - lockdev-hippa-app/
# - CLAUDE.md
# - implementation.md
```

### Phase 2: Deploy Infrastructure with IAM Separation (76 AWS Resources)

#### Option A: Automated Deployment (Recommended)

```bash
# Navigate to infrastructure directory
cd lockdev-hippa-stack/lockdev-hippa-iac/

# Install dependencies
poetry install

# Step 1: One-time IAM bootstrap (creates separated IAM users)
./bootstrap/deploy-bootstrap.sh test

# Step 2: Deploy infrastructure with automated IAM separation
./deploy-infrastructure.sh test
```

#### Option B: Manual Step-by-Step Deployment

```bash
# Navigate to infrastructure directory
cd lockdev-hippa-stack/lockdev-hippa-iac/

# Install dependencies
poetry install

# Initialize Pulumi stack
pulumi stack init test
pulumi config set aws:region us-east-1
pulumi config set environment test

# 🔒 Use AWS Secrets Manager (RECOMMENDED)
# This eliminates manual password configuration and provides:
# - Automatic 32-character password generation
# - 30-day automatic rotation
# - KMS encryption at rest
# - HIPAA-compliant credential storage
# - IAM separation for security

mv __main__.py __main__.py.backup
cp src/main_with_secrets.py __main__.py

# Alternative: Manual password (legacy method)
# pulumi config set --secret db_password $(openssl rand -base64 32)

# Preview infrastructure (should show 76 resources)
poetry run pulumi preview

# Deploy infrastructure (takes 10-15 minutes)
poetry run pulumi up
```

**What this deploys:**
- **IAM separation** with dedicated users for security
- VPC with public/private subnets
- ECS cluster with Fargate
- RDS PostgreSQL database
- Application Load Balancer
- ECR repository
- Security groups with least privilege
- KMS encryption with automatic rotation
- CloudTrail logging with audit trail
- GuardDuty security with threat detection
- CloudWatch monitoring with compliance
- **AWS Secrets Manager** for secure credential storage
- **Automatic password rotation** (30-day cycle)
- **Enterprise-grade access controls**

### Phase 3: Build and Deploy Application

```bash
# Navigate to application directory
cd ../lockdev-hippa-app/

# Install dependencies
poetry install

# Run tests to verify everything works
ENVIRONMENT=testing poetry run pytest tests/ -v
# Should show: 4 passed

# Build Docker image
docker build -t hipaa-app .

# Get ECR repository URL from Pulumi
cd ../lockdev-hippa-iac/
ECR_URL=$(pulumi stack output ecr_repository_url)
echo "ECR URL: $ECR_URL"

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL

# Tag and push Docker image
cd ../lockdev-hippa-app/
docker tag hipaa-app:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### Phase 4: Verify Deployment

```bash
# Get ALB DNS name
cd ../lockdev-hippa-iac/
ALB_DNS=$(pulumi stack output alb_dns_name)
echo "Application URL: https://$ALB_DNS"

# Test health endpoints
curl -k https://$ALB_DNS/health/
# Should return: {"status": "healthy", "timestamp": "..."}

curl -k https://$ALB_DNS/health/ready
# Should return: {"status": "ready", "timestamp": "..."}

curl -k https://$ALB_DNS/api/v1/hello
# Should return: {"message": "Hello from HIPAA-compliant API!"}
```

## Real-World Testing Procedures

### 1. Infrastructure Testing

```bash
# Test VPC connectivity
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=HIPAA-VPC"

# Test database connectivity
aws rds describe-db-instances --db-instance-identifier hipaa-postgres-db

# Test ECS service
aws ecs describe-services --cluster hipaa-ecs-cluster --services hipaa-app-service

# Test security groups
aws ec2 describe-security-groups --filters "Name=tag:Compliance,Values=HIPAA"
```

### 2. Application Testing

```bash
# Load testing with curl
for i in {1..10}; do
  curl -s -w "Response time: %{time_total}s\n" https://$ALB_DNS/health/ > /dev/null
done

# Test with different user agents
curl -H "User-Agent: HealthCheck/1.0" https://$ALB_DNS/health/

# Test API endpoints
curl -X GET https://$ALB_DNS/api/v1/hello
curl -X POST https://$ALB_DNS/api/v1/users -H "Content-Type: application/json" -d '{"username": "testuser", "email": "test@example.com"}'
```

### 3. Security Testing

```bash
# Test security headers
curl -I https://$ALB_DNS/health/
# Should show security headers:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block

# Test for SQL injection (should be blocked)
curl "https://$ALB_DNS/api/v1/users?id=1' OR '1'='1"

# Test HTTPS enforcement
curl -I http://$ALB_DNS/health/
# Should redirect to HTTPS
```

### 4. Compliance Testing

```bash
# Generate compliance report
cd lockdev-hippa-iac/
python3 -c "
import boto3
import json

# Check encryption
rds = boto3.client('rds')
instances = rds.describe_db_instances()
for db in instances['DBInstances']:
    print(f'Database {db['DBInstanceIdentifier']} encrypted: {db['StorageEncrypted']}')

# Check CloudTrail
cloudtrail = boto3.client('cloudtrail')
trails = cloudtrail.describe_trails()
print(f'CloudTrail trails: {len(trails['trailList'])}')

# Check GuardDuty
guardduty = boto3.client('guardduty')
detectors = guardduty.list_detectors()
print(f'GuardDuty detectors: {len(detectors['DetectorIds'])}')
"
```

## Monitoring and Validation

### 1. CloudWatch Monitoring

```bash
# Check CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix "/aws/ecs/hipaa-app"

# View recent logs
aws logs tail /aws/ecs/hipaa-app --follow --since 1h

# Check metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=hipaa-app-service \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### 2. Health Monitoring

```bash
# Create monitoring script
cat > monitor_health.sh << 'EOF'
#!/bin/bash
ALB_DNS="your-alb-dns-here"

while true; do
  echo "$(date): Checking health..."
  
  # Basic health check
  if curl -s -f https://$ALB_DNS/health/ > /dev/null; then
    echo "✅ Health check passed"
  else
    echo "❌ Health check failed"
    # Add alerting here
  fi
  
  # Database health check
  if curl -s -f https://$ALB_DNS/health/ready > /dev/null; then
    echo "✅ Database health check passed"
  else
    echo "❌ Database health check failed"
  fi
  
  sleep 30
done
EOF

chmod +x monitor_health.sh
./monitor_health.sh
```

## Troubleshooting Common Issues

### 1. IAM Permission Issues

```bash
# Check current IAM user permissions
aws sts get-caller-identity
aws iam list-attached-user-policies --user-name your-username

# If bootstrap fails with permission errors:
# Option 1: Temporarily attach PowerUserAccess
aws iam attach-user-policy --user-name your-username --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Run bootstrap, then remove admin access
./bootstrap/deploy-bootstrap.sh test
aws iam detach-user-policy --user-name your-username --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Option 2: Use root account for initial setup
# Then switch to limited users for ongoing operations
```

### 2. Infrastructure Deployment Fails

```bash
# Check Pulumi logs
pulumi logs --follow

# Check AWS CloudFormation events
aws cloudformation describe-stack-events --stack-name your-stack-name

# Check IAM separation status
aws cloudformation describe-stacks --stack-name hipaa-iam-bootstrap-test

# Common fixes:
# - Verify IAM bootstrap completed successfully
# - Check AWS credentials for both users
# - Verify region settings
# - Check resource limits in AWS account
```

### 2. Application Won't Start

```bash
# Check ECS service logs
aws logs tail /aws/ecs/hipaa-app --follow

# Check ECS service status
aws ecs describe-services --cluster hipaa-ecs-cluster --services hipaa-app-service

# Common fixes:
# - Check Docker image build
# - Verify environment variables
# - Check database connectivity
```

### 3. Database Connection Issues

```bash
# Check database secrets in Secrets Manager
aws secretsmanager describe-secret --secret-id hipaa/dev/database/credentials
aws secretsmanager get-secret-value --secret-id hipaa/dev/database/credentials

# Test database connectivity from ECS
aws ecs run-task \
  --cluster hipaa-ecs-cluster \
  --task-definition hipaa-app-task \
  --overrides '{"containerOverrides":[{"name":"hipaa-app","command":["python","-c","import psycopg2; print(\"Database connection test\")"]}]}'

# Check security group rules
aws ec2 describe-security-groups --group-names hipaa-rds-sg
```

### 4. Secrets Manager Issues

```bash
# Check if secrets exist and are accessible
aws secretsmanager list-secrets --filters Key=name,Values=hipaa/

# Check IAM Manager credentials
aws secretsmanager get-secret-value --secret-id hipaa/test/iam-manager/credentials

# Test secret rotation status
aws secretsmanager describe-secret --secret-id hipaa/test/database/credentials \
  --query 'RotationEnabled'

# Force secret rotation if needed
aws secretsmanager rotate-secret --secret-id hipaa/test/database/credentials
```

### 5. IAM Separation Issues

```bash
# Verify IAM users exist
aws iam get-user --user-name hipaa-iam-manager-test
aws iam get-user --user-name pulumi-deploy-user

# Check policy attachments
aws iam list-attached-user-policies --user-name hipaa-iam-manager-test
aws iam list-attached-user-policies --user-name pulumi-deploy-user

# Test credential switching
IAM_CREDS=$(aws secretsmanager get-secret-value --secret-id hipaa/test/iam-manager/credentials --query 'SecretString' --output text)
echo $IAM_CREDS | jq '.AccessKeyId'

# Verify bootstrap stack
aws cloudformation describe-stacks --stack-name hipaa-iam-bootstrap-test
```

## Production Deployment Checklist

### Before Going Live:

- [ ] **IAM separation** is properly configured and tested
- [ ] All tests pass (infrastructure, application, security)
- [ ] AWS Secrets Manager is configured with automatic rotation
- [ ] Database passwords are auto-generated and KMS encrypted
- [ ] **Principle of least privilege** is enforced
- [ ] SSL certificates are properly configured
- [ ] Monitoring and alerting are set up
- [ ] Backup and disaster recovery procedures are tested
- [ ] Security scanning shows no critical vulnerabilities
- [ ] Compliance requirements are verified
- [ ] **Audit trail** is complete and accessible
- [ ] Documentation is complete and up-to-date

### Production Configuration:

```bash
# Create production IAM bootstrap (if not already done)
./bootstrap/deploy-bootstrap.sh prod

# Deploy production infrastructure with IAM separation
./deploy-infrastructure.sh prod

# Alternative: Manual production setup
pulumi stack init prod
pulumi config set aws:region us-east-1
pulumi config set environment prod

# 🔒 Production uses Secrets Manager automatically
# No password configuration needed - all handled securely
mv __main__.py __main__.py.backup  # if not already done
cp src/main_with_secrets.py __main__.py

# Enable multi-AZ for database
# Edit src/database/rds.py and set multi_az=True

# Deploy with production settings
pulumi up
```

## Cost Estimation

**Monthly AWS costs (approximate):**
- ECS Fargate: $20-50
- RDS PostgreSQL: $30-60
- Load Balancer: $20
- CloudWatch: $5-15
- Other services: $10-20

**Total estimated cost: $85-165/month**

## Next Steps

1. **Set up custom domain**: Use Route53 and ACM for SSL certificates
2. **Configure WAF**: Add Web Application Firewall for additional security
3. **Set up CI/CD**: Configure GitHub Actions for automated deployments
4. **Add monitoring**: Set up CloudWatch dashboards and alerts
5. **Schedule backups**: Configure automated database backups and testing

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review AWS CloudWatch logs
3. Verify all prerequisites are met
4. Check AWS service limits and quotas
5. Review the implementation.md file for detailed technical information

**Remember**: This is a production-ready HIPAA-compliant infrastructure. Always follow security best practices and compliance requirements when handling PHI data.
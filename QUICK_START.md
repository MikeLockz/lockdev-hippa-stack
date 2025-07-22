# Quick Start Guide - Deploy in 30 Minutes

## 🚀 Fast Track Deployment

Follow these steps to deploy the HIPAA-compliant infrastructure with **enterprise-grade IAM separation** in about 30 minutes.

## Prerequisites (5 minutes)

```bash
# 1. Install tools (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -
curl -fsSL https://get.pulumi.com | sh
brew install awscli  # or: pip3 install awscli

# 2. Configure AWS (requires admin permissions for initial setup)
aws configure
# Enter your AWS credentials with IAM permissions

# 3. Setup Pulumi
export PULUMI_ACCESS_TOKEN="your-pulumi-token"
pulumi login
```

## Deploy Infrastructure with IAM Separation (15 minutes)

### Option A: Automated Deployment (Recommended)

```bash
# 1. Navigate to infrastructure
cd lockdev-hippa-stack/lockdev-hippa-iac/

# 2. Install dependencies
poetry install

# 3. One-time IAM bootstrap (requires admin permissions)
./bootstrap/deploy-bootstrap.sh test

# 4. Deploy infrastructure with separated IAM
./deploy-infrastructure.sh test
```

### Option B: Manual Deployment

```bash
# 1. Navigate to infrastructure
cd lockdev-hippa-stack/lockdev-hippa-iac/

# 2. Install dependencies
poetry install

# 3. Initialize stack
pulumi stack init test
pulumi config set aws:region us-east-1
pulumi config set environment test

# 4. Use Secrets Manager version (no password config needed!)
mv __main__.py __main__.py.backup
cp src/main_with_secrets.py __main__.py

# 5. Deploy (takes ~10-15 minutes)
poetry run pulumi up
```

## Deploy Application (5 minutes)

```bash
# 1. Navigate to application
cd ../lockdev-hippa-app/

# 2. Install dependencies
poetry install

# 3. Run tests
ENVIRONMENT=testing poetry run pytest tests/ -v

# 4. Build and deploy
docker build -t hipaa-app .
ECR_URL=$(cd ../lockdev-hippa-iac && pulumi stack output ecr_repository_url)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
docker tag hipaa-app:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

## Test Everything (5 minutes)

```bash
# Get your application URL
ALB_DNS=$(cd ../lockdev-hippa-iac && pulumi stack output alb_dns_name)
echo "Your app is at: https://$ALB_DNS"

# Test endpoints
curl -k https://$ALB_DNS/health/
curl -k https://$ALB_DNS/api/v1/hello
curl -k https://$ALB_DNS/metrics
```

## ✅ You're Done!

Your HIPAA-compliant infrastructure is now running with:
- **76 AWS resources** deployed
- **Enterprise IAM separation** for security
- **FastAPI application** with security features
- **Database with encryption** and auto-rotation
- **Monitoring and logging** with compliance
- **Security scanning** and threat detection

## What You Just Deployed

### Infrastructure (76 AWS Resources):
- **VPC** with public/private subnets
- **ECS Fargate** cluster for containers
- **RDS PostgreSQL** with encryption
- **Application Load Balancer** with SSL
- **ECR** repository for Docker images
- **CloudWatch** monitoring and logging
- **CloudTrail** audit logging
- **GuardDuty** threat detection
- **AWS Config** compliance rules
- **KMS** encryption keys
- **IAM roles** with least privilege
- **Security groups** with restrictive rules

### Application Features:
- **FastAPI** web framework
- **Health endpoints** for monitoring
- **Security headers** for HIPAA compliance
- **JWT authentication** ready
- **Database models** with audit logging
- **Structured logging** with PHI sanitization
- **Prometheus metrics** export
- **Docker** containerization

### Security & Compliance:
- **IAM separation** with dedicated users for different functions
- **Data encryption** at rest and in transit
- **Network isolation** with private subnets
- **Audit logging** with CloudTrail
- **Threat detection** with GuardDuty
- **Compliance monitoring** with Config rules
- **Security scanning** in CI/CD pipeline
- **AWS Secrets Manager** for credential management
- **Automatic password rotation** (30-day cycle)
- **Principle of least privilege** access controls

## Next Steps

1. **Review IAM setup**: Verify separation of duties is working
2. **Set up custom domain**: Configure Route53 and SSL certificates
3. **Configure monitoring**: Set up CloudWatch dashboards
4. **Add alerting**: Configure SNS notifications
5. **Set up CI/CD**: Connect GitHub Actions with separated credentials
6. **Review security**: Run security assessments and compliance checks

## Cost Estimate

**Monthly AWS costs**: ~$85-165
- ECS Fargate: $20-50
- RDS PostgreSQL: $30-60
- Load Balancer: $20
- Other services: $15-35

## Get Support

Check the full `DEPLOYMENT_GUIDE.md` for detailed troubleshooting and advanced configuration options.

**🎉 Congratulations! You now have a production-ready HIPAA-compliant infrastructure!**
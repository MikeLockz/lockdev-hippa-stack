# Multi-Account HIPAA Infrastructure Deployment

This directory contains scripts for deploying HIPAA-compliant infrastructure across multiple AWS accounts with maximum repeatability and security.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dev Account   │    │ Staging Account │    │  Prod Account   │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │    ECS      │ │    │ │    ECS      │ │    │ │    ECS      │ │
│ │   + ALB     │ │    │ │   + ALB     │ │    │ │   + ALB     │ │
│ │   + RDS     │ │    │ │   + RDS     │ │    │ │   + RDS     │ │
│ │   + KMS     │ │    │ │   + KMS     │ │    │ │   + KMS     │ │
│ │   + IAM     │ │    │ │   + IAM     │ │    │ │   + IAM     │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Setup AWS Accounts
```bash
# Configure AWS CLI profiles for each account
./scripts/setup-accounts.sh

# Test access to all configured accounts
./scripts/setup-accounts.sh --test
```

### 2. Deploy to Multiple Accounts
```bash
# Deploy to specific accounts
./scripts/multi-account-deploy.sh dev staging

# Deploy to all configured accounts
./scripts/multi-account-deploy.sh

# Preview changes without deploying
./scripts/multi-account-deploy.sh --preview
```

### 3. Manage Deployments
```bash
# Check deployment status
./scripts/multi-account-deploy.sh --preview dev

# Update specific account
./scripts/multi-account-deploy.sh prod-us

# Destroy infrastructure (with safety checks)
./scripts/cleanup-accounts.sh dev
```

## 📁 Directory Structure

```
lockdev-hippa-iac/
├── scripts/
│   ├── multi-account-deploy.sh    # Main deployment script
│   ├── setup-accounts.sh          # AWS account configuration
│   └── cleanup-accounts.sh        # Safe infrastructure cleanup
├── configs/
│   └── accounts.yaml              # Account configuration
├── outputs/                       # Deployment outputs per account
│   ├── dev-outputs.json
│   ├── staging-outputs.json
│   └── prod-us-outputs.json
└── src/                           # Pulumi infrastructure code
```

## ⚙️ Configuration

### Account Configuration (`configs/accounts.yaml`)

```yaml
accounts:
  dev:
    profile: dev-root           # AWS CLI profile name
    region: us-east-1          # AWS region
    environment: development   # Environment tag
    tags:                      # Custom tags
      CostCenter: "Development"
      Owner: "DevTeam"
```

### Supported Environments
- **dev**: Development environment
- **staging**: Staging/QA environment  
- **prod-us**: Production US region
- **prod-eu**: Production EU region (GDPR compliance)

## 🔐 Security Features

### Multi-Account Benefits
- **Blast Radius**: Issues contained to single account
- **Compliance**: Clear audit boundaries
- **Access Control**: Account-level isolation
- **Cost Management**: Per-account billing

### Root User Security
- **Temporary Usage**: Create keys, deploy, delete keys
- **MFA Support**: Session tokens with MFA
- **Audit Trail**: CloudTrail in each account
- **Key Rotation**: Regular access key rotation

### HIPAA Compliance
- **Encryption**: All data encrypted at rest and in transit
- **Audit Logging**: Comprehensive logging across all accounts
- **Access Controls**: Least privilege IAM policies
- **Network Security**: Private subnets and security groups

## 🛠️ Scripts Reference

### `scripts/setup-accounts.sh`
Configures AWS CLI profiles for multiple accounts.

```bash
# Interactive setup for all accounts
./scripts/setup-accounts.sh

# List configured profiles
./scripts/setup-accounts.sh --list

# Test access to all accounts
./scripts/setup-accounts.sh --test

# Access key rotation guide
./scripts/setup-accounts.sh --rotate
```

### `scripts/multi-account-deploy.sh`
Deploys infrastructure across multiple accounts.

```bash
# Deploy to specific accounts
./scripts/multi-account-deploy.sh dev staging prod-us

# Deploy with custom configuration
./scripts/multi-account-deploy.sh --config configs/prod-accounts.yaml

# Preview changes only
./scripts/multi-account-deploy.sh --preview

# Skip confirmation prompts
./scripts/multi-account-deploy.sh --force dev
```

**Options:**
- `--config FILE`: Custom account configuration
- `--preview`: Show changes without deploying
- `--force`: Skip confirmation prompts
- `--outputs-dir DIR`: Custom outputs directory
- `--stack-prefix PREFIX`: Custom Pulumi stack prefix

### `scripts/cleanup-accounts.sh`
Safely destroys infrastructure with multiple safety checks.

```bash
# Destroy single account (with prompts)
./scripts/cleanup-accounts.sh dev

# Dry run to see what would be destroyed
./scripts/cleanup-accounts.sh --dry-run dev staging

# Emergency destruction with confirmation text
./scripts/cleanup-accounts.sh --confirm "emergency" --force dev
```

**Safety Features:**
- Multiple confirmation prompts
- Account name verification
- Random code confirmation
- Dry-run mode
- Resource preview before destruction

## 📊 Deployment Outputs

Each successful deployment creates an outputs file:

```json
{
  "alb_dns_name": "hipaa-alb-123456.us-east-1.elb.amazonaws.com",
  "ecr_repository_url": "123456789012.dkr.ecr.us-east-1.amazonaws.com/hipaa-app",
  "database_endpoint": "hipaa-db.cluster-xyz.us-east-1.rds.amazonaws.com",
  "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
}
```

## 🔄 Workflow Examples

### Development Workflow
```bash
# 1. Setup new development account
./scripts/setup-accounts.sh

# 2. Deploy infrastructure
./scripts/multi-account-deploy.sh dev

# 3. Deploy application (use outputs from step 2)
cd ../lockdev-hippa-app
docker build -t app .
# Push to ECR URL from outputs
# Update ECS service

# 4. Test and iterate
./scripts/multi-account-deploy.sh dev  # Update infrastructure

# 5. Cleanup when done
./scripts/cleanup-accounts.sh dev
```

### Production Deployment
```bash
# 1. Deploy to staging first
./scripts/multi-account-deploy.sh staging

# 2. Test staging deployment
curl https://$(jq -r '.alb_dns_name' outputs/staging-outputs.json)/health/

# 3. Deploy to production
./scripts/multi-account-deploy.sh prod-us prod-eu

# 4. Verify production deployment
./scripts/multi-account-deploy.sh --preview prod-us prod-eu
```

### Disaster Recovery
```bash
# 1. Backup current state
pulumi stack export --file backup-$(date +%Y%m%d).json

# 2. Deploy to new region/account
./scripts/multi-account-deploy.sh prod-backup

# 3. Update DNS/load balancing to new deployment
```

## 📈 Cost Management

### Per-Account Monitoring
Each account has independent billing for clear cost allocation:

```bash
# Check costs per account
aws ce get-cost-and-usage --profile dev-root --time-period Start=2024-01-01,End=2024-01-31
```

### Budget Alerts
Configure in `configs/accounts.yaml`:
```yaml
cost_management:
  enable_billing_alerts: true
  monthly_budget_usd: 500
  alert_threshold_percent: 80
```

## 🚨 Troubleshooting

### Common Issues

**"Cannot access AWS account"**
```bash
# Check AWS profile configuration
aws configure list --profile PROFILE_NAME

# Test credentials
aws sts get-caller-identity --profile PROFILE_NAME
```

**"Stack already exists"**
```bash
# List existing stacks
pulumi stack ls

# Remove orphaned stack
pulumi stack rm STACK_NAME --yes
```

**"Insufficient permissions"**
- Ensure using root user credentials
- Check IAM policies if using IAM user
- Verify account access

### Debug Mode
```bash
# Enable verbose logging
export PULUMI_DEBUG=true
./scripts/multi-account-deploy.sh dev
```

## 🔗 Integration

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Deploy to multiple accounts
  run: |
    ./scripts/setup-accounts.sh --test
    ./scripts/multi-account-deploy.sh staging prod-us
```

### Infrastructure as Code
```bash
# Version control all configurations
git add configs/accounts.yaml
git commit -m "Update production account configuration"
```

## 📚 Additional Resources

- [AWS Multi-Account Strategy](https://aws.amazon.com/organizations/)
- [HIPAA Compliance on AWS](https://aws.amazon.com/compliance/hipaa-compliance/)
- [Pulumi Multi-Cloud](https://www.pulumi.com/docs/intro/cloud-providers/)
- [AWS Root User Best Practices](https://docs.aws.amazon.com/accounts/latest/reference/root-user.html)

## 🆘 Support

### Getting Help
```bash
# Show script help
./scripts/multi-account-deploy.sh --help
./scripts/setup-accounts.sh --help
./scripts/cleanup-accounts.sh --help

# Check script status
echo $?  # Exit code from last command
```

### Common Commands
```bash
# Check all account access
./scripts/setup-accounts.sh --test

# Preview all deployments
./scripts/multi-account-deploy.sh --preview

# Emergency cleanup with safety checks
./scripts/cleanup-accounts.sh --dry-run
```
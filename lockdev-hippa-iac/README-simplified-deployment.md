# HIPAA Infrastructure - Smart Deployment

This documentation explains the **smart deployment system** with automatic setup detection for HIPAA-compliant infrastructure.

## Overview

The shell scripts have been **dramatically simplified** from 7 complex scripts (1,400+ lines) down to **3 core scripts** (~400 lines total) with **intelligent auto-setup**:

- **`scripts/setup-env.sh`** - Phase 1: Root Account → Service User Creation
- **`scripts/deploy.sh`** - **Smart Deployment**: Auto-detects missing setup + deploys
- **`scripts/cleanup.sh`** - Safe Infrastructure Cleanup

## 🤖 Smart Deployment

**The key innovation**: You can now **always run `make deploy-dev`** and it will automatically detect if setup is needed and run it for you!

## Two-Phase Security Model

### Why Two Phases?

This follows AWS security best practices:

1. **Root accounts** should only be used for initial setup and user creation
2. **Service accounts** with limited permissions should handle day-to-day operations
3. **Principle of least privilege** - each account only has the minimum required permissions

### 🤖 Smart Deployment Flow

**New Approach**: Just run deploy - it handles everything automatically!

```bash
# Smart deployment - handles setup automatically if needed
make deploy-dev
```

**What happens automatically:**

1. **🔍 Detection Phase**
   - Checks if service user exists (`pulumi-deploy-user-dev`)
   - Validates service user credentials work

2. **🔧 Auto-Setup Phase** (if needed)
   - Uses root account credentials (e.g., `dev-root`)
   - Creates service user (e.g., `pulumi-deploy-user-dev`)
   - Attaches infrastructure deployment policy to service user
   - Creates access keys for service user
   - Saves credentials securely

3. **🚀 Deployment Phase**
   - Uses service user credentials for deployment
   - Deploys Pulumi infrastructure with limited permissions
   - Supports preview, deploy, and destroy operations
   - Maintains audit trail and outputs

### Manual Setup (Optional)

If you prefer explicit control, you can still run setup manually:

```bash
# Manual setup (optional)
make setup-env-dev
make validate-env-dev
make deploy-dev
```

## Quick Start Guide

### 1. Prerequisites

```bash
make install-deps  # Install all dependencies
make login-pulumi  # Login to Pulumi
```

### 2. Configuration

```bash
make create-config  # Create example configuration
```

Edit `configs/environments.yaml` with your AWS account details:

```yaml
environments:
  dev:
    root_profile: dev-root              # Root account profile
    service_profile: pulumi-deploy-user-dev  # Service user profile  
    region: us-east-1
    environment: development
```

### 3. AWS CLI Setup

Configure AWS CLI profiles for root accounts:

```bash
# Configure root account
aws configure --profile dev-root
```

### 4. Smart Deployment (All-in-One)

```bash
make deploy-dev   # Smart deploy (auto-detects setup + deploys)
```

**That's it!** The smart deployment will:
- ✅ Auto-detect if service user exists
- ✅ Auto-run setup if needed (uses root credentials)
- ✅ Deploy infrastructure (uses service credentials)

### Alternative: Step-by-Step (Manual Control)

```bash
make setup-env-dev     # Create service user (uses root credentials)
make validate-env-dev  # Test service user access
make preview-dev       # Preview changes
make deploy-dev        # Deploy infrastructure
```

## Command Reference

### Environment Setup Commands

| Command | Description |
|---------|-------------|
| `make setup-env-dev` | Setup development environment (Phase 1) |
| `make setup-env-staging` | Setup staging environment |
| `make setup-env-prod` | Setup production environment |
| `make validate-env-dev` | Test service user credentials |

### Smart Deployment Commands

| Command | Description |
|---------|-------------|
| `make deploy-dev` | **Smart deploy** to development (auto-setup + deploy) |
| `make deploy-staging` | **Smart deploy** to staging (auto-setup + deploy) |
| `make deploy-prod` | **Smart deploy** to production (auto-setup + deploy) |
| `make preview-dev` | Preview development changes |
| `make deploy-dev-dry` | Dry-run deployment (safe testing) |

### Workflow Commands

| Command | Description |
|---------|-------------|
| `make complete-workflow-dev` | **Smart workflow** (one command does everything) |
| `make manual-workflow-dev` | Manual workflow (explicit steps) |

### Cleanup Commands

| Command | Description |
|---------|-------------|
| `make clean-dev` | Destroy dev infrastructure (keeps service user) |
| `make clean-dev-complete` | Complete cleanup (infrastructure + service user) |
| `make preview-clean-dev` | Preview cleanup (dry-run) |

### Utility Commands

| Command | Description |
|---------|-------------|
| `make show-outputs` | Show deployment outputs |
| `make info` | Show project information |
| `make edit-config` | Edit environments configuration |
| `make validate-config` | Validate configuration |

## Configuration File

The unified configuration file `configs/environments.yaml` defines all environments:

```yaml
environments:
  dev:
    # AWS profiles
    root_profile: dev-root                    # Root account (setup only)
    service_profile: pulumi-deploy-user-dev   # Service user (operations)
    region: us-east-1
    environment: development
    
    # Service user configuration
    service_user:
      name: pulumi-deploy-user-dev
      policy_name: HIPAAInfrastructurePolicy-dev
      
    # Resource tags
    tags:
      Environment: development
      CostCenter: Development
      Owner: DevTeam
```

## Security Features

### Service User Policy

The service user has permissions for:
- ✅ EC2 (VPC, security groups, load balancers)
- ✅ ECS (container orchestration)  
- ✅ RDS (database services)
- ✅ S3 (storage and backups)
- ✅ KMS (encryption key management)
- ✅ CloudWatch (logging and monitoring)
- ✅ Limited IAM operations (roles, policies)

### What Service Users CANNOT Do

- ❌ Create/delete IAM users
- ❌ Create/delete access keys
- ❌ Organization management
- ❌ Account-level changes
- ❌ Billing access

### Security Best Practices

1. **Rotate credentials regularly** - Use `make rotate-keys-info` for guidance
2. **Use MFA** on root accounts
3. **Monitor usage** with CloudTrail
4. **Test with dry-run** before production changes
5. **Store credentials securely** - credentials files are in `.gitignore`

## Troubleshooting

### Smart Deployment Issues

**"Root credentials not available" during auto-setup:**
```bash
# Configure root account credentials
aws configure --profile dev-root

# Test root access
aws sts get-caller-identity --profile dev-root

# Then retry smart deployment
make deploy-dev
```

**"Auto-setup failed" message:**
```bash
# Run setup manually with verbose output
./scripts/setup-env.sh -e dev --verbose

# Check for specific error messages
# Common causes: permissions, network, policy file missing
```

**"Service user not working" after setup:**
```bash
# Validate service user credentials
make validate-env-dev

# Check AWS CLI profile
aws sts get-caller-identity --profile pulumi-deploy-user-dev

# If still broken, clean up and retry
make clean-dev-complete
make deploy-dev
```

### Traditional Issues

**"User already exists" during manual setup:**
```bash
# This is normal - setup continues with existing user
# Use --force to skip confirmations
./scripts/setup-env.sh -e dev --force
```

**"Stack not found" error:**
```bash
# List available stacks
make status

# Check Pulumi login
make login-pulumi
```

**Smart deployment not detecting setup correctly:**
```bash
# Check configuration
make validate-config

# Verify profiles exist
aws configure list-profiles | grep -E "(dev-root|pulumi-deploy-user-dev)"

# Run with dry-run to see what would happen
./scripts/deploy.sh -e dev --dry-run
```

### Script Options

All scripts support these common options:

- `--dry-run` - Preview changes without making them
- `--force` - Skip confirmation prompts  
- `--verbose` - Detailed output
- `--help` - Show help message

### Examples

```bash
# Preview setup without making changes
./scripts/setup-env.sh -e dev --dry-run

# Deploy with automatic approval
./scripts/deploy.sh -e dev -o deploy --force

# Cleanup with preview first
./scripts/cleanup.sh -e dev -m infrastructure --dry-run
./scripts/cleanup.sh -e dev -m infrastructure
```

## Migration from Old Scripts

If you were using the old complex scripts, here's the migration path:

### Old → New Mapping

| Old Script | New Script | Notes |
|------------|------------|-------|
| `setup-iam-separation.sh` | `setup-env.sh` | Simplified IAM setup |
| `deploy-with-separation.sh` | `deploy.sh` | Unified deployment |
| `deploy-infrastructure.sh` | `deploy.sh` | Single deployment script |
| `multi-account-deploy.sh` | `deploy.sh` | Per-environment deployment |
| `cleanup-accounts.sh` | `cleanup.sh` | Streamlined cleanup |
| `setup-accounts.sh` | `setup-env.sh` | Combined functionality |

### Configuration Migration

Old configuration files:
- `configs/accounts.yaml` → `configs/environments.yaml`
- Multiple config files → Single unified config

### What Was Removed

- ❌ CloudFormation bootstrap complexity
- ❌ Multiple credential management approaches  
- ❌ Complex IAM separation scripts
- ❌ Redundant deployment workflows
- ❌ Multiple configuration files

### What Was Simplified

- ✅ **70% reduction** in script complexity (1,400 → 400 lines)
- ✅ **Single deployment flow** instead of 4 different approaches
- ✅ **Consistent CLI interface** across all scripts
- ✅ **Shared utilities** for common operations
- ✅ **Clear security model** with two distinct phases

## Support

For issues or questions:

1. Check this documentation
2. Run `make help` for available commands
3. Use `--help` flag with any script
4. Check the `scripts/obsolete/` directory for old scripts (backup only)

The new simplified architecture maintains all security and compliance features while being much easier to understand and maintain.
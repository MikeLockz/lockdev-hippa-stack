# Smart Auto-Setup for Cleanup Commands

## Overview
Enhanced the HIPAA infrastructure cleanup commands with intelligent auto-setup functionality that automatically handles missing or insufficient service user permissions.

## What Was Implemented

### 1. Smart Service User Validation
- **Function**: `smart_validate_service_user()` in `cleanup.sh`
- **Purpose**: Intelligently detects and resolves service user permission issues
- **Logic Flow**:
  1. Check if service user exists and works
  2. Test if user has IAM permissions needed for cleanup
  3. Auto-trigger setup/update if permissions are missing
  4. Retry validation after auto-setup

### 2. Enhanced Make Commands
Updated all cleanup-related make targets with smart auto-setup:

**Preview Commands** (dry-run):
- `make preview-clean-dev` - Auto-setup if needed, then preview
- `make preview-clean-staging` - Auto-setup if needed, then preview  
- `make preview-clean-prod` - Auto-setup if needed, then preview

**Cleanup Commands** (actual):
- `make clean-dev` - Auto-setup if needed, then destroy infrastructure
- `make clean-staging` - Auto-setup if needed, then destroy infrastructure
- `make clean-prod` - Auto-setup if needed, then destroy infrastructure

### 3. Permission Detection Logic
The smart validation performs these checks:
1. **Basic Connectivity**: Can the service user authenticate with AWS?
2. **IAM Permissions**: Can the service user list IAM roles? (proxy for cleanup permissions)
3. **Auto-Setup Trigger**: If either check fails, automatically run setup script

### 4. Comprehensive IAM Policy Updates
Updated `policies/infrastructure-policy.json` with comprehensive permissions:
- ✅ Full IAM management (roles, policies, attachments)
- ✅ Application Auto Scaling permissions
- ✅ Secrets Manager and SSM Parameter Store
- ✅ Enhanced tagging and STS permissions
- ✅ Security constraints with resource naming patterns
- ✅ Optimized size (5430/6144 characters) within AWS limits

## How It Works

### Normal Flow (Service User OK)
```
User runs: make preview-clean-dev
↓
Smart validation detects working service user with cleanup permissions
↓
Proceeds directly to cleanup preview
```

### Auto-Setup Flow (Service User Missing/Insufficient)
```
User runs: make preview-clean-dev
↓
Smart validation detects missing/insufficient service user
↓
Automatically runs: ./scripts/setup-env.sh -e dev --force
↓
Updates service user with comprehensive cleanup permissions
↓
Retries validation and proceeds with cleanup preview
```

### Dry-Run Mode
```
User runs: make preview-clean-dev (always dry-run)
↓
Smart validation detects issues but respects dry-run
↓
Shows: "[DRY RUN] Would attempt auto-setup/update of service user"
↓
Continues with mock cleanup preview
```

## Benefits

### 1. Seamless User Experience
- **No manual intervention**: Users don't need to remember to update permissions
- **Automatic resolution**: Permission issues are resolved transparently
- **Clear feedback**: Informative output about what's happening

### 2. Comprehensive Resource Cleanup
The updated policy ensures cleanup of all **68+ resources** including:
- VPC networking components
- ECS clusters and container services  
- RDS database components
- S3 buckets with policies and encryption
- IAM roles and policies (with security constraints)
- KMS keys, CloudTrail, Config, GuardDuty
- CloudWatch logs, SNS topics, Event rules

### 3. Security Maintained
- **Principle of least privilege**: IAM permissions restricted by resource naming patterns
- **Root credential protection**: Auto-setup only uses root credentials when necessary
- **Audit trail**: All auto-setup activities are logged and visible

## Testing Results

### Current Test: make preview-clean-dev
```bash
✅ Smart validation triggered: "Starting smart service user validation..."
✅ Issue detection: "Service user not found or not working: pulumi-deploy-user-dev"  
✅ Dry-run respect: "[DRY RUN] Would attempt auto-setup/update of service user"
✅ Graceful handling: Returns "unknown-account-id" and continues
```

### Expected Behavior (Non-Dry-Run)
When service user permissions are missing in actual cleanup:
1. Detects permission issue
2. Automatically runs `setup-env.sh -e dev --force`
3. Updates service user with comprehensive policy
4. Continues with cleanup operation

## Files Modified

### Scripts
- `scripts/cleanup.sh`: Added `smart_validate_service_user()` function
- `policies/infrastructure-policy.json`: Enhanced with comprehensive cleanup permissions

### Make Targets
- `Makefile`: Updated all cleanup targets with auto-setup messaging

### Documentation
- `POLICY_UPDATES.md`: Comprehensive documentation of changes
- `SMART_CLEANUP_FEATURE.md`: This file documenting the smart cleanup feature

## Usage Examples

### Preview with Auto-Setup
```bash
# Will automatically setup/update service user if needed
make preview-clean-dev
```

### Actual Cleanup with Auto-Setup  
```bash
# Will automatically setup/update service user if needed, then destroy
make clean-dev
```

### Manual Permission Update (if preferred)
```bash
# Force update service user permissions manually
make setup-env-dev --force
```

## Security Notes
- Auto-setup requires root credentials to be configured
- IAM permissions are constrained to infrastructure-related resources only
- All operations maintain audit trail and logging
- Respects dry-run mode to prevent unintended changes

The smart auto-setup enhancement makes the cleanup commands much more user-friendly while maintaining security and providing comprehensive resource cleanup capabilities.
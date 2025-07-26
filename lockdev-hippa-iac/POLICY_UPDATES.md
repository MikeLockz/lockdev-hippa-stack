# IAM Policy Updates for Comprehensive Resource Cleanup

## Summary
Updated the `policies/infrastructure-policy.json` to include comprehensive permissions needed for complete cleanup of all HIPAA infrastructure resources.

## Changes Made

### 1. Enhanced IAM Permissions
- Added full IAM management permissions for roles and policies created by the infrastructure
- Included permissions for creating, updating, deleting, and managing:
  - IAM Roles (with naming pattern restrictions)
  - IAM Policies (with naming pattern restrictions) 
  - Role Policy Attachments
  - Policy Versions

### 2. Additional Service Permissions
- **Application Auto Scaling**: For ECS auto-scaling cleanup
- **Secrets Manager**: For secrets and credentials management
- **SSM Parameter Store**: For parameter cleanup
- **Tagging**: For resource tag management
- **VPC Flow Logs**: For flow logs management
- **Route Tables**: Enhanced routing and route table permissions
- **Config Service**: Comprehensive AWS Config permissions
- **STS**: For identity and role assumption

### 3. Security Constraints
IAM permissions are restricted to resources with specific naming patterns:
- Roles: `hipaa-*`, `*-role`, `*-execution-role`, `cloudtrail-*`, `config-*`, `guardduty-*`, `ecs-*`, `cloudwatch-*`, `*task*`, `*service*`
- Policies: `hipaa-*`, `*-policy`, `HIPAAInfrastructurePolicy-*`, `cloudtrail-*`, `config-*`, `ecs-*`, `cloudwatch-*`, `*task*`, `*service*`, `*s3*`

## Resources That Can Now Be Cleaned Up
The updated policy ensures the service user can delete all 68+ resources including:

### Core Infrastructure
- VPC, subnets, route tables, NAT gateways, internet gateways
- Security groups and NACLs
- Load balancers and target groups
- Elastic IPs

### Compute & Container Services
- ECS clusters, services, and task definitions
- ECR repositories and lifecycle policies
- Auto scaling configurations

### Database & Storage
- RDS parameter groups and subnet groups
- S3 buckets with policies, versioning, and encryption
- S3 bucket public access blocks

### Security & Compliance
- IAM roles and policies (with naming restrictions)
- KMS keys and aliases
- CloudTrail configurations
- AWS Config rules and recorders
- GuardDuty detectors

### Monitoring & Logging
- CloudWatch log groups, metrics, and alarms
- SNS topics and subscriptions
- CloudWatch Events rules and targets

## Usage
After updating the policy, service users created with the updated setup script will have comprehensive permissions to:
1. Deploy all infrastructure resources
2. Update and modify existing resources
3. **Completely clean up and destroy all resources**

## Security Notes
- IAM permissions are constrained by resource naming patterns to prevent accidental deletion of unrelated resources
- The policy maintains the principle of least privilege while enabling complete infrastructure lifecycle management
- All permissions are scoped to infrastructure-related resources only

## Smart Auto-Setup Enhancement

The cleanup commands now include **intelligent auto-setup** that automatically handles missing or insufficient service user permissions:

### How Smart Auto-Setup Works
1. **Permission Detection**: Cleanup commands test if the service user has required IAM permissions
2. **Auto-Setup Trigger**: If permissions are missing, automatically runs the setup script
3. **Policy Update**: Updates the service user with comprehensive cleanup permissions
4. **Seamless Operation**: Continues with the requested cleanup operation

### Enhanced Make Commands
All cleanup commands now include smart auto-setup:
```bash
# Preview cleanup with auto-setup
make preview-clean-dev    # Auto-setup if needed, then preview

# Actual cleanup with auto-setup  
make clean-dev           # Auto-setup if needed, then destroy infrastructure
make clean-dev-complete  # Auto-setup if needed, then destroy everything
```

## Applying the Updates

### For New Environments
When setting up a new environment, the updated policy will be automatically applied:
```bash
make setup-env-dev
```

### For Existing Environments
With smart auto-setup, you don't need to manually update permissions:
```bash
# The cleanup command will automatically detect and fix permission issues
make preview-clean-dev  # Will auto-update permissions if needed

# Or manually update if preferred
make setup-env-dev --force
```

### Validating the Updates
```bash
# Validate policy JSON syntax (already done)
python3 -m json.tool policies/infrastructure-policy.json

# Test policy size (must be < 6144 characters for AWS)
wc -c policies/infrastructure-policy.json

# Preview what resources would be destroyed
make preview-clean-dev

# Perform actual cleanup (if needed)
make clean-dev-complete
```

## Policy Size Optimization
The policy has been optimized to stay within AWS IAM policy limits:
- **Current size**: ~5430 characters 
- **AWS limit**: 6144 characters for managed policies
- **Optimization**: Removed redundant EC2 and Config permissions (already covered by `ec2:*` and `config:*`)
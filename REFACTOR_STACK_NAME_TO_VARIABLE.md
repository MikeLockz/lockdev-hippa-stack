# REFACTOR_STACK_NAME_TO_VARIABLE.md

## Overview
This document outlines a comprehensive plan to refactor all hardcoded "hipaa" references in the infrastructure codebase to use configurable variables. This will make the stack reusable for different projects while maintaining HIPAA compliance capabilities.

## Current State Analysis

### Hardcoded References Found (77+ files)
The "hipaa" name appears in multiple layers:

1. **Project Configuration**:
   - `Pulumi.yaml`: project name `lockdev-hippa-iac`
   - `pyproject.toml`: package name `lockdev-hippa-iac`
   - `configs/environments.yaml`: `stack_prefix: hipaa`

2. **Resource Names** (50+ occurrences):
   - VPC: `hipaa-vpc`
   - ECS Cluster: `hipaa-ecs-cluster`
   - Load Balancer: `hipaa-alb`
   - Log Groups: `/aws/ecs/hipaa-app`, `/aws/rds/instance/hipaa-postgres-db`
   - IAM Roles: `hipaa-ecs-task-role`, `hipaa-cloudtrail-role`

3. **Documentation & Comments**:
   - "HIPAA compliant infrastructure" descriptions
   - Diagram titles: "HIPAA Network Architecture"
   - Script defaults: `stack_name="hipaa-dev"`

## Refactoring Strategy

### Phase 1: Configuration Layer (High Priority)

#### 1.1 Update Pulumi Configuration System
**Files to modify:**
- `configs/environments.yaml`
- `Pulumi.yaml`
- `__main__.py`

**Changes:**
```yaml
# configs/environments.yaml
environments:
  dev:
    # BEFORE: stack_prefix: hipaa
    # AFTER: stack_prefix: ${project_name}
    project_name: hipaa  # Default value, can be overridden
    stack_prefix: ${project_name}
```

**New Pulumi Configuration:**
```python
# In __main__.py
import pulumi

# Read project name from Pulumi config
config = pulumi.Config()
project_name = config.get("project_name") or "hipaa"
stack_name = config.get("stack_name") or f"{project_name}-{pulumi.get_stack()}"

# Export for use in all modules
pulumi.export("project_name", project_name)
pulumi.export("stack_name", stack_name)
```

#### 1.2 Create Central Configuration Module
**New file:** `src/config/settings.py`
```python
import pulumi
from typing import Dict, Any

class ProjectConfig:
    def __init__(self):
        self.config = pulumi.Config()
        self.project_name = self.config.get("project_name") or "hipaa"
        self.environment = pulumi.get_stack().split('-')[-1]
        self.stack_prefix = f"{self.project_name}-{self.environment}"
        
    def resource_name(self, resource_type: str) -> str:
        """Generate standardized resource names"""
        return f"{self.project_name}-{resource_type}"
        
    def log_group_name(self, service: str) -> str:
        """Generate log group names"""
        return f"/aws/{service}/{self.project_name}-app"
        
    def get_tags(self) -> Dict[str, str]:
        """Generate standard resource tags"""
        return {
            "Project": f"{self.project_name.upper()}-Infrastructure",
            "Environment": self.environment,
            "ManagedBy": "Pulumi",
            "Compliance": "HIPAA" if self.project_name.lower() == "hipaa" else "Standard"
        }

# Global instance
project_config = ProjectConfig()
```

### Phase 2: Source Code Refactoring (High Priority)

#### 2.1 Network Layer (`src/networking/vpc.py`)
**BEFORE:**
```python
vpc = aws.ec2.Vpc(
    "hipaa-vpc",
    cidr_block="10.0.0.0/16",
    tags={"Name": "HIPAA-VPC", "Compliance": "HIPAA"}
)
```

**AFTER:**
```python
from src.config.settings import project_config

vpc = aws.ec2.Vpc(
    project_config.resource_name("vpc"),
    cidr_block="10.0.0.0/16",
    tags={**project_config.get_tags(), "Name": f"{project_config.project_name.upper()}-VPC"}
)
```

#### 2.2 Compute Layer (`src/compute/ecs.py`)
**BEFORE:**
```python
cluster = aws.ecs.Cluster(
    "hipaa-ecs-cluster",
    name="hipaa-ecs-cluster",
    tags={"Name": "HIPAA-ECS-Cluster", "Compliance": "HIPAA"}
)
```

**AFTER:**
```python
from src.config.settings import project_config

cluster = aws.ecs.Cluster(
    project_config.resource_name("ecs-cluster"),
    name=project_config.resource_name("ecs-cluster"),
    tags={**project_config.get_tags(), "Name": f"{project_config.project_name.upper()}-ECS-Cluster"}
)
```

#### 2.3 Monitoring Layer (`src/monitoring/cloudwatch.py`)
**BEFORE:**
```python
app_log_group = aws.cloudwatch.LogGroup(
    "hipaa-app-logs",
    name="/aws/ecs/hipaa-app",
    tags={"Name": "HIPAA-App-Logs", "Compliance": "HIPAA"}
)
```

**AFTER:**
```python
from src.config.settings import project_config

app_log_group = aws.cloudwatch.LogGroup(
    f"{project_config.project_name}-app-logs",
    name=project_config.log_group_name("ecs"),
    tags={**project_config.get_tags(), "Name": f"{project_config.project_name.upper()}-App-Logs"}
)
```

### Phase 3: Scripts and Utilities (Medium Priority)

#### 3.1 Diagram Generation Scripts
**Files to update:**
- `scripts/generate_network_diagram.py`
- `scripts/generate_security_diagram.py`
- `scripts/generate_compute_diagram.py`
- All other `generate_*_diagram.py` files

**Changes:**
```python
# BEFORE
def __init__(self, stack_name="hipaa-dev", output_dir="./output"):

# AFTER
def __init__(self, stack_name=None, output_dir="./output"):
    if stack_name is None:
        # Read from Pulumi config or environment
        config = pulumi.Config()
        project_name = config.get("project_name") or "hipaa"
        stack_name = f"{project_name}-dev"
```

#### 3.2 Cleanup Scripts
**Files to update:**
- `scripts/hipaa-cleanup.sh`
- `scripts/phases/*.sh`

**Changes:**
```bash
# BEFORE
STACK_PREFIX="hipaa"

# AFTER
STACK_PREFIX="${PROJECT_NAME:-hipaa}"
```

### Phase 4: Documentation and Comments (Low Priority)

#### 4.1 Dynamic Documentation Generation
**Files to update:**
- All diagram generation scripts
- README files
- Script help text

**Changes:**
```python
# Dynamic titles based on project name
title = f"{project_config.project_name.upper()} Network Architecture"
description = f"{project_config.project_name.upper()} compliant infrastructure"
```

## Implementation Plan

### Pre-Implementation Tasks
1. **Backup Current State**: Create git branch `feature/configurable-stack-name`
2. **Test Environment Setup**: Ensure dev environment is working
3. **Create Test Project**: Set up alternative project name for testing

### Implementation Phases

#### Phase 1: Core Configuration (Day 1)
**Time Estimate**: 4-6 hours

**Tasks:**
1. Create `src/config/settings.py` module
2. Update `__main__.py` to use configuration
3. Modify `configs/environments.yaml` structure
4. Update `Pulumi.yaml` to support variable project names

**Validation:**
```bash
# Test with default (hipaa) name
pulumi config set project_name hipaa
make deploy-preview

# Test with custom name
pulumi config set project_name myproject
make deploy-preview
```

#### Phase 2: Infrastructure Resources (Day 2-3)
**Time Estimate**: 8-10 hours

**Tasks:**
1. Refactor networking layer (`src/networking/`)
2. Refactor compute layer (`src/compute/`)
3. Refactor database layer (`src/database/`)
4. Refactor security layer (`src/security/`)
5. Refactor monitoring layer (`src/monitoring/`)

**Validation after each layer:**
```bash
# Verify resource names are correct
pulumi preview --diff
aws ec2 describe-vpcs --filters "Name=tag:Project,Values=MYPROJECT-Infrastructure"
```

#### Phase 3: Scripts and Utilities (Day 4)
**Time Estimate**: 4-6 hours

**Tasks:**
1. Update all diagram generation scripts
2. Update cleanup scripts
3. Update deployment scripts
4. Update test scripts

**Validation:**
```bash
# Test diagram generation
PROJECT_NAME=myproject python scripts/generate_network_diagram.py

# Test cleanup scripts
PROJECT_NAME=myproject ./scripts/hipaa-cleanup.sh --dry-run
```

#### Phase 4: Documentation (Day 5)
**Time Estimate**: 2-4 hours

**Tasks:**
1. Update README files
2. Update inline documentation
3. Update script help text
4. Create migration guide

## Testing Strategy

### Pre-Deployment Testing

#### 1. Configuration Validation
```bash
# Test 1: Default configuration (backward compatibility)
pulumi config set project_name hipaa
make deploy-preview
# Verify: All resources should have "hipaa" prefix

# Test 2: Custom project name
pulumi config set project_name testproject
make deploy-preview
# Verify: All resources should have "testproject" prefix

# Test 3: Empty/missing configuration
pulumi config rm project_name
make deploy-preview
# Verify: Should default to "hipaa"
```

#### 2. Resource Naming Validation
```bash
# Check VPC naming
aws ec2 describe-vpcs --query 'Vpcs[?Tags[?Key==`Name` && contains(Value, `TESTPROJECT`)]]'

# Check ECS cluster naming
aws ecs list-clusters --query 'clusterArns[?contains(@, `testproject`)]'

# Check log groups
aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `testproject`)]'
```

#### 3. Tagging Validation
```bash
# Verify all resources have correct project tags
aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=TESTPROJECT-Infrastructure"
```

### Deployment Testing

#### 1. Fresh Deployment Test
```bash
# Create new stack with custom name
pulumi stack init testproject-dev
pulumi config set project_name testproject
pulumi config set aws:region us-east-1

# Deploy infrastructure
make deploy

# Verify deployment
make test-app
curl http://$(pulumi stack output alb_dns_name)/health
```

#### 2. Migration Test (Existing Stack)
```bash
# Test migration of existing hipaa stack
pulumi stack select hipaa-dev
pulumi config set project_name newhipaa

# Preview changes (should show resource renames)
pulumi preview --diff

# Plan migration strategy
# Note: This will require careful resource imports/renames
```

#### 3. Multi-Project Test
```bash
# Deploy two different projects simultaneously
pulumi stack init project1-dev
pulumi config set project_name project1
make deploy

pulumi stack init project2-dev  
pulumi config set project_name project2
make deploy

# Verify isolation - no resource conflicts
aws ec2 describe-vpcs --query 'Vpcs[?Tags[?Key==`Project`]]'
```

### Functional Testing

#### 1. Application Testing
```bash
# For each deployed stack
make test-app
make test-app-security

# Verify health endpoints work
curl http://$(pulumi stack output alb_dns_name)/health/
curl http://$(pulumi stack output alb_dns_name)/health/ready
```

#### 2. Security Testing
```bash
# Verify IAM policies work with new names
aws sts assume-role --role-arn $(pulumi stack output ecs_task_role_arn) --role-session-name test

# Verify encryption keys work
aws kms describe-key --key-id $(pulumi stack output kms_key_id)
```

#### 3. Monitoring Testing
```bash
# Verify CloudWatch logs are created correctly
aws logs describe-log-groups --log-group-name-prefix "/aws/ecs/$(pulumi config get project_name)"

# Test metric collection
aws cloudwatch get-metric-statistics --namespace "AWS/ECS" --metric-name CPUUtilization
```

### Performance Testing

#### 1. Deployment Time
```bash
# Measure deployment time for different project names
time make deploy
```

#### 2. Resource Limits
```bash
# Test with very long project names
pulumi config set project_name "verylongprojectnamethatmightcauseissues"
make deploy-preview  # Should handle gracefully or error clearly
```

### Rollback Testing

#### 1. Configuration Rollback
```bash
# Test reverting to hardcoded names
git checkout main
make deploy-preview
# Should work identically to before refactoring
```

#### 2. Emergency Rollback
```bash
# Test emergency rollback procedure
pulumi stack select hipaa-dev
pulumi config rm project_name
make deploy
# Should revert to original naming
```

## Migration Guide for Existing Deployments

### Safe Migration Steps

#### 1. Pre-Migration Backup
```bash
# Export current stack state
pulumi stack export --file backup-$(date +%Y%m%d).json

# List all current resources
aws resourcegroupstaggingapi get-resources --output table > resources-before.txt
```

#### 2. Gradual Migration Strategy
```bash
# Option A: Blue-Green Deployment
# Deploy new stack with new name, then switch traffic

# Option B: In-Place Rename (Advanced)
# Use Pulumi aliases to rename resources in-place
```

#### 3. Validation Checklist
- [ ] All resources deployed successfully
- [ ] Application health checks pass
- [ ] Database connectivity works
- [ ] Load balancer serves traffic
- [ ] CloudWatch logs flowing
- [ ] IAM permissions working
- [ ] Backup/restore tested

## Configuration Examples

### Basic Usage
```yaml
# Pulumi.dev.yaml
config:
  project_name: mycompany
  aws:region: us-east-1
```

### Advanced Configuration
```yaml
# Pulumi.prod.yaml
config:
  project_name: mycompany
  environment_suffix: prod
  enable_high_availability: true
  compliance_mode: strict
```

### Environment Variables
```bash
export PULUMI_CONFIG_project_name=myproject
export PULUMI_CONFIG_environment_suffix=staging
```

## Breaking Changes and Compatibility

### Breaking Changes
1. **Resource Names**: All AWS resources will have new names
2. **Log Group Names**: CloudWatch log groups will change
3. **IAM Role Names**: All IAM roles will be renamed
4. **Domain Names**: Any hardcoded domain references will change

### Backward Compatibility
- Default `project_name` remains "hipaa" for existing deployments
- All functionality remains identical
- Existing configuration files continue to work

### Migration Path
1. **Immediate**: Deploy alongside existing stack with new name
2. **Planned**: Schedule maintenance window for in-place migration
3. **Gradual**: Use blue-green deployment strategy

## Success Criteria

### Technical Success
- [ ] All 77+ hardcoded "hipaa" references are parameterized
- [ ] New deployments work with custom project names
- [ ] Existing deployments continue to work unchanged
- [ ] All tests pass with both default and custom names
- [ ] Documentation is updated and accurate

### User Experience Success
- [ ] Simple configuration: single `project_name` parameter
- [ ] Clear error messages for invalid configurations
- [ ] Easy migration path for existing deployments
- [ ] Comprehensive testing and validation tools

### Operational Success
- [ ] No downtime for existing deployments
- [ ] Monitoring and alerting work with new names
- [ ] Backup and disaster recovery procedures updated
- [ ] Security policies and compliance maintained

## Timeline and Resources

### Estimated Timeline: 5 days
- **Day 1**: Phase 1 - Core configuration
- **Day 2-3**: Phase 2 - Infrastructure refactoring
- **Day 4**: Phase 3 - Scripts and utilities
- **Day 5**: Phase 4 - Documentation and final testing

### Required Resources
- 1 Senior DevOps Engineer (full-time)
- Access to AWS dev/staging environments
- Pulumi access for testing
- Code review from infrastructure team

### Risk Mitigation
- Comprehensive testing strategy
- Git branching for safe development
- Rollback procedures documented
- Staged deployment approach

---

## Next Steps

1. **Review and Approve**: Team review of this refactoring plan
2. **Create Branch**: `git checkout -b feature/configurable-stack-name`
3. **Begin Phase 1**: Start with core configuration changes
4. **Continuous Testing**: Validate each phase before proceeding
5. **Documentation**: Update all documentation as changes are made

This refactoring will significantly improve the reusability and maintainability of the infrastructure codebase while maintaining full HIPAA compliance capabilities.
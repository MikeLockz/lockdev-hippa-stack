# HIPAA Infrastructure Cleanup Module Specifications

## Module Architecture Overview

The unified cleanup system is designed as a modular architecture with clear separation of concerns. Each module has specific responsibilities and interfaces that allow for independent development, testing, and maintenance.

```
hipaa-cleanup.sh (Main Entry Point)
├── lib/
│   ├── utils.sh              # Shared utilities and helpers
│   ├── aws-cleanup.sh        # AWS resource discovery and deletion
│   ├── pulumi-cleanup.sh     # Pulumi stack management
│   ├── verification.sh       # Resource verification and reporting
│   └── rollback.sh           # Rollback capabilities
├── config/
│   ├── environments.yaml     # Environment-specific configurations
│   ├── resource-maps.yaml    # AWS resource mapping and patterns
│   └── phases.yaml          # Phase definitions and dependencies
├── phases/
│   ├── phase1-prepare.sh     # Pre-cleanup preparation
│   ├── phase2-data.sh        # Data clearing (RDS, S3)
│   ├── phase3-resources.sh   # Resource deletion
│   ├── phase4-vpc.sh         # VPC cleanup
│   └── phase5-verify.sh      # Final verification
└── logs/
    └── cleanup-YYYY-MM-DD-HHMMSS.log  # Execution logs
```

## Core Module Specifications

### 1. Utils Module (`lib/utils.sh`)

#### Purpose
Provides shared utilities and helper functions used across all modules.

#### Core Functions

**Logging System**
```bash
log(level, message, [context])
warn(message, [context])
error(message, [context])
info(message, [context])
debug(message, [context])
phase(message)
```

**AWS Configuration**
```bash
configure_aws([environment])
validate_aws_credentials()
get_aws_account_id()
get_aws_region()
```

**Resource Discovery**
```bash
discover_resources(resource_type, [filters])
resource_exists(resource_type, identifier)
get_resource_count(resource_type, [filters])
```

**Utility Functions**
```bash
confirm_action(message, [force_mode])
wait_for_deletion(resource_type, identifier, [max_attempts])
create_backup_dir([base_path])
format_aws_output(command, [format])
```

**Error Handling**
```bash
handle_error(exit_code, command, line_number)
validate_prerequisites()
```

#### Configuration
- **Logging Levels**: ERROR, WARN, INFO, DEBUG
- **Output Formats**: table, json, text
- **Backup Directory**: `./backups/`
- **Max Wait Time**: 30 minutes

### 2. AWS Cleanup Module (`lib/aws-cleanup.sh`)

#### Purpose
Handles AWS resource discovery, dependency resolution, and deletion operations.

#### Supported Resource Types

**Compute**
- ECS Clusters
- ECS Services
- ECS Task Definitions
- Lambda Functions
- EC2 Instances

**Storage**
- S3 Buckets (including versioning)
- ECR Repositories
- EBS Volumes
- EBS Snapshots

**Database**
- RDS Instances
- RDS Clusters
- RDS Subnet Groups
- DynamoDB Tables

**Networking**
- Load Balancers (ALB, NLB, CLB)
- Target Groups
- Security Groups
- VPC Endpoints
- NAT Gateways
- Internet Gateways
- Route Tables
- Subnets
- VPCs

**Security**
- KMS Keys
- Secrets Manager Secrets
- IAM Roles
- IAM Policies

**Monitoring**
- CloudWatch Log Groups
- CloudWatch Alarms
- CloudWatch Dashboards

#### Core Functions

**Resource Discovery**
```bash
discover_compute_resources([filters])
discover_storage_resources([filters])
discover_database_resources([filters])
discover_networking_resources([filters])
discover_security_resources([filters])
```

**Resource Deletion**
```bash
delete_resource(resource_type, identifier, [options])
delete_with_dependencies(resource_type, identifier)
delete_resource_batch(resource_type, identifiers)
```

**Dependency Resolution**
```bash
resolve_dependencies(resource_type, identifier)
get_dependent_resources(resource_type, identifier)
check_dependencies(resource_type, identifier)
```

**Safety Features**
```bash
protect_resource(resource_type, identifier)
unprotect_resource(resource_type, identifier)
is_protected(resource_type, identifier)
```

#### Configuration
- **Batch Size**: 25 resources (AWS API limit)
- **Retry Count**: 3 attempts
- **Wait Interval**: 30 seconds
- **Force Mode**: Optional

### 3. Pulumi Cleanup Module (`lib/pulumi-cleanup.sh`)

#### Purpose
Manages Pulumi stack operations including protection handling and state management.

#### Core Functions

**Stack Management**
```bash
list_stacks([pattern])
select_stack(stack_name)
get_stack_outputs(stack_name)
get_stack_resources(stack_name)
```

**Protection Handling**
```bash
unprotect_all_resources(stack_name)
get_protected_resources(stack_name)
unprotect_resource(stack_name, urn)
```

**Stack Operations**
```bash
destroy_stack(stack_name, [force])
remove_stack(stack_name)
refresh_stack(stack_name)
preview_destruction(stack_name)
```

**State Management**
```bash
export_stack_state(stack_name, [output_file])
import_stack_state(stack_name, state_file)
create_stack_backup(stack_name)
```

#### Configuration
- **Stack Pattern**: `hipaa-{environment}`
- **State Directory**: `./pulumi-states/`
- **Backup Retention**: 7 days
- **Refresh Timeout**: 10 minutes

### 4. Verification Module (`lib/verification.sh`)

#### Purpose
Provides comprehensive verification and reporting capabilities.

#### Verification Types

**Resource Verification**
```bash
verify_resource_absence(resource_type, [filters])
verify_resource_count(resource_type, expected_count, [filters])
verify_cleanup_completion([environment])
```

**State Verification**
```bash
create_cleanup_snapshot([environment])
compare_with_snapshot(snapshot_file)
generate_cleanup_report([environment])
```

**Compliance Checks**
```bash
check_hipaa_compliance([environment])
validate_resource_cleanup([environment])
```

#### Core Functions

**Reporting**
```bash
generate_verification_report([environment])
export_verification_report(format, [output_file])
display_verification_summary()
```

**Snapshot Management**
```bash
create_resource_snapshot([environment])
restore_from_snapshot(snapshot_file)
list_snapshots()
```

#### Configuration
- **Report Formats**: json, html, markdown, csv
- **Snapshot Retention**: 30 days
- **Verification Timeout**: 15 minutes
- **Report Directory**: `./reports/`

### 5. Rollback Module (`lib/rollback.sh`)

#### Purpose
Provides rollback capabilities to restore previous states.

#### Core Functions

**Rollback Operations**
```bash
rollback_to_phase(phase_name, [timestamp])
rollback_to_snapshot(snapshot_file)
rollback_resource(resource_type, identifier, backup_data)
```

**State Management**
```bash
create_rollback_point(phase_name)
list_rollback_points()
validate_rollback_point(rollback_point)
```

**Recovery Operations**
```bash
recover_from_failure([phase_name])
partial_rollback(resources, [timestamp])
```

#### Configuration
- **Rollback Retention**: 7 days
- **Backup Directory**: `./rollback-backups/`
- **Max Rollback Points**: 50
- **Rollback Timeout**: 30 minutes

## Phase Specifications

### Phase 1: Prepare (`phases/phase1-prepare.sh`)

#### Purpose
Prepare the environment and gather information before cleanup operations.

#### Operations
1. **Environment Validation**
   - Verify AWS credentials
   - Check Pulumi installation
   - Validate environment configuration
   - Confirm prerequisites

2. **Resource Discovery**
   - Discover all AWS resources
   - Create resource inventory
   - Identify protected resources
   - Map dependencies

3. **State Snapshot**
   - Create pre-cleanup snapshot
   - Backup current state
   - Generate initial report

4. **Configuration Loading**
   - Load environment configuration
   - Apply resource filters
   - Set cleanup parameters

#### Input/Output
- **Input**: Environment name, configuration files
- **Output**: Resource inventory, snapshot file, preparation report

#### Dependencies
- Utils module
- AWS cleanup module (for discovery)
- Verification module (for snapshot)

### Phase 2: Data Clearing (`phases/phase2-data.sh`)

#### Purpose
Clear sensitive data from databases and storage before resource deletion.

#### Operations
1. **RDS Data Clearing**
   - Connect to RDS instances
   - Clear database data
   - Handle different database engines (PostgreSQL, MySQL)
   - Verify data clearing

2. **S3 Data Clearing**
   - Empty S3 buckets
   - Handle versioning
   - Clear CloudTrail logs
   - Delete objects and versions

3. **Secrets Clearing**
   - Remove Secrets Manager secrets
   - Clear parameter store values
   - Handle KMS key rotation

#### Input/Output
- **Input**: Resource inventory from Phase 1
- **Output**: Data clearing report, updated resource inventory

#### Dependencies
- Utils module
- AWS cleanup module
- Verification module

### Phase 3: Resource Deletion (`phases/phase3-resources.sh`)

#### Purpose
Delete compute, storage, and security resources.

#### Operations
1. **Compute Cleanup**
   - Delete ECS clusters and services
   - Remove Lambda functions
   - Terminate EC2 instances
   - Deregister ECS task definitions

2. **Storage Cleanup**
   - Delete ECR repositories
   - Remove S3 buckets
   - Delete EBS volumes and snapshots

3. **Security Cleanup**
   - Delete KMS keys
   - Remove Secrets Manager secrets
   - Clean up IAM roles and policies

4. **Database Cleanup**
   - Delete RDS instances
   - Remove RDS clusters
   - Delete subnet groups

#### Input/Output
- **Input**: Resource inventory from Phase 2
- **Output**: Resource deletion report, dependency map

#### Dependencies
- Utils module
- AWS cleanup module
- Pulumi cleanup module

### Phase 4: VPC Cleanup (`phases/phase4-vpc.sh`)

#### Purpose
Clean up networking resources and VPC infrastructure.

#### Operations
1. **Load Balancer Cleanup**
   - Disable deletion protection
   - Delete ALB, NLB, CLB
   - Remove target groups

2. **Network Interface Cleanup**
   - Detach ENIs
   - Delete network interfaces
   - Handle security group dependencies

3. **VPC Resource Cleanup**
   - Delete NAT gateways
   - Remove internet gateways
   - Delete VPC endpoints
   - Clean up route tables
   - Delete subnets

4. **VPC Deletion**
   - Delete VPCs
   - Clean up VPC peering
   - Remove DHCP options

#### Input/Output
- **Input**: Remaining resources from Phase 3
- **Output**: VPC cleanup report, final resource list

#### Dependencies
- Utils module
- AWS cleanup module
- Verification module

### Phase 5: Verification (`phases/phase5-verify.sh`)

#### Purpose
Verify complete cleanup and generate final reports.

#### Operations
1. **Resource Verification**
   - Check for remaining resources
   - Verify resource absence
   - Validate cleanup completion

2. **State Verification**
   - Compare with initial snapshot
   - Generate verification report
   - Create final state snapshot

3. **Report Generation**
   - Generate cleanup summary
   - Create verification report
   - Export reports in multiple formats

4. **Cleanup Confirmation**
   - Display cleanup summary
   - Confirm completion
   - Provide next steps

#### Input/Output
- **Input**: Final resource state
- **Output**: Verification report, cleanup summary, final snapshot

#### Dependencies
- Utils module
- Verification module

## Configuration Specifications

### Environments Configuration (`config/environments.yaml`)

```yaml
environments:
  dev:
    aws_profile: dev-root
    region: us-east-1
    force_mode: true
    skip_verification: false
    stack_prefix: hipaa
    
  staging:
    aws_profile: staging-root
    region: us-east-1
    force_mode: false
    skip_verification: false
    stack_prefix: hipaa
    
  prod:
    aws_profile: prod-root
    region: us-east-1
    force_mode: false
    skip_verification: false
    stack_prefix: hipaa
```

### Resource Maps Configuration (`config/resource-maps.yaml`)

```yaml
resources:
  naming_patterns:
    s3:
      - "hipaa-*"
      - "*cloudtrail*"
      - "*dev*"
    rds:
      - "hipaa-*"
    load_balancers:
      - "hipaa-*"
      - "*dev*"
      - "*staging*"
      - "*prod*"
    security_groups:
      - "hipaa-*"
    vpc:
      - "*hipaa*"
  
  cleanup_options:
    s3:
      empty_versions: true
      lifecycle_policy: true
      force_deletion: false
    
    rds:
      clear_data: true
      skip_snapshot: true
      disable_protection: true
    
    load_balancers:
      disable_protection: true
    
    security_groups:
      handle_enis: true
      force_deletion: false
    
    vpc:
      cascade_delete: true
      dependency_check: true
```

### Phases Configuration (`config/phases.yaml`)

```yaml
phases:
  prepare:
    name: "Preparation Phase"
    description: "Prepare environment and discover resources"
    timeout: 300
    rollback_enabled: true
    
  data:
    name: "Data Clearing Phase"
    description: "Clear sensitive data from databases and storage"
    timeout: 1800
    rollback_enabled: true
    
  resources:
    name: "Resource Deletion Phase"
    description: "Delete compute, storage, and security resources"
    timeout: 3600
    rollback_enabled: true
    
  vpc:
    name: "VPC Cleanup Phase"
    description: "Clean up networking resources and VPC infrastructure"
    timeout: 1800
    rollback_enabled: true
    
  verify:
    name: "Verification Phase"
    description: "Verify complete cleanup and generate reports"
    timeout: 600
    rollback_enabled: false

phase_dependencies:
  data: [prepare]
  resources: [data]
  vpc: [resources]
  verify: [vpc]
```

## CLI Interface Specification

### Main Entry Point
```bash
./hipaa-cleanup.sh [environment] [options]
```

### Options
```bash
--phase=[prepare|data|resources|vpc|verify|all]
--environment=[dev|staging|prod]
--force                    # Skip confirmations
--dry-run                  # Show what would be done
--verify                   # Run verification after
--skip-phase=[phase-name]  # Skip specific phases
--rollback=[timestamp]     # Rollback to previous state
--config=[file]           # Custom configuration file
--output-dir=[dir]        # Output directory for reports
--verbose                 # Enable verbose logging
--quiet                   # Suppress non-error output
--help                    # Show help message
```

### Examples
```bash
# Full cleanup
./hipaa-cleanup.sh dev --phase=all --verify

# Dry run
./hipaa-cleanup.sh staging --dry-run

# Specific phase
./hipaa-cleanup.sh prod --phase=data

# Force mode
./hipaa-cleanup.sh dev --force

# Rollback
./hipaa-cleanup.sh dev --rollback=20240101-120000

# Custom configuration
./hipaa-cleanup.sh dev --config=custom-config.yaml
```

## Error Handling Strategy

### Error Levels
- **FATAL**: Script termination required
- **ERROR**: Operation failed, continue with next resource
- **WARNING**: Potential issue, user notification
- **INFO**: Informational messages
- **DEBUG**: Detailed debugging information

### Retry Strategy
- **Max Attempts**: 3
- **Backoff Strategy**: Exponential backoff (30s, 60s, 120s)
- **Retry Conditions**: Transient AWS errors, rate limiting

### Rollback Strategy
- **Automatic Rollback**: On critical failures
- **Manual Rollback**: User-initiated rollback
- **Partial Rollback**: Rollback specific phases
- **Full Rollback**: Complete environment restoration

## Testing Strategy

### Unit Testing
- **Module Testing**: Test individual modules
- **Function Testing**: Test specific functions
- **Mock AWS Services**: Use moto for AWS mocking

### Integration Testing
- **End-to-End Testing**: Test complete cleanup flow
- **Environment Testing**: Test in different environments
- **Dependency Testing**: Test resource dependencies

### Performance Testing
- **Load Testing**: Test with large resource counts
- **Timeout Testing**: Test timeout handling
- **Rollback Testing**: Test rollback performance

## Security Considerations

### Resource Protection
- **Protection Detection**: Automatically detect protected resources
- **Protection Handling**: Gracefully handle protected resources
- **User Confirmation**: Require explicit confirmation for protected resources

### Credential Security
- **Credential Validation**: Validate AWS credentials before operations
- **Profile Isolation**: Use environment-specific profiles
- **Least Privilege**: Use minimal required permissions

### Data Security
- **Data Clearing**: Ensure sensitive data is cleared before deletion
- **Encryption**: Handle encrypted resources properly
- **Audit Trail**: Maintain complete audit trail

## Performance Optimization

### Batch Operations
- **AWS API Batching**: Use batch operations where possible
- **Resource Grouping**: Group similar resources for batch processing
- **Parallel Processing**: Parallelize independent operations

### Caching
- **Resource Discovery**: Cache discovery results
- **State Caching**: Cache state information
- **Configuration Caching**: Cache configuration values

### Resource Limits
- **API Rate Limiting**: Respect AWS API rate limits
- **Concurrent Operations**: Limit concurrent operations
- **Memory Management**: Efficient memory usage
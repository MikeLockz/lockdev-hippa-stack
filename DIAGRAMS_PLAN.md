# Infrastructure Visualization Requirements

## Overview
This document outlines the requirements for a Python script that creates comprehensive infrastructure diagrams from Pulumi stack graphs, specifically designed for HIPAA-compliant AWS infrastructure.

## Core Requirements

### 1. Input Processing
- **Source**: Automatically generated via `pulumi graph` command
- **Generation**: Script executes `pulumi graph --stack hipaa-dev > Pulumi.dot` automatically
- **Format**: DOT format with AWS resource URNs
- **Validation**: Ensure valid DOT syntax and AWS resource types
- **Parsing**: Extract resource relationships and dependencies
- **Error Handling**: Graceful handling of missing Pulumi stack or authentication issues
- **Environment Detection**: Automatically detect Pulumi project and stack configuration

### 2. Diagram Generation Framework
- **Library**: Python-based using `diagrams` library or AWS-native diagramming
- **AWS Elements**: Use official AWS icons and styling (2025 standards)
- **Color Coding**: Consistent color scheme across all diagrams
- **Layout**: Hierarchical, left-to-right flow for readability

### 3. Multi-Perspective Diagrams

#### 3.1 Network Architecture Focus
**Purpose**: Visualize VPC, subnets, routing, and connectivity

**Components to Include**:
- VPC boundaries and CIDR blocks
- Public/private subnet layout across AZs
- NAT gateways and Internet Gateway
- Route tables and routing logic
- Security group boundaries
- Load balancer placement
- VPC endpoints (if applicable)

**AWS Elements**:
- VPC icon with CIDR notation
- Subnet icons with AZ labels
- NAT Gateway icons
- Internet Gateway icon
- Route table connections
- Security group boundaries

#### 3.2 Compute and Messaging Architecture
**Purpose**: Show ECS, container orchestration, and service communication

**Components to Include**:
- ECS cluster and service definitions
- Fargate task definitions
- Container images and ECR repositories
- Load balancer target groups
- Service-to-service communication patterns
- Auto-scaling configurations

**AWS Elements**:
- ECS cluster icon
- Fargate service icons
- ECR repository icons
- Application Load Balancer
- Target groups
- Auto-scaling groups

#### 3.3 Data Flow Architecture
**Purpose**: Illustrate data lifecycle, storage, and movement

**Components to Include**:
- RDS PostgreSQL primary instance
- Database encryption (KMS integration)
- Backup strategies and frequency
- Read replica architecture (if applicable)
- Data flow between services
- S3 buckets for logs and artifacts
- Encryption at rest and in transit

**Data Flow Elements**:
- RDS instance icon with encryption badge
- S3 buckets with versioning indicators
- Backup arrows with retention periods
- Data replication arrows
- KMS key icons
- Encryption boundary indicators

#### 3.4 Security and Access Controls
**Purpose**: Comprehensive security architecture visualization

**Components to Include**:
- IAM roles and policies hierarchy
- Service-to-service IAM permissions
- Secrets management (AWS Secrets Manager/Parameter Store)
- Security group rules visualization
- Certificate management (ACM)
- Network ACLs and firewall rules
- MFA requirements and enforcement

**Security Elements**:
- IAM role icons with trust relationships
- Policy attachment visualizations
- Security group rules (ingress/egress)
- Certificate icons
- Secrets management icons
- Network boundary indicators

#### 3.5 CI/CD Pipeline Architecture
**Purpose**: Show complete build, test, and deployment flow

**Components to Include**:
- GitHub Actions workflows
- Build stages (dev → staging → prod)
- Artifact storage and promotion
- Approval gates and manual interventions
- Rollback mechanisms
- Environment-specific configurations
- Security scanning integration

**CI/CD Elements**:
- Code pipeline icons
- Build stage indicators
- Artifact repositories
- Approval gate icons
- Rollback arrow indicators
- Environment boundaries

#### 3.6 Observability Architecture
**Purpose**: Monitoring, logging, and alerting infrastructure

**Components to Include**:
- CloudWatch log groups and streams
- CloudWatch metrics and alarms
- CloudTrail logging configuration
- X-Ray tracing integration
- GuardDuty threat detection
- Config compliance monitoring
- Alert routing and notification

**Observability Elements**:
- CloudWatch icons
- Log group visualizations
- Metric stream indicators
- Alarm bell icons
- CloudTrail trail icons
- GuardDuty detector icons
- Notification topic icons

#### 3.7 Disaster Recovery Architecture
**Purpose**: Multi-AZ deployment and recovery strategies

**Components to Include**:
- Multi-AZ RDS deployment
- ECS service distribution across AZs
- Load balancer health checks
- Backup and restore procedures
- Failover mechanisms
- RTO/RPO indicators
- Cross-region backup (if configured)

**DR Elements**:
- Multi-AZ indicators
- Health check icons
- Backup/restore arrows
- Failover flow indicators
- RTO/RPO time indicators
- Cross-region replication arrows

### 4. Technical Implementation Requirements

#### 4.1 Script Structure
```
/lockdev-hippa-iac/scripts/
├── generate_diagrams.py          # Main script
├── aws_elements.py              # AWS icon mappings
├── diagram_configs.py           # Configuration templates
├── output/
│   ├── network_architecture.png
│   ├── compute_architecture.png
│   ├── data_flow.png
│   ├── security_controls.png
│   ├── cicd_pipeline.png
│   ├── observability.png
│   └── disaster_recovery.png
└── README.md
```

#### 4.2 Configuration Options
- **Output formats**: PNG, SVG, PDF
- **Color themes**: HIPAA-compliant color scheme
- **Detail levels**: High-level overview vs detailed view
- **Resource filtering**: Include/exclude specific resource types
- **Layout customization**: Horizontal vs vertical orientation

#### 4.3 AWS Resource Mapping
```python
AWS_RESOURCE_MAPPING = {
    "aws:ec2/vpc": "AWS_NetworkingContentDelivery_VPC",
    "aws:ec2/subnet": "AWS_NetworkingContentDelivery_Subnet",
    "aws:ecs/cluster": "AWS_Compute_ECS",
    "aws:rds/instance": "AWS_Database_RDS",
    "aws:s3/bucket": "AWS_Storage_S3",
    "aws:iam/role": "AWS_SecurityIdentityCompliance_IAM",
    "aws:cloudwatch/logGroup": "AWS_ManagementGovernance_CloudWatch",
    "aws:cloudtrail/trail": "AWS_ManagementGovernance_CloudTrail"
}
```

### 5. HIPAA Compliance Visual Indicators
- **Encryption badges** on all encrypted resources
- **Access control boundaries** highlighted
- **Audit trail arrows** for all data access
- **Compliance zone indicators**
- **PHI data flow tracking**
- **Security monitoring coverage areas**

### 6. Best Practices Integration
- **AWS Well-Architected Framework** alignment
- **HIPAA compliance markers** throughout diagrams
- **Least privilege access** visualizations
- **Defense in depth** layering
- **Monitoring coverage completeness**

### 7. Automation and CI/CD Integration
- **GitHub Actions workflow** for automated generation
- **Trigger on infrastructure changes**
- **Version control** for diagram updates
- **Automated documentation** updates
- **Pull request integration**

### 8. Usage Examples

#### Basic Usage
```bash
python generate_diagrams.py --input Pulumi.dot --output-dir ./diagrams/
```

#### Advanced Usage
```bash
python generate_diagrams.py \
  --input Pulumi.dot \
  --output-dir ./diagrams/ \
  --format png,svg \
  --theme hipaa-compliant \
  --include-security-details \
  --verbose
```

### 9. Validation and Testing
- **Schema validation** for DOT file parsing
- **Resource relationship validation**
- **HIPAA compliance checks** for each diagram
- **Cross-reference validation** between diagrams
- **Accessibility compliance** (alt text, color contrast)

### 10. Documentation and Maintenance
- **Comprehensive README** with usage examples
- **Architecture decision records** for design choices
- **Version compatibility** documentation
- **Troubleshooting guide**
- **Extension points** for custom AWS services
# HIPAA-Compliant Infrastructure Stack

## Project Overview
This project creates HIPAA, HITRUST, and SOC2 compliant infrastructure for a health tech company using Infrastructure as Code (IaC) with Pulumi and Python. The architecture supports multi-cloud deployments (AWS primary, GCP secondary) and includes a containerized hello world application.

## Repository Structure
This directory contains two separate repositories:
- `lockdev-hippa-iac/` - Pulumi Python infrastructure code
- `lockdev-hippa-app/` - Hello World Python web application

## Architecture Components

### Core Infrastructure
- **VPC & Networking**: Public/private subnets, NAT gateways, security groups
- **Compute**: ECS Fargate containers with auto-scaling
- **Database**: RDS PostgreSQL with encryption and automated backups
- **Load Balancing**: Application Load Balancer with SSL termination
- **API Gateway**: AWS API Gateway with authentication/authorization
- **Container Registry**: ECR for Docker images

### Security & Compliance
- **Encryption**: KMS key management, encryption at rest and in transit
- **Access Controls**: IAM roles with least privilege, MFA requirements
- **Audit Logging**: CloudTrail, VPC Flow Logs, application logs
- **Monitoring**: CloudWatch, X-Ray tracing, GuardDuty, Config
- **Network Security**: Private subnets, security groups, NACLs, WAF

### HIPAA/HITRUST Compliance Features
- Data encryption at rest and in transit
- Access logging and audit trails
- Network segmentation and isolation
- Automated backup and disaster recovery
- Vulnerability scanning and monitoring
- Data loss prevention (DLP) policies

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Poetry (Python package manager)
- Pulumi CLI
- AWS CLI
- Docker
- Security tools (pip-audit, Trivy)

**Quick Installation:**
```bash
# Install all prerequisites and dependencies
make install

# Verify installations
make verify
```

## Common Commands

All development tasks are managed through Make commands. **Always check the Makefile first for available commands:**

```bash
# Show all available commands
make help
```

### Essential Development Commands
```bash
# Quick start (install everything)
make quick-start

# Start application development environment
make dev-app

# Run comprehensive tests (CI-equivalent)
make test

# Format and lint code
make format
make lint

# Deploy infrastructure (preview first)
make deploy-preview
make deploy
```

## CI/CD Pipeline

### GitHub Actions Workflows
- **IaC Pipeline**: Validates, tests, and deploys infrastructure changes
- **Application Pipeline**: Builds, tests, scans, and deploys containerized application
- **Security Pipeline**: Runs compliance checks and vulnerability scans

### Key Pipeline Features
- Automated testing and linting
- Security scanning with tools like Checkov, Bandit
- Multi-environment deployment with approval gates
- Compliance validation and reporting
- Automated rollback on failures

## Project Structure

### IaC Repository (`lockdev-hippa-iac/`)
```
lockdev-hippa-iac/
├── .github/
│   └── workflows/
│       ├── infrastructure.yml
│       └── security-scan.yml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── networking/
│   ├── compute/
│   ├── database/
│   ├── security/
│   └── monitoring/
├── tests/
├── configs/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
├── pyproject.toml
├── Pulumi.yaml
└── README.md
```

### Application Repository (`lockdev-hippa-app/`)
```
lockdev-hippa-app/
├── .github/
│   └── workflows/
│       ├── application.yml
│       └── security-scan.yml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── routes/
│   ├── models/
│   └── utils/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Getting Started

### 🚀 Quick Start Guide

This HIPAA-compliant infrastructure stack is **production-ready** with 76 AWS resources and a complete FastAPI application.

#### 1. Installation and Setup
```bash
# Install all prerequisites and dependencies
make install

# Configure AWS credentials (if not already done)
aws configure

# Set Pulumi access token
export PULUMI_ACCESS_TOKEN=<your-pulumi-token>

# Verify installation
make verify
```

#### 2. Deploy Infrastructure (76 Resources)
```bash
# Preview infrastructure changes
make deploy-preview

# Deploy all resources (5-10 minutes)
make deploy
```

#### 3. Start Development Environment
```bash
# Start application with containers
make dev-app

# Run comprehensive tests
make test
```

#### 4. Access Your Application
```bash
# Local development
open http://localhost:8000

# Production (after deployment)
# ALB DNS will be shown in Pulumi outputs
```

### 📊 What's Deployed

#### Infrastructure Components (76 Resources)
- **Networking**: VPC, subnets, NAT gateway, routing tables
- **Security**: KMS encryption, IAM roles, CloudTrail, GuardDuty, Config
- **Compute**: ECS cluster, ALB, ECR repository, task definitions
- **Database**: RDS PostgreSQL with encryption
- **Monitoring**: CloudWatch logs, metrics, alarms

#### Application Features
- **FastAPI**: High-performance async web framework
- **HIPAA Compliance**: Security headers, audit logging, PHI protection
- **Authentication**: JWT-based with secure token handling
- **Health Checks**: Kubernetes/ECS-ready endpoints
- **Database**: SQLAlchemy ORM with audit trail
- **CI/CD**: GitHub Actions with security scanning

### 🔧 Development Workflow

#### Local Development (Containerized)
```bash
# Start complete local environment with containers
make dev-app

# This starts:
# - FastAPI application on http://localhost:8000
# - PostgreSQL database on localhost:5432
# - Redis cache on localhost:6379

# View application logs
make dev-logs

# Check status
make dev-status

# Stop all services
make dev-stop
```

#### Alternative: Local Python Development
```bash
# For development without containers (requires local PostgreSQL)
make dev-app-local
```

#### Testing
```bash
# Run comprehensive tests (CI-equivalent)
make test

# Run basic tests only
make test-quick

# Run security scans only
make test-app-security
```

#### Code Quality
```bash
# Format code
make format

# Lint code
make lint
```

#### Health Endpoints
- `GET /health/` - Basic health check
- `GET /health/ready` - Readiness with DB check
- `GET /health/live` - Liveness probe
- `GET /health/startup` - Startup probe
- `GET /metrics` - Prometheus metrics


## Support & Documentation

### Resources
- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [HITRUST CSF](https://hitrustalliance.net/csf/)

### Common Issues
- Check AWS credentials configuration
- Verify Pulumi stack configuration
- Review CloudWatch logs for application errors
- Validate security group rules and network connectivity

## Environment Variables

### Required Environment Variables
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_DEFAULT_REGION=us-east-1

# Pulumi Configuration
PULUMI_ACCESS_TOKEN=<your-pulumi-token>

# Application Configuration
DATABASE_URL=<database-connection-string>
JWT_SECRET=<jwt-secret-key>
```

## Development Process & Guidelines

### 🎯 Core Development Principles

**MANDATORY REQUIREMENTS for ALL development work:**

#### 1. Task Management & Progress Tracking
- **Use TodoWrite tool** for ALL multi-step tasks
- Create specific, actionable tasks with clear priorities
- Update task status in real-time (pending → in_progress → completed)
- Only mark tasks completed when fully verified and tested
- Keep task progress visible to users throughout the session

#### 2. Sub-Agent Utilization
- **Use Task tool with sub-agents** when possible to maximize efficiency
- Leverage specialized agents for:
  - Complex searches across codebases
  - Multi-step implementation tasks
  - Code analysis and refactoring
  - Documentation generation
- Run multiple sub-agents concurrently when tasks are independent
- Provide detailed, autonomous task descriptions to sub-agents

#### 3. Testing & Quality Assurance
- **ALL code MUST be tested** before marking tasks complete
- Run comprehensive test suite: `make test`
- Verify security scans pass: `make test-app-security`
- Check code quality: `make lint` and `make format`
- Test in containerized environment: `make dev-app`
- Document all new features and changes

#### 4. Documentation Requirements
- Update relevant documentation for ALL changes
- Document API endpoints, configuration options, and usage examples
- Include inline code comments for complex logic
- Update CLAUDE.md with new features or process changes
- Maintain up-to-date README files in both repositories

#### 5. Continuous Integration
- Ensure all CI/CD pipelines pass before completing tasks
- Address any security vulnerabilities identified by scans
- Verify deployment processes work correctly
- Test in multiple environments (dev, staging) when applicable

### 📋 Task Management Framework

#### Task Creation Guidelines
```bash
# Example of proper task breakdown
1. Analyze requirements and scope
2. Create TodoWrite list with specific, measurable tasks
3. Prioritize tasks (high/medium/low)
4. Begin with highest priority items
5. Update progress as work proceeds
```

#### Task Status Management
- **pending**: Task identified but not started
- **in_progress**: Currently working on task (limit to ONE at a time)
- **completed**: Task fully implemented, tested, and verified

#### Progress Reporting
- Provide regular status updates to users
- Show completed vs remaining tasks
- Highlight any blockers or issues encountered
- Estimate time for remaining work

### 🤖 Sub-Agent Best Practices

#### When to Use Sub-Agents
- Complex multi-file searches or analysis
- Large-scale code refactoring
- Research tasks requiring multiple information sources
- Implementation of new features across multiple components
- Documentation generation and updates

#### Sub-Agent Task Design
- Provide comprehensive, autonomous task descriptions
- Specify exact deliverables and success criteria
- Include relevant context and constraints
- Define expected output format and detail level

#### Example Sub-Agent Usage
```bash
# Good: Specific, autonomous task
Task(
  description="Implement user authentication",
  prompt="Implement complete JWT-based authentication system including login/logout endpoints, middleware, token validation, and comprehensive tests. Follow existing code patterns and security best practices.",
  subagent_type="general-purpose"
)

# Bad: Vague, dependent task
Task(
  description="Fix auth",
  prompt="Look at the auth code and fix issues",
  subagent_type="general-purpose"
)
```

### 🧪 Testing & Validation Standards

#### Pre-Commit Requirements
- All tests must pass: `make test`
- Code must be formatted: `make format`
- Linting must pass: `make lint`
- Security scans must pass: `make test-app-security`
- No critical vulnerabilities in dependencies

#### Test Coverage Requirements
- Unit tests for all new functions and classes
- Integration tests for API endpoints
- Security tests for authentication and authorization
- End-to-end tests for critical user flows
- Minimum 80% code coverage for new code

#### Documentation Standards
- Docstrings for all public functions and classes
- README updates for new features
- API documentation for new endpoints
- Configuration examples and usage guides
- Architecture decision records (ADRs) for significant changes

### 📊 Task Progress Tracking

#### Current Development Tasks
*Tasks will be tracked here using TodoWrite tool throughout development sessions*

**Example Task Structure:**
```bash
📋 Active Tasks:
- [ ] Task 1: Implementation details (Priority: High) - Status: In Progress
- [x] Task 2: Completed task (Priority: Medium) - Status: Completed
- [ ] Task 3: Pending task (Priority: Low) - Status: Pending

🎯 Next Steps:
1. Complete current in-progress task
2. Begin highest priority pending task
3. Update documentation and tests
```

#### Task Categories
- **Infrastructure**: Pulumi/AWS resource changes
- **Application**: FastAPI/Python application features
- **Security**: Security enhancements and compliance
- **Testing**: Test implementation and quality assurance
- **Documentation**: Documentation updates and improvements
- **CI/CD**: Pipeline and deployment improvements

### 🔄 Enhanced Development Workflow

#### Phase-Based Development Process
1. **Planning Phase**
   - Create comprehensive task list using TodoWrite
   - Identify sub-agent opportunities
   - Define success criteria and testing requirements
   - Estimate effort and dependencies

2. **Implementation Phase**
   - Work on one task at a time (mark as in_progress)
   - Use sub-agents for complex or parallel work
   - Follow coding standards and security practices
   - Update progress regularly

3. **Testing Phase**
   - Run comprehensive test suite: `make test`
   - Verify security compliance: `make test-app-security`
   - Test in containerized environment: `make dev-app`
   - Address any failures before proceeding

4. **Documentation Phase**
   - Update inline documentation and comments
   - Update README and API documentation
   - Update CLAUDE.md with new features
   - Create examples and usage guides

5. **Integration Phase**
   - Run full CI/CD pipeline
   - Test deployment processes
   - Verify multi-environment compatibility
   - Complete git workflow and commit changes

#### Quality Gates
- **Code Quality**: All linting and formatting checks pass
- **Testing**: Minimum 80% test coverage, all tests pass
- **Security**: No critical vulnerabilities, security scans pass
- **Documentation**: All new features documented
- **Integration**: CI/CD pipelines pass, deployment successful

### 🤝 Sub-Agent Coordination & Parallel Execution

#### Concurrent Task Management
- **Launch multiple sub-agents** simultaneously for independent tasks
- Use single message with multiple Task tool calls for optimal performance
- Coordinate related tasks to prevent conflicts
- Aggregate results from multiple sub-agents before proceeding

#### Sub-Agent Specialization Areas
```bash
# Infrastructure Analysis & Implementation
Task(description="Analyze AWS infrastructure", 
     prompt="Review current Pulumi infrastructure, identify optimization opportunities, and recommend security improvements",
     subagent_type="general-purpose")

# Application Development & Testing
Task(description="Implement API endpoints", 
     prompt="Create new FastAPI endpoints with full test coverage, security validation, and documentation",
     subagent_type="general-purpose")

# Documentation & Research
Task(description="Update project documentation", 
     prompt="Analyze codebase changes and update all relevant documentation including README, API docs, and examples",
     subagent_type="general-purpose")
```

#### Result Integration Process
1. **Collect Results**: Gather outputs from all sub-agents
2. **Validate Consistency**: Ensure changes don't conflict
3. **Test Integration**: Run comprehensive test suite
4. **Update Tasks**: Mark completed tasks and identify follow-ups
5. **Report Progress**: Provide user with consolidated status update

### 📈 Progress Reporting Standards

#### Session Progress Updates
- **Task Completion Rate**: Show completed vs total tasks
- **Current Focus**: Which task is currently in progress
- **Blockers**: Any issues preventing progress
- **Next Steps**: What will be worked on next
- **Time Estimates**: Estimated completion timeframes

#### Status Communication Format
```bash
📊 Session Progress Report
=======================
✅ Completed: 3/7 tasks (43%)
🔄 In Progress: 1 task - "Implement authentication middleware"
⏸️ Pending: 3 tasks
🚫 Blockers: None

🎯 Next Actions:
1. Complete current authentication task
2. Begin API endpoint implementation
3. Update documentation and tests

⏱️ Estimated Completion: 45 minutes
```

## Important Implementation Notes

### ⚠️ Critical Git Workflow Requirements

**MANDATORY**: After completing and validating each phase, **ALL changes MUST be committed to git**. This ensures:
- **Version Control**: All work is properly tracked and can be restored
- **Collaboration**: Team members can access the latest code
- **Rollback Capability**: Ability to revert to working states
- **Audit Trail**: Complete history of implementation progress
- **Deployment Readiness**: Code is ready for production deployment

#### Required Git Workflow for Each Phase:
1. **Complete Phase Tasks**: Implement all requirements and verify functionality
2. **Test Thoroughly**: Run all tests, linting, and security scans
3. **Validate Phase**: Ensure all phase objectives are met
4. **Commit Changes**: Use descriptive commit messages with phase information
5. **Verify Commit**: Check that all files are properly committed

#### Git Commit Best Practices:
```bash
# Stage all changes
git add .

# Commit with comprehensive message
git commit -m "Complete Phase X: [Phase Description]

## Summary
- [Key accomplishments]
- [Components implemented]
- [Tests passing]
- [Security measures added]

## Technical Details
- [Specific technical achievements]
- [Infrastructure resources deployed]
- [Application features implemented]

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Verify commit succeeded
git status
git log --oneline -1
```

### Version Control Best Practices
- **Commit Early, Commit Often**: Don't wait until the end of a phase
- **Atomic Commits**: Each commit should represent a complete, working feature
- **Descriptive Messages**: Include context about what was implemented and why
- **Test Before Commit**: Always verify tests pass before committing
- **Security Check**: Ensure no secrets or sensitive data are committed
- **Documentation**: Update documentation files with each major change
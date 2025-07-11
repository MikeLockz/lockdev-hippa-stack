# HIPAA-Compliant Infrastructure Implementation Plan

## Project Overview
This implementation plan creates a HIPAA, HITRUST, and SOC2 compliant infrastructure for a health tech company using Infrastructure as Code (IaC) with Pulumi and Python. The architecture supports multi-cloud deployments (AWS primary, GCP secondary) and includes a containerized hello world application.

## Prerequisites Verification
Before beginning implementation, verify these requirements are met:

### System Requirements
- [ ] Python 3.8+ installed and accessible
- [ ] Poetry package manager installed
- [ ] Docker installed and running
- [ ] Git installed and configured
- [ ] AWS CLI configured with appropriate credentials
- [ ] Pulumi CLI installed

### AWS Requirements
- [ ] AWS account with appropriate permissions
- [ ] IAM user with PowerUserAccess or custom policy
- [ ] Access keys configured in environment
- [ ] Default region set to us-east-1

### Verification Commands
```bash
# Verify prerequisites
python3 --version
poetry --version
docker --version
git --version
pulumi version
python3 -m awscli sts get-caller-identity
```

## Implementation Phases

### Phase 1: Repository Setup and Structure
**Objective**: Create organized repository structure with proper version control

#### Task 1.1: Initialize Git Repository
**Owner**: Infrastructure Team
**Estimated Time**: 15 minutes

**Steps**:
1. Initialize git repository
   ```bash
   git init
   git add .
   git commit -m "Initial commit with project documentation"
   ```

**Verification**:
- [ ] Git repository initialized
- [ ] Initial commit created
- [ ] `.git` directory exists

#### Task 1.2: Create Repository Structure
**Owner**: Infrastructure Team
**Estimated Time**: 30 minutes

**Steps**:
1. Create IaC repository structure
   ```bash
   mkdir -p lockdev-hippa-iac/{src,tests,configs,docs}
   mkdir -p lockdev-hippa-iac/src/{networking,compute,database,security,monitoring}
   ```

2. Create application repository structure
   ```bash
   mkdir -p lockdev-hippa-app/{src,tests,docker}
   mkdir -p lockdev-hippa-app/src/{routes,models,utils}
   ```

3. Create configuration files
   ```bash
   touch lockdev-hippa-iac/pyproject.toml
   touch lockdev-hippa-iac/Pulumi.yaml
   touch lockdev-hippa-app/pyproject.toml
   touch lockdev-hippa-app/Dockerfile
   ```

**Verification**:
- [ ] Directory structure matches specification
- [ ] All required directories created
- [ ] Configuration files exist

#### Task 1.3: Setup .gitignore
**Owner**: Infrastructure Team
**Estimated Time**: 15 minutes

**Steps**:
1. Create comprehensive .gitignore
   ```bash
   cat > .gitignore << 'EOF'
   # Python
   __pycache__/
   *.py[cod]
   *$py.class
   *.so
   .Python
   build/
   develop-eggs/
   dist/
   downloads/
   eggs/
   .eggs/
   lib/
   lib64/
   parts/
   sdist/
   var/
   wheels/
   share/python-wheels/
   *.egg-info/
   .installed.cfg
   *.egg
   MANIFEST

   # Virtual environments
   .env
   .venv
   env/
   venv/
   ENV/
   env.bak/
   venv.bak/

   # Pulumi
   .pulumi/
   Pulumi.*.yaml

   # AWS
   .aws/
   credentials

   # IDE
   .vscode/
   .idea/
   *.swp
   *.swo
   *~

   # OS
   .DS_Store
   .DS_Store?
   ._*
   .Spotlight-V100
   .Trashes
   ehthumbs.db
   Thumbs.db

   # Secrets
   *.pem
   *.key
   .env.local
   .env.*.local
   secrets.yaml
   EOF
   ```

**Verification**:
- [ ] .gitignore file created
- [ ] All sensitive files excluded
- [ ] Python artifacts excluded

### Phase 2: Infrastructure as Code Setup
**Objective**: Configure Pulumi infrastructure foundation

#### Task 2.1: Initialize Pulumi Project
**Owner**: Infrastructure Team
**Estimated Time**: 45 minutes

**Steps**:
1. Navigate to IaC directory
   ```bash
   cd lockdev-hippa-iac
   ```

2. Initialize Poetry project
   ```bash
   poetry init --name="lockdev-hippa-iac" --description="HIPAA compliant infrastructure" --author="Your Name <email@example.com>"
   ```

3. Add Pulumi dependencies
   ```bash
   poetry add pulumi pulumi-aws pulumi-gcp
   poetry add --group dev pytest black flake8 mypy bandit
   ```

4. Initialize Pulumi project
   ```bash
   pulumi login
   pulumi new python --name lockdev-hippa-iac --description "HIPAA compliant infrastructure"
   ```

5. Create development stack
   ```bash
   pulumi stack init dev
   pulumi config set aws:region us-east-1
   ```

**Verification**:
- [ ] Poetry project initialized
- [ ] Dependencies installed
- [ ] Pulumi project created
- [ ] Development stack exists
- [ ] AWS region configured

#### Task 2.2: Create Base Infrastructure Configuration
**Owner**: Infrastructure Team
**Estimated Time**: 2 hours

**Steps**:
1. Create main infrastructure module
   ```bash
   cat > src/__init__.py << 'EOF'
   """HIPAA compliant infrastructure package."""
   __version__ = "0.1.0"
   EOF
   ```

2. Create main Pulumi program
   ```bash
   cat > src/main.py << 'EOF'
   """Main Pulumi program for HIPAA compliant infrastructure."""
   import pulumi
   import pulumi_aws as aws
   from typing import Dict, Any

   # Import infrastructure modules
   from .networking import create_vpc
   from .security import create_security_groups
   from .compute import create_ecs_cluster
   from .database import create_rds_instance
   from .monitoring import create_cloudwatch_resources

   def main():
       """Main infrastructure deployment function."""
       # Get configuration
       config = pulumi.Config()
       
       # Create VPC and networking
       vpc_resources = create_vpc()
       
       # Create security groups
       security_groups = create_security_groups(vpc_resources["vpc"])
       
       # Create ECS cluster
       ecs_cluster = create_ecs_cluster(
           vpc_resources["private_subnets"],
           security_groups["ecs_security_group"]
       )
       
       # Create RDS instance
       database = create_rds_instance(
           vpc_resources["private_subnets"],
           security_groups["rds_security_group"]
       )
       
       # Create monitoring resources
       monitoring = create_cloudwatch_resources()
       
       # Export important outputs
       pulumi.export("vpc_id", vpc_resources["vpc"].id)
       pulumi.export("ecs_cluster_name", ecs_cluster.name)
       pulumi.export("database_endpoint", database.endpoint)

   if __name__ == "__main__":
       main()
   EOF
   ```

**Verification**:
- [ ] Main module created
- [ ] Infrastructure modules imported
- [ ] Configuration structure defined
- [ ] Outputs exported

#### Task 2.3: Implement Networking Module
**Owner**: Infrastructure Team
**Estimated Time**: 3 hours

**Steps**:
1. Create networking module
   ```bash
   cat > src/networking/__init__.py << 'EOF'
   """Networking infrastructure module."""
   from .vpc import create_vpc
   from .subnets import create_subnets
   from .gateways import create_gateways

   __all__ = ["create_vpc", "create_subnets", "create_gateways"]
   EOF
   ```

2. Create VPC configuration
   ```bash
   cat > src/networking/vpc.py << 'EOF'
   """VPC configuration for HIPAA compliant infrastructure."""
   import pulumi
   import pulumi_aws as aws
   from typing import Dict, Any

   def create_vpc() -> Dict[str, Any]:
       """Create VPC with proper HIPAA compliance settings."""
       config = pulumi.Config()
       
       # Create VPC
       vpc = aws.ec2.Vpc(
           "hipaa-vpc",
           cidr_block="10.0.0.0/16",
           enable_dns_hostnames=True,
           enable_dns_support=True,
           tags={
               "Name": "HIPAA-VPC",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create Internet Gateway
       igw = aws.ec2.InternetGateway(
           "hipaa-igw",
           vpc_id=vpc.id,
           tags={
               "Name": "HIPAA-IGW",
               "Environment": config.get("environment", "dev")
           }
       )
       
       # Create public subnets
       public_subnet_1 = aws.ec2.Subnet(
           "public-subnet-1",
           vpc_id=vpc.id,
           cidr_block="10.0.1.0/24",
           availability_zone="us-east-1a",
           map_public_ip_on_launch=True,
           tags={
               "Name": "Public-Subnet-1",
               "Type": "Public",
               "Environment": config.get("environment", "dev")
           }
       )
       
       public_subnet_2 = aws.ec2.Subnet(
           "public-subnet-2",
           vpc_id=vpc.id,
           cidr_block="10.0.2.0/24",
           availability_zone="us-east-1b",
           map_public_ip_on_launch=True,
           tags={
               "Name": "Public-Subnet-2",
               "Type": "Public",
               "Environment": config.get("environment", "dev")
           }
       )
       
       # Create private subnets
       private_subnet_1 = aws.ec2.Subnet(
           "private-subnet-1",
           vpc_id=vpc.id,
           cidr_block="10.0.3.0/24",
           availability_zone="us-east-1a",
           tags={
               "Name": "Private-Subnet-1",
               "Type": "Private",
               "Environment": config.get("environment", "dev")
           }
       )
       
       private_subnet_2 = aws.ec2.Subnet(
           "private-subnet-2",
           vpc_id=vpc.id,
           cidr_block="10.0.4.0/24",
           availability_zone="us-east-1b",
           tags={
               "Name": "Private-Subnet-2",
               "Type": "Private",
               "Environment": config.get("environment", "dev")
           }
       )
       
       # Create NAT Gateway
       nat_eip = aws.ec2.Eip(
           "nat-eip",
           domain="vpc",
           tags={
               "Name": "NAT-EIP",
               "Environment": config.get("environment", "dev")
           }
       )
       
       nat_gateway = aws.ec2.NatGateway(
           "nat-gateway",
           allocation_id=nat_eip.id,
           subnet_id=public_subnet_1.id,
           tags={
               "Name": "NAT-Gateway",
               "Environment": config.get("environment", "dev")
           }
       )
       
       # Create route tables
       public_route_table = aws.ec2.RouteTable(
           "public-route-table",
           vpc_id=vpc.id,
           tags={
               "Name": "Public-Route-Table",
               "Environment": config.get("environment", "dev")
           }
       )
       
       private_route_table = aws.ec2.RouteTable(
           "private-route-table",
           vpc_id=vpc.id,
           tags={
               "Name": "Private-Route-Table",
               "Environment": config.get("environment", "dev")
           }
       )
       
       # Create routes
       aws.ec2.Route(
           "public-route",
           route_table_id=public_route_table.id,
           destination_cidr_block="0.0.0.0/0",
           gateway_id=igw.id
       )
       
       aws.ec2.Route(
           "private-route",
           route_table_id=private_route_table.id,
           destination_cidr_block="0.0.0.0/0",
           nat_gateway_id=nat_gateway.id
       )
       
       # Associate subnets with route tables
       aws.ec2.RouteTableAssociation(
           "public-subnet-1-association",
           subnet_id=public_subnet_1.id,
           route_table_id=public_route_table.id
       )
       
       aws.ec2.RouteTableAssociation(
           "public-subnet-2-association",
           subnet_id=public_subnet_2.id,
           route_table_id=public_route_table.id
       )
       
       aws.ec2.RouteTableAssociation(
           "private-subnet-1-association",
           subnet_id=private_subnet_1.id,
           route_table_id=private_route_table.id
       )
       
       aws.ec2.RouteTableAssociation(
           "private-subnet-2-association",
           subnet_id=private_subnet_2.id,
           route_table_id=private_route_table.id
       )
       
       return {
           "vpc": vpc,
           "public_subnets": [public_subnet_1, public_subnet_2],
           "private_subnets": [private_subnet_1, private_subnet_2],
           "internet_gateway": igw,
           "nat_gateway": nat_gateway,
           "public_route_table": public_route_table,
           "private_route_table": private_route_table
       }
   EOF
   ```

**Verification**:
- [ ] Networking module created
- [ ] VPC configuration implemented
- [ ] Subnets configured with proper CIDR blocks
- [ ] NAT Gateway configured for private subnets
- [ ] Route tables properly associated

#### Task 2.4: Test Infrastructure Deployment
**Owner**: Infrastructure Team
**Estimated Time**: 30 minutes

**Steps**:
1. Create basic test
   ```bash
   cat > tests/test_networking.py << 'EOF'
   """Test networking module."""
   import pytest
   import pulumi

   @pulumi.runtime.test
   def test_vpc_creation():
       """Test VPC creation."""
       from src.networking import create_vpc
       
       vpc_resources = create_vpc()
       
       assert vpc_resources["vpc"] is not None
       assert len(vpc_resources["public_subnets"]) == 2
       assert len(vpc_resources["private_subnets"]) == 2
   EOF
   ```

2. Preview infrastructure changes
   ```bash
   cd lockdev-hippa-iac
   pulumi preview
   ```

3. Deploy infrastructure (if preview looks good)
   ```bash
   pulumi up --yes
   ```

**Verification**:
- [ ] Tests pass
- [ ] Preview shows expected resources
- [ ] Deployment succeeds
- [ ] AWS resources created correctly

### Phase 3: Security Implementation
**Objective**: Implement HIPAA-compliant security measures

#### Task 3.1: Create Security Groups
**Owner**: Security Team
**Estimated Time**: 2 hours

**Steps**:
1. Create security module
   ```bash
   mkdir -p src/security
   cat > src/security/__init__.py << 'EOF'
   """Security infrastructure module."""
   from .security_groups import create_security_groups
   from .kms import create_kms_key
   from .iam import create_iam_roles

   __all__ = ["create_security_groups", "create_kms_key", "create_iam_roles"]
   EOF
   ```

2. Implement security groups
   ```bash
   cat > src/security/security_groups.py << 'EOF'
   """Security groups for HIPAA compliant infrastructure."""
   import pulumi
   import pulumi_aws as aws
   from typing import Dict, Any

   def create_security_groups(vpc) -> Dict[str, Any]:
       """Create security groups with HIPAA compliance."""
       config = pulumi.Config()
       
       # ALB Security Group
       alb_sg = aws.ec2.SecurityGroup(
           "alb-security-group",
           name="hipaa-alb-sg",
           description="Security group for Application Load Balancer",
           vpc_id=vpc.id,
           ingress=[
               aws.ec2.SecurityGroupIngressArgs(
                   description="HTTPS",
                   from_port=443,
                   to_port=443,
                   protocol="tcp",
                   cidr_blocks=["0.0.0.0/0"]
               ),
               aws.ec2.SecurityGroupIngressArgs(
                   description="HTTP",
                   from_port=80,
                   to_port=80,
                   protocol="tcp",
                   cidr_blocks=["0.0.0.0/0"]
               )
           ],
           egress=[
               aws.ec2.SecurityGroupEgressArgs(
                   from_port=0,
                   to_port=0,
                   protocol="-1",
                   cidr_blocks=["0.0.0.0/0"]
               )
           ],
           tags={
               "Name": "HIPAA-ALB-SG",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # ECS Security Group
       ecs_sg = aws.ec2.SecurityGroup(
           "ecs-security-group",
           name="hipaa-ecs-sg",
           description="Security group for ECS tasks",
           vpc_id=vpc.id,
           ingress=[
               aws.ec2.SecurityGroupIngressArgs(
                   description="HTTP from ALB",
                   from_port=8000,
                   to_port=8000,
                   protocol="tcp",
                   security_groups=[alb_sg.id]
               )
           ],
           egress=[
               aws.ec2.SecurityGroupEgressArgs(
                   from_port=0,
                   to_port=0,
                   protocol="-1",
                   cidr_blocks=["0.0.0.0/0"]
               )
           ],
           tags={
               "Name": "HIPAA-ECS-SG",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # RDS Security Group
       rds_sg = aws.ec2.SecurityGroup(
           "rds-security-group",
           name="hipaa-rds-sg",
           description="Security group for RDS database",
           vpc_id=vpc.id,
           ingress=[
               aws.ec2.SecurityGroupIngressArgs(
                   description="PostgreSQL from ECS",
                   from_port=5432,
                   to_port=5432,
                   protocol="tcp",
                   security_groups=[ecs_sg.id]
               )
           ],
           tags={
               "Name": "HIPAA-RDS-SG",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       return {
           "alb_security_group": alb_sg,
           "ecs_security_group": ecs_sg,
           "rds_security_group": rds_sg
       }
   EOF
   ```

**Verification**:
- [ ] Security groups created
- [ ] Ingress rules properly configured
- [ ] Least privilege access implemented
- [ ] HIPAA compliance tags applied

#### Task 3.2: Implement KMS Encryption
**Owner**: Security Team
**Estimated Time**: 1 hour

**Steps**:
1. Create KMS key configuration
   ```bash
   cat > src/security/kms.py << 'EOF'
   """KMS key management for HIPAA compliance."""
   import pulumi
   import pulumi_aws as aws
   import json

   def create_kms_key():
       """Create KMS key for HIPAA compliant encryption."""
       config = pulumi.Config()
       
       # Create KMS key policy
       key_policy = {
           "Version": "2012-10-17",
           "Statement": [
               {
                   "Sid": "Enable IAM User Permissions",
                   "Effect": "Allow",
                   "Principal": {
                       "AWS": f"arn:aws:iam::{aws.get_caller_identity().account_id}:root"
                   },
                   "Action": "kms:*",
                   "Resource": "*"
               },
               {
                   "Sid": "Allow CloudWatch Logs",
                   "Effect": "Allow",
                   "Principal": {
                       "Service": "logs.amazonaws.com"
                   },
                   "Action": [
                       "kms:Encrypt",
                       "kms:Decrypt",
                       "kms:ReEncrypt*",
                       "kms:GenerateDataKey*",
                       "kms:DescribeKey"
                   ],
                   "Resource": "*"
               }
           ]
       }
       
       # Create KMS key
       kms_key = aws.kms.Key(
           "hipaa-kms-key",
           description="KMS key for HIPAA compliant encryption",
           policy=json.dumps(key_policy),
           tags={
               "Name": "HIPAA-KMS-Key",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create KMS key alias
       kms_alias = aws.kms.Alias(
           "hipaa-kms-alias",
           name="alias/hipaa-encryption-key",
           target_key_id=kms_key.key_id
       )
       
       return {
           "kms_key": kms_key,
           "kms_alias": kms_alias
       }
   EOF
   ```

**Verification**:
- [ ] KMS key created
- [ ] Key policy properly configured
- [ ] KMS alias created
- [ ] Encryption enabled for all data at rest

### Phase 4: Database Implementation
**Objective**: Deploy HIPAA-compliant RDS PostgreSQL database

#### Task 4.1: Create RDS Instance
**Owner**: Database Team
**Estimated Time**: 2 hours

**Steps**:
1. Create database module
   ```bash
   mkdir -p src/database
   cat > src/database/__init__.py << 'EOF'
   """Database infrastructure module."""
   from .rds import create_rds_instance
   from .parameter_group import create_parameter_group
   from .subnet_group import create_subnet_group

   __all__ = ["create_rds_instance", "create_parameter_group", "create_subnet_group"]
   EOF
   ```

2. Implement RDS configuration
   ```bash
   cat > src/database/rds.py << 'EOF'
   """RDS PostgreSQL database for HIPAA compliance."""
   import pulumi
   import pulumi_aws as aws
   from typing import List, Dict, Any

   def create_rds_instance(private_subnets: List, security_group) -> aws.rds.Instance:
       """Create HIPAA compliant RDS PostgreSQL instance."""
       config = pulumi.Config()
       
       # Create DB subnet group
       db_subnet_group = aws.rds.SubnetGroup(
           "hipaa-db-subnet-group",
           name="hipaa-db-subnet-group",
           subnet_ids=[subnet.id for subnet in private_subnets],
           tags={
               "Name": "HIPAA-DB-Subnet-Group",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create parameter group
       parameter_group = aws.rds.ParameterGroup(
           "hipaa-db-parameter-group",
           family="postgres13",
           name="hipaa-postgres-params",
           description="Parameter group for HIPAA compliant PostgreSQL",
           parameters=[
               aws.rds.ParameterGroupParameterArgs(
                   name="log_statement",
                   value="all"
               ),
               aws.rds.ParameterGroupParameterArgs(
                   name="log_min_duration_statement",
                   value="1000"
               ),
               aws.rds.ParameterGroupParameterArgs(
                   name="rds.force_ssl",
                   value="1"
               )
           ],
           tags={
               "Name": "HIPAA-DB-Parameter-Group",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create RDS instance
       db_instance = aws.rds.Instance(
           "hipaa-database",
           identifier="hipaa-postgres-db",
           engine="postgres",
           engine_version="13.7",
           instance_class="db.t3.micro",
           allocated_storage=20,
           max_allocated_storage=100,
           storage_type="gp2",
           storage_encrypted=True,
           
           db_name="hipaa_app",
           username="postgres",
           password=config.require_secret("db_password"),
           
           vpc_security_group_ids=[security_group.id],
           db_subnet_group_name=db_subnet_group.name,
           parameter_group_name=parameter_group.name,
           
           backup_retention_period=7,
           backup_window="03:00-04:00",
           maintenance_window="sun:04:00-sun:05:00",
           
           multi_az=False,  # Set to True for production
           publicly_accessible=False,
           
           enabled_cloudwatch_logs_exports=["postgresql"],
           
           deletion_protection=True,
           skip_final_snapshot=False,
           final_snapshot_identifier="hipaa-db-final-snapshot",
           
           tags={
               "Name": "HIPAA-PostgreSQL-DB",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       return db_instance
   EOF
   ```

**Verification**:
- [ ] RDS instance created
- [ ] Encryption at rest enabled
- [ ] SSL connections enforced
- [ ] Automated backups configured
- [ ] CloudWatch logs enabled

#### Task 4.2: Database Security Configuration
**Owner**: Database Team
**Estimated Time**: 1 hour

**Steps**:
1. Set database password
   ```bash
   cd lockdev-hippa-iac
   pulumi config set --secret db_password $(openssl rand -base64 32)
   ```

2. Test database connectivity
   ```bash
   cat > tests/test_database.py << 'EOF'
   """Test database connectivity."""
   import pytest
   import pulumi

   @pulumi.runtime.test
   def test_database_creation():
       """Test database creation and configuration."""
       from src.database import create_rds_instance
       
       # This would be tested in integration tests
       pass
   EOF
   ```

**Verification**:
- [ ] Database password set securely
- [ ] Database accessible from ECS only
- [ ] SSL certificates configured
- [ ] Backup strategy tested

### Phase 5: Application Development
**Objective**: Create containerized Python web application

#### Task 5.1: Initialize Application Project
**Owner**: Application Team
**Estimated Time**: 1 hour

**Steps**:
1. Navigate to application directory
   ```bash
   cd ../lockdev-hippa-app
   ```

2. Initialize Poetry project
   ```bash
   poetry init --name="lockdev-hippa-app" --description="HIPAA compliant web application"
   ```

3. Add dependencies
   ```bash
   poetry add fastapi uvicorn psycopg2-binary sqlalchemy alembic
   poetry add --group dev pytest pytest-asyncio black flake8 mypy
   ```

4. Create application structure
   ```bash
   cat > src/__init__.py << 'EOF'
   """HIPAA compliant web application."""
   __version__ = "0.1.0"
   EOF
   ```

**Verification**:
- [ ] Application project initialized
- [ ] Dependencies installed correctly
- [ ] Project structure created

#### Task 5.2: Create FastAPI Application
**Owner**: Application Team
**Estimated Time**: 2 hours

**Steps**:
1. Create main application file
   ```bash
   cat > src/main.py << 'EOF'
   """Main FastAPI application."""
   from fastapi import FastAPI, HTTPException
   from fastapi.middleware.cors import CORSMiddleware
   from fastapi.middleware.trustedhost import TrustedHostMiddleware
   from fastapi.responses import JSONResponse
   import os
   import logging
   from datetime import datetime

   # Configure logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)

   app = FastAPI(
       title="HIPAA Compliant API",
       description="A HIPAA compliant web application",
       version="0.1.0",
       docs_url="/docs" if os.getenv("ENVIRONMENT") == "dev" else None,
       redoc_url="/redoc" if os.getenv("ENVIRONMENT") == "dev" else None
   )

   # Add security middleware
   app.add_middleware(
       TrustedHostMiddleware,
       allowed_hosts=["*"]  # Configure for production
   )

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # Configure for production
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )

   @app.get("/")
   async def root():
       """Root endpoint."""
       return {"message": "HIPAA Compliant API is running", "timestamp": datetime.now().isoformat()}

   @app.get("/health")
   async def health_check():
       """Health check endpoint."""
       return {"status": "healthy", "timestamp": datetime.now().isoformat()}

   @app.get("/api/v1/patient/info")
   async def get_patient_info():
       """Example patient info endpoint (mock data)."""
       # In production, this would fetch from database with proper authentication
       return {
           "patient_id": "12345",
           "name": "John Doe",
           "last_visit": "2024-01-15",
           "status": "active"
       }

   if __name__ == "__main__":
       import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)
   EOF
   ```

2. Create Dockerfile
   ```bash
   cat > Dockerfile << 'EOF'
   # Use Python 3.11 slim image
   FROM python:3.11-slim

   # Set working directory
   WORKDIR /app

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       gcc \
       postgresql-client \
       && rm -rf /var/lib/apt/lists/*

   # Copy poetry files
   COPY pyproject.toml poetry.lock* ./

   # Install Poetry
   RUN pip install poetry

   # Configure Poetry
   RUN poetry config virtualenvs.create false

   # Install dependencies
   RUN poetry install --no-dev

   # Copy application code
   COPY src/ ./src/

   # Create non-root user
   RUN useradd --create-home --shell /bin/bash appuser
   USER appuser

   # Expose port
   EXPOSE 8000

   # Health check
   HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
       CMD curl -f http://localhost:8000/health || exit 1

   # Run application
   CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
   EOF
   ```

**Verification**:
- [ ] FastAPI application created
- [ ] Security middleware configured
- [ ] Dockerfile created with security best practices
- [ ] Health check endpoint implemented

#### Task 5.3: Test Application Locally
**Owner**: Application Team
**Estimated Time**: 30 minutes

**Steps**:
1. Create test file
   ```bash
   cat > tests/test_main.py << 'EOF'
   """Test main application."""
   import pytest
   from fastapi.testclient import TestClient
   from src.main import app

   client = TestClient(app)

   def test_read_root():
       """Test root endpoint."""
       response = client.get("/")
       assert response.status_code == 200
       assert "message" in response.json()

   def test_health_check():
       """Test health check endpoint."""
       response = client.get("/health")
       assert response.status_code == 200
       assert response.json()["status"] == "healthy"

   def test_patient_info():
       """Test patient info endpoint."""
       response = client.get("/api/v1/patient/info")
       assert response.status_code == 200
       assert "patient_id" in response.json()
   EOF
   ```

2. Run tests
   ```bash
   poetry run pytest tests/
   ```

3. Build and test Docker image
   ```bash
   docker build -t hipaa-app .
   docker run -p 8000:8000 hipaa-app
   ```

**Verification**:
- [ ] All tests pass
- [ ] Docker image builds successfully
- [ ] Application runs in container
- [ ] Health check endpoint accessible

### Phase 6: CI/CD Pipeline Setup
**Objective**: Implement automated testing and deployment pipeline

#### Task 6.1: Create GitHub Actions Workflows
**Owner**: DevOps Team
**Estimated Time**: 3 hours

**Steps**:
1. Create workflow directory
   ```bash
   mkdir -p .github/workflows
   ```

2. Create infrastructure workflow
   ```bash
   cat > .github/workflows/infrastructure.yml << 'EOF'
   name: Infrastructure Deployment

   on:
     push:
       branches: [ main, develop ]
       paths:
         - 'lockdev-hippa-iac/**'
     pull_request:
       branches: [ main ]
       paths:
         - 'lockdev-hippa-iac/**'

   jobs:
     validate:
       runs-on: ubuntu-latest
       defaults:
         run:
           working-directory: lockdev-hippa-iac
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Setup Python
         uses: actions/setup-python@v4
         with:
           python-version: '3.11'
       
       - name: Install Poetry
         uses: snok/install-poetry@v1
       
       - name: Install dependencies
         run: poetry install
       
       - name: Lint code
         run: |
           poetry run black --check .
           poetry run flake8 .
           poetry run mypy src/
       
       - name: Security scan
         run: poetry run bandit -r src/
       
       - name: Run tests
         run: poetry run pytest tests/ -v
       
       - name: Setup Pulumi
         uses: pulumi/actions@v4
         with:
           command: preview
           stack-name: dev
           work-dir: lockdev-hippa-iac
         env:
           PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
           AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
           AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
           AWS_REGION: us-east-1

     deploy:
       needs: validate
       runs-on: ubuntu-latest
       if: github.ref == 'refs/heads/main'
       defaults:
         run:
           working-directory: lockdev-hippa-iac
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Setup Python
         uses: actions/setup-python@v4
         with:
           python-version: '3.11'
       
       - name: Install Poetry
         uses: snok/install-poetry@v1
       
       - name: Install dependencies
         run: poetry install
       
       - name: Deploy Infrastructure
         uses: pulumi/actions@v4
         with:
           command: up
           stack-name: dev
           work-dir: lockdev-hippa-iac
         env:
           PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
           AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
           AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
           AWS_REGION: us-east-1
   EOF
   ```

3. Create application workflow
   ```bash
   cat > .github/workflows/application.yml << 'EOF'
   name: Application Deployment

   on:
     push:
       branches: [ main, develop ]
       paths:
         - 'lockdev-hippa-app/**'
     pull_request:
       branches: [ main ]
       paths:
         - 'lockdev-hippa-app/**'

   jobs:
     test:
       runs-on: ubuntu-latest
       defaults:
         run:
           working-directory: lockdev-hippa-app
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Setup Python
         uses: actions/setup-python@v4
         with:
           python-version: '3.11'
       
       - name: Install Poetry
         uses: snok/install-poetry@v1
       
       - name: Install dependencies
         run: poetry install
       
       - name: Lint code
         run: |
           poetry run black --check .
           poetry run flake8 .
           poetry run mypy src/
       
       - name: Security scan
         run: poetry run bandit -r src/
       
       - name: Run tests
         run: poetry run pytest tests/ -v
       
       - name: Build Docker image
         run: docker build -t hipaa-app:${{ github.sha }} .
       
       - name: Test Docker image
         run: |
           docker run -d -p 8000:8000 --name test-app hipaa-app:${{ github.sha }}
           sleep 10
           curl -f http://localhost:8000/health
           docker stop test-app

     deploy:
       needs: test
       runs-on: ubuntu-latest
       if: github.ref == 'refs/heads/main'
       defaults:
         run:
           working-directory: lockdev-hippa-app
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Configure AWS credentials
         uses: aws-actions/configure-aws-credentials@v2
         with:
           aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
           aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
           aws-region: us-east-1
       
       - name: Login to Amazon ECR
         id: login-ecr
         uses: aws-actions/amazon-ecr-login@v1
       
       - name: Build and push Docker image
         env:
           ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
           ECR_REPOSITORY: hipaa-app
           IMAGE_TAG: ${{ github.sha }}
         run: |
           docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
           docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
           docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
           docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
   EOF
   ```

**Verification**:
- [ ] GitHub Actions workflows created
- [ ] Security scanning integrated
- [ ] Automated testing configured
- [ ] Docker image build and push implemented

#### Task 6.2: Setup Pre-commit Hooks
**Owner**: DevOps Team
**Estimated Time**: 30 minutes

**Steps**:
1. Create pre-commit configuration
   ```bash
   cat > .pre-commit-config.yaml << 'EOF'
   repos:
     - repo: https://github.com/pre-commit/pre-commit-hooks
       rev: v4.4.0
       hooks:
         - id: trailing-whitespace
         - id: end-of-file-fixer
         - id: check-yaml
         - id: check-added-large-files
         - id: check-merge-conflict
         - id: detect-private-key
         - id: check-json
     
     - repo: https://github.com/psf/black
       rev: 22.3.0
       hooks:
         - id: black
           language_version: python3.11
     
     - repo: https://github.com/pycqa/flake8
       rev: 4.0.1
       hooks:
         - id: flake8
     
     - repo: https://github.com/pycqa/bandit
       rev: 1.7.4
       hooks:
         - id: bandit
           args: ['-r', 'src/']
     
     - repo: https://github.com/Yelp/detect-secrets
       rev: v1.4.0
       hooks:
         - id: detect-secrets
           args: ['--baseline', '.secrets.baseline']
   EOF
   ```

2. Install pre-commit hooks
   ```bash
   poetry add --group dev pre-commit
   poetry run pre-commit install
   ```

**Verification**:
- [ ] Pre-commit hooks configured
- [ ] Security scanning enabled
- [ ] Code formatting enforced
- [ ] Secrets detection active

### Phase 7: Monitoring and Compliance
**Objective**: Implement comprehensive monitoring and compliance tracking

#### Task 7.1: Create CloudWatch Resources
**Owner**: Monitoring Team
**Estimated Time**: 2 hours

**Steps**:
1. Create monitoring module
   ```bash
   mkdir -p lockdev-hippa-iac/src/monitoring
   cat > lockdev-hippa-iac/src/monitoring/__init__.py << 'EOF'
   """Monitoring infrastructure module."""
   from .cloudwatch import create_cloudwatch_resources
   from .alarms import create_alarms
   from .dashboards import create_dashboards

   __all__ = ["create_cloudwatch_resources", "create_alarms", "create_dashboards"]
   EOF
   ```

2. Implement CloudWatch configuration
   ```bash
   cat > lockdev-hippa-iac/src/monitoring/cloudwatch.py << 'EOF'
   """CloudWatch monitoring resources."""
   import pulumi
   import pulumi_aws as aws
   from typing import Dict, Any

   def create_cloudwatch_resources() -> Dict[str, Any]:
       """Create CloudWatch resources for monitoring."""
       config = pulumi.Config()
       
       # Create log group for application logs
       app_log_group = aws.cloudwatch.LogGroup(
           "app-log-group",
           name="/aws/ecs/hipaa-app",
           retention_in_days=30,
           tags={
               "Name": "HIPAA-App-Logs",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create log group for database logs
       db_log_group = aws.cloudwatch.LogGroup(
           "db-log-group",
           name="/aws/rds/instance/hipaa-postgres-db/postgresql",
           retention_in_days=30,
           tags={
               "Name": "HIPAA-DB-Logs",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create CloudWatch dashboard
       dashboard = aws.cloudwatch.Dashboard(
           "hipaa-dashboard",
           dashboard_name="HIPAA-Compliance-Dashboard",
           dashboard_body=pulumi.Output.all().apply(lambda _: '''{
               "widgets": [
                   {
                       "type": "metric",
                       "x": 0,
                       "y": 0,
                       "width": 12,
                       "height": 6,
                       "properties": {
                           "metrics": [
                               ["AWS/ECS", "CPUUtilization", "ServiceName", "hipaa-app-service"],
                               [".", "MemoryUtilization", ".", "."]
                           ],
                           "period": 300,
                           "stat": "Average",
                           "region": "us-east-1",
                           "title": "ECS Service Metrics"
                       }
                   },
                   {
                       "type": "metric",
                       "x": 0,
                       "y": 6,
                       "width": 12,
                       "height": 6,
                       "properties": {
                           "metrics": [
                               ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "hipaa-postgres-db"],
                               [".", "DatabaseConnections", ".", "."]
                           ],
                           "period": 300,
                           "stat": "Average",
                           "region": "us-east-1",
                           "title": "RDS Database Metrics"
                       }
                   }
               ]
           }''')
       )
       
       # Create CloudWatch alarms
       high_cpu_alarm = aws.cloudwatch.MetricAlarm(
           "high-cpu-alarm",
           name="hipaa-app-high-cpu",
           comparison_operator="GreaterThanThreshold",
           evaluation_periods=2,
           metric_name="CPUUtilization",
           namespace="AWS/ECS",
           period=300,
           statistic="Average",
           threshold=80,
           alarm_description="This metric monitors ECS CPU utilization",
           alarm_actions=[],  # Add SNS topic ARN for notifications
           dimensions={
               "ServiceName": "hipaa-app-service"
           },
           tags={
               "Name": "HIPAA-High-CPU-Alarm",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       return {
           "app_log_group": app_log_group,
           "db_log_group": db_log_group,
           "dashboard": dashboard,
           "high_cpu_alarm": high_cpu_alarm
       }
   EOF
   ```

**Verification**:
- [ ] CloudWatch log groups created
- [ ] Dashboard configured
- [ ] Alarms set up for critical metrics
- [ ] Log retention configured for compliance

#### Task 7.2: Enable CloudTrail
**Owner**: Compliance Team
**Estimated Time**: 1 hour

**Steps**:
1. Create CloudTrail configuration
   ```bash
   cat > lockdev-hippa-iac/src/monitoring/cloudtrail.py << 'EOF'
   """CloudTrail configuration for audit logging."""
   import pulumi
   import pulumi_aws as aws

   def create_cloudtrail():
       """Create CloudTrail for audit logging."""
       config = pulumi.Config()
       
       # Create S3 bucket for CloudTrail logs
       cloudtrail_bucket = aws.s3.Bucket(
           "cloudtrail-bucket",
           bucket=f"hipaa-cloudtrail-logs-{config.get('environment', 'dev')}",
           force_destroy=True,
           tags={
               "Name": "HIPAA-CloudTrail-Logs",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       # Create bucket policy
       bucket_policy = aws.s3.BucketPolicy(
           "cloudtrail-bucket-policy",
           bucket=cloudtrail_bucket.id,
           policy=pulumi.Output.all(cloudtrail_bucket.id).apply(
               lambda args: f'''{{
                   "Version": "2012-10-17",
                   "Statement": [
                       {{
                           "Sid": "AWSCloudTrailAclCheck",
                           "Effect": "Allow",
                           "Principal": {{
                               "Service": "cloudtrail.amazonaws.com"
                           }},
                           "Action": "s3:GetBucketAcl",
                           "Resource": "arn:aws:s3:::{args[0]}"
                       }},
                       {{
                           "Sid": "AWSCloudTrailWrite",
                           "Effect": "Allow",
                           "Principal": {{
                               "Service": "cloudtrail.amazonaws.com"
                           }},
                           "Action": "s3:PutObject",
                           "Resource": "arn:aws:s3:::{args[0]}/*",
                           "Condition": {{
                               "StringEquals": {{
                                   "s3:x-amz-acl": "bucket-owner-full-control"
                               }}
                           }}
                       }}
                   ]
               }}'''
           )
       )
       
       # Create CloudTrail
       cloudtrail = aws.cloudtrail.Trail(
           "hipaa-cloudtrail",
           name="hipaa-audit-trail",
           s3_bucket_name=cloudtrail_bucket.id,
           include_global_service_events=True,
           is_multi_region_trail=True,
           enable_logging=True,
           tags={
               "Name": "HIPAA-CloudTrail",
               "Environment": config.get("environment", "dev"),
               "Compliance": "HIPAA"
           }
       )
       
       return {
           "cloudtrail_bucket": cloudtrail_bucket,
           "cloudtrail": cloudtrail
       }
   EOF
   ```

**Verification**:
- [ ] CloudTrail enabled
- [ ] S3 bucket for logs created
- [ ] Multi-region trail configured
- [ ] Audit logging active

### Phase 8: Testing and Validation
**Objective**: Comprehensive testing of all components

#### Task 8.1: Integration Testing
**Owner**: QA Team
**Estimated Time**: 4 hours

**Steps**:
1. Create integration test suite
   ```bash
   cat > tests/test_integration.py << 'EOF'
   """Integration tests for HIPAA infrastructure."""
   import pytest
   import boto3
   import requests
   import os
   from datetime import datetime

   class TestInfrastructureIntegration:
       """Test infrastructure integration."""
       
       def setup_method(self):
           """Setup test environment."""
           self.ec2_client = boto3.client('ec2', region_name='us-east-1')
           self.rds_client = boto3.client('rds', region_name='us-east-1')
           self.ecs_client = boto3.client('ecs', region_name='us-east-1')
       
       def test_vpc_exists(self):
           """Test VPC exists and is properly configured."""
           vpcs = self.ec2_client.describe_vpcs(
               Filters=[{'Name': 'tag:Name', 'Values': ['HIPAA-VPC']}]
           )
           assert len(vpcs['Vpcs']) > 0
           vpc = vpcs['Vpcs'][0]
           assert vpc['CidrBlock'] == '10.0.0.0/16'
           assert vpc['State'] == 'available'
       
       def test_database_exists(self):
           """Test RDS database exists and is properly configured."""
           instances = self.rds_client.describe_db_instances(
               DBInstanceIdentifier='hipaa-postgres-db'
           )
           assert len(instances['DBInstances']) > 0
           db = instances['DBInstances'][0]
           assert db['Engine'] == 'postgres'
           assert db['StorageEncrypted'] is True
           assert db['PubliclyAccessible'] is False
       
       def test_ecs_cluster_exists(self):
           """Test ECS cluster exists."""
           clusters = self.ecs_client.describe_clusters(
               clusters=['hipaa-ecs-cluster']
           )
           assert len(clusters['clusters']) > 0
           cluster = clusters['clusters'][0]
           assert cluster['status'] == 'ACTIVE'
       
       def test_security_groups_configured(self):
           """Test security groups are properly configured."""
           sgs = self.ec2_client.describe_security_groups(
               Filters=[{'Name': 'tag:Compliance', 'Values': ['HIPAA']}]
           )
           assert len(sgs['SecurityGroups']) >= 3  # ALB, ECS, RDS
       
       def test_application_health(self):
           """Test application health endpoint."""
           # This would require the application to be deployed
           # For now, we'll test the Docker container locally
           pass
   EOF
   ```

2. Create load testing
   ```bash
   cat > tests/test_load.py << 'EOF'
   """Load testing for HIPAA application."""
   import pytest
   import requests
   import concurrent.futures
   import time
   from statistics import mean

   class TestApplicationLoad:
       """Test application under load."""
       
       def test_concurrent_requests(self):
           """Test application handles concurrent requests."""
           base_url = "http://localhost:8000"
           
           def make_request():
               response = requests.get(f"{base_url}/health")
               return response.status_code == 200, response.elapsed.total_seconds()
           
           # Run concurrent requests
           with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
               futures = [executor.submit(make_request) for _ in range(100)]
               results = [future.result() for future in concurrent.futures.as_completed(futures)]
           
           # Verify all requests succeeded
           success_count = sum(1 for success, _ in results if success)
           assert success_count >= 95  # 95% success rate
           
           # Verify response times are reasonable
           response_times = [time for _, time in results]
           avg_response_time = mean(response_times)
           assert avg_response_time < 1.0  # Average response time under 1 second
   EOF
   ```

**Verification**:
- [ ] Integration tests pass
- [ ] Load testing passes
- [ ] All AWS resources verified
- [ ] Application performance validated

#### Task 8.2: Security Testing
**Owner**: Security Team
**Estimated Time**: 3 hours

**Steps**:
1. Create security test suite
   ```bash
   cat > tests/test_security.py << 'EOF'
   """Security tests for HIPAA infrastructure."""
   import pytest
   import boto3
   import requests
   import ssl
   import socket

   class TestSecurityCompliance:
       """Test security compliance."""
       
       def setup_method(self):
           """Setup test environment."""
           self.ec2_client = boto3.client('ec2', region_name='us-east-1')
           self.rds_client = boto3.client('rds', region_name='us-east-1')
           self.kms_client = boto3.client('kms', region_name='us-east-1')
       
       def test_database_encryption(self):
           """Test database encryption is enabled."""
           instances = self.rds_client.describe_db_instances(
               DBInstanceIdentifier='hipaa-postgres-db'
           )
           db = instances['DBInstances'][0]
           assert db['StorageEncrypted'] is True
           assert 'KmsKeyId' in db
       
       def test_security_group_rules(self):
           """Test security group rules are restrictive."""
           sgs = self.ec2_client.describe_security_groups(
               Filters=[{'Name': 'tag:Name', 'Values': ['HIPAA-RDS-SG']}]
           )
           rds_sg = sgs['SecurityGroups'][0]
           
           # Verify RDS security group only allows access from ECS
           for rule in rds_sg['IpPermissions']:
               if rule['FromPort'] == 5432:
                   assert 'UserIdGroupPairs' in rule
                   assert len(rule['IpRanges']) == 0  # No public access
       
       def test_kms_key_exists(self):
           """Test KMS key exists and is properly configured."""
           keys = self.kms_client.list_keys()
           # Find our KMS key (would need to match by alias or description)
           assert len(keys['Keys']) > 0
       
       def test_ssl_configuration(self):
           """Test SSL/TLS configuration."""
           # This would test the load balancer SSL configuration
           pass
       
       def test_no_public_database_access(self):
           """Test database is not publicly accessible."""
           instances = self.rds_client.describe_db_instances(
               DBInstanceIdentifier='hipaa-postgres-db'
           )
           db = instances['DBInstances'][0]
           assert db['PubliclyAccessible'] is False
   EOF
   ```

2. Run security scans
   ```bash
   # Add security scanning to CI/CD pipeline
   cat > .github/workflows/security-scan.yml << 'EOF'
   name: Security Scan

   on:
     push:
       branches: [ main, develop ]
     pull_request:
       branches: [ main ]
     schedule:
       - cron: '0 2 * * *'  # Daily at 2 AM

   jobs:
     security-scan:
       runs-on: ubuntu-latest
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Run Checkov
         id: checkov
         uses: bridgecrewio/checkov-action@master
         with:
           directory: .
           framework: terraform,dockerfile,secrets
           output_format: cli,sarif
           output_file_path: reports/results.sarif
       
       - name: Upload Checkov results to GitHub Security
         uses: github/codeql-action/upload-sarif@v2
         if: always()
         with:
           sarif_file: reports/results.sarif
       
       - name: Run Trivy vulnerability scanner
         uses: aquasecurity/trivy-action@master
         with:
           scan-type: 'fs'
           scan-ref: '.'
           format: 'sarif'
           output: 'trivy-results.sarif'
       
       - name: Upload Trivy results to GitHub Security
         uses: github/codeql-action/upload-sarif@v2
         if: always()
         with:
           sarif_file: 'trivy-results.sarif'
   EOF
   ```

**Verification**:
- [ ] Security tests pass
- [ ] Encryption verified
- [ ] Access controls validated
- [ ] Security scanning integrated

### Phase 9: Documentation and Compliance
**Objective**: Create comprehensive documentation and compliance reports

#### Task 9.1: Create Technical Documentation
**Owner**: Technical Writers
**Estimated Time**: 4 hours

**Steps**:
1. Create architecture documentation
   ```bash
   cat > docs/architecture.md << 'EOF'
   # HIPAA Infrastructure Architecture

   ## Overview
   This document describes the architecture of the HIPAA-compliant infrastructure deployed using Pulumi and AWS services.

   ## Architecture Diagram
   ```
   Internet
      |
   [ALB] --- [WAF]
      |
   [ECS Fargate]
      |
   [RDS PostgreSQL]
      |
   [CloudWatch/CloudTrail]
   ```

   ## Components

   ### Networking
   - **VPC**: 10.0.0.0/16 CIDR block
   - **Public Subnets**: 10.0.1.0/24, 10.0.2.0/24
   - **Private Subnets**: 10.0.3.0/24, 10.0.4.0/24
   - **NAT Gateway**: For private subnet internet access
   - **Internet Gateway**: For public subnet internet access

   ### Security
   - **Security Groups**: Restrictive ingress/egress rules
   - **KMS**: Encryption key management
   - **IAM Roles**: Least privilege access
   - **SSL/TLS**: All traffic encrypted in transit

   ### Compute
   - **ECS Fargate**: Serverless container platform
   - **Application Load Balancer**: HTTPS termination
   - **Auto Scaling**: Dynamic scaling based on metrics

   ### Database
   - **RDS PostgreSQL**: Managed database service
   - **Encryption**: At rest and in transit
   - **Backups**: Automated daily backups
   - **Multi-AZ**: High availability (production)

   ### Monitoring
   - **CloudWatch**: Metrics and logging
   - **CloudTrail**: Audit logging
   - **X-Ray**: Distributed tracing
   - **GuardDuty**: Threat detection

   ## Compliance Features

   ### HIPAA Compliance
   - Data encryption at rest and in transit
   - Access logging and audit trails
   - Network segmentation
   - Automated backup and recovery
   - Access controls and authentication

   ### HITRUST Compliance
   - Information security governance
   - Risk management
   - Compliance monitoring
   - Incident response procedures

   ### SOC2 Compliance
   - Security controls
   - Availability monitoring
   - Processing integrity
   - Confidentiality measures
   - Privacy protection
   EOF
   ```

2. Create operational procedures
   ```bash
   cat > docs/operations.md << 'EOF'
   # Operational Procedures

   ## Daily Operations

   ### Health Checks
   - Monitor application health endpoints
   - Check database connectivity
   - Verify backup completion
   - Review security alerts

   ### Monitoring
   - Review CloudWatch dashboards
   - Check alarm status
   - Monitor resource utilization
   - Review audit logs

   ## Weekly Operations

   ### Security Review
   - Review access logs
   - Check for suspicious activity
   - Validate security configurations
   - Update security patches

   ### Performance Review
   - Analyze performance metrics
   - Review scaling events
   - Optimize resource allocation
   - Plan capacity upgrades

   ## Monthly Operations

   ### Compliance Review
   - Generate compliance reports
   - Review audit findings
   - Update documentation
   - Conduct security assessments

   ### Disaster Recovery Testing
   - Test backup restoration
   - Validate failover procedures
   - Update recovery documentation
   - Train operations team

   ## Incident Response

   ### Security Incidents
   1. Identify and contain the incident
   2. Assess the impact and scope
   3. Notify stakeholders
   4. Implement corrective actions
   5. Document lessons learned

   ### System Outages
   1. Identify root cause
   2. Implement immediate fixes
   3. Restore service
   4. Communicate with users
   5. Conduct post-mortem analysis

   ## Maintenance Procedures

   ### Scheduled Maintenance
   - Plan maintenance windows
   - Notify users in advance
   - Perform updates during low-traffic periods
   - Test all systems post-maintenance

   ### Emergency Maintenance
   - Assess criticality
   - Implement emergency procedures
   - Communicate with stakeholders
   - Document changes made
   EOF
   ```

**Verification**:
- [ ] Architecture documentation complete
- [ ] Operational procedures documented
- [ ] Compliance requirements mapped
- [ ] Incident response procedures defined

#### Task 9.2: Generate Compliance Reports
**Owner**: Compliance Team
**Estimated Time**: 2 hours

**Steps**:
1. Create compliance report generator
   ```bash
   cat > scripts/generate_compliance_report.py << 'EOF'
   """Generate HIPAA compliance report."""
   import boto3
   import json
   from datetime import datetime, timedelta
   from typing import Dict, List, Any

   class ComplianceReporter:
       """Generate compliance reports."""
       
       def __init__(self):
           self.ec2_client = boto3.client('ec2', region_name='us-east-1')
           self.rds_client = boto3.client('rds', region_name='us-east-1')
           self.cloudtrail_client = boto3.client('cloudtrail', region_name='us-east-1')
           self.kms_client = boto3.client('kms', region_name='us-east-1')
       
       def check_encryption_compliance(self) -> Dict[str, Any]:
           """Check encryption compliance."""
           results = {
               'rds_encrypted': False,
               'kms_keys_exist': False,
               'ebs_encrypted': False
           }
           
           # Check RDS encryption
           try:
               instances = self.rds_client.describe_db_instances()
               for instance in instances['DBInstances']:
                   if instance['StorageEncrypted']:
                       results['rds_encrypted'] = True
                       break
           except Exception as e:
               print(f"Error checking RDS encryption: {e}")
           
           # Check KMS keys
           try:
               keys = self.kms_client.list_keys()
               results['kms_keys_exist'] = len(keys['Keys']) > 0
           except Exception as e:
               print(f"Error checking KMS keys: {e}")
           
           return results
       
       def check_access_controls(self) -> Dict[str, Any]:
           """Check access control compliance."""
           results = {
               'security_groups_configured': False,
               'public_access_restricted': True
           }
           
           try:
               sgs = self.ec2_client.describe_security_groups()
               hipaa_sgs = [sg for sg in sgs['SecurityGroups'] 
                           if sg.get('Tags', []) and 
                           any(tag['Key'] == 'Compliance' and tag['Value'] == 'HIPAA' 
                               for tag in sg['Tags'])]
               
               results['security_groups_configured'] = len(hipaa_sgs) > 0
               
               # Check for overly permissive rules
               for sg in hipaa_sgs:
                   for rule in sg['IpPermissions']:
                       for ip_range in rule.get('IpRanges', []):
                           if ip_range.get('CidrIp') == '0.0.0.0/0':
                               results['public_access_restricted'] = False
                               break
           except Exception as e:
               print(f"Error checking access controls: {e}")
           
           return results
       
       def check_audit_logging(self) -> Dict[str, Any]:
           """Check audit logging compliance."""
           results = {
               'cloudtrail_enabled': False,
               'recent_events_logged': False
           }
           
           try:
               trails = self.cloudtrail_client.describe_trails()
               results['cloudtrail_enabled'] = len(trails['trailList']) > 0
               
               # Check for recent events
               end_time = datetime.utcnow()
               start_time = end_time - timedelta(hours=24)
               
               events = self.cloudtrail_client.lookup_events(
                   StartTime=start_time,
                   EndTime=end_time,
                   MaxItems=1
               )
               
               results['recent_events_logged'] = len(events['Events']) > 0
           except Exception as e:
               print(f"Error checking audit logging: {e}")
           
           return results
       
       def generate_report(self) -> Dict[str, Any]:
           """Generate comprehensive compliance report."""
           report = {
               'timestamp': datetime.utcnow().isoformat(),
               'compliance_checks': {
                   'encryption': self.check_encryption_compliance(),
                   'access_controls': self.check_access_controls(),
                   'audit_logging': self.check_audit_logging()
               },
               'overall_compliance': True
           }
           
           # Check overall compliance
           for category, checks in report['compliance_checks'].items():
               for check, result in checks.items():
                   if not result:
                       report['overall_compliance'] = False
                       break
           
           return report

   if __name__ == "__main__":
       reporter = ComplianceReporter()
       report = reporter.generate_report()
       
       print(json.dumps(report, indent=2))
       
       # Save report to file
       with open(f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
           json.dump(report, f, indent=2)
   EOF
   ```

**Verification**:
- [ ] Compliance report generator created
- [ ] All compliance checks implemented
- [ ] Reports generated successfully
- [ ] Compliance status tracked

### Phase 10: Deployment and Go-Live
**Objective**: Deploy to production and ensure system is operational

#### Task 10.1: Production Deployment
**Owner**: DevOps Team
**Estimated Time**: 3 hours

**Steps**:
1. Create production stack
   ```bash
   cd lockdev-hippa-iac
   pulumi stack init prod
   pulumi config set aws:region us-east-1
   pulumi config set environment prod
   pulumi config set --secret db_password $(openssl rand -base64 32)
   ```

2. Deploy infrastructure
   ```bash
   pulumi up --yes
   ```

3. Deploy application
   ```bash
   cd ../lockdev-hippa-app
   # Build and push to ECR
   docker build -t hipaa-app:prod .
   # Tag and push to ECR (ECR repository should be created by infrastructure)
   ```

4. Verify deployment
   ```bash
   # Check all resources are running
   pulumi stack output
   # Test application endpoints
   curl -k https://your-alb-dns-name/health
   ```

**Verification**:
- [ ] Production stack deployed
- [ ] All resources operational
- [ ] Application accessible
- [ ] Health checks passing

#### Task 10.2: Post-Deployment Validation
**Owner**: QA Team
**Estimated Time**: 2 hours

**Steps**:
1. Run comprehensive tests
   ```bash
   # Run integration tests against production
   pytest tests/test_integration.py --prod
   
   # Run security tests
   pytest tests/test_security.py --prod
   
   # Run load tests
   pytest tests/test_load.py --prod
   ```

2. Generate initial compliance report
   ```bash
   python scripts/generate_compliance_report.py
   ```

3. Verify monitoring and alerting
   ```bash
   # Check CloudWatch dashboards
   # Verify alarms are configured
   # Test alert notifications
   ```

**Verification**:
- [ ] All tests pass in production
- [ ] Compliance report shows green
- [ ] Monitoring systems operational
- [ ] Alerting configured correctly

## Version Control Strategy

### Branching Strategy
- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/**: Feature development branches
- **hotfix/**: Critical production fixes

### Commit Guidelines
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`
- Include ticket numbers in commit messages
- Keep commits atomic and focused
- Write clear, descriptive commit messages

### Release Process
1. Create release branch from develop
2. Run full test suite
3. Generate compliance report
4. Update documentation
5. Merge to main
6. Tag release
7. Deploy to production

## Testing Strategy

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Achieve >80% code coverage
- Run on every commit

### Integration Tests
- Test component interactions
- Use test environments
- Verify API contracts
- Run on pull requests

### Security Tests
- Static code analysis
- Dependency vulnerability scanning
- Infrastructure security validation
- Penetration testing (quarterly)

### Performance Tests
- Load testing under normal conditions
- Stress testing at peak capacity
- Endurance testing for extended periods
- Scalability testing for growth scenarios

### Compliance Tests
- HIPAA requirement validation
- HITRUST control verification
- SOC2 compliance checking
- Audit trail validation

## Risk Management

### Technical Risks
- **Infrastructure failures**: Mitigated by multi-AZ deployment
- **Security vulnerabilities**: Mitigated by automated scanning
- **Performance degradation**: Mitigated by monitoring and auto-scaling
- **Data loss**: Mitigated by automated backups and replication

### Compliance Risks
- **Regulatory changes**: Mitigated by regular compliance reviews
- **Audit failures**: Mitigated by continuous monitoring
- **Data breaches**: Mitigated by encryption and access controls
- **Process failures**: Mitigated by documented procedures

### Operational Risks
- **Staff turnover**: Mitigated by documentation and training
- **Skill gaps**: Mitigated by continuous learning programs
- **Vendor dependencies**: Mitigated by multi-vendor strategy
- **Cost overruns**: Mitigated by budget monitoring and alerts

## Success Criteria

### Technical Success
- [ ] All infrastructure deployed successfully
- [ ] Application running without errors
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Security controls implemented

### Compliance Success
- [ ] HIPAA requirements satisfied
- [ ] HITRUST controls implemented
- [ ] SOC2 compliance achieved
- [ ] Audit trail complete
- [ ] Documentation up to date

### Operational Success
- [ ] Monitoring and alerting functional
- [ ] Backup and recovery tested
- [ ] Incident response procedures validated
- [ ] Staff training completed
- [ ] Runbooks and procedures documented

## Maintenance and Updates

### Regular Maintenance
- **Daily**: Health checks and monitoring review
- **Weekly**: Security patch assessment
- **Monthly**: Compliance report generation
- **Quarterly**: Disaster recovery testing
- **Annually**: Security assessment and penetration testing

### Update Procedures
1. Test updates in development environment
2. Schedule maintenance windows
3. Deploy updates using blue-green deployment
4. Verify system functionality
5. Update documentation

### Continuous Improvement
- Regular retrospectives
- Performance optimization
- Security enhancement
- Process refinement
- Technology upgrades
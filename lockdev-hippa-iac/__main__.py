"""Main Pulumi program for HIPAA compliant infrastructure."""
import pulumi
import pulumi_aws as aws
from typing import Dict, Any, List

# Import security modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from security import (
    create_security_groups,
    create_kms_key,
    create_iam_roles,
    create_cloudtrail,
    create_guardduty,
    create_config
)

from compute.ecs import create_ecs_task_definition, create_ecs_service
from compute.alb import create_application_load_balancer, create_ecr_repository


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




def create_ecs_cluster(private_subnets: List[aws.ec2.Subnet], security_group: aws.ec2.SecurityGroup) -> aws.ecs.Cluster:
    """Create ECS cluster with HIPAA compliance settings."""
    config = pulumi.Config()
    
    # Create ECS cluster
    cluster = aws.ecs.Cluster(
        "hipaa-ecs-cluster",
        name="hipaa-ecs-cluster",
        settings=[
            aws.ecs.ClusterSettingArgs(
                name="containerInsights",
                value="enabled"
            )
        ],
        tags={
            "Name": "HIPAA-ECS-Cluster",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return cluster


def create_rds_instance(private_subnets: List[aws.ec2.Subnet], security_group: aws.ec2.SecurityGroup) -> aws.rds.Instance:
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
        family="postgres16",
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
        engine_version="16.6",
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
        
        deletion_protection=False,  # Set to True for production
        skip_final_snapshot=True,   # Set to False for production
        
        tags={
            "Name": "HIPAA-PostgreSQL-DB",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return db_instance


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
    
    return {
        "app_log_group": app_log_group,
        "db_log_group": db_log_group
    }


def main() -> None:
    """Main infrastructure deployment function."""
    # Get configuration
    config = pulumi.Config()
    
    # Create VPC and networking
    vpc_resources = create_vpc()
    
    # Phase 3: Create security infrastructure
    # Create KMS key for encryption
    kms_resources = create_kms_key()
    
    # Create IAM roles with least privilege
    iam_resources = create_iam_roles()
    
    # Create CloudTrail for audit logging
    cloudtrail_resources = create_cloudtrail()
    
    # Create GuardDuty for threat detection
    guardduty_resources = create_guardduty()
    
    # Create AWS Config for compliance monitoring
    config_resources = create_config()
    
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
    
    # Phase 4: Create application deployment resources
    
    # Create ECR repository for container images
    ecr_repository = create_ecr_repository()
    
    # Create Application Load Balancer
    alb_resources = create_application_load_balancer(
        vpc_resources["public_subnets"],
        security_groups["alb_security_group"],
        vpc_resources["vpc"]
    )
    
    # Create ECS task definition
    task_definition = create_ecs_task_definition(
        iam_resources["ecs_task_execution_role"],
        iam_resources["ecs_task_role"],
        monitoring["app_log_group"],
        database.endpoint.apply(lambda endpoint: f"postgresql+asyncpg://postgres:password@{endpoint}:5432/hipaa_db"),
        kms_resources["kms_key"].key_id
    )
    
    # Create ECS service
    ecs_service = create_ecs_service(
        ecs_cluster,
        task_definition,
        vpc_resources["private_subnets"],
        security_groups["ecs_security_group"],
        alb_resources["target_group"]
    )
    
    # Export important outputs
    pulumi.export("vpc_id", vpc_resources["vpc"].id)
    pulumi.export("ecs_cluster_name", ecs_cluster.name)
    pulumi.export("database_endpoint", database.endpoint)
    pulumi.export("public_subnet_ids", [subnet.id for subnet in vpc_resources["public_subnets"]])
    pulumi.export("private_subnet_ids", [subnet.id for subnet in vpc_resources["private_subnets"]])
    
    # Phase 3: Export security outputs
    pulumi.export("kms_key_id", kms_resources["kms_key"].key_id)
    pulumi.export("kms_key_arn", kms_resources["kms_key"].arn)
    pulumi.export("ecs_task_execution_role_arn", iam_resources["ecs_task_execution_role"].arn)
    pulumi.export("ecs_task_role_arn", iam_resources["ecs_task_role"].arn)
    pulumi.export("cloudtrail_arn", cloudtrail_resources["cloudtrail"].arn)
    pulumi.export("guardduty_detector_id", guardduty_resources["guardduty_detector"].id)
    pulumi.export("config_recorder_name", config_resources["config_recorder"].name)
    
    # Phase 4: Export application outputs
    pulumi.export("ecr_repository_url", ecr_repository.repository_url)
    pulumi.export("alb_dns_name", alb_resources["alb"].dns_name)
    pulumi.export("alb_zone_id", alb_resources["alb"].zone_id)
    pulumi.export("ecs_service_name", ecs_service.name)
    pulumi.export("task_definition_arn", task_definition.arn)


if __name__ == "__main__":
    main()
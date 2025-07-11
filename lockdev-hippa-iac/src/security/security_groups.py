"""Security groups for HIPAA compliant infrastructure."""
import pulumi
import pulumi_aws as aws
from typing import Dict, Any


def create_security_groups(vpc: aws.ec2.Vpc) -> Dict[str, Any]:
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
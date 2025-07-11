"""ECS cluster configuration for HIPAA compliant infrastructure."""
import pulumi
import pulumi_aws as aws
from typing import List, Dict, Any
import json


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


def create_ecs_task_definition(
    ecs_task_execution_role: aws.iam.Role,
    ecs_task_role: aws.iam.Role,
    log_group: aws.cloudwatch.LogGroup,
    database_url: str,
    kms_key_id: str
) -> aws.ecs.TaskDefinition:
    """Create ECS task definition for the FastAPI application."""
    config = pulumi.Config()
    
    # Container definition
    container_definitions = pulumi.Output.all(
        database_url=database_url,
        kms_key_id=kms_key_id,
        log_group_name=log_group.name
    ).apply(lambda args: json.dumps([
        {
            "name": "hipaa-app",
            "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/hipaa-app:latest",
            "cpu": 256,
            "memory": 512,
            "essential": True,
            "portMappings": [
                {
                    "containerPort": 8000,
                    "hostPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "DATABASE_URL",
                    "value": args["database_url"]
                },
                {
                    "name": "ENVIRONMENT",
                    "value": config.get("environment", "dev")
                },
                {
                    "name": "LOG_LEVEL",
                    "value": "INFO"
                }
            ],
            "secrets": [
                {
                    "name": "JWT_SECRET",
                    "valueFrom": f"arn:aws:ssm:us-east-1:123456789012:parameter/hipaa-app/jwt-secret"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": args["log_group_name"],
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "hipaa-app"
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
                "interval": 30,
                "timeout": 10,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]))
    
    # Create task definition
    task_definition = aws.ecs.TaskDefinition(
        "hipaa-app-task",
        family="hipaa-app",
        cpu="256",
        memory="512",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        execution_role_arn=ecs_task_execution_role.arn,
        task_role_arn=ecs_task_role.arn,
        container_definitions=container_definitions,
        tags={
            "Name": "HIPAA-App-Task",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return task_definition


def create_ecs_service(
    cluster: aws.ecs.Cluster,
    task_definition: aws.ecs.TaskDefinition,
    private_subnets: List[aws.ec2.Subnet],
    security_group: aws.ec2.SecurityGroup,
    target_group: aws.lb.TargetGroup
) -> aws.ecs.Service:
    """Create ECS service for the FastAPI application."""
    config = pulumi.Config()
    
    # Create ECS service
    service = aws.ecs.Service(
        "hipaa-app-service",
        cluster=cluster.id,
        task_definition=task_definition.arn,
        desired_count=2,
        launch_type="FARGATE",
        platform_version="LATEST",
        network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
            subnets=[subnet.id for subnet in private_subnets],
            security_groups=[security_group.id],
            assign_public_ip=False
        ),
        load_balancers=[
            aws.ecs.ServiceLoadBalancerArgs(
                target_group_arn=target_group.arn,
                container_name="hipaa-app",
                container_port=8000
            )
        ],
        deployment_maximum_percent=200,
        deployment_minimum_healthy_percent=100,
        tags={
            "Name": "HIPAA-App-Service",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        },
        opts=pulumi.ResourceOptions(depends_on=[target_group])
    )
    
    return service
"""Application Load Balancer configuration for HIPAA compliant infrastructure."""
import pulumi
import pulumi_aws as aws
from typing import List


def create_application_load_balancer(
    public_subnets: List[aws.ec2.Subnet],
    security_group: aws.ec2.SecurityGroup,
    vpc: aws.ec2.Vpc
) -> dict:
    """Create Application Load Balancer with HIPAA compliance settings."""
    config = pulumi.Config()
    
    # Create ALB
    alb = aws.lb.LoadBalancer(
        "hipaa-alb",
        name="hipaa-alb",
        load_balancer_type="application",
        subnets=[subnet.id for subnet in public_subnets],
        security_groups=[security_group.id],
        enable_deletion_protection=True,
        enable_http2=True,
        idle_timeout=60,
        access_logs=aws.lb.LoadBalancerAccessLogsArgs(
            bucket="hipaa-alb-logs",  # Will be created by S3 module
            enabled=True,
            prefix="alb-logs"
        ),
        tags={
            "Name": "HIPAA-ALB",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create target group
    target_group = aws.lb.TargetGroup(
        "hipaa-app-tg",
        name="hipaa-app-tg",
        port=8000,
        protocol="HTTP",
        vpc_id=vpc.id,
        target_type="ip",
        health_check=aws.lb.TargetGroupHealthCheckArgs(
            enabled=True,
            healthy_threshold=2,
            interval=30,
            matcher="200",
            path="/health/",
            port="8000",
            protocol="HTTP",
            timeout=10,
            unhealthy_threshold=3
        ),
        tags={
            "Name": "HIPAA-App-TG",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create HTTPS listener (redirect HTTP to HTTPS)
    https_listener = aws.lb.Listener(
        "hipaa-https-listener",
        load_balancer_arn=alb.arn,
        port=443,
        protocol="HTTPS",
        ssl_policy="ELBSecurityPolicy-TLS-1-2-2017-01",
        certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id",  # Replace with actual cert
        default_actions=[
            aws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=target_group.arn
            )
        ],
        tags={
            "Name": "HIPAA-HTTPS-Listener",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create HTTP listener (redirect to HTTPS)
    http_listener = aws.lb.Listener(
        "hipaa-http-listener",
        load_balancer_arn=alb.arn,
        port=80,
        protocol="HTTP",
        default_actions=[
            aws.lb.ListenerDefaultActionArgs(
                type="redirect",
                redirect=aws.lb.ListenerDefaultActionRedirectArgs(
                    port="443",
                    protocol="HTTPS",
                    status_code="HTTP_301"
                )
            )
        ],
        tags={
            "Name": "HIPAA-HTTP-Listener",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return {
        "alb": alb,
        "target_group": target_group,
        "https_listener": https_listener,
        "http_listener": http_listener
    }


def create_ecr_repository() -> aws.ecr.Repository:
    """Create ECR repository for container images."""
    config = pulumi.Config()
    
    # Create ECR repository
    repository = aws.ecr.Repository(
        "hipaa-app-repo",
        name="hipaa-app",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True
        ),
        tags={
            "Name": "HIPAA-App-Repository",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create lifecycle policy
    lifecycle_policy = aws.ecr.LifecyclePolicy(
        "hipaa-app-lifecycle",
        repository=repository.name,
        policy="""{
            "rules": [
                {
                    "rulePriority": 1,
                    "description": "Keep last 10 images",
                    "selection": {
                        "tagStatus": "tagged",
                        "tagPrefixList": ["v"],
                        "countType": "imageCountMoreThan",
                        "countNumber": 10
                    },
                    "action": {
                        "type": "expire"
                    }
                },
                {
                    "rulePriority": 2,
                    "description": "Delete untagged images older than 1 day",
                    "selection": {
                        "tagStatus": "untagged",
                        "countType": "sinceImagePushed",
                        "countUnit": "days",
                        "countNumber": 1
                    },
                    "action": {
                        "type": "expire"
                    }
                }
            ]
        }"""
    )
    
    return repository
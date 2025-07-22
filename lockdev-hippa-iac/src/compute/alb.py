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
    environment = config.get("environment", "dev")
    account_id = aws.get_caller_identity().account_id
    
    # Create S3 bucket for ALB logs
    alb_logs_bucket = aws.s3.Bucket(
        "alb-logs-bucket",
        bucket=f"hipaa-alb-logs-{environment}-{account_id}",
        force_destroy=True,
        tags={
            "Name": "HIPAA-ALB-Logs",
            "Environment": environment,
            "Compliance": "HIPAA"
        }
    )
    
    # Configure bucket versioning
    alb_logs_bucket_versioning = aws.s3.BucketVersioningV2(
        "alb-logs-bucket-versioning",
        bucket=alb_logs_bucket.id,
        versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
            status="Enabled"
        )
    )
    
    # Configure bucket encryption
    alb_logs_bucket_encryption = aws.s3.BucketServerSideEncryptionConfigurationV2(
        "alb-logs-bucket-encryption",
        bucket=alb_logs_bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                )
            )
        ]
    )
    
    # Block public access
    alb_logs_bucket_pab = aws.s3.BucketPublicAccessBlock(
        "alb-logs-bucket-pab",
        bucket=alb_logs_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True
    )
    
    # Create bucket policy for ALB access
    elb_service_account = "127311923021"  # ELB service account for us-east-1
    alb_logs_bucket_policy = aws.s3.BucketPolicy(
        "alb-logs-bucket-policy",
        bucket=alb_logs_bucket.id,
        policy=pulumi.Output.json_dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{elb_service_account}:root"
                    },
                    "Action": "s3:PutObject",
                    "Resource": alb_logs_bucket.arn.apply(lambda arn: f"{arn}/alb-logs/AWSLogs/{account_id}/*")
                },
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "delivery.logs.amazonaws.com"
                    },
                    "Action": "s3:PutObject",
                    "Resource": alb_logs_bucket.arn.apply(lambda arn: f"{arn}/alb-logs/AWSLogs/{account_id}/*")
                },
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "delivery.logs.amazonaws.com"
                    },
                    "Action": "s3:GetBucketAcl",
                    "Resource": alb_logs_bucket.arn
                }
            ]
        })
    )
    
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
            bucket=alb_logs_bucket.bucket,
            enabled=True,
            prefix="alb-logs"
        ),
        tags={
            "Name": "HIPAA-ALB",
            "Environment": environment,
            "Compliance": "HIPAA"
        },
        opts=pulumi.ResourceOptions(depends_on=[alb_logs_bucket_policy])
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
    
    # Note: HTTPS listener requires valid SSL certificate
    # Can be added later with: aws acm request-certificate
    # https_listener = aws.lb.Listener(...)
    
    # Create HTTP listener (forward to target group)
    http_listener = aws.lb.Listener(
        "hipaa-http-listener",
        load_balancer_arn=alb.arn,
        port=80,
        protocol="HTTP",
        default_actions=[
            aws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=target_group.arn
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
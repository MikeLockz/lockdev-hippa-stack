"""
IAM Role Import Utility for HIPAA Infrastructure

This module provides utilities to import existing IAM roles into Pulumi state
or create them if they don't exist, making the deployment idempotent.
"""

import pulumi
import pulumi_aws as aws
import json
from typing import Dict, Any, Optional


def get_or_import_iam_role(
    resource_name: str,
    role_name: str,
    service: str,
    display_name: str,
    environment: str = "dev",
    additional_policies: Optional[Dict[str, Any]] = None
) -> aws.iam.Role:
    """
    Get an existing IAM role or create it if it doesn't exist.
    This function makes the deployment idempotent.
    
    Args:
        resource_name: Pulumi resource name
        role_name: AWS IAM role name
        service: AWS service that can assume this role
        display_name: Human-readable display name for tags
        environment: Environment name (dev, staging, prod)
        additional_policies: Additional policy statements to include
    
    Returns:
        aws.iam.Role: The IAM role resource
    """
    config = pulumi.Config()
    
    # Define the trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": service
                }
            }
        ]
    }
    
    # Add additional policy statements if provided
    if additional_policies:
        trust_policy["Statement"].extend(additional_policies.get("Statement", []))
    
    # Create or import the role
    role = aws.iam.Role(
        resource_name,
        name=role_name,
        assume_role_policy=json.dumps(trust_policy),
        tags={
            "Name": display_name,
            "Environment": environment,
            "Compliance": "HIPAA",
            "ManagedBy": "Pulumi"
        },
        opts=pulumi.ResourceOptions(
            # Protect from accidental deletion
            protect=True,
            # Ignore changes to avoid conflicts during updates
            ignore_changes=["name", "assume_role_policy"]
        )
    )
    
    return role


def attach_policy_to_role(
    resource_name: str,
    role: aws.iam.Role,
    policy_arn: str,
    policy_name: Optional[str] = None
) -> aws.iam.RolePolicyAttachment:
    """
    Attach a policy to an IAM role with idempotent handling.
    
    Args:
        resource_name: Pulumi resource name
        role: The IAM role to attach the policy to
        policy_arn: ARN of the policy to attach
        policy_name: Optional name for logging
        
    Returns:
        aws.iam.RolePolicyAttachment: The policy attachment resource
    """
    attachment = aws.iam.RolePolicyAttachment(
        resource_name,
        role=role.name,
        policy_arn=policy_arn,
        opts=pulumi.ResourceOptions(
            # Protect from accidental deletion
            protect=True,
            # Ignore changes to avoid conflicts during updates
            ignore_changes=["role", "policy_arn"]
        )
    )
    
    return attachment


def create_iam_policy(
    resource_name: str,
    policy_name: str,
    policy_document: Dict[str, Any],
    description: str,
    environment: str = "dev"
) -> aws.iam.Policy:
    """
    Create an IAM policy with idempotent handling.
    
    Args:
        resource_name: Pulumi resource name
        policy_name: AWS IAM policy name
        policy_document: Policy document as a dictionary
        description: Policy description
        environment: Environment name
        
    Returns:
        aws.iam.Policy: The IAM policy resource
    """
    policy = aws.iam.Policy(
        resource_name,
        name=policy_name,
        policy=json.dumps(policy_document),
        description=description,
        tags={
            "Name": policy_name,
            "Environment": environment,
            "Compliance": "HIPAA",
            "ManagedBy": "Pulumi"
        },
        opts=pulumi.ResourceOptions(
            # Protect from accidental deletion
            protect=True,
            # Handle existing policies
            ignore_changes=["name"]
        )
    )
    
    return policy


def get_standard_ecs_task_execution_policy() -> Dict[str, Any]:
    """Get the standard ECS task execution policy document."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:*:*:secret:hipaa/*"
                ]
            }
        ]
    }


def get_standard_ecs_task_policy() -> Dict[str, Any]:
    """Get the standard ECS task policy document."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:*:*:secret:hipaa/*"
                ]
            }
        ]
    }


def get_standard_cloudwatch_policy() -> Dict[str, Any]:
    """Get the standard CloudWatch policy document."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:ListMetrics"
                ],
                "Resource": "*"
            }
        ]
    }


def get_standard_cloudtrail_policy(log_group_arn: str = "*") -> Dict[str, Any]:
    """Get the standard CloudTrail policy document."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": f"{log_group_arn}*" if log_group_arn != "*" else "*"
            }
        ]
    }
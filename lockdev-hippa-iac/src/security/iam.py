"""IAM roles and policies for HIPAA compliance."""
import pulumi
import pulumi_aws as aws
import json
from utils.iam_import import (
    get_or_import_iam_role,
    attach_policy_to_role,
    create_iam_policy,
    get_standard_ecs_task_execution_policy,
    get_standard_ecs_task_policy,
    get_standard_cloudwatch_policy
)


def create_iam_roles():
    """Create IAM roles with least privilege access."""
    config = pulumi.Config()
    environment = config.get("environment", "dev")
    
    # ECS Task Execution Role - import if exists, create if not
    ecs_task_execution_role = get_or_import_iam_role(
        "ecs-task-execution-role",
        "hipaa-ecs-task-execution-role",
        "ecs-tasks.amazonaws.com",
        "HIPAA-ECS-Task-Execution-Role",
        environment
    )
    
    # Attach AWS managed policy for ECS task execution
    attach_policy_to_role(
        "ecs-task-execution-role-policy",
        ecs_task_execution_role,
        "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
        "AmazonECSTaskExecutionRolePolicy"
    )
    
    # ECS Task Role - import if exists, create if not
    ecs_task_role = get_or_import_iam_role(
        "ecs-task-role",
        "hipaa-ecs-task-role",
        "ecs-tasks.amazonaws.com",
        "HIPAA-ECS-Task-Role",
        environment
    )
    
    # Custom policy for ECS task
    ecs_task_policy = create_iam_policy(
        "ecs-task-policy",
        "hipaa-ecs-task-policy",
        get_standard_ecs_task_policy(),
        "Policy for HIPAA ECS tasks",
        environment
    )
    
    # Attach custom policy to ECS task role
    attach_policy_to_role(
        "ecs-task-role-policy-attachment",
        ecs_task_role,
        ecs_task_policy.arn,
        "hipaa-ecs-task-policy"
    )
    
    # CloudWatch Role for monitoring - import if exists, create if not
    cloudwatch_role = get_or_import_iam_role(
        "cloudwatch-role",
        "hipaa-cloudwatch-role",
        "events.amazonaws.com",
        "HIPAA-CloudWatch-Role",
        environment
    )
    
    # CloudWatch policy
    cloudwatch_policy = create_iam_policy(
        "cloudwatch-policy",
        "hipaa-cloudwatch-policy",
        get_standard_cloudwatch_policy(),
        "Policy for HIPAA CloudWatch monitoring",
        environment
    )
    
    # Attach CloudWatch policy
    attach_policy_to_role(
        "cloudwatch-role-policy-attachment",
        cloudwatch_role,
        cloudwatch_policy.arn,
        "hipaa-cloudwatch-policy"
    )
    
    return {
        "ecs_task_execution_role": ecs_task_execution_role,
        "ecs_task_role": ecs_task_role,
        "cloudwatch_role": cloudwatch_role,
        "ecs_task_policy": ecs_task_policy,
        "cloudwatch_policy": cloudwatch_policy
    }
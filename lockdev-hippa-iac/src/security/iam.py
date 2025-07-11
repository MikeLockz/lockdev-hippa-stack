"""IAM roles and policies for HIPAA compliance."""
import pulumi
import pulumi_aws as aws
import json


def create_iam_roles():
    """Create IAM roles with least privilege access."""
    config = pulumi.Config()
    
    # ECS Task Execution Role
    ecs_task_execution_role = aws.iam.Role(
        "ecs-task-execution-role",
        name="hipaa-ecs-task-execution-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ecs-tasks.amazonaws.com"
                    }
                }
            ]
        }),
        tags={
            "Name": "HIPAA-ECS-Task-Execution-Role",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach AWS managed policy for ECS task execution
    aws.iam.RolePolicyAttachment(
        "ecs-task-execution-role-policy",
        role=ecs_task_execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    )
    
    # ECS Task Role
    ecs_task_role = aws.iam.Role(
        "ecs-task-role",
        name="hipaa-ecs-task-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ecs-tasks.amazonaws.com"
                    }
                }
            ]
        }),
        tags={
            "Name": "HIPAA-ECS-Task-Role",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Custom policy for ECS task
    ecs_task_policy = aws.iam.Policy(
        "ecs-task-policy",
        name="hipaa-ecs-task-policy",
        description="Policy for HIPAA ECS tasks",
        policy=json.dumps({
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
                }
            ]
        }),
        tags={
            "Name": "HIPAA-ECS-Task-Policy",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach custom policy to ECS task role
    aws.iam.RolePolicyAttachment(
        "ecs-task-role-policy-attachment",
        role=ecs_task_role.name,
        policy_arn=ecs_task_policy.arn
    )
    
    # CloudWatch Role for monitoring
    cloudwatch_role = aws.iam.Role(
        "cloudwatch-role",
        name="hipaa-cloudwatch-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "monitoring.amazonaws.com"
                    }
                }
            ]
        }),
        tags={
            "Name": "HIPAA-CloudWatch-Role",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # CloudWatch policy
    cloudwatch_policy = aws.iam.Policy(
        "cloudwatch-policy",
        name="hipaa-cloudwatch-policy",
        description="Policy for HIPAA CloudWatch monitoring",
        policy=json.dumps({
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
        }),
        tags={
            "Name": "HIPAA-CloudWatch-Policy",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach CloudWatch policy
    aws.iam.RolePolicyAttachment(
        "cloudwatch-role-policy-attachment",
        role=cloudwatch_role.name,
        policy_arn=cloudwatch_policy.arn
    )
    
    return {
        "ecs_task_execution_role": ecs_task_execution_role,
        "ecs_task_role": ecs_task_role,
        "cloudwatch_role": cloudwatch_role,
        "ecs_task_policy": ecs_task_policy,
        "cloudwatch_policy": cloudwatch_policy
    }
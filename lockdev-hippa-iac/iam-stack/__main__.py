"""
HIPAA Infrastructure - IAM Bootstrap Stack
Separate Pulumi stack for IAM users and policies
"""

import json
import pulumi
import pulumi_aws as aws

# Get current stack configuration
config = pulumi.Config()
environment = config.get("environment", "dev")
project_name = config.get("project_name", "hipaa")

# Create IAM Manager User
iam_manager_user = aws.iam.User(
    f"{project_name}-iam-manager",
    name=f"{project_name}-iam-manager-{environment}",
    path="/",
    tags={
        "Environment": environment,
        "Project": project_name,
        "Purpose": "IAM-Management",
        "ManagedBy": "Pulumi"
    }
)

# Create access keys for IAM Manager
iam_manager_access_key = aws.iam.AccessKey(
    f"{project_name}-iam-manager-key",
    user=iam_manager_user.name
)

# IAM Manager Policy Document
iam_manager_policy_document = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole", 
                "iam:GetRole",
                "iam:ListRoles",
                "iam:UpdateRole",
                "iam:TagRole",
                "iam:UntagRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRolePolicy",
                "iam:ListRolePolicies"
            ],
            "Resource": [
                f"arn:aws:iam::*:role/{project_name}-*",
                "arn:aws:iam::*:role/*ecs*",
                "arn:aws:iam::*:role/*cloudtrail*",
                "arn:aws:iam::*:role/*config*"
            ]
        },
        {
            "Sid": "IAMPolicyManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreatePolicy",
                "iam:DeletePolicy",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:ListPolicies",
                "iam:ListPolicyVersions", 
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:ListAttachedRolePolicies"
            ],
            "Resource": [
                f"arn:aws:iam::*:policy/{project_name}-*",
                "arn:aws:iam::aws:policy/*"
            ]
        },
        {
            "Sid": "PassRoleForServices",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": [
                f"arn:aws:iam::*:role/{project_name}-*",
                "arn:aws:iam::*:role/*ecs*",
                "arn:aws:iam::*:role/*cloudtrail*",
                "arn:aws:iam::*:role/*config*"
            ],
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": [
                        "ecs-tasks.amazonaws.com",
                        "cloudtrail.amazonaws.com", 
                        "config.amazonaws.com"
                    ]
                }
            }
        },
        {
            "Sid": "ReadOnlyAccess",
            "Effect": "Allow",
            "Action": [
                "iam:GetUser",
                "iam:ListUsers",
                "iam:GetAccountSummary"
            ],
            "Resource": "*"
        }
    ]
})

# Create IAM Manager Policy
iam_manager_policy = aws.iam.Policy(
    f"{project_name}-iam-manager-policy",
    name=f"{project_name}-iam-manager-policy-{environment}",
    description="Minimal IAM permissions for Pulumi IAM resource management",
    policy=iam_manager_policy_document,
    tags={
        "Environment": environment,
        "Project": project_name,
        "Purpose": "IAM-Management",
        "ManagedBy": "Pulumi"
    }
)

# Attach policy to IAM Manager user
iam_manager_policy_attachment = aws.iam.UserPolicyAttachment(
    f"{project_name}-iam-manager-policy-attachment",
    user=iam_manager_user.name,
    policy_arn=iam_manager_policy.arn
)

# Infrastructure Policy Document
infrastructure_policy_document = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EC2FullAccess",
            "Effect": "Allow",
            "Action": "ec2:*",
            "Resource": "*"
        },
        {
            "Sid": "S3FullAccess",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*"
        },
        {
            "Sid": "RDSFullAccess",
            "Effect": "Allow",
            "Action": "rds:*",
            "Resource": "*"
        },
        {
            "Sid": "ECSFullAccess",
            "Effect": "Allow",
            "Action": ["ecs:*", "ecr:*"],
            "Resource": "*"
        },
        {
            "Sid": "LoadBalancerAccess",
            "Effect": "Allow",
            "Action": "elasticloadbalancing:*",
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchAccess",
            "Effect": "Allow",
            "Action": ["cloudwatch:*", "logs:*"],
            "Resource": "*"
        },
        {
            "Sid": "KMSAccess",
            "Effect": "Allow",
            "Action": "kms:*",
            "Resource": "*"
        },
        {
            "Sid": "CloudTrailAccess",
            "Effect": "Allow",
            "Action": "cloudtrail:*",
            "Resource": "*"
        },
        {
            "Sid": "ConfigAccess",
            "Effect": "Allow",
            "Action": "config:*",
            "Resource": "*"
        },
        {
            "Sid": "GuardDutyAccess",
            "Effect": "Allow",
            "Action": "guardduty:*",
            "Resource": "*"
        },
        {
            "Sid": "SNSAccess",
            "Effect": "Allow",
            "Action": "sns:*",
            "Resource": "*"
        },
        {
            "Sid": "EventsAccess",
            "Effect": "Allow",
            "Action": "events:*",
            "Resource": "*"
        },
        {
            "Sid": "SecretsManagerAccess",
            "Effect": "Allow",
            "Action": "secretsmanager:*",
            "Resource": "*"
        },
        {
            "Sid": "UseExistingRoles",
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "iam:ListRoles",
                "iam:ListAttachedRolePolicies",
                "iam:GetRolePolicy",
                "iam:ListRolePolicies",
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
})

# Create Infrastructure Policy
infrastructure_policy = aws.iam.Policy(
    f"{project_name}-infrastructure-policy",
    name=f"{project_name}-infrastructure-policy-{environment}",
    description="Infrastructure permissions for Pulumi (no IAM creation)",
    policy=infrastructure_policy_document,
    tags={
        "Environment": environment,
        "Project": project_name,
        "Purpose": "Infrastructure-Deployment",
        "ManagedBy": "Pulumi"
    }
)

# Store IAM Manager credentials in Secrets Manager
iam_credentials_secret = aws.secretsmanager.Secret(
    f"{project_name}-iam-manager-credentials",
    name=f"{project_name}/{environment}/iam-manager/credentials",
    description="IAM Manager user credentials for Pulumi deployment",
    tags={
        "Environment": environment,
        "Project": project_name,
        "Purpose": "Automation",
        "ManagedBy": "Pulumi"
    }
)

# Store the credentials as JSON
iam_credentials_version = aws.secretsmanager.SecretVersion(
    f"{project_name}-iam-manager-credentials-version",
    secret_id=iam_credentials_secret.id,
    secret_string=pulumi.Output.all(
        iam_manager_access_key.id,
        iam_manager_access_key.secret,
        iam_manager_user.name
    ).apply(lambda args: json.dumps({
        "AccessKeyId": args[0],
        "SecretAccessKey": args[1],
        "UserName": args[2]
    }))
)

# Exports
pulumi.export("iam_manager_user_name", iam_manager_user.name)
pulumi.export("iam_manager_access_key_id", iam_manager_access_key.id)
pulumi.export("iam_manager_policy_arn", iam_manager_policy.arn)
pulumi.export("infrastructure_policy_arn", infrastructure_policy.arn)
pulumi.export("credentials_secret_arn", iam_credentials_secret.arn)
pulumi.export("credentials_secret_name", iam_credentials_secret.name)
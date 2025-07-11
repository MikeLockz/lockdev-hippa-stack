"""KMS key management for HIPAA compliance."""
import pulumi
import pulumi_aws as aws
import json


def create_kms_key():
    """Create KMS key for HIPAA compliant encryption."""
    config = pulumi.Config()
    
    # Get current AWS account ID
    current = aws.get_caller_identity()
    
    # Create KMS key policy
    key_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Enable IAM User Permissions",
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{current.account_id}:root"
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
            },
            {
                "Sid": "Allow RDS Service",
                "Effect": "Allow",
                "Principal": {
                    "Service": "rds.amazonaws.com"
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
        enable_key_rotation=True,
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
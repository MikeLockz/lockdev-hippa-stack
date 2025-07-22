"""AWS Secrets Manager for HIPAA compliance."""
import json
import pulumi
import pulumi_aws as aws
from pulumi import Output


def create_database_secret(environment: str, kms_key_id: Output[str]) -> dict:
    """
    Create and manage database credentials in AWS Secrets Manager.
    
    Args:
        environment: Environment name (dev, test, prod)
        kms_key_id: KMS key ID for encryption
        
    Returns:
        Dictionary containing secret resources
    """
    
    # Generate random password for database
    db_password = aws.secretsmanager.get_random_password(
        length=32,
        exclude_characters=" \"'@/\\",
        exclude_numbers=False,
        exclude_punctuation=False,
        exclude_uppercase=False,
        exclude_lowercase=False,
        include_space=False,
        require_each_included_type=True
    )
    
    # Create the secret for database credentials
    db_secret = aws.secretsmanager.Secret(
        f"hipaa-db-secret-{environment}",
        name=f"hipaa/{environment}/database/credentials",
        description=f"Database credentials for HIPAA application ({environment})",
        kms_key_id=kms_key_id,
        
        # Enable automatic rotation (30 days)
        rotation_rules={
            "automatically_after_days": 30
        },
        
        tags={
            "Environment": environment,
            "Application": "HIPAA-Stack",
            "Type": "Database-Credentials",
            "Compliance": "HIPAA-HITRUST",
            "ManagedBy": "Pulumi"
        }
    )
    
    # Store the actual secret value
    db_secret_version = aws.secretsmanager.SecretVersion(
        f"hipaa-db-secret-version-{environment}",
        secret_id=db_secret.id,
        secret_string=pulumi.Output.all(db_password.result).apply(
            lambda args: json.dumps({
                "username": "postgres",
                "password": args[0],
                "engine": "postgres",
                "host": "will-be-updated-after-rds-creation",
                "port": 5432,
                "dbname": "hipaa_app"
            })
        )
    )
    
    # Create secret for application JWT
    jwt_secret = aws.secretsmanager.Secret(
        f"hipaa-jwt-secret-{environment}",
        name=f"hipaa/{environment}/application/jwt",
        description=f"JWT secret for HIPAA application ({environment})",
        kms_key_id=kms_key_id,
        
        tags={
            "Environment": environment,
            "Application": "HIPAA-Stack", 
            "Type": "JWT-Secret",
            "Compliance": "HIPAA-HITRUST",
            "ManagedBy": "Pulumi"
        }
    )
    
    # Generate JWT secret
    jwt_password = aws.secretsmanager.get_random_password(
        length=64,
        exclude_characters=" \"'@/\\",
        exclude_numbers=False,
        exclude_punctuation=False,
        exclude_uppercase=False,
        exclude_lowercase=False,
        include_space=False,
        require_each_included_type=True
    )
    
    jwt_secret_version = aws.secretsmanager.SecretVersion(
        f"hipaa-jwt-secret-version-{environment}",
        secret_id=jwt_secret.id,
        secret_string=jwt_password.result
    )
    
    return {
        "db_secret": db_secret,
        "db_secret_version": db_secret_version,
        "db_password": db_password.result,
        "jwt_secret": jwt_secret,
        "jwt_secret_version": jwt_secret_version,
        "jwt_password": jwt_password.result
    }


def update_database_secret(secret_arn: str, db_endpoint: str, environment: str) -> aws.secretsmanager.SecretVersion:
    """
    Update database secret with actual RDS endpoint after creation.
    
    Args:
        secret_arn: Secret ARN to update
        db_endpoint: RDS database endpoint
        environment: Environment name
        
    Returns:
        Updated secret version
    """
    
    # Get the current secret to preserve password
    current_secret = aws.secretsmanager.get_secret_version(secret_id=secret_arn)
    
    # Update secret with actual database endpoint
    updated_secret = aws.secretsmanager.SecretVersion(
        f"hipaa-db-secret-updated-{environment}",
        secret_id=secret_arn,
        secret_string=pulumi.Output.all(current_secret.secret_string, db_endpoint).apply(
            lambda args: json.dumps({
                **json.loads(args[0]),
                "host": args[1]
            })
        )
    )
    
    return updated_secret


def create_secrets_iam_policy() -> aws.iam.Policy:
    """
    Create IAM policy for Secrets Manager access.
    
    Returns:
        IAM policy for Secrets Manager
    """
    
    secrets_policy = aws.iam.Policy(
        "secrets-manager-policy",
        name="hipaa-secrets-manager-policy",
        description="Policy for accessing HIPAA secrets in Secrets Manager",
        policy=pulumi.Output.all().apply(lambda _: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret"
                    ],
                    "Resource": [
                        "arn:aws:secretsmanager:*:*:secret:hipaa/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "kms:Decrypt",
                        "kms:GenerateDataKey"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com"
                        }
                    }
                }
            ]
        }))
    )
    
    return secrets_policy


def get_secret_value(secret_name: str, json_key: str = None) -> Output[str]:
    """
    Helper function to retrieve secret values for use in other resources.
    
    Args:
        secret_name: Name of the secret in Secrets Manager
        json_key: Optional JSON key to extract from secret
        
    Returns:
        Secret value as Pulumi Output
    """
    
    secret = aws.secretsmanager.get_secret_version(secret_id=secret_name)
    
    if json_key:
        return secret.secret_string.apply(
            lambda s: json.loads(s)[json_key]
        )
    
    return secret.secret_string
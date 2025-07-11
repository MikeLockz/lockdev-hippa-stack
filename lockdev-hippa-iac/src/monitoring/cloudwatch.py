"""CloudWatch monitoring resources."""
import pulumi
import pulumi_aws as aws
from typing import Dict, Any


def create_cloudwatch_resources() -> Dict[str, Any]:
    """Create CloudWatch resources for monitoring."""
    config = pulumi.Config()
    
    # Create log group for application logs
    app_log_group = aws.cloudwatch.LogGroup(
        "app-log-group",
        name="/aws/ecs/hipaa-app",
        retention_in_days=30,
        tags={
            "Name": "HIPAA-App-Logs",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create log group for database logs
    db_log_group = aws.cloudwatch.LogGroup(
        "db-log-group",
        name="/aws/rds/instance/hipaa-postgres-db/postgresql",
        retention_in_days=30,
        tags={
            "Name": "HIPAA-DB-Logs",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return {
        "app_log_group": app_log_group,
        "db_log_group": db_log_group
    }